import asyncio
import os
from pathlib import Path

from lightrag import QueryParam
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai import AIConfig
from app.ai.memory import ChatAI
from app.ai.repositories.sqlalchemy_repo import SQLAlchemyChatRepository
from app.ai.repositories.orm_model import Base
from app.ai.rag import ContextLightRAGBackend, initialize_lightrag
from app.utils.database import SessionLocal, engine
from app.config import Config

async def main():
    working_dir = Path("./rag_storage")
    # data_dir = Path("./data/rag")
    config = AIConfig(
        model="Pro/zai-org/GLM-5.1",
        api_key=os.getenv("SILICONFLOW_API_KEY", ""),
        base_url="https://api.siliconflow.cn/v1",
        embedding_model="BAAI/bge-m3",
        embedding_dim=1024,
        rerank_model="BAAI/bge-reranker-v2-m3",
        rerank_base_url="https://api.siliconflow.cn/v1/rerank",
        system_prompt="你是一位电商客服。必须严格根据检索到的知识图谱内容回答。",
    )

    rag = await initialize_lightrag(config, working_dir=working_dir, enable_rerank=True)
    Base.metadata.create_all(engine)
    # First run only: put markdown files into ./data/rag and uncomment this line.
    # await ingest_markdown_dir(rag, data_dir)
    ai = ChatAI(
        config=config,
        repository=SQLAlchemyChatRepository(session_factory=SessionLocal),
        backend=ContextLightRAGBackend(
            rag=rag,
            config=config,
            working_dir=str(working_dir),
            query_param=QueryParam(
                mode="hybrid",
                enable_rerank=True,
                top_k=20,
                chunk_top_k=5,
                response_type="Single Paragraph",
            ),
            clear_cache=True,
        ),
    )

    try:
        reply = await ai.chat(
            tenant_id="demo_user",
            message="蓝色的裙子有没有大号的？",
        )
        print(reply)
    finally:
        await rag.finalize_storages()


if __name__ == "__main__":
    asyncio.run(main())
