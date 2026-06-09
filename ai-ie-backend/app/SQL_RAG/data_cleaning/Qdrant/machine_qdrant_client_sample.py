# -*- coding: utf-8 -*-
"""其他机台连接当前服务器 Qdrant collection 的读取和语义查询样例。"""

# 修改日期：2026-06-01 17:52:00。
# 修改理由：给其他机台提供最小可执行样例，验证其能连接服务器 Qdrant 并读取/查询已同步的 QA 向量库。

# 导入 argparse，用于接收服务器地址、collection 和查询文本。
import argparse
# 导入 json，用于格式化输出测试结果。
import json
# 导入 os，用于读取环境变量。
import os
# 导入 Path，用于显式定位项目 .env。
from pathlib import Path

# 导入 OpenAI 官方 SDK，用同一 embedding 模型把用户问题转成查询向量。
from openai import OpenAI
# 导入 dotenv，用于读取本机 .env。
from dotenv import load_dotenv
# 导入 Qdrant 官方 Python 客户端。
from qdrant_client import QdrantClient


# 定义当前脚本目录。
CURRENT_DIR = Path(__file__).resolve().parent
# 2026-06-02 10:06:01 修改：别人机台样例跟随 SQL_RAG 独立后端配置，不再读取外层 ai-ie-backend/.env。
SQL_RAG_DIR = CURRENT_DIR.parents[1]
# 2026-06-02 10:06:01 修改：固定读取 SQL_RAG/.env，保证 collection、embedding 维度和同步脚本一致。
ENV_PATH = SQL_RAG_DIR / ".env"


def load_project_env() -> None:
    # 如果项目 .env 存在，就显式加载它。
    if ENV_PATH.exists():
        # override=True 用来确保脚本读取项目最新配置。
        load_dotenv(ENV_PATH, override=True)


def parse_args() -> argparse.Namespace:
    # 创建命令行解析器。
    parser = argparse.ArgumentParser(description="其他机台连接 Qdrant 并查询 sql_rag_qa_chunks_v1 的样例。")
    # 添加 Qdrant URL 参数，其他机台应传入 http://服务器IP:6333。
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"))
    # 添加 collection 参数。
    parser.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION", "sql_rag_qa_chunks_v1"))
    # 添加查询文本参数。
    parser.add_argument("--query", default="补料单怎么操作？")
    # 添加返回条数参数。
    parser.add_argument("--top-k", type=int, default=5)
    # 添加 embedding 服务地址参数。
    parser.add_argument("--embedding-api-base", default=os.getenv("EMBEDDING_SERVICE_URL", "https://api.siliconflow.cn/v1"))
    # 添加 embedding API key 参数。
    parser.add_argument("--embedding-api-key", default=os.getenv("EMBEDDING_SERVICE_API_KEY", ""))
    # 添加 embedding 模型参数。
    parser.add_argument("--embedding-model", default=os.getenv("MODEL_EMBED", "Qwen/Qwen3-Embedding-0.6B"))
    # 添加 embedding 维度参数。
    parser.add_argument("--embedding-dimension", type=int, default=int(os.getenv("EMBEDDING_DIMENSIONS", "1024")))
    # 返回解析结果。
    return parser.parse_args()


def embed_query(args: argparse.Namespace) -> list[float]:
    # 没有 embedding key 时无法做语义查询。
    if not args.embedding_api_key:
        # 抛出明确错误。
        raise ValueError("缺少 EMBEDDING_SERVICE_API_KEY，不能生成查询向量。")
    # 创建 OpenAI-compatible embedding 客户端。
    embedding_client = OpenAI(api_key=args.embedding_api_key, base_url=args.embedding_api_base)
    # 调用 embedding API。
    response = embedding_client.embeddings.create(
        # 指定模型名。
        model=args.embedding_model,
        # 指定查询文本。
        input=[args.query],
        # 指定维度，必须和 Qdrant collection 一致。
        dimensions=args.embedding_dimension,
    )
    # 返回第一条 embedding。
    return response.data[0].embedding


def main() -> None:
    # 读取项目根目录 .env。
    load_project_env()
    # 解析命令行参数。
    args = parse_args()
    # 创建 Qdrant 官方客户端。
    # 2026-06-06 11:30:19 修改原因：禁用系统代理环境，避免本机 no_proxy IPv6 CIDR 影响局域网或本地 Qdrant 连接。
    client = QdrantClient(url=args.qdrant_url, trust_env=False)
    # 获取 collection 点数。
    count = client.count(collection_name=args.collection, exact=True).count
    # 生成查询向量。
    query_vector = embed_query(args)
    # 调用 Qdrant 官方 query_points API 查询。
    result = client.query_points(
        # 指定 collection。
        collection_name=args.collection,
        # 传入查询向量。
        query=query_vector,
        # 指定 top-k。
        limit=args.top_k,
        # 返回 payload。
        with_payload=True,
        # 不返回向量。
        with_vectors=False,
    )
    # 构造输出。
    output = {
        # 输出 Qdrant URL。
        "qdrant_url": args.qdrant_url,
        # 输出 collection。
        "collection": args.collection,
        # 输出 collection 点数。
        "point_count": count,
        # 输出查询文本。
        "query": args.query,
        # 输出命中结果。
        "hits": [
            {
                # 输出相似度得分。
                "score": point.score,
                # 输出 chunk_id。
                "chunk_id": point.payload.get("chunk_id"),
                # 输出文档 ID。
                "document_id": point.payload.get("document_id"),
                # 输出场景。
                "scene": point.payload.get("scene"),
                # 输出问题。
                "question": point.payload.get("question"),
                # 输出答案。
                "answer": point.payload.get("answer"),
            }
            # 遍历 Qdrant 命中点。
            for point in result.points
        ],
    }
    # 打印 JSON 结果。
    print(json.dumps(output, ensure_ascii=False, indent=2))


# 作为脚本运行时进入 main。
if __name__ == "__main__":
    # 调用 main。
    main()
