# bm25_index.py
import os

from llama_index.core import VectorStoreIndex, StorageContext, SimpleDirectoryReader, Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import exceptions as qdrant_exceptions
# 全局配置
BASE_DATA_PATH = "D:\\getsoftAI\\rag\\ai-ie-backend\\app\\services\\rag\\"
API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
BASE_URL = "https://api.siliconflow.cn/v1"
#配置huggingface镜像网
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

def build_index(folder_name: str,collection_name: str):
    """
    构建混合索引 (BM25 + Vector)
    """
    # 1. 拼接完整路径
    data_dir = BASE_DATA_PATH + folder_name
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"目录不存在，已自动创建: {data_dir}")
    else:
        print(f"目录已存在，正在读取: {data_dir}")

    # 2. 初始化 Settings (Embedding 模型)
    Settings.embed_model = OpenAIEmbedding(
        model_name="Qwen/Qwen3-Embedding-4B",
        api_key=API_KEY,
        api_base=BASE_URL,
        embed_batch_size=16,
        dimensions=1024,
    )
    Settings.chunk_size = 512

    # 3. 加载文档
    try:
        documents = SimpleDirectoryReader(data_dir).load_data()
    except Exception as e:
        raise RuntimeError(f"无法读取目录 {data_dir}: {str(e)}")

    # 4. 初始化向量库 (Qdrant)
    client = QdrantClient(host="yulith", port=6333)
    aclient = AsyncQdrantClient(host="yulith", port=6333)
    # 5. 创建集合
    vector_store = QdrantVectorStore(
        collection_name=collection_name,
        client=client,
        aclient=aclient,
        enable_hybrid=True,
        fastembed_sparse_model="Qdrant/bm25",
        batch_size=20,
    )

    # 5. 构建索引
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context
    )

    print(f"索引构建完成，共处理 {len(documents)} 个文档")
    return index
