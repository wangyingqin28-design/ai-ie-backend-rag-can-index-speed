# -*- coding: utf-8 -*-
"""基于 LlamaIndex TextNode 官方序列化结果整理 JSON payload。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：把问答对、官方 evaluator 分数、RAG 聚类结构一起整理成正式 Pydantic payload。
# 修改日期：2026-06-01 13:29:35。
# 修改理由：补齐全局聚类、问题哈希、答案哈希和融合状态字段，支撑多文档 RAG 入库。

# 导入 JSON 库。
import json
# 导入路径类型。
from pathlib import Path

# 导入 LlamaIndex 官方 TextNode。
from llama_index.core.schema import TextNode

# 导入通用 JSON 安全清洗函数。
from common.utils import json_safe_value
# 导入入库 payload 类型和正式 payload schema。
from data_structures.models import RagClusterPayloadModel, RagGlobalClusterPayloadModel, RagQAPayloadModel, StoragePayload


def _as_string_list(value: object) -> list[str]:
    # 列表直接转字符串列表。
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    # 非空字符串作为单项列表。
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    # 其他值返回空列表。
    return []


def _as_dict_list(value: object) -> list[dict[str, object]]:
    # 非列表直接返回空。
    if not isinstance(value, list):
        return []
    # 只保留 dict 项。
    return [item for item in value if isinstance(item, dict)]


def _build_cleaned_text(question: str, answer: str) -> str:
    # 问答均存在时返回标准 QA 文本。
    if question or answer:
        return f"问题：{question}\n答案：{answer}".strip()
    # 都不存在时返回空。
    return ""


def _build_answer_first_text(metadata: dict[str, object], cleaned_text: str) -> str:
    # 读取核心字段。
    question = str(metadata.get("question", "") or "")
    answer = str(metadata.get("answer_text") or metadata.get("answer") or "")
    canonical_question = str(metadata.get("canonical_question") or question)
    scene = str(metadata.get("scene", "") or "")
    steps = _as_string_list(metadata.get("resolution_steps", []))
    aliases = _as_string_list(metadata.get("query_aliases", []))
    duplicate_contexts = _as_dict_list(metadata.get("duplicate_contexts", []))
    # 先放标准答案，兼容外部 RAG loader 默认读取 text 的情况。
    parts = [
        f"标准答案：{answer}",
        f"用户问题：{question}",
        f"规范问题：{canonical_question}",
        f"业务场景：{scene}",
    ]
    # 操作步骤。
    if steps:
        parts.append("操作步骤：" + "；".join(steps))
    # 相关问法。
    if aliases:
        parts.append("相关问法：" + "；".join(aliases))
    # 兼容清洗文本。
    if cleaned_text and cleaned_text not in parts:
        parts.append("兼容问答文本：" + cleaned_text)
    # 合并 duplicate 中更完整的上下文。
    if duplicate_contexts:
        duplicate_texts = []
        for context in duplicate_contexts:
            context_text = str(context.get("cleaned_text") or context.get("source_excerpt") or "")
            if context_text:
                duplicate_texts.append(context_text)
        if duplicate_texts:
            parts.append("已融合重复上下文：" + "\n".join(duplicate_texts))
    # 返回非空文本。
    return "\n".join(part for part in parts if part and not part.endswith("："))


def _build_retrieval_text(metadata: dict[str, object], llm_text: str) -> str:
    # 检索文本加入 question/canonical/alias，和答案文本同源。
    question = str(metadata.get("question", "") or "")
    canonical_question = str(metadata.get("canonical_question") or question)
    aliases = "；".join(_as_string_list(metadata.get("query_aliases", [])))
    return "\n".join(
        part
        for part in [
            f"问题：{question}",
            f"规范问题：{canonical_question}",
            f"相关问法：{aliases}" if aliases else "",
            llm_text,
        ]
        if part
    )


def _build_contract_node_dict(node: TextNode, metadata: dict[str, object], llm_text: str) -> dict[str, object]:
    # 复制官方 node.to_dict()，但把 text 和 metadata 升级成可直接消费契约。
    node_dict = node.to_dict()
    # 更新默认文本。
    node_dict["text"] = llm_text
    # 合并 metadata。
    node_metadata = dict(node_dict.get("metadata") or {})
    node_metadata.update(metadata)
    # 写回 metadata。
    node_dict["metadata"] = json_safe_value(node_metadata)
    # 返回契约化 node dict。
    return node_dict


def llamaindex_nodes_to_storage_json(nodes: list[TextNode]) -> list[StoragePayload]:
    # 创建入库 payload 列表。
    payloads: list[StoragePayload] = []
    # 遍历 LlamaIndex TextNode。
    for node in nodes:
        # 读取节点 metadata。
        metadata = dict(node.metadata)
        # 读取问题。
        question = str(metadata.get("question", "") or "")
        # 读取答案。
        answer = str(metadata.get("answer_text") or metadata.get("answer") or "")
        # 读取规范问题。
        canonical_question = str(metadata.get("canonical_question") or question)
        # 读取 query aliases。
        query_aliases = _as_string_list(metadata.get("query_aliases", []))
        # 构造完整清洗文本，优先 question + answer 而不是 node.get_content() 残片。
        cleaned_text = str(metadata.get("cleaned_text") or _build_cleaned_text(question, answer))
        if answer and answer not in cleaned_text:
            cleaned_text = _build_cleaned_text(question, answer)
        # 读取/重建完整来源摘录。
        source_excerpt_full = str(metadata.get("source_excerpt_full") or metadata.get("source_excerpt") or cleaned_text)
        if answer and answer not in source_excerpt_full:
            source_excerpt_full = cleaned_text
        # 读取/重建 LLM 消费文本。
        llm_text = str(metadata.get("llm_text") or "")
        validation_flags = _as_string_list(metadata.get("validation_flags", []))
        if answer and answer not in llm_text:
            validation_flags.append("llm_text_rebuilt_from_answer")
            metadata["answer_text"] = answer
            metadata["canonical_question"] = canonical_question
            metadata["query_aliases"] = query_aliases
            llm_text = _build_answer_first_text(metadata, cleaned_text)
        # 读取/重建检索文本。
        retrieval_text = str(metadata.get("retrieval_text") or "")
        if answer and answer not in retrieval_text:
            validation_flags.append("retrieval_text_rebuilt_from_answer")
            retrieval_text = _build_retrieval_text(metadata, llm_text)
        # 重新写回契约 metadata。
        metadata["canonical_question"] = canonical_question
        metadata["answer_text"] = answer
        metadata["query_aliases"] = query_aliases
        metadata["cleaned_text"] = cleaned_text
        metadata["source_excerpt"] = source_excerpt_full
        metadata["source_excerpt_full"] = source_excerpt_full
        metadata["llm_text"] = llm_text
        metadata["retrieval_text"] = retrieval_text
        metadata["validation_flags"] = list(dict.fromkeys(validation_flags))
        # 计算 Qdrant 可同步状态。
        qdrant_ready = bool(question and answer and llm_text and answer in llm_text and retrieval_text and answer in retrieval_text)
        metadata["qdrant_ready"] = qdrant_ready
        # 构造契约化 LlamaIndex node。
        llamaindex_node = _build_contract_node_dict(node, metadata, llm_text)
        # 构造面向 SQL Server 的扁平 JSON payload。
        payload = {
            # 写入 payload schema 版本。
            "payload_schema_version": "qa-rag-payload-v3",
            # 写入 RAG 消费契约版本。
            "rag_contract_version": "qa-rag-contract-v1",
            # 使用 LlamaIndex 官方 node_id 作为 chunk_id。
            "chunk_id": node.node_id,
            # 从 metadata 读取文档 ID。
            "document_id": metadata.get("document_id", ""),
            # 从 metadata 读取音频编号。
            "audio_no": metadata.get("audio_no", 0),
            # 从 metadata 读取音频标题。
            "audio_title": metadata.get("audio_title", ""),
            # 从 metadata 读取分块序号。
            "chunk_index": metadata.get("chunk_index", 0),
            # 从 metadata 读取问答对 ID。
            "qa_pair_id": metadata.get("qa_pair_id", ""),
            # 从 metadata 读取问答对序号。
            "qa_pair_index": metadata.get("qa_pair_index", 0),
            # 从 metadata 读取官方 evaluator 分数。
            "qa_similarity_score": metadata.get("qa_similarity_score", 0.0),
            # 从 metadata 读取官方 evaluator 阈值。
            "qa_similarity_threshold": metadata.get("qa_similarity_threshold", 0.0),
            # 从 metadata 读取问答对验证状态。
            "qa_pair_validated": bool(metadata.get("qa_pair_validated", False)),
            # 从 metadata 读取聚类 ID。
            "cluster_id": metadata.get("cluster_id", ""),
            # 从 metadata 读取聚类标签。
            "cluster_label": metadata.get("cluster_label", ""),
            # 从 metadata 读取聚类层级。
            "cluster_level": metadata.get("cluster_level", ""),
            # 从 metadata 读取聚类路径。
            "cluster_path": metadata.get("cluster_path", []),
            # 从 metadata 读取全局聚类 ID。
            "global_cluster_id": metadata.get("global_cluster_id", ""),
            # 从 metadata 读取全局聚类标签。
            "global_cluster_label": metadata.get("global_cluster_label", ""),
            # 从 metadata 读取全局聚类层级。
            "global_cluster_level": metadata.get("global_cluster_level", ""),
            # 从 metadata 读取全局聚类路径。
            "global_cluster_path": metadata.get("global_cluster_path", []),
            # 从 metadata 读取问题哈希。
            "question_hash": metadata.get("question_hash", ""),
            # 从 metadata 读取答案哈希。
            "answer_hash": metadata.get("answer_hash", ""),
            # 从 metadata 读取规范 chunk ID。
            "canonical_chunk_id": metadata.get("canonical_chunk_id", node.node_id),
            # 从 metadata 读取融合状态。
            "fusion_status": metadata.get("fusion_status", "canonical"),
            # 从 metadata 读取业务场景。
            "scene": metadata.get("scene", ""),
            # 从 metadata 读取问题。
            "question": question,
            # 从 metadata 读取答案。
            "answer": answer,
            # 从 metadata 读取规范问题。
            "canonical_question": canonical_question,
            # 写入答案优先字段。
            "answer_text": answer,
            # 写入 query aliases。
            "query_aliases": query_aliases,
            # 从 metadata 读取解决步骤。
            "resolution_steps": metadata.get("resolution_steps", []),
            # 从 metadata 读取关键词。
            "keywords": metadata.get("keywords", []),
            # 从 metadata 读取实体。
            "entities": metadata.get("entities", {}),
            # 从 LlamaIndex node 读取文本。
            "cleaned_text": cleaned_text,
            # 从 metadata 读取来源摘录。
            "source_excerpt": source_excerpt_full,
            # 写入完整来源摘录。
            "source_excerpt_full": source_excerpt_full,
            # 写入 LLM 消费文本。
            "llm_text": llm_text,
            # 写入检索文本。
            "retrieval_text": retrieval_text,
            # 写入 duplicate 融合上下文。
            "duplicate_contexts": _as_dict_list(metadata.get("duplicate_contexts", [])),
            # 写入已合并 duplicate chunk ID。
            "merged_duplicate_chunk_ids": _as_string_list(metadata.get("merged_duplicate_chunk_ids", [])),
            # 写入 Qdrant 同步契约状态。
            "qdrant_ready": qdrant_ready,
            # 写入校验标记。
            "validation_flags": metadata["validation_flags"],
            # 从 metadata 读取内容哈希。
            "content_hash": metadata.get("content_hash", ""),
            # 从 metadata 读取向量模型名。
            "vector_model": metadata.get("vector_model", ""),
            # 从 metadata 读取向量维度。
            "vector_dim": metadata.get("vector_dim", len(node.embedding or [])),
            # 从 LlamaIndex node 读取向量。
            "vector": node.embedding or [],
            # 保存 LlamaIndex 官方 node.to_dict() 结果。
            "llamaindex_node": llamaindex_node,
        }
        # 先把 payload 转成 JSON 安全结构。
        safe_payload = json_safe_value(payload)
        # 用正式 Pydantic schema 校验 payload。
        validated_payload = RagQAPayloadModel(**safe_payload).model_dump(mode="json")
        # 追加校验后的 payload。
        payloads.append(validated_payload)
    # 返回 payload 列表。
    return payloads


def llamaindex_cluster_nodes_to_storage_json(cluster_nodes: list[TextNode]) -> list[StoragePayload]:
    # 创建聚类 payload 列表。
    cluster_payloads: list[StoragePayload] = []
    # 遍历 LlamaIndex 官方聚类节点。
    for cluster_node in cluster_nodes:
        # 读取聚类 metadata。
        metadata = dict(cluster_node.metadata)
        # 构造聚类 payload。
        payload = {
            # 写入所属文档 ID。
            "document_id": metadata.get("document_id", ""),
            # 写入聚类 ID。
            "cluster_id": metadata.get("cluster_id", cluster_node.node_id),
            # 写入聚类标签。
            "cluster_label": metadata.get("cluster_label", ""),
            # 写入聚类层级。
            "cluster_level": metadata.get("cluster_level", "document_scene"),
            # 写入聚类类型。
            "cluster_type": metadata.get("cluster_type", "qa_scene_cluster"),
            # 写入聚类关键词。
            "cluster_keywords": metadata.get("cluster_keywords", []),
            # 写入聚类成员数量。
            "cluster_member_count": metadata.get("cluster_member_count", 0),
            # 写入聚类成员 chunk_id。
            "cluster_member_chunk_ids": metadata.get("cluster_member_chunk_ids", []),
            # 保存 LlamaIndex 官方聚类 TextNode.to_dict() 结果。
            "cluster_node_json": cluster_node.to_dict(),
        }
        # 转换为 JSON 安全结构。
        safe_payload = json_safe_value(payload)
        # 用正式 Pydantic schema 校验聚类 payload。
        validated_payload = RagClusterPayloadModel(**safe_payload).model_dump(mode="json")
        # 追加聚类 payload。
        cluster_payloads.append(validated_payload)
    # 返回聚类 payload 列表。
    return cluster_payloads


def llamaindex_global_cluster_nodes_to_storage_json(global_cluster_nodes: list[TextNode]) -> list[StoragePayload]:
    # 创建全局聚类 payload 列表。
    global_cluster_payloads: list[StoragePayload] = []
    # 遍历 LlamaIndex 官方全局聚类节点。
    for cluster_node in global_cluster_nodes:
        # 读取聚类 metadata。
        metadata = dict(cluster_node.metadata)
        # 构造全局聚类 payload。
        payload = {
            # 写入全局聚类 ID。
            "global_cluster_id": metadata.get("global_cluster_id", cluster_node.node_id),
            # 写入全局聚类标签。
            "global_cluster_label": metadata.get("global_cluster_label", ""),
            # 写入全局聚类层级。
            "global_cluster_level": metadata.get("global_cluster_level", "global_scene"),
            # 写入全局聚类类型。
            "global_cluster_type": metadata.get("global_cluster_type", "cross_document_scene_cluster"),
            # 写入全局聚类关键词。
            "global_cluster_keywords": metadata.get("global_cluster_keywords", []),
            # 写入成员文档 ID。
            "member_document_ids": metadata.get("member_document_ids", []),
            # 写入成员文档内聚类 ID。
            "member_cluster_ids": metadata.get("member_cluster_ids", []),
            # 写入成员 chunk ID。
            "member_chunk_ids": metadata.get("member_chunk_ids", []),
            # 写入成员数量。
            "global_member_count": metadata.get("global_member_count", 0),
            # 保存 LlamaIndex 官方全局聚类 TextNode.to_dict() 结果。
            "global_cluster_node_json": cluster_node.to_dict(),
        }
        # 转换为 JSON 安全结构。
        safe_payload = json_safe_value(payload)
        # 用正式 Pydantic schema 校验全局聚类 payload。
        validated_payload = RagGlobalClusterPayloadModel(**safe_payload).model_dump(mode="json")
        # 追加全局聚类 payload。
        global_cluster_payloads.append(validated_payload)
    # 返回全局聚类 payload 列表。
    return global_cluster_payloads


def write_json_outputs(payloads: list[StoragePayload], output_json: Path | None, output_jsonl: Path | None) -> None:
    # 如果需要输出 JSON 数组文件。
    if output_json:
        # 创建父目录。
        output_json.parent.mkdir(parents=True, exist_ok=True)
        # 写入格式化 JSON。
        output_json.write_text(json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")
    # 如果需要输出 JSONL 文件。
    if output_jsonl:
        # 创建父目录。
        output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        # 打开 JSONL 文件。
        with output_jsonl.open("w", encoding="utf-8") as file:
            # 逐条写入 JSON 行。
            for payload in payloads:
                # 写入当前 payload。
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")
