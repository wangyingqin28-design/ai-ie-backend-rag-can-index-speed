from typing import Any, Iterable

from app.config import Config
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
from llama_index.llms.openai_like import OpenAILike

config = Config()


def configure_llamaindex() -> None:
    """配置 LlamaIndex 使用 OpenAI 兼容接口的 LLM 与 Embedding。"""
    # OpenAILike 用于兼容硅基流动这类 OpenAI API 风格的服务。
    # Settings 是 LlamaIndex 的全局配置，后续 VectorStoreIndex 会自动使用。
    Settings.llm = OpenAILike(
        model=config.LLM_MODEL,
        api_base=config.embedding_service_url,
        api_key=config.embedding_service_api_key,
        is_chat_model=True,
    )

    Settings.embed_model = OpenAILikeEmbedding(
        model_name=config.EMBEDDING_MODEL,
        api_base=config.embedding_service_url,
        api_key=config.embedding_service_api_key,
    )


def build_index_from_items(items: Iterable[dict[str, Any]]):
    """把解析后的文件内容转换成 LlamaIndex 文档并建立临时向量索引。"""
    configure_llamaindex()

    documents = []
    for item in items:
        # 文档使用 markdown；文本/图片 OCR 结果使用 text。
        text = item.get("markdown") or item.get("text") or ""
        if not text.strip():
            continue

        documents.append(
            Document(
                text=text,
                metadata={
                    "file_path": item.get("file_path", ""),
                    "file_name": item.get("file_name", ""),
                    "file_type": item.get("file_type", ""),
                    "engine": item.get("engine", ""),
                },
            )
        )

    if not documents:
        # 没有可索引文本时直接报错，便于接口层定位是解析为空还是问答失败。
        raise ValueError("No parsable text content was found for LlamaIndex.")

    return VectorStoreIndex.from_documents(documents)


def query_items_with_llamaindex(
    items: Iterable[dict[str, Any]],
    question: str,
    similarity_top_k: int = 3,
) -> dict[str, Any]:
    """基于一组解析结果进行检索问答。"""
    index = build_index_from_items(items)
    query_engine = index.as_query_engine(
        # similarity_top_k 控制检索时取多少个最相关文本片段。
        similarity_top_k=similarity_top_k,
    )
    response = query_engine.query(question)

    source_nodes = []
    for node in getattr(response, "source_nodes", []) or []:
        # source_nodes 用于运维排查答案来源，也方便前端展示引用片段。
        source_nodes.append({
            "score": getattr(node, "score", None),
            "metadata": dict(getattr(node.node, "metadata", {}) or {}),
            "text": getattr(node.node, "text", ""),
        })

    return {
        "question": question,
        "answer": str(response),
        "source_nodes": source_nodes,
    }
