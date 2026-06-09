# -*- coding: utf-8 -*-
"""基于 LlamaIndex 官方 BaseEmbedding/IngestionPipeline 的向量化。"""

# 导入哈希库，用于本地稳定 embedding。
import hashlib
# 导入数学库，用于向量归一化。
import math
# 导入正则库，用于生成中文 ngram 和英文数字 token。
import re
# 导入列表类型。
from typing import List

# 导入 LlamaIndex 官方 embedding 基类。
from llama_index.core.embeddings import BaseEmbedding
# 导入 LlamaIndex 官方 IngestionPipeline。
from llama_index.core.ingestion import IngestionPipeline
# 导入 LlamaIndex 官方节点类型。
from llama_index.core.schema import BaseNode, TextNode


class LlamaIndexLocalHashEmbedding(BaseEmbedding):
    # 使用 LlamaIndex 官方 BaseEmbedding 扩展接口定义向量维度。
    dimensions: int = 256
    # 使用 LlamaIndex 官方 BaseEmbedding 扩展接口定义模型名。
    model_name: str = "llamaindex-local-hash-embedding-v1"

    # LlamaIndex 官方同步查询向量接口。
    def _get_query_embedding(self, query: str) -> List[float]:
        # 查询文本和文档文本使用同一套本地稳定向量。
        return self._hash_embedding(query)

    # LlamaIndex 官方同步文本向量接口。
    def _get_text_embedding(self, text: str) -> List[float]:
        # 返回文档文本向量。
        return self._hash_embedding(text)

    # LlamaIndex 官方异步查询向量接口。
    async def _aget_query_embedding(self, query: str) -> List[float]:
        # 复用同步查询向量结果。
        return self._get_query_embedding(query)

    # 本地稳定哈希向量实现，供 LlamaIndex BaseEmbedding 官方接口调用。
    def _hash_embedding(self, text: str) -> List[float]:
        # 初始化定长向量。
        vector = [0.0] * self.dimensions
        # 逐个特征写入哈希桶。
        for feature in self._features(text):
            # 用 SHA256 生成稳定哈希值。
            stable_hash = int(hashlib.sha256(feature.encode("utf-8")).hexdigest(), 16)
            # 计算向量下标。
            index = stable_hash % self.dimensions
            # 累加该特征。
            vector[index] += 1.0
        # 计算向量范数。
        norm = math.sqrt(sum(value * value for value in vector))
        # 空文本返回全零向量。
        if norm == 0:
            # 返回全零向量。
            return vector
        # 返回归一化向量。
        return [round(value / norm, 6) for value in vector]

    # 抽取本地向量特征。
    def _features(self, text: str) -> list[str]:
        # 去掉文本空白。
        compact = re.sub(r"\s+", "", text)
        # 生成中文友好的 2-gram。
        grams = [compact[index : index + 2] for index in range(max(len(compact) - 1, 0))]
        # 生成英文和数字 token。
        tokens = re.findall(r"[A-Za-z0-9]+", text)
        # 返回综合特征。
        return grams + tokens


def build_llamaindex_embedding_model(vector_dim: int, model_name: str) -> BaseEmbedding:
    # 使用 LlamaIndex 官方 BaseEmbedding 扩展接口创建本地稳定 embedding。
    return LlamaIndexLocalHashEmbedding(dimensions=vector_dim, model_name=model_name)


def vectorize_nodes_with_llamaindex(nodes: list[BaseNode], embed_model: BaseEmbedding, vector_model_name: str) -> list[TextNode]:
    # 创建 LlamaIndex 官方 IngestionPipeline，把 embedding 模型作为 transformation。
    pipeline = IngestionPipeline(transformations=[embed_model])
    # 执行官方 embedding transformation。
    vectorized_nodes = pipeline.run(nodes=nodes)
    # 创建结果列表。
    result_nodes: list[TextNode] = []
    # 遍历向量化后的节点。
    for node in vectorized_nodes:
        # 只保留 TextNode。
        if not isinstance(node, TextNode):
            # 跳过非文本节点。
            continue
        # 写入向量模型名。
        node.metadata["vector_model"] = vector_model_name
        # 写入向量维度。
        node.metadata["vector_dim"] = len(node.embedding or [])
        # 追加结果节点。
        result_nodes.append(node)
    # 返回向量化节点。
    return result_nodes
