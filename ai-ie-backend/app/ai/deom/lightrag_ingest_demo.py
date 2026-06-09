import asyncio
from pathlib import Path

from app.ai import AIConfig
from app.ai.rag.lightrag_factory import initialize_lightrag
from app.ai.rag.ingest import ingest_markdown_dir
from app.config import Config


async def init_lightrag():
    configs = Config()
    config = AIConfig(
        model="Pro/zai-org/GLM-5.1",
        api_key=configs.embedding_service_api_key,
        base_url=configs.embedding_service_url,

        embedding_model="BAAI/bge-m3",
        embedding_dim=1024,
        embedding_api_key=configs.embedding_service_api_key,
        embedding_base_url=configs.embedding_service_url,

        rerank_model="BAAI/bge-reranker-v2-m3",
        rerank_api_key=configs.embedding_service_api_key,
        rerank_base_url=configs.embedding_service_url,
    )

    rag = await initialize_lightrag(
        config,
        working_dir=Path("./rag_storage"),
        enable_rerank=True,
    )

    return rag


async def main():
    rag = await init_lightrag()

    try:
        count = await ingest_markdown_dir(rag, Path("D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data"))
        print(f"Ingested {count} markdown files.")
    finally:
        await rag.finalize_storages()


if __name__ == "__main__":
    asyncio.run(main())