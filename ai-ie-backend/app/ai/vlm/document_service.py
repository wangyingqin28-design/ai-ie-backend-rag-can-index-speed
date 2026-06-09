from functools import partial
from pathlib import Path

from raganything import RAGAnything, RAGAnythingConfig
from lightrag.llm.openai import openai_embed
from lightrag.utils import EmbeddingFunc

from app.config import Config
from .llm_client import llm_model_func, vision_model_func

config = Config()
async def build_rag():
    config = RAGAnythingConfig(
        working_dir="./rag_storage",
        parser="docling",
        parse_method="auto",
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
    )

    embedding_func = EmbeddingFunc(
        embedding_dim=3072,
        max_token_size=8192,
        func=partial(
            openai_embed.func,
            model=config.EMBEDDING_MODEL,
            api_key=config.embedding_service_api_key,
            base_url=config.embedding_service_url,
        ),
    )

    return RAGAnything(
        config=config,
        llm_model_func=llm_model_func,
        vision_model_func=vision_model_func,
        embedding_func=embedding_func,
    )


async def process_document_to_rag(
    file_path: str,
    parse_method: str = "auto",
    query: str = "请总结这个文档的主要内容，如果有图片、表格、公式表达的信息，请说明。",
):
    rag = await build_rag()

    await rag.process_document_complete(
        file_path=file_path,
        output_dir="./output",
        parse_method=parse_method,
    )

    return await rag.aquery(
        query,
        mode="hybrid",
    )


async def process_text_file(file_path: str):
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    prompt = f"""
请总结下面这个文本文件的主要内容：

{content}
"""

    return await llm_model_func(prompt)