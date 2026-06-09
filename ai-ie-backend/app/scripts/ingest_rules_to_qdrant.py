# app/ingestion.py
import json
import asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest
from llama_index.embeddings.openai import OpenAIEmbedding
import os
import sys

# 配置（从环境变量读取）
QDRANT_URL = os.getenv("QDRANT_URL", "http://yulith:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "箱包规则")
JSON_FILE_PATH = os.getenv("JSON_FILE_PATH", "规则表.json")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")

embed_model = OpenAIEmbedding(
    model_name="Qwen/Qwen3-Embedding-0.6B",
    api_key=EMBEDDING_API_KEY,
    api_base=EMBEDDING_BASE_URL,
    dimensions=1024,
    truncate_dim=1024,
)


async def rebuild_knowledge_base():
    """核心逻辑：重建 Qdrant 集合（无交互、无 print）"""
    client = AsyncQdrantClient(url=QDRANT_URL)

    # 删除旧集合（如果存在）
    try:
        await client.get_collection(collection_name=COLLECTION_NAME)
        await client.delete_collection(collection_name=COLLECTION_NAME)
    except Exception:
        pass  # 忽略不存在的错误

    # 创建新集合
    await client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=rest.VectorParams(size=1024, distance=rest.Distance.COSINE),
        optimizers_config=rest.OptimizersConfigDiff(
            indexing_threshold=1000,
            memmap_threshold=10000,
            vacuum_min_vector_number=1000
        ),
        hnsw_config=rest.HnswConfigDiff(m=16, ef_construct=100)
    )

    # 读取 JSON
    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    rules = data["通用规则库"]

    # 生成嵌入
    embeddings = []
    for rule in rules:
        try:
            embedding = await asyncio.to_thread(embed_model.get_query_embedding, rule["text"])
            embeddings.append(embedding)
        except Exception:
            embeddings.append([0.0] * 1024)  # 失败时填充零向量

    # 准备 points
    points = []
    for i, (rule, embedding) in enumerate(zip(rules, embeddings)):
        if not all(v == 0 for v in embedding[:10]):  # 跳过无效嵌入
            points.append(rest.PointStruct(
                id=i + 1,
                vector=embedding,
                payload={
                    "rule_id": rule["id"],
                    "text": rule["text"],
                    "source": "通用规则库",
                    "category": "箱包工艺"
                }
            ))

    # 批量插入
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        await client.upsert(collection_name=COLLECTION_NAME, points=batch)

    await client.close()
    return {"status": "success", "inserted_count": len(points)}
if __name__ == "__main__":
    try:
        result = asyncio.run(rebuild_knowledge_base())
        print(f"知识库重建成功: {result['inserted_count']} 条规则已插入")
    except Exception as e:
        print(f"知识库重建失败: {e}", file=sys.stderr)
        sys.exit(1)
