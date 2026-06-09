# app/services/rag/RAG.py
import logging
import os

import time

# from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from loguru import logger
import uuid
from contextlib import asynccontextmanager
import json
from fastapi import FastAPI,Request
from llama_index.core.chat_engine.types import BaseChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai_like import OpenAILike
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.postprocessor import LongContextReorder

from llama_index.core import VectorStoreIndex, PromptTemplate, Settings, PropertyGraphIndex
from llama_index.core.storage.chat_store import SimpleChatStore
from qdrant_client import QdrantClient, AsyncQdrantClient
from app.services.rag.reank.reank import SiliconFlowRerank
from app.services.rag.qdrant_duqu import CustomQdrantVectorStore
from typing import Optional, Dict, Any, List
from app.services.rag.db_operations import (
    load_session_history,
    check_session_exists,
    get_session_metadata,
    get_recent_sessions,
)
from app.config import settings
from app.utils.exceptions import AppException


# 从配置中获取值
API_KEY = settings.embedding_service_api_key
BASE_URL = settings.embedding_service_url

# 获取模型配置
MODEL = settings.model_llm
MODEL_EMBED = settings.model_embedding
#配置huggingface镜像网
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
# 解析向量数据库配置
vector_db_ctx = json.loads(settings.vector_db_context)
QDRANT_URL = f"{vector_db_ctx['url']}:{vector_db_ctx['port']}"
QDRANT_URL_locahost="http://localhost:6333"
QDRANT_COLLECTION = settings.qdrant_collection
QDRANT_COLLECTION_locahost=settings.qdrant_collection
def init_llm_and_embeddings():
    """初始化 LLM 和嵌入模型"""
    Settings.llm = OpenAILike(
        model=MODEL,
        api_base=BASE_URL,
        api_key=API_KEY,
        context_window=128000,
        is_chat_model=True,
        verbose=True,
        timeout=120.0

    )

    Settings.embed_model = OpenAIEmbedding(
        model_name=MODEL_EMBED,
        api_key=API_KEY,
        api_base=BASE_URL,
        dimensions=1024,
        truncate_dim=1024,
    )
    logger.info("LLM 和嵌入模型初始化完成")

# 全局状态
class GlobalState:
    qdrant_client: Optional[QdrantClient] = None
    vector_index: Optional[VectorStoreIndex] = None
    query_template: Optional[PromptTemplate] = None

# 会话管理类
class PersistentChatManager:
    def __init__(self):
        # 全局聊天存储 - 应用生命周期内缓存活跃会话
        self.global_chat_store = SimpleChatStore()#存放聊天记录
        # 会话元数据缓存 {session_id: {title, created_at, last_active, message_count}}
        self.session_metadata: Dict[str, Dict] = {}#存放列表
        # 会话数据缓存
        self.sessions: Dict[str, Dict] = {}#存放引擎

    def get_or_create_session(self, request: Request,session_id: Optional[str] = None,current_gs_id: Optional[int] = None) -> Dict[str, Any]:
        """获取现有会话或创建新会话，支持从持久化存储恢复"""
        # 1. 如果提供了session_id(不为空)且已在缓存中，直接返回
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session["last_active"] = time.time()
            return session

        # 2. 如果提供了session_id但不在缓存中，尝试从数据库加载
        if session_id and check_session_exists(request,session_id,current_gs_id):
            logger.info(f"从数据库恢复会话: {session_id}")
            metadata = get_session_metadata(request,session_id,current_gs_id)
            if metadata:
                # 加载历史消息
                chat_history = load_session_history(request,session_id,current_gs_id)

                # 创建聊天记忆
                chat_memory = ChatMemoryBuffer.from_defaults(
                    token_limit=6000,
                    chat_store=self.global_chat_store,
                    chat_store_key=session_id,

                )

                # 将历史消息加载到记忆中
                for message in chat_history:
                    chat_memory.put(message)

                # 创建会话数据
                title = metadata["title"]
                session_data = {
                    "session_id": session_id,
                    "query_engine": None,
                    "created_at": metadata["created_at"],
                    "last_active": time.time(),
                    "title": title
                }

                # 更新缓存
                self.sessions[session_id] = session_data
                self.session_metadata[session_id] = {
                    "title": title,
                    "created_at": metadata["created_at"],
                    "last_active": time.time(),
                    "message_count": len(chat_history)
                }
                return session_data

        # 3. 创建全新会话
        new_session_id = str(uuid.uuid4())
        logger.info(f"创建新会话: {new_session_id}")

        # 创建会话数据
        session_data = {
            "session_id": new_session_id,
            "query_engine": None,
            "created_at": time.time(),
            "last_active": time.time(),
            "title": "新对话"
        }

        # 更新缓存
        self.sessions[new_session_id] = session_data#new_session_id作为键
        self.session_metadata[new_session_id] = {
            "title": "新对话",
            "created_at": session_data["created_at"],
            "last_active": session_data["last_active"],
            "message_count": 0
        }

        return session_data

    def initialize_query_engine(self, session_id: str) -> BaseChatEngine:
        #重排序模型
        reank_model = SiliconFlowRerank(
            model="Qwen/Qwen3-Reranker-8B",
            api_key=API_KEY,
            base_url="https://api.siliconflow.cn/v1/rerank",
            top_n=5
        )
        """为指定会话初始化查询引擎"""
        if session_id not in self.sessions:
            raise ValueError(f"会话 {session_id} 不存在")

        session = self.sessions[session_id]
        # reorder=LongContextReorder()

        # 为会话创建专用查询引擎
        query_engine = global_state.vector_index.as_chat_engine(
            context_prompt=global_state.query_template,
            similarity_top_k=20,
            verbose=True,
            sparse_top_k=12,
            vector_store_query_mode="hybrid",
            node_postprocessors=[reank_model],
            memory=ChatMemoryBuffer.from_defaults(
                token_limit=3000,
                chat_store=self.global_chat_store,
                chat_store_key=session_id,
            ),
        )

        session["query_engine"] = query_engine
        return query_engine

def init_qdrant():
    """初始化 Qdrant 连接和向量索引"""
    try:
        client = QdrantClient(url=QDRANT_URL)
        # 检查集合是否存在
        if not client.collection_exists(QDRANT_COLLECTION):
            raise ValueError(f"集合 '{QDRANT_COLLECTION}' 不存在")
        async_client = AsyncQdrantClient(url=QDRANT_URL)
        vector_store = QdrantVectorStore(
            client=client,
            aclient=async_client,
            collection_name=QDRANT_COLLECTION,
            show_progress=False,
            enable_hybrid=True
        )
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        logger.info(f"成功连接到 Qdrant 集合: {QDRANT_COLLECTION}")
        return client, index
    except Exception as e:
        raise AppException(
            code=500,
            details=f"连接 Qdrant 失败: {str(e)}",
            message ="连接 Qdrant 失败"
        )


# def init_qdrant():
#     """初始化 neo4j 连接和向量索引"""
#     try:
#         graph_store = Neo4jPropertyGraphStore(
#             username="neo4j",
#             password="12345678",
#             url="neo4j://localhost:7687"
#
#         )
#          # 构建索引后使用，防止二次构建
#         index = PropertyGraphIndex.from_existing(
#              property_graph_store=graph_store
#          )
#         logger.info(f"成功连接到 Qdrant 集合: {QDRANT_COLLECTION}")
#         return index
#     except Exception as e:
#         raise AppException(
#             code=500,
#             details=f"连接 Qdrant 失败: {str(e)}",
#             message ="连接 Qdrant 失败"
#         )

# 初始化全局对象
global_state = GlobalState()
chat_manager = PersistentChatManager()
