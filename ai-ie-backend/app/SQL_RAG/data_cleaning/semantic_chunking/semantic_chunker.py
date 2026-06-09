# -*- coding: utf-8 -*-
"""基于 LlamaIndex 官方 SemanticSplitterNodeParser 的语义分块。"""

# 导入 LlamaIndex 官方 embedding 基类。
from llama_index.core.embeddings import BaseEmbedding
# 导入 LlamaIndex 官方 IngestionPipeline。
from llama_index.core.ingestion import IngestionPipeline
# 导入 LlamaIndex 官方语义分块器。
from llama_index.core.node_parser import SemanticSplitterNodeParser
# 导入 LlamaIndex 官方节点类型。
from llama_index.core.schema import BaseNode, TextNode

# 导入中文 Markdown 问答句子切分函数，作为 LlamaIndex 官方 sentence_splitter 参数。
from cleaning_extraction.text_cleaner import split_markdown_sentences


def semantic_chunk_nodes_with_llamaindex(nodes: list[BaseNode], embed_model: BaseEmbedding, breakpoint_percentile: float) -> list[TextNode]:
    # 已通过 QA evaluator 的节点是原子知识，不允许再被语义分块切成半句答案。
    qa_nodes: list[TextNode] = []
    # 普通长文档节点仍然进入官方 SemanticSplitter，保持多文档泛化流程。
    splittable_nodes: list[BaseNode] = []
    # 遍历输入节点并分流。
    for node in nodes:
        # 读取 metadata。
        metadata = dict(node.metadata or {})
        # QA 已验证时直接保留完整节点。
        if metadata.get("qa_pair_validated"):
            # 复制成 TextNode，避免后续 transformation 修改原对象。
            qa_nodes.append(
                TextNode(
                    id_=node.node_id,
                    text=node.get_content(),
                    metadata=metadata,
                    embedding=node.embedding,
                    relationships=node.relationships,
                )
            )
            # 继续下一节点。
            continue
        # 非 QA 节点加入普通语义分块。
        splittable_nodes.append(node)
    # 没有普通节点时直接返回 QA 原子节点。
    if not splittable_nodes:
        return qa_nodes
    # 创建 LlamaIndex 官方 SemanticSplitterNodeParser。
    semantic_splitter = SemanticSplitterNodeParser(
        # 使用单句缓冲，按相邻句语义距离判断断点。
        buffer_size=1,
        # 使用官方断点百分位参数。
        breakpoint_percentile_threshold=breakpoint_percentile,
        # 使用 LlamaIndex 官方 embedding 模型接口。
        embed_model=embed_model,
        # 使用官方 sentence_splitter 扩展点适配中文 Markdown 转写句子。
        sentence_splitter=split_markdown_sentences,
    )
    # 创建 LlamaIndex 官方 IngestionPipeline。
    pipeline = IngestionPipeline(transformations=[semantic_splitter])
    # 运行官方语义分块 transformation。
    chunk_nodes = pipeline.run(nodes=splittable_nodes)
    # 返回 QA 原子节点和普通语义分块节点。
    return qa_nodes + [node for node in chunk_nodes if isinstance(node, TextNode)]
