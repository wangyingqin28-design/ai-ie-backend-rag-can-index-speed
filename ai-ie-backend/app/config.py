# 配置文件

from pathlib import Path
from dotenv import load_dotenv
import os
from pydantic import Field
from typing import Annotated, Any, AsyncGenerator, Dict, Generator, Optional

from pydantic_settings import BaseSettings

from app.vectorstore.connector import VectorStoreConnectorAdaptor
import json
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, ".env"), verbose=True)

class Config(BaseSettings):
    # Debug mode
    debug: bool = Field(False, alias="DEBUG")

    # mssql atomic fields
    db_host: str = Field("yulith", alias="DB_HOST")
    db_port: int = Field(1433, alias="DB_PORT")
    db_db: str = Field("master", alias="DB_NAME")
    db_user: str = Field("sa", alias="DB_USER")
    db_password: str = Field("sa", alias="DB_PASSWORD")
    db_driver: str = Field("ODBC Driver 17 for SQL Server", alias="DB_DRIVER")

    # Redis atomic fields
    redis_host: str = Field("yulith", alias="REDIS_HOST")
    redis_port: int = Field(6379, alias="REDIS_PORT")
    redis_user: str = Field("default", alias="REDIS_USER")
    redis_password: str = Field("password", alias="REDIS_PASSWORD")

    # Database
    database_url: Optional[str] = Field(None, alias="DATABASE_URL")

    # Database connection pool settings
    db_pool_size: int = Field(10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(10, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(60, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(3600, alias="DB_POOL_RECYCLE")
    db_pool_pre_ping: bool = Field(True, alias="DB_POOL_PRE_PING")

    # Celery
    celery_broker_url: Optional[str] = Field(None, alias="CELERY_BROKER_URL")
    celery_result_backend: Optional[str] = Field(None, alias="CELERY_RESULT_BACKEND")
    celery_beat_scheduler: str = "django_celery_beat.schedulers:DatabaseScheduler"
    celery_worker_send_task_events: bool = True
    celery_task_send_sent_event: bool = True
    celery_task_track_started: bool = True

    # Vector DB
    vector_db_type: str = Field("qdrant", alias="VECTOR_DB_TYPE")
    vector_db_context: str = Field(
        '{"url":"http://127.0.0.1", "port":6333, "distance":"Cosine"}', alias="VECTOR_DB_CONTEXT"
    )
    qdrant_collection: str = Field("sql_rag_qa_chunks_v1", alias="QDRANT_COLLECTION")
    EDITOR_BASE_URL: str =Field("")

    # Memory backend
    memory_redis_url: Optional[str] = Field(None, alias="MEMORY_REDIS_URL")

    # Embedding
    embedding_max_chunks_in_batch: int = Field(10, alias="EMBEDDING_MAX_CHUNKS_IN_BATCH")
    embedding_service_url: str = Field("https://api.siliconflow.cn/v1", alias="EMBEDDING_SERVICE_URL")
    embedding_model_tags: str = Field('{"multimodal": false}', alias="EMBEDDING_MODEL_TAGS")
    embedding_model: str = Field('BAAI/bge-m3', alias="EMBEDDING_MODEL")
    embedding_model_service_provider: str = Field('siliconflow', alias="EMBEDDING_MODEL_SERVICE_PROVIDER")
    embedding_custom_llm_provider: str = Field('openai', alias="EMBEDDING_CUSTOM_LLM_PROVIDER")
    embedding_service_api_key: str = Field('', alias="EMBEDDING_SERVICE_API_KEY")
    embedding_dimensions: Optional[int] = Field(None, alias="EMBEDDING_DIMENSIONS")

    #models
    model_llm: str =Field("Pro/deepseek-ai/DeepSeek-V3.1-Terminus", alias="MODEL_LLM")
    model_embedding: str = Field("Qwen/Qwen3-Embedding-4B", alias="MODEL_EMBED")

    #vlm
    LLM_MODEL:str =Field("deepseek-ai/DeepSeek-V3.1-Terminus",alias="VLM_LLM_MODEL")
    VISION_MODEL:str = Field("Qwen/Qwen3.5-397B-A17B",alias="VISION_MODEL")
    EMBEDDING_MODEL:str = Field("Qwen/Qwen3-VL-Embedding-8B",alias="EMBEDDING_MODEL_VLM")
    AUDIO_TRANSCRIPTION_MODEL:str =Field("FunAudioLLM/SenseVoiceSmall",alias="AUDIO_TRANSCRIPTION_MODEL")


    def __init__(self, **kwargs):
        super().__init__(**kwargs)    

        # DATABASE_URL
        if not self.database_url:
            self.database_url = (
                f"mssql+pyodbc://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_db}"
                f"?driver={self.db_driver.replace(' ', '+')}&"
                "trusted_connection=no&"
                "encrypt=no"
            )

        # CELERY_BROKER_URL
        if not self.celery_broker_url:
            self.celery_broker_url = (
                f"redis://{self.redis_user}:{self.redis_password}@{self.redis_host}:{self.redis_port}/2"
            )

        # CELERY_RESULT_BACKEND
        if not self.celery_result_backend:
            # self.celery_result_backend = self.celery_broker_url
            self.celery_result_backend = (
                f"redis://{self.redis_user}:{self.redis_password}@{self.redis_host}:{self.redis_port}/3"
            )            

        # MEMORY_REDIS_URL
        if not self.memory_redis_url:
            self.memory_redis_url = (
                f"redis://{self.redis_user}:{self.redis_password}@{self.redis_host}:{self.redis_port}/1"
            )     

def get_sync_database_url(url: str):
    """Convert async database URL to sync version for celery"""
    if url.startswith("mssql+aioodbc://"):
        return url.replace("mssql+aioodbc://", "mssql+pyodbc://")
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://")
    if url.startswith("postgres+asyncpg://"):
        return url.replace("postgres+asyncpg://", "postgres://")
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://")
    return url


def get_async_database_url(url: str):
    """Convert sync database URL to async version"""
    if url.startswith("mssql+pyodbc://"):
        return url.replace("mssql+pyodbc://", "mssql+aioodbc://")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://")
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://")
    return url


def new_async_engine():
    return create_async_engine(
        get_async_database_url(settings.database_url),
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=settings.db_pool_pre_ping,
    )


def new_sync_engine():
    return create_engine(
        get_sync_database_url(settings.database_url),
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=settings.db_pool_pre_ping,
    )


settings = Config()

# Database connection pool settings from configuration
async_engine = new_async_engine()
sync_engine = new_sync_engine()


async def get_async_session(engine=None) -> AsyncGenerator[AsyncSession, None]:
    if engine is None:
        engine = async_engine
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


def get_sync_session(engine=None) -> Generator[Session, None, None]:
    if engine is None:
        engine = sync_engine
    sync_session = sessionmaker(engine)
    with sync_session() as session:
        yield session


def get_vector_db_connector(collection: str) -> VectorStoreConnectorAdaptor:
    # todo: specify the collection for different user
    # one person one collection
    ctx = json.loads(settings.vector_db_context)
    ctx["collection"] = collection
    return VectorStoreConnectorAdaptor(settings.vector_db_type, ctx=ctx)   


