"""LightRAG 单例工厂。应用启动时调用 init_lightrag() 一次。"""
import asyncio
import os
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

from lightrag import LightRAG
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.utils import  wrap_embedding_func_with_attrs
from app.config import settings

_rag_instance: Optional[LightRAG] = None
_init_lock = asyncio.Lock()

WORKING_DIR = Path("./lightrag_workdir")
EMBEDDING_DIM = 1024


#自定义大语言模型函数
async def llm_model_func(
    prompt, system_prompt=None, history_messages=[], keyword_extraction=False, **kwargs
) -> str:
    return await openai_complete_if_cache(
        settings.model_llm,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        api_key=settings.embedding_service_api_key,
        base_url=settings.embedding_service_url,
        **kwargs,
    )


#自定义嵌入函数
@wrap_embedding_func_with_attrs(embedding_dim=2560, max_token_size=8192, model_name=os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-4B"))
async def embedding_func(texts: list[str]) -> np.ndarray:
    return await openai_embed.func(
        texts,
        model="Qwen/Qwen3-Embedding-4B",
        api_key=settings.embedding_service_api_key,
        base_url=settings.embedding_service_url,
    )


async def init_lightrag() -> LightRAG:
    """幂等初始化：第一次调用真初始化，后续调用直接返回单例。"""
    global _rag_instance
    if _rag_instance is not None:
        return _rag_instance

    async with _init_lock:
        if _rag_instance is not None:
            return _rag_instance

        WORKING_DIR.mkdir(exist_ok=True)

        rag = LightRAG(
            working_dir=str(WORKING_DIR),
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
            # llm_model_name=settings.model_llm,
            # llm_model_max_async=4,       # 并发 LLM 调用数，按 API 限额调
            # # 默认存储 = NetworkX(图)+NanoVectorDB(向量)+JsonKV(键值)
            # # 文件存储，开发足够；生产换 Neo4JStorage / QdrantVectorDBStorage
            # chunk_token_size=1200,
            # chunk_overlap_token_size=100,
        )

        await rag.initialize_storages()
        await initialize_pipeline_status()

        _rag_instance = rag
        logger.info(f"LightRAG 初始化完成 | workdir={WORKING_DIR}")
        return rag


async def get_lightrag() -> LightRAG:
    """供 FastAPI 依赖注入使用。"""
    return await init_lightrag()
