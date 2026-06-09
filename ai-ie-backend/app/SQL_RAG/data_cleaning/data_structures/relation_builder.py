# -*- coding: utf-8 -*-
"""从 LlamaIndex TextNode 构建多文档关系型入库对象。"""

# 修改日期：2026-06-01 13:29:35。
# 修改理由：补齐多文档进入后端后的实体、融合、校验、版本和 RAG 同步关系构建逻辑。

# 导入路径类型。
from pathlib import Path
# 导入类型标注。
from typing import Any, Sequence

# 导入 LlamaIndex 官方摄取流水线。
from llama_index.core.ingestion import IngestionPipeline
# 导入 LlamaIndex 官方 Document/TextNode/TransformComponent。
from llama_index.core.schema import BaseNode, Document, TextNode, TransformComponent
# 导入 Pydantic 字段工具，用于定义 TransformComponent 可序列化字段。
from pydantic import Field

# 导入通用工具。
from common.utils import cosine_similarity, normalize_for_hash, sha256_text, stable_id, unique_keep_order
# 导入正式数据契约。
from data_structures.models import (
    DocumentVersionPayloadModel,
    IngestionJobPayloadModel,
    RagChunkFusionPayloadModel,
    RagEntityAliasPayloadModel,
    RagEntityMentionPayloadModel,
    RagSyncStatePayloadModel,
    RagValidationIssuePayloadModel,
    StoragePayload,
)


def _as_string_list(value: Any) -> list[str]:
    # 列表转字符串列表。
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    # 字符串作为单项列表。
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    # 其他类型返回空列表。
    return []


def _build_duplicate_context(node: TextNode, fusion_payload: dict[str, Any]) -> dict[str, Any]:
    # 读取重复节点 metadata。
    metadata = dict(node.metadata or {})
    # 读取答案。
    answer = str(metadata.get("answer_text") or metadata.get("answer") or "")
    # 读取问题。
    question = str(metadata.get("question", ""))
    # 读取清洗文本。
    cleaned_text = str(metadata.get("cleaned_text") or node.get_content())
    # 如果清洗文本没有完整答案，用 question + answer 修复。
    if answer and answer not in cleaned_text:
        cleaned_text = f"问题：{question}\n答案：{answer}"
    # 构造 duplicate 上下文。
    return {
        "chunk_id": node.node_id,
        "document_id": str(metadata.get("document_id", "")),
        "question": question,
        "answer": answer,
        "cleaned_text": cleaned_text,
        "source_excerpt": str(metadata.get("source_excerpt_full") or metadata.get("source_excerpt") or cleaned_text),
        "resolution_steps": _as_string_list(metadata.get("resolution_steps", [])),
        "fusion_rule": str(fusion_payload.get("fusion_rule", "")),
        "fusion_score": float(fusion_payload.get("fusion_score", 0.0) or 0.0),
    }


class FusionMetadataTransform(TransformComponent):
    # 定义 duplicate chunk 到融合 payload 的映射。
    fusion_by_duplicate: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # 定义 canonical chunk 到 duplicate 上下文的映射。
    fusion_by_canonical: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)

    # LlamaIndex 官方 TransformComponent 入口，给节点写入融合结果 metadata。
    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> Sequence[BaseNode]:
        # 创建融合 metadata 增强后的节点列表。
        fused_nodes: list[TextNode] = []
        # 遍历官方节点。
        for node in nodes:
            # 复制节点 metadata。
            metadata = dict(node.metadata)
            # 读取当前节点对应的融合关系。
            fusion_payload = self.fusion_by_duplicate.get(node.node_id)
            # 读取当前节点作为 canonical 时需要合并的重复上下文。
            duplicate_contexts = self.fusion_by_canonical.get(node.node_id, [])
            # 如果当前节点是重复节点，则绑定规范 chunk。
            if fusion_payload:
                # 写入规范 chunk ID。
                metadata["canonical_chunk_id"] = fusion_payload.get("canonical_chunk_id", node.node_id)
                # 写入融合状态。
                metadata["fusion_status"] = "duplicate"
                # 写入融合规则。
                metadata["fusion_rule"] = fusion_payload.get("fusion_rule", "")
                # 写入融合分数。
                metadata["fusion_score"] = fusion_payload.get("fusion_score", 0.0)
            # 如果当前节点不是重复节点，则保持自己为规范节点。
            else:
                # 写入规范 chunk ID。
                metadata["canonical_chunk_id"] = metadata.get("canonical_chunk_id", node.node_id)
                # 写入融合状态。
                metadata["fusion_status"] = metadata.get("fusion_status", "canonical")
            # canonical 节点合并 duplicate 上下文，避免 Qdrant 只保留 canonical 后丢完整操作句。
            if duplicate_contexts and metadata.get("fusion_status") == "canonical":
                # 合并已有 duplicate_contexts。
                existing_contexts = metadata.get("duplicate_contexts", [])
                if not isinstance(existing_contexts, list):
                    existing_contexts = []
                # 按 chunk_id 去重。
                merged_context_map = {
                    str(context.get("chunk_id", "")): context
                    for context in [*existing_contexts, *duplicate_contexts]
                    if isinstance(context, dict) and context.get("chunk_id")
                }
                # 写回 duplicate 上下文。
                metadata["duplicate_contexts"] = list(merged_context_map.values())
                # 写回已合并 duplicate chunk IDs。
                metadata["merged_duplicate_chunk_ids"] = list(merged_context_map.keys())
                # 合并 resolution steps。
                merged_steps = _as_string_list(metadata.get("resolution_steps", []))
                for context in metadata["duplicate_contexts"]:
                    merged_steps.extend(_as_string_list(context.get("resolution_steps", [])))
                metadata["resolution_steps"] = unique_keep_order(merged_steps)
                # 如果已有 LLM 消费文本，则追加 duplicate 上下文。
                llm_text = str(metadata.get("llm_text", ""))
                duplicate_text = "\n".join(str(context.get("cleaned_text", "")) for context in metadata["duplicate_contexts"] if context.get("cleaned_text"))
                if duplicate_text and duplicate_text not in llm_text:
                    metadata["llm_text"] = f"{llm_text}\n已融合重复上下文：\n{duplicate_text}".strip()
            # 复制为 LlamaIndex 官方 TextNode。
            fused_nodes.append(TextNode(id_=node.node_id, text=node.get_content(), metadata=metadata, embedding=node.embedding, relationships=node.relationships))
        # 返回融合 metadata 增强后的节点。
        return fused_nodes


def build_ingestion_job_payload(input_path: Path, job_id: str, args: Any, documents: list[Document], chunks: list[TextNode], global_cluster_count: int, fusion_count: int, validation_issue_count: int) -> StoragePayload:
    # 构造任务参数快照。
    job_options = {
        "qa_similarity_threshold": getattr(args, "qa_similarity_threshold", 0.0),
        "max_answer_sentences": getattr(args, "max_answer_sentences", 0),
        "breakpoint_percentile": getattr(args, "breakpoint_percentile", 0.0),
        "vector_dim": getattr(args, "vector_dim", 0),
        "vector_model": getattr(args, "vector_model", ""),
        "fusion_similarity_threshold": getattr(args, "fusion_similarity_threshold", 0.0),
    }
    # 构造任务 payload。
    payload = {
        "job_id": job_id,
        "input_path": str(input_path.expanduser().resolve()),
        "job_status": "completed",
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "global_cluster_count": global_cluster_count,
        "fusion_count": fusion_count,
        "validation_issue_count": validation_issue_count,
        "job_options_json": job_options,
    }
    # 用正式 Pydantic schema 校验后返回。
    return IngestionJobPayloadModel(**payload).model_dump(mode="json")


def build_document_version_payloads(documents: list[Document], job_id: str) -> list[StoragePayload]:
    # 创建文档版本 payload 列表。
    payloads: list[StoragePayload] = []
    # 遍历 LlamaIndex 官方文档。
    for document in documents:
        # 复制文档 metadata。
        metadata = dict(document.metadata)
        # 读取源路径。
        source_path = str(metadata.get("source_path", ""))
        # 读取内容哈希。
        content_hash = str(metadata.get("source_hash", ""))
        # 生成版本 ID。
        version_id = stable_id("qadocver", source_path, content_hash)
        # 构造版本 payload。
        payload = {
            "version_id": version_id,
            "document_id": document.node_id,
            "source_path": source_path,
            "source_name": str(metadata.get("source_name", "")),
            "content_hash": content_hash,
            "job_id": job_id,
            "is_current": True,
        }
        # 校验并追加 payload。
        payloads.append(DocumentVersionPayloadModel(**payload).model_dump(mode="json"))
    # 返回文档版本 payload。
    return payloads


def build_entity_relation_payloads(nodes: list[TextNode]) -> tuple[list[StoragePayload], list[StoragePayload]]:
    # 创建实体提及 payload 列表。
    mention_payloads: list[StoragePayload] = []
    # 创建实体别名 payload 字典，按 alias_id 去重。
    alias_payload_map: dict[str, StoragePayload] = {}
    # 遍历所有节点。
    for node in nodes:
        # 读取节点 metadata。
        metadata = dict(node.metadata)
        # 读取实体字典。
        entities = metadata.get("entities", {})
        # 非字典实体直接跳过。
        if not isinstance(entities, dict):
            # 继续下一节点。
            continue
        # 遍历每个实体类型。
        for entity_type, values in entities.items():
            # 非列表实体值跳过。
            if not isinstance(values, list):
                # 继续下一实体类型。
                continue
            # 遍历实体值。
            for entity_value in values:
                # 转成字符串并去掉空白。
                raw_value = str(entity_value).strip()
                # 空实体跳过。
                if not raw_value:
                    # 继续下一实体。
                    continue
                # 计算规范实体。
                canonical_entity = normalize_for_hash(raw_value) or raw_value
                # 计算实体哈希。
                entity_hash = sha256_text(f"{entity_type}|{canonical_entity}")
                # 生成实体提及 ID。
                mention_id = stable_id("qamention", node.node_id, entity_type, raw_value)
                # 构造实体提及 payload。
                mention_payload = {
                    "mention_id": mention_id,
                    "document_id": str(metadata.get("document_id", "")),
                    "chunk_id": node.node_id,
                    "entity_type": str(entity_type),
                    "entity_value": raw_value,
                    "canonical_entity": canonical_entity,
                    "entity_hash": entity_hash,
                    "global_cluster_id": str(metadata.get("global_cluster_id", "")),
                }
                # 校验并追加实体提及。
                mention_payloads.append(RagEntityMentionPayloadModel(**mention_payload).model_dump(mode="json"))
                # 生成别名 ID。
                alias_id = stable_id("qaalias", entity_type, raw_value)
                # 构造实体别名 payload。
                alias_payload = {
                    "alias_id": alias_id,
                    "entity_type": str(entity_type),
                    "alias_value": raw_value,
                    "canonical_entity": canonical_entity,
                    "entity_hash": entity_hash,
                }
                # 按 alias_id 去重保存。
                alias_payload_map[alias_id] = RagEntityAliasPayloadModel(**alias_payload).model_dump(mode="json")
    # 返回实体提及和实体别名 payload。
    return mention_payloads, list(alias_payload_map.values())


def _neo4j_chunk_lookup(chunk_payloads: list[StoragePayload]) -> dict[str, StoragePayload]:
    # 2026-06-04 16:18:42 新增原因：把 chunk payload 按 chunk_id 建索引，供 Neo4j 三元组补充问答证据。
    return {str(payload.get("chunk_id", "")): payload for payload in chunk_payloads if payload.get("chunk_id")}


def _neo4j_add_triple(triple_map: dict[str, StoragePayload], payload: StoragePayload) -> None:
    # 2026-06-04 16:18:42 新增原因：用稳定 triple_id 去重，避免同一实体在同一 chunk 重复写图。
    triple_id = str(payload.get("triple_id", ""))
    # 2026-06-04 16:18:42 新增原因：没有 triple_id 的候选关系不能安全 MERGE，直接跳过。
    if not triple_id:
        # 2026-06-04 16:18:42 新增原因：结束无效关系写入。
        return
    # 2026-06-04 16:18:42 新增原因：保存规范化后的三元组 payload。
    triple_map[triple_id] = payload


def build_neo4j_triple_payloads(
    entity_mention_payloads: list[StoragePayload],
    chunk_payloads: list[StoragePayload],
    fusion_payloads: list[StoragePayload] | None = None,
) -> list[StoragePayload]:
    # 2026-06-04 16:18:42 新增原因：创建 chunk 查找表，让图谱边携带 RAG 可消费证据文本。
    chunks_by_id = _neo4j_chunk_lookup(chunk_payloads)
    # 2026-06-04 16:18:42 新增原因：创建 chunk 到实体提及的分组，后续生成同 chunk 共现边。
    mentions_by_chunk: dict[str, list[StoragePayload]] = {}
    # 2026-06-04 16:18:42 新增原因：遍历 SQL_RAG 已抽取实体 mention，转成 Neo4j 三元组。
    for mention in entity_mention_payloads:
        # 2026-06-04 16:18:42 新增原因：读取 chunk_id 作为实体和证据 chunk 的连接点。
        chunk_id = str(mention.get("chunk_id", ""))
        # 2026-06-04 16:18:42 新增原因：没有 chunk_id 的实体提及无法参与多跳路径。
        if not chunk_id:
            # 2026-06-04 16:18:42 新增原因：跳过无证据锚点的实体。
            continue
        # 2026-06-04 16:18:42 新增原因：把 mention 放入 chunk 分组。
        mentions_by_chunk.setdefault(chunk_id, []).append(mention)
    # 2026-06-04 16:18:42 新增原因：创建去重字典承载最终三元组。
    triple_map: dict[str, StoragePayload] = {}
    # 2026-06-04 16:18:42 新增原因：遍历每个 chunk 的实体组，生成实体到 chunk 和实体共现关系。
    for chunk_id, mentions in mentions_by_chunk.items():
        # 2026-06-04 16:18:42 新增原因：读取 chunk payload，补充问题、答案和证据文本。
        chunk_payload = chunks_by_id.get(chunk_id, {})
        # 2026-06-04 16:18:42 新增原因：生成实体到 chunk 的 MENTIONED_IN_CHUNK 边。
        for mention in mentions:
            # 2026-06-04 16:18:42 新增原因：读取规范实体名，优先使用 canonical_entity。
            subject = str(mention.get("canonical_entity") or mention.get("entity_value") or "").strip()
            # 2026-06-04 16:18:42 新增原因：空实体不能写入图谱。
            if not subject:
                # 2026-06-04 16:18:42 新增原因：跳过空实体。
                continue
            # 2026-06-04 16:18:42 新增原因：构造稳定三元组 ID。
            triple_id = stable_id("qatriple", subject, "MENTIONED_IN_CHUNK", chunk_id)
            # 2026-06-04 16:18:42 新增原因：写入实体提及三元组。
            _neo4j_add_triple(
                triple_map,
                {
                    "triple_id": triple_id,
                    "subject": subject,
                    "predicate": "MENTIONED_IN_CHUNK",
                    "object": chunk_id,
                    "subject_type": str(mention.get("entity_type", "entity")),
                    "object_type": "chunk",
                    "chunk_id": chunk_id,
                    "document_id": str(mention.get("document_id") or chunk_payload.get("document_id") or ""),
                    "global_cluster_id": str(mention.get("global_cluster_id") or chunk_payload.get("global_cluster_id") or ""),
                    "evidence_text": str(chunk_payload.get("llm_text") or chunk_payload.get("retrieval_text") or chunk_payload.get("answer") or ""),
                    "properties": {
                        "entity_value": str(mention.get("entity_value", "")),
                        "question": str(chunk_payload.get("question", "")),
                        "answer": str(chunk_payload.get("answer_text") or chunk_payload.get("answer") or ""),
                    },
                },
            )
        # 2026-06-04 16:18:42 新增原因：提取同 chunk 内去重后的实体名，构建共现关系。
        canonical_entities = unique_keep_order(
            [
                str(mention.get("canonical_entity") or mention.get("entity_value") or "").strip()
                for mention in mentions
                if str(mention.get("canonical_entity") or mention.get("entity_value") or "").strip()
            ]
        )
        # 2026-06-04 16:18:42 新增原因：两两实体共现形成多跳图谱的横向关系。
        for left_index, left_entity in enumerate(canonical_entities):
            # 2026-06-04 16:18:42 新增原因：只连接右侧实体，避免重复边。
            for right_entity in canonical_entities[left_index + 1 :]:
                # 2026-06-04 16:18:42 新增原因：构造共现关系 ID。
                triple_id = stable_id("qatriple", left_entity, "CO_OCCURS_WITH", right_entity, chunk_id)
                # 2026-06-04 16:18:42 新增原因：写入同 chunk 实体共现三元组。
                _neo4j_add_triple(
                    triple_map,
                    {
                        "triple_id": triple_id,
                        "subject": left_entity,
                        "predicate": "CO_OCCURS_WITH",
                        "object": right_entity,
                        "subject_type": "entity",
                        "object_type": "entity",
                        "chunk_id": chunk_id,
                        "document_id": str(chunk_payload.get("document_id", "")),
                        "global_cluster_id": str(chunk_payload.get("global_cluster_id", "")),
                        "evidence_text": str(chunk_payload.get("llm_text") or chunk_payload.get("retrieval_text") or chunk_payload.get("answer") or ""),
                        "properties": {
                            "question": str(chunk_payload.get("question", "")),
                            "answer": str(chunk_payload.get("answer_text") or chunk_payload.get("answer") or ""),
                        },
                    },
                )
        # 2026-06-04 16:18:42 新增原因：chunk 归属全局聚类，支持从实体跳到业务场景。
        global_cluster_id = str(chunk_payload.get("global_cluster_id", "")).strip()
        # 2026-06-04 16:18:42 新增原因：有全局聚类时才写 CHUNK_IN_GLOBAL_CLUSTER。
        if global_cluster_id:
            # 2026-06-04 16:18:42 新增原因：构造 chunk 到全局聚类的三元组 ID。
            triple_id = stable_id("qatriple", chunk_id, "CHUNK_IN_GLOBAL_CLUSTER", global_cluster_id)
            # 2026-06-04 16:18:42 新增原因：写入 chunk 归属聚类三元组。
            _neo4j_add_triple(
                triple_map,
                {
                    "triple_id": triple_id,
                    "subject": chunk_id,
                    "predicate": "CHUNK_IN_GLOBAL_CLUSTER",
                    "object": global_cluster_id,
                    "subject_type": "chunk",
                    "object_type": "global_cluster",
                    "chunk_id": chunk_id,
                    "document_id": str(chunk_payload.get("document_id", "")),
                    "global_cluster_id": global_cluster_id,
                    "evidence_text": str(chunk_payload.get("llm_text") or chunk_payload.get("retrieval_text") or chunk_payload.get("answer") or ""),
                    "properties": {
                        "global_cluster_label": str(chunk_payload.get("global_cluster_label", "")),
                    },
                },
            )
    # 2026-06-04 16:18:42 新增原因：融合关系也进入 Neo4j，支持 canonical/duplicate 多跳回溯。
    for fusion in fusion_payloads or []:
        # 2026-06-04 16:18:42 新增原因：读取规范 chunk。
        canonical_chunk_id = str(fusion.get("canonical_chunk_id", "")).strip()
        # 2026-06-04 16:18:42 新增原因：读取重复 chunk。
        duplicate_chunk_id = str(fusion.get("duplicate_chunk_id", "")).strip()
        # 2026-06-04 16:18:42 新增原因：缺任一端点时跳过。
        if not canonical_chunk_id or not duplicate_chunk_id:
            # 2026-06-04 16:18:42 新增原因：结束无效融合关系。
            continue
        # 2026-06-04 16:18:42 新增原因：构造融合三元组 ID。
        triple_id = stable_id("qatriple", duplicate_chunk_id, "FUSED_INTO", canonical_chunk_id)
        # 2026-06-04 16:18:42 新增原因：写入 duplicate 到 canonical 的融合关系。
        _neo4j_add_triple(
            triple_map,
            {
                "triple_id": triple_id,
                "subject": duplicate_chunk_id,
                "predicate": "FUSED_INTO",
                "object": canonical_chunk_id,
                "subject_type": "chunk",
                "object_type": "chunk",
                "chunk_id": canonical_chunk_id,
                "document_id": str(fusion.get("canonical_document_id", "")),
                "global_cluster_id": str(fusion.get("global_cluster_id", "")),
                "evidence_text": str(fusion.get("duplicate_cleaned_text", "")),
                "properties": {
                    "fusion_score": float(fusion.get("fusion_score", 0.0) or 0.0),
                    "fusion_rule": str(fusion.get("fusion_rule", "")),
                },
            },
        )
    # 2026-06-04 16:18:42 新增原因：返回稳定排序后的三元组列表，方便测试和导入复现。
    return sorted(triple_map.values(), key=lambda item: str(item.get("triple_id", "")))


def build_chunk_fusion_payloads_with_llamaindex(nodes: list[TextNode], similarity_threshold: float) -> list[StoragePayload]:
    # 创建融合 payload 字典，避免同一重复节点被多次写入。
    fusion_payload_map: dict[str, StoragePayload] = {}
    # 创建问题哈希到节点列表的映射。
    question_groups: dict[str, list[TextNode]] = {}
    # 遍历所有节点。
    for node in nodes:
        # 读取问题哈希。
        question_hash = str(node.metadata.get("question_hash", ""))
        # 空问题哈希跳过。
        if not question_hash:
            # 继续下一节点。
            continue
        # 把节点加入同问题组。
        question_groups.setdefault(question_hash, []).append(node)
    # 先按完全相同问题哈希构建强融合关系。
    for question_hash, members in question_groups.items():
        # 单成员问题不需要融合。
        if len(members) <= 1:
            # 继续下一组。
            continue
        # 按文档 ID、chunk 序号、chunk ID 选最稳定的规范记录。
        ordered_members = sorted(members, key=lambda item: (str(item.metadata.get("document_id", "")), int(item.metadata.get("chunk_index", 0)), item.node_id))
        # 取第一个作为规范 chunk。
        canonical = ordered_members[0]
        # 读取规范答案哈希。
        canonical_answer_hash = str(canonical.metadata.get("answer_hash", ""))
        # 遍历剩余成员。
        for duplicate in ordered_members[1:]:
            # 读取答案哈希。
            answer_hash = str(duplicate.metadata.get("answer_hash", ""))
            # 同问题但答案不同的记录不自动融合，交给 validation issue 做消歧提示。
            if answer_hash != canonical_answer_hash:
                # 继续下一候选。
                continue
            # 生成融合关系 ID。
            fusion_id = stable_id("qafusion", canonical.node_id, duplicate.node_id, question_hash)
            # 构造融合 payload。
            payload = {
                "fusion_id": fusion_id,
                "canonical_chunk_id": canonical.node_id,
                "duplicate_chunk_id": duplicate.node_id,
                "canonical_document_id": str(canonical.metadata.get("document_id", "")),
                "duplicate_document_id": str(duplicate.metadata.get("document_id", "")),
                "global_cluster_id": str(duplicate.metadata.get("global_cluster_id", "")),
                "question_hash": question_hash,
                "answer_hash": answer_hash,
                "fusion_score": 1.0,
                "fusion_rule": "same_normalized_question_hash",
                "duplicate_question": str(duplicate.metadata.get("question", "")),
                "duplicate_answer": str(duplicate.metadata.get("answer_text") or duplicate.metadata.get("answer") or ""),
                "duplicate_cleaned_text": str(duplicate.metadata.get("cleaned_text") or duplicate.get_content()),
                "duplicate_resolution_steps": _as_string_list(duplicate.metadata.get("resolution_steps", [])),
                "merge_payload": _build_duplicate_context(duplicate, {"fusion_rule": "same_normalized_question_hash", "fusion_score": 1.0}),
            }
            # 校验并保存融合 payload。
            fusion_payload_map[duplicate.node_id] = RagChunkFusionPayloadModel(**payload).model_dump(mode="json")
    # 创建全局聚类到节点列表的映射。
    global_groups: dict[str, list[TextNode]] = {}
    # 遍历所有节点。
    for node in nodes:
        # 读取全局聚类 ID。
        global_cluster_id = str(node.metadata.get("global_cluster_id", ""))
        # 空全局聚类跳过。
        if not global_cluster_id:
            # 继续下一节点。
            continue
        # 放入对应全局聚类组。
        global_groups.setdefault(global_cluster_id, []).append(node)
    # 再按 LlamaIndex embedding 后的向量相似度做近似融合。
    for global_cluster_id, members in global_groups.items():
        # 成员太少时无需比较。
        if len(members) <= 1:
            # 继续下一组。
            continue
        # 遍历左侧节点。
        for left_index, left in enumerate(members):
            # 遍历右侧节点，避免重复比较。
            for right in members[left_index + 1 :]:
                # 已经作为重复节点融合过时跳过。
                if right.node_id in fusion_payload_map:
                    # 继续下一候选。
                    continue
                # 同一个问题哈希已由强规则处理过，避免重复。
                if left.metadata.get("question_hash") == right.metadata.get("question_hash"):
                    # 继续下一候选。
                    continue
                # 向量近似融合只允许跨文档，避免同一文档内部过度压缩导致 RAG 丢知识。
                if str(left.metadata.get("document_id", "")) == str(right.metadata.get("document_id", "")):
                    # 继续下一候选。
                    continue
                # 计算 LlamaIndex embedding 向量余弦相似度。
                score = cosine_similarity(left.embedding or [], right.embedding or [])
                # 相似度不足阈值时跳过。
                if score < similarity_threshold:
                    # 继续下一候选。
                    continue
                # 按稳定排序选规范和重复记录。
                canonical, duplicate = sorted([left, right], key=lambda item: (str(item.metadata.get("document_id", "")), int(item.metadata.get("chunk_index", 0)), item.node_id))
                # 如果重复节点已经融合过，跳过。
                if duplicate.node_id in fusion_payload_map:
                    # 继续下一候选。
                    continue
                # 生成融合关系 ID。
                fusion_id = stable_id("qafusion", canonical.node_id, duplicate.node_id, score)
                # 构造融合 payload。
                payload = {
                    "fusion_id": fusion_id,
                    "canonical_chunk_id": canonical.node_id,
                    "duplicate_chunk_id": duplicate.node_id,
                    "canonical_document_id": str(canonical.metadata.get("document_id", "")),
                    "duplicate_document_id": str(duplicate.metadata.get("document_id", "")),
                    "global_cluster_id": global_cluster_id,
                    "question_hash": str(duplicate.metadata.get("question_hash", "")),
                    "answer_hash": str(duplicate.metadata.get("answer_hash", "")),
                    "fusion_score": score,
                    "fusion_rule": "llamaindex_embedding_vector_similarity",
                    "duplicate_question": str(duplicate.metadata.get("question", "")),
                    "duplicate_answer": str(duplicate.metadata.get("answer_text") or duplicate.metadata.get("answer") or ""),
                    "duplicate_cleaned_text": str(duplicate.metadata.get("cleaned_text") or duplicate.get_content()),
                    "duplicate_resolution_steps": _as_string_list(duplicate.metadata.get("resolution_steps", [])),
                    "merge_payload": _build_duplicate_context(duplicate, {"fusion_rule": "llamaindex_embedding_vector_similarity", "fusion_score": score}),
                }
                # 校验并保存融合 payload。
                fusion_payload_map[duplicate.node_id] = RagChunkFusionPayloadModel(**payload).model_dump(mode="json")
    # 返回融合 payload 列表。
    return list(fusion_payload_map.values())


def apply_fusion_metadata_with_llamaindex(nodes: list[TextNode], fusion_payloads: list[StoragePayload]) -> list[TextNode]:
    # 创建重复 chunk 到融合 payload 的映射。
    fusion_by_duplicate = {str(payload.get("duplicate_chunk_id")): payload for payload in fusion_payloads}
    # 创建节点 ID 到节点的映射。
    nodes_by_id = {node.node_id: node for node in nodes}
    # 创建 canonical chunk 到 duplicate 上下文的映射。
    fusion_by_canonical: dict[str, list[dict[str, Any]]] = {}
    # 遍历融合 payload。
    for payload in fusion_payloads:
        # 读取 canonical ID。
        canonical_chunk_id = str(payload.get("canonical_chunk_id", ""))
        # 读取 duplicate ID。
        duplicate_chunk_id = str(payload.get("duplicate_chunk_id", ""))
        # 找到 duplicate 节点。
        duplicate_node = nodes_by_id.get(duplicate_chunk_id)
        # 找不到节点时跳过。
        if not canonical_chunk_id or duplicate_node is None:
            continue
        # 优先使用 payload 中已经保存的 merge_payload。
        merge_payload = payload.get("merge_payload")
        # 兜底从节点生成。
        if not isinstance(merge_payload, dict):
            merge_payload = _build_duplicate_context(duplicate_node, dict(payload))
        # 加入 canonical 映射。
        fusion_by_canonical.setdefault(canonical_chunk_id, []).append(merge_payload)
    # 创建 LlamaIndex 官方 IngestionPipeline。
    pipeline = IngestionPipeline(
        transformations=[
            FusionMetadataTransform(
                fusion_by_duplicate=fusion_by_duplicate,
                fusion_by_canonical=fusion_by_canonical,
            )
        ]
    )
    # 执行融合 metadata 写入。
    fused_nodes = pipeline.run(nodes=nodes)
    # 返回 LlamaIndex 官方 TextNode 列表。
    return [node for node in fused_nodes if isinstance(node, TextNode)]


def build_validation_issue_payloads(nodes: list[TextNode]) -> list[StoragePayload]:
    # 创建校验问题 payload 列表。
    issue_payloads: list[StoragePayload] = []
    # 创建问题哈希到答案哈希集合的映射。
    answer_hashes_by_question: dict[str, set[str]] = {}
    # 创建问题哈希到节点列表的映射。
    nodes_by_question: dict[str, list[TextNode]] = {}
    # 遍历所有节点。
    for node in nodes:
        # 复制节点 metadata。
        metadata = dict(node.metadata)
        # 读取文档 ID。
        document_id = str(metadata.get("document_id", ""))
        # 读取问题。
        question = str(metadata.get("question", ""))
        # 读取答案。
        answer = str(metadata.get("answer", ""))
        # 读取问题哈希。
        question_hash = str(metadata.get("question_hash", ""))
        # 读取答案哈希。
        answer_hash = str(metadata.get("answer_hash", ""))
        # 同问题哈希聚合答案哈希。
        if question_hash:
            # 初始化答案哈希集合。
            answer_hashes_by_question.setdefault(question_hash, set()).add(answer_hash)
            # 初始化节点列表。
            nodes_by_question.setdefault(question_hash, []).append(node)
        # 缺少问题时登记严重问题。
        if not question:
            # 生成问题 ID。
            issue_id = stable_id("qaissue", node.node_id, "missing_question")
            # 构造问题 payload。
            payload = {
                "issue_id": issue_id,
                "document_id": document_id,
                "chunk_id": node.node_id,
                "issue_type": "missing_question",
                "issue_level": "error",
                "issue_message": "chunk 缺少问题文本，不能直接喂给后续 RAG。",
                "issue_payload": {"chunk_id": node.node_id},
            }
            # 校验并追加问题。
            issue_payloads.append(RagValidationIssuePayloadModel(**payload).model_dump(mode="json"))
        # 缺少答案时登记严重问题。
        if not answer:
            # 生成问题 ID。
            issue_id = stable_id("qaissue", node.node_id, "missing_answer")
            # 构造问题 payload。
            payload = {
                "issue_id": issue_id,
                "document_id": document_id,
                "chunk_id": node.node_id,
                "issue_type": "missing_answer",
                "issue_level": "error",
                "issue_message": "chunk 缺少答案文本，不能直接喂给后续 RAG。",
                "issue_payload": {"chunk_id": node.node_id},
            }
            # 校验并追加问题。
            issue_payloads.append(RagValidationIssuePayloadModel(**payload).model_dump(mode="json"))
        # 官方 evaluator 未通过时登记问题。
        if not metadata.get("qa_pair_validated"):
            # 生成问题 ID。
            issue_id = stable_id("qaissue", node.node_id, "qa_pair_not_validated")
            # 构造问题 payload。
            payload = {
                "issue_id": issue_id,
                "document_id": document_id,
                "chunk_id": node.node_id,
                "issue_type": "qa_pair_not_validated",
                "issue_level": "error",
                "issue_message": "问题和答案没有通过 LlamaIndex SemanticSimilarityEvaluator 绑定检测。",
                "issue_payload": {"qa_similarity_score": metadata.get("qa_similarity_score", 0.0)},
            }
            # 校验并追加问题。
            issue_payloads.append(RagValidationIssuePayloadModel(**payload).model_dump(mode="json"))
        # 读取 RAG/LLM 可消费文本。
        llm_text = str(metadata.get("llm_text") or node.get_content() or "")
        # 有答案但 LLM 消费文本漏掉答案时登记严重问题。
        if answer and answer not in llm_text:
            # 生成问题 ID。
            issue_id = stable_id("qaissue", node.node_id, "llm_text_missing_answer")
            # 构造问题 payload。
            payload = {
                "issue_id": issue_id,
                "document_id": document_id,
                "chunk_id": node.node_id,
                "issue_type": "llm_text_missing_answer",
                "issue_level": "error",
                "issue_message": "chunk 的 llm_text 未包含完整 answer，通用 RAG/LLM 消费时会漏关键操作句。",
                "issue_payload": {"answer": answer, "llm_text": llm_text[:500]},
            }
            # 校验并追加问题。
            issue_payloads.append(RagValidationIssuePayloadModel(**payload).model_dump(mode="json"))
        # 读取检索文本。
        retrieval_text = str(metadata.get("retrieval_text") or "")
        # 检索文本为空或漏答案时登记问题，防止向量化语义和答案证据脱节。
        if answer and (not retrieval_text or answer not in retrieval_text):
            # 生成问题 ID。
            issue_id = stable_id("qaissue", node.node_id, "retrieval_text_missing_answer")
            # 构造问题 payload。
            payload = {
                "issue_id": issue_id,
                "document_id": document_id,
                "chunk_id": node.node_id,
                "issue_type": "retrieval_text_missing_answer",
                "issue_level": "error",
                "issue_message": "chunk 的 retrieval_text 未包含完整 answer，向量同步前必须修复。",
                "issue_payload": {"answer": answer, "retrieval_text": retrieval_text[:500]},
            }
            # 校验并追加问题。
            issue_payloads.append(RagValidationIssuePayloadModel(**payload).model_dump(mode="json"))
    # 遍历同问题多答案冲突。
    for question_hash, answer_hashes in answer_hashes_by_question.items():
        # 不同答案哈希超过 1 个时视为需要消歧。
        if len({answer_hash for answer_hash in answer_hashes if answer_hash}) <= 1:
            # 继续下一问题。
            continue
        # 遍历冲突问题对应节点。
        for node in nodes_by_question.get(question_hash, []):
            # 复制节点 metadata。
            metadata = dict(node.metadata)
            # 生成问题 ID。
            issue_id = stable_id("qaissue", node.node_id, "conflicting_answer", question_hash)
            # 构造问题 payload。
            payload = {
                "issue_id": issue_id,
                "document_id": str(metadata.get("document_id", "")),
                "chunk_id": node.node_id,
                "issue_type": "conflicting_answer",
                "issue_level": "warning",
                "issue_message": "跨文档发现同一规范问题存在不同答案，需要下游或人工消歧后再作为确定知识使用。",
                "issue_payload": {"question_hash": question_hash, "answer_hashes": sorted(answer_hashes)},
            }
            # 校验并追加问题。
            issue_payloads.append(RagValidationIssuePayloadModel(**payload).model_dump(mode="json"))
    # 返回校验问题 payload。
    return issue_payloads


def build_rag_sync_payloads(documents: list[Document], nodes: list[TextNode]) -> list[StoragePayload]:
    # 创建文档 ID 到 chunk 数量的映射。
    chunk_count_by_document: dict[str, int] = {}
    # 遍历所有节点。
    for node in nodes:
        # 读取文档 ID。
        document_id = str(node.metadata.get("document_id", ""))
        # 累加文档 chunk 数量。
        chunk_count_by_document[document_id] = chunk_count_by_document.get(document_id, 0) + 1
    # 创建同步状态 payload 列表。
    sync_payloads: list[StoragePayload] = []
    # 遍历文档。
    for document in documents:
        # 复制文档 metadata。
        metadata = dict(document.metadata)
        # 读取内容哈希。
        content_hash = str(metadata.get("source_hash", ""))
        # 生成同步状态 ID。
        sync_id = stable_id("qasync", document.node_id, content_hash, "llamaindex_vector_store")
        # 构造同步状态 payload。
        payload = {
            "sync_id": sync_id,
            "document_id": document.node_id,
            "content_hash": content_hash,
            "sync_target": "llamaindex_vector_store",
            "sync_status": "pending",
            "chunk_count": chunk_count_by_document.get(document.node_id, 0),
            "needs_reindex": True,
            "sync_message": "SQL Server 已完成结构化入库，等待后续 RAG/向量库消费并标记 synced。",
        }
        # 校验并追加同步状态。
        sync_payloads.append(RagSyncStatePayloadModel(**payload).model_dump(mode="json"))
    # 返回同步状态 payload。
    return sync_payloads


def build_job_id(input_path: Path, documents: list[Document]) -> str:
    # 汇总本次输入源路径。
    input_text = str(input_path.expanduser().resolve())
    # 汇总文档内容哈希。
    document_hashes = "|".join(str(document.metadata.get("source_hash", "")) for document in documents)
    # 生成稳定任务 ID。
    return stable_id("qaingest", input_text, document_hashes)
