# -*- coding: utf-8 -*-
"""基于 LlamaIndex 官方 TextNode 的 RAG 典型聚类结构。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：为下一步 RAG 消费补齐 document -> scene cluster -> qa chunk 的典型聚类层级结构。

# 导入类型标注，保证官方 transformation 接口清晰。
from typing import Any, Sequence

# 导入 LlamaIndex 官方摄取流水线。
from llama_index.core.ingestion import IngestionPipeline
# 导入 LlamaIndex 官方节点和 transformation 基类。
from llama_index.core.schema import BaseNode, TextNode, TransformComponent

# 导入稳定 ID 工具。
from common.utils import stable_id, unique_keep_order


class RagClusterAssignmentTransform(TransformComponent):
    # LlamaIndex 官方 TransformComponent 入口，给每个问答 chunk 写入聚类层级。
    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> Sequence[BaseNode]:
        # 创建聚类增强后的节点列表。
        clustered_nodes: list[TextNode] = []
        # 遍历官方节点。
        for node in nodes:
            # 复制节点 metadata。
            metadata = dict(node.metadata)
            # 读取文档 ID。
            document_id = str(metadata.get("document_id", ""))
            # 读取业务场景作为一级聚类标签。
            cluster_label = str(metadata.get("scene") or metadata.get("audio_title") or "未分类问答")
            # 生成稳定聚类 ID。
            cluster_id = stable_id("qacluster", document_id, cluster_label)
            # 写入聚类 ID。
            metadata["cluster_id"] = cluster_id
            # 写入聚类标签。
            metadata["cluster_label"] = cluster_label
            # 写入聚类层级。
            metadata["cluster_level"] = "document_scene"
            # 写入聚类类型。
            metadata["cluster_type"] = "qa_scene_cluster"
            # 写入 RAG 层级路径。
            metadata["cluster_path"] = [document_id, cluster_label]
            # 写入修改时间。
            metadata["cluster_modified_at"] = "2026-06-01 10:14:00"
            # 写入修改理由。
            metadata["cluster_modified_reason"] = "补齐下一步 RAG 可直接使用的典型聚类层级。"
            # 复制为官方 TextNode。
            clustered_nodes.append(TextNode(id_=node.node_id, text=node.get_content(), metadata=metadata))
        # 返回聚类增强后的节点序列。
        return clustered_nodes


def assign_rag_clusters_with_llamaindex(nodes: list[BaseNode]) -> list[TextNode]:
    # 创建 LlamaIndex 官方 IngestionPipeline。
    pipeline = IngestionPipeline(transformations=[RagClusterAssignmentTransform()])
    # 执行聚类 metadata 写入。
    clustered_nodes = pipeline.run(nodes=nodes)
    # 返回 LlamaIndex 官方 TextNode 列表。
    return [node for node in clustered_nodes if isinstance(node, TextNode)]


def build_cluster_summary_nodes_with_llamaindex(nodes: list[TextNode]) -> list[TextNode]:
    # 创建 cluster_id 到节点列表的映射。
    grouped_nodes: dict[str, list[TextNode]] = {}
    # 遍历所有问答 chunk。
    for node in nodes:
        # 读取 cluster_id。
        cluster_id = str(node.metadata.get("cluster_id", ""))
        # 跳过没有聚类 ID 的节点。
        if not cluster_id:
            # 继续下一节点。
            continue
        # 初始化聚类列表并追加当前节点。
        grouped_nodes.setdefault(cluster_id, []).append(node)
    # 创建聚类摘要节点列表。
    cluster_nodes: list[TextNode] = []
    # 遍历每个聚类。
    for cluster_id, members in grouped_nodes.items():
        # 读取第一个成员的 metadata。
        first_metadata = dict(members[0].metadata)
        # 汇总成员 chunk_id。
        member_chunk_ids = [member.node_id for member in members]
        # 汇总聚类关键词。
        cluster_keywords = unique_keep_order(
            [
                keyword
                for member in members
                for keyword in list(member.metadata.get("keywords", []))
            ]
        )[:24]
        # 读取聚类标签。
        cluster_label = str(first_metadata.get("cluster_label", "未分类问答"))
        # 拼接聚类摘要文本。
        cluster_text = "\n".join(
            f"问题：{member.metadata.get('question', '')}\n答案：{member.metadata.get('answer', '')}"
            for member in members[:8]
        )
        # 构造聚类 metadata。
        cluster_metadata = {
            "document_id": first_metadata.get("document_id", ""),
            "cluster_id": cluster_id,
            "cluster_label": cluster_label,
            "cluster_level": "document_scene",
            "cluster_type": "qa_scene_cluster",
            "cluster_keywords": cluster_keywords,
            "cluster_member_count": len(members),
            "cluster_member_chunk_ids": member_chunk_ids,
            "cluster_modified_at": "2026-06-01 10:14:00",
            "cluster_modified_reason": "用 LlamaIndex TextNode 表示 RAG 聚类摘要节点，便于后续索引或入库。",
        }
        # 创建 LlamaIndex 官方聚类摘要 TextNode。
        cluster_nodes.append(TextNode(id_=cluster_id, text=cluster_text, metadata=cluster_metadata))
    # 返回聚类摘要节点列表。
    return cluster_nodes
