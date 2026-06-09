# -*- coding: utf-8 -*-
"""基于 LlamaIndex 官方 TextNode/IngestionPipeline 的跨文档全局聚类。"""

# 修改日期：2026-06-01 13:29:35。
# 修改理由：补齐多 Markdown 文档进入后端后的全局聚类层，避免只停留在单文档 scene 聚类。

# 导入类型标注。
from typing import Any, Sequence

# 导入 LlamaIndex 官方摄取流水线。
from llama_index.core.ingestion import IngestionPipeline
# 导入 LlamaIndex 官方节点与 transformation 基类。
from llama_index.core.schema import BaseNode, TextNode, TransformComponent

# 导入稳定 ID、归一化哈希和去重工具。
from common.utils import normalize_for_hash, sha256_text, stable_id, unique_keep_order


class GlobalClusterAssignmentTransform(TransformComponent):
    # LlamaIndex 官方 TransformComponent 入口，给每个问答 chunk 写入跨文档全局聚类字段。
    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> Sequence[BaseNode]:
        # 创建全局聚类增强后的节点列表。
        global_nodes: list[TextNode] = []
        # 遍历官方节点。
        for node in nodes:
            # 复制节点 metadata，避免原地污染上游对象。
            metadata = dict(node.metadata)
            # 读取文档内聚类标签。
            local_cluster_label = str(metadata.get("cluster_label") or metadata.get("scene") or "未分类问答")
            # 归一化全局聚类标签，保证不同文档同一业务场景落到同一个全局簇。
            normalized_label = normalize_for_hash(local_cluster_label) or "unknown"
            # 生成跨文档全局聚类 ID。
            global_cluster_id = stable_id("qaglobal", normalized_label)
            # 读取问题文本。
            question = str(metadata.get("question", ""))
            # 读取答案文本。
            answer = str(metadata.get("answer", ""))
            # 生成归一化问题哈希。
            question_hash = sha256_text(normalize_for_hash(question)) if question else ""
            # 生成归一化答案哈希。
            answer_hash = sha256_text(normalize_for_hash(answer)) if answer else ""
            # 写入全局聚类 ID。
            metadata["global_cluster_id"] = global_cluster_id
            # 写入全局聚类标签。
            metadata["global_cluster_label"] = local_cluster_label
            # 写入全局聚类层级。
            metadata["global_cluster_level"] = "global_scene"
            # 写入全局聚类类型。
            metadata["global_cluster_type"] = "cross_document_scene_cluster"
            # 写入全局聚类路径。
            metadata["global_cluster_path"] = ["global", local_cluster_label]
            # 写入问题哈希。
            metadata["question_hash"] = question_hash
            # 写入答案哈希。
            metadata["answer_hash"] = answer_hash
            # 默认把自己作为规范 chunk。
            metadata["canonical_chunk_id"] = node.node_id
            # 默认融合状态为规范记录。
            metadata["fusion_status"] = "canonical"
            # 写入修改时间。
            metadata["global_cluster_modified_at"] = "2026-06-01 13:29:35"
            # 写入修改理由。
            metadata["global_cluster_modified_reason"] = "补齐跨文档全局聚类字段，支持新文档进入后统一归档、融合和校验。"
            # 用 LlamaIndex 官方 TextNode 承载增强后的 metadata。
            global_nodes.append(TextNode(id_=node.node_id, text=node.get_content(), metadata=metadata, relationships=node.relationships))
        # 返回全局聚类增强后的节点序列。
        return global_nodes


def assign_global_clusters_with_llamaindex(nodes: list[BaseNode]) -> list[TextNode]:
    # 创建 LlamaIndex 官方 IngestionPipeline。
    pipeline = IngestionPipeline(transformations=[GlobalClusterAssignmentTransform()])
    # 执行全局聚类字段写入。
    global_nodes = pipeline.run(nodes=nodes)
    # 返回 LlamaIndex 官方 TextNode 列表。
    return [node for node in global_nodes if isinstance(node, TextNode)]


def build_global_cluster_summary_nodes_with_llamaindex(nodes: list[TextNode]) -> list[TextNode]:
    # 创建全局聚类 ID 到成员节点的映射。
    grouped_nodes: dict[str, list[TextNode]] = {}
    # 遍历所有问答 chunk。
    for node in nodes:
        # 读取全局聚类 ID。
        global_cluster_id = str(node.metadata.get("global_cluster_id", ""))
        # 跳过缺少全局聚类 ID 的节点。
        if not global_cluster_id:
            # 继续下一节点。
            continue
        # 把当前节点放入对应全局聚类。
        grouped_nodes.setdefault(global_cluster_id, []).append(node)
    # 创建全局聚类摘要节点列表。
    global_cluster_nodes: list[TextNode] = []
    # 遍历每个全局聚类。
    for global_cluster_id, members in grouped_nodes.items():
        # 读取第一个成员 metadata。
        first_metadata = dict(members[0].metadata)
        # 汇总成员文档 ID。
        member_document_ids = unique_keep_order([str(member.metadata.get("document_id", "")) for member in members])
        # 汇总成员文档内聚类 ID。
        member_cluster_ids = unique_keep_order([str(member.metadata.get("cluster_id", "")) for member in members])
        # 汇总成员 chunk ID。
        member_chunk_ids = [member.node_id for member in members]
        # 汇总关键词。
        global_keywords = unique_keep_order(
            [
                keyword
                for member in members
                for keyword in list(member.metadata.get("keywords", []))
            ]
        )[:40]
        # 读取全局聚类标签。
        global_cluster_label = str(first_metadata.get("global_cluster_label", "未分类问答"))
        # 拼接全局聚类摘要文本。
        cluster_text = "\n".join(
            f"文档：{member.metadata.get('document_id', '')}\n问题：{member.metadata.get('question', '')}\n答案：{member.metadata.get('answer', '')}"
            for member in members[:12]
        )
        # 构造全局聚类 metadata。
        cluster_metadata = {
            "global_cluster_id": global_cluster_id,
            "global_cluster_label": global_cluster_label,
            "global_cluster_level": "global_scene",
            "global_cluster_type": "cross_document_scene_cluster",
            "global_cluster_keywords": global_keywords,
            "member_document_ids": member_document_ids,
            "member_cluster_ids": member_cluster_ids,
            "member_chunk_ids": member_chunk_ids,
            "global_member_count": len(members),
            "global_cluster_modified_at": "2026-06-01 13:29:35",
            "global_cluster_modified_reason": "用 LlamaIndex TextNode 表示跨文档全局聚类摘要，便于后续 RAG 建索引或入库。",
        }
        # 创建 LlamaIndex 官方全局聚类摘要 TextNode。
        global_cluster_nodes.append(TextNode(id_=global_cluster_id, text=cluster_text, metadata=cluster_metadata))
    # 返回全局聚类摘要节点列表。
    return global_cluster_nodes
