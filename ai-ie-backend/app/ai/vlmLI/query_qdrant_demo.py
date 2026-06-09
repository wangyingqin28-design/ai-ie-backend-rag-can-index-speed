import os

from app.config import Config

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.vector_stores.types import VectorStoreQueryMode
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
from llama_index.llms.openai_like import OpenAILike
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.vector_stores.qdrant.utils import fastembed_sparse_encoder
from qdrant_client import QdrantClient
from app.ai.reank.reank import SiliconFlowRerank

config = Config()

QDRANT_URL = "http://yulith:6333"
COLLECTION_NAME = "vlmcopy"

SPARSE_MODEL = "Qdrant/bm25"
BM25_MODEL_CACHE_DIR = "D:/huangjing/Llamalndex/models"


def configure_llamaindex():
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
        dimensions=1024,
        truncate_dim=1024,
    )


def query_qdrant(question: str):
    configure_llamaindex()

    client = QdrantClient(url=QDRANT_URL)

    sparse_encoder = fastembed_sparse_encoder(
        model_name=SPARSE_MODEL,
        cache_dir=BM25_MODEL_CACHE_DIR,
    )

    vector_store = QdrantVectorStore(
        collection_name=COLLECTION_NAME,
        client=client,
        enable_hybrid=True,
        sparse_doc_fn=sparse_encoder,
        sparse_query_fn=sparse_encoder,
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
    )
    reranker = SiliconFlowRerank(
        api_key=os.getenv("SILICONFLOW_API_KEY", ""),
        base_url="https://api.siliconflow.cn/v1/rerank",
        top_n=3,
        model="Qwen/Qwen3-Reranker-8B"
    )
    query_engine = index.as_query_engine(
        vector_store_query_mode=VectorStoreQueryMode.HYBRID,
        similarity_top_k=10,
        node_postprocessors=[reranker]
    )

    response = query_engine.query(question)

    print("回答：")
    print(response)

    # print("\n来源：")
    # for node in response.source_nodes:
    #     print("score:", node.score)
    #     print("metadata:", node.node.metadata)
    #     print("text:", node.node.text[:300])
    #     print("-" * 50)


if __name__ == "__main__":
    query_qdrant("本次会议讨论了那些问题")
