import os
from llama_index.vector_stores.qdrant.utils import fastembed_sparse_encoder
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_ENDPOINT"] = "https://hf-mirror.com"
from typing import Any, Iterable
from app.config import Config
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


config = Config()

QDRANT_URL = "http://yulith:6333/"
DEFAULT_COLLECTION_NAME = "vlmcopy_default"
SPARSE_MODEL = "Qdrant/bm25"
BM25_MODEL_DIR = "D:/huangjing/Llamalndex/models"

def configure_embedding() -> None:
    """
    只配置 embedding，不配置 LLM。
    当前文件只负责构建索引，不负责问答。
    """
    Settings.embed_model = OpenAILikeEmbedding(
        model_name=config.EMBEDDING_MODEL,
        api_base=config.embedding_service_url,
        api_key=config.embedding_service_api_key,
        dimensions=1024,
        truncate_dim=1024,
    )


def build_qdrant_vector_store(
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> QdrantVectorStore:
    """
    构建 Qdrant 混合向量库。
    enable_hybrid=True 表示同时写入 dense 向量和 sparse 向量。
    fastembed_sparse_model="Qdrant/bm25" 表示 sparse 部分使用 BM25。
    """
    client = QdrantClient(url=QDRANT_URL)
    #本地模型导入
    sparse_encoder = fastembed_sparse_encoder(
        model_name=SPARSE_MODEL,
        cache_dir=BM25_MODEL_DIR,
    )
    return QdrantVectorStore(
        collection_name=collection_name,
        client=client,
        enable_hybrid=True,
        sparse_doc_fn=sparse_encoder,
        sparse_query_fn=sparse_encoder,
    )


def build_documents_from_items(
    items: Iterable[dict[str, Any]],
) -> list[Document]:
    """
    将解析后的数据转换为 LlamaIndex Document。
    markdown / text 是真正会被向量化的内容。
    metadata 会写入 Qdrant payload。
    """
    documents = []

    for item in items:
        text = item.get("markdown") or item.get("text") or ""

        if not text.strip():
            continue

        documents.append(
            Document(
                text=text,
                metadata={
                    "kb_id": item.get("kb_id", "default"),
                    "file_id": item.get("file_id", ""),
                    "file_path": item.get("file_path", ""),
                    "file_name": item.get("file_name", ""),
                    "file_type": item.get("file_type", ""),
                    "engine": item.get("engine", ""),
                    "mode": item.get("mode", ""),
                },
            )
        )

    return documents


def upsert_items_to_qdrant(
    items: Iterable[dict[str, Any]],
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> dict[str, Any]:
    """
    写入 Qdrant。
    这里只负责入库，不做查询。
    """
    configure_embedding()

    vector_store = build_qdrant_vector_store(
        collection_name=collection_name,
    )

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
    )

    documents = build_documents_from_items(items)

    if not documents:
        raise ValueError("没有可写入向量库的文本内容")

    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
    )

    return {
        "success": True,
        "collection_name": collection_name,
        "indexed_count": len(documents),
        "qdrant_url": QDRANT_URL,
        "hybrid": True,
        "sparse_model": SPARSE_MODEL,
    }