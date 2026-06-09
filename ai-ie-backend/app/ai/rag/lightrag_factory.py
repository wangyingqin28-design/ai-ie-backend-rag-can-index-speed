from functools import partial
from pathlib import Path
from typing import Optional

import numpy as np
from lightrag import LightRAG
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.rerank import jina_rerank
from lightrag.utils import setup_logger, wrap_embedding_func_with_attrs

from app.ai.config import AIConfig

setup_logger("lightrag", level="INFO")


def build_lightrag_llm_func(config: AIConfig):
    async def llm_model_func(
        prompt,
        system_prompt=None,
        history_messages=None,
        keyword_extraction=False,
        **kwargs,
    ) -> str:
        return await openai_complete_if_cache(
            config.model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=config.api_key,
            base_url=config.base_url,
            **kwargs,
        )

    return llm_model_func


def build_lightrag_embedding_func(config: AIConfig):
    embedding_api_key = config.embedding_api_key or config.api_key
    embedding_base_url = config.embedding_base_url or config.base_url

    @wrap_embedding_func_with_attrs(
        embedding_dim=config.embedding_dim,
        max_token_size=8192,
        model_name=config.embedding_model,
    )
    async def embedding_func(texts: list[str]) -> np.ndarray:
        return await openai_embed.func(
            texts,
            model=config.embedding_model,
            api_key=embedding_api_key,
            base_url=embedding_base_url,
        )

    return embedding_func


def build_lightrag_rerank_func(config: AIConfig):
    if not config.rerank_model:
        return None

    return partial(
        jina_rerank,
        api_key=config.rerank_api_key or config.api_key,
        model=config.rerank_model,
        base_url=config.rerank_base_url or config.base_url.rstrip("/") + "/rerank",
    )

#初始化
async def initialize_lightrag(
    config: AIConfig,
    *,
    working_dir: str | Path,
    enable_rerank: bool = True,
    chunk_token_size: Optional[int] = None,
    chunk_overlap_token_size: Optional[int] = None,
) -> LightRAG:
    """Initialize LightRAG with explicit LLM, embedding, and rerank functions."""

    workdir = Path(working_dir)
    workdir.mkdir(parents=True, exist_ok=True)

    kwargs = {}
    if chunk_token_size is not None:
        kwargs["chunk_token_size"] = chunk_token_size
    if chunk_overlap_token_size is not None:
        kwargs["chunk_overlap_token_size"] = chunk_overlap_token_size

    rag = LightRAG(
        working_dir=str(workdir),
        llm_model_func=build_lightrag_llm_func(config),
        embedding_func=build_lightrag_embedding_func(config),
        rerank_model_func=build_lightrag_rerank_func(config) if enable_rerank else None,
        **kwargs,
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()
    return rag
