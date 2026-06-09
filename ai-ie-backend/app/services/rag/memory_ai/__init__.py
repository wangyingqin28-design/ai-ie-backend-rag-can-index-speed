"""memory_ai —— 有持久化记忆的可插拔后端聊天 AI 模块。

公开 API:
    ChatAI                       核心入口类（编排层）
    AIConfig                     配置 dataclass
    MemoryAIError                模块统一异常
    DEFAULT_SYSTEM_PROMPT        默认系统提示词

    IChatBackend                 对话后端抽象接口（决定检索/生成策略）
    LlamaIndexBackend            基于 llama_index 的后端（纯聊天 或 向量 RAG）
    LightRAGBackend              基于 LightRAG 的后端（知识图谱 RAG）

    IChatRepository              持久化抽象接口（自定义后端时实现它）
    SQLAlchemyChatRepository     默认 SQLAlchemy 实现
    Base, MemoryAIMessage        ORM 基类和消息表模型（用于建表）
    ChatRecord, SessionMetadata, SessionSummary    数据传输对象

最小用法示例（纯聊天）：
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.services.rag.memory_ai import (
        ChatAI, AIConfig, SQLAlchemyChatRepository, Base,
        LlamaIndexBackend,
    )
    from app.services.rag.memory_ai.llm import build_llm

    engine = create_engine("sqlite:///./memory_ai.db")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    config = AIConfig(model="...", api_key="...", base_url="...")
    ai = ChatAI(
        config=config,
        repository=SQLAlchemyChatRepository(session_factory=SessionLocal),
        backend=LlamaIndexBackend(llm=build_llm(config)),
    )
    reply = asyncio.run(ai.chat(tenant_id="user_001", message="你好"))

切换到 LightRAG（知识图谱）：
    from app.services.rag.memory_ai import LightRAGBackend
    # rag = await init_lightrag()  # 见 LightRAGBackend 文档
    ai = ChatAI(
        config=config,
        repository=SQLAlchemyChatRepository(session_factory=SessionLocal),
        backend=LightRAGBackend(rag=rag, mode="mix"),
    )
"""

from .backends import IChatBackend, LightRAGBackend, LlamaIndexBackend
from .chat_ai import ChatAI
from .config import AIConfig
from .exceptions import MemoryAIError
from .prompts import DEFAULT_SYSTEM_PROMPT
from .repositories import (
    Base,
    ChatRecord,
    IChatRepository,
    MemoryAIMessage,
    SessionMetadata,
    SessionSummary,
    SQLAlchemyChatRepository,
)

__all__ = [
    "ChatAI",
    "AIConfig",
    "MemoryAIError",
    "DEFAULT_SYSTEM_PROMPT",
    "IChatBackend",
    "LlamaIndexBackend",
    "LightRAGBackend",
    "IChatRepository",
    "ChatRecord",
    "SessionMetadata",
    "SessionSummary",
    "Base",
    "MemoryAIMessage",
    "SQLAlchemyChatRepository",
]
