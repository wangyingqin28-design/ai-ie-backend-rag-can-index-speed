import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from .backends.base import IChatBackend
from .config import AIConfig
from .exceptions import MemoryAIError
from .prompts import DEFAULT_SYSTEM_PROMPT
from .repositories.base import IChatRepository, SessionSummary


class ChatAI:
    """有记忆的聊天 AI，通过注入 backend 决定检索/生成策略。

    构造：
        ChatAI(
            config=AIConfig(...),
            repository=SQLAlchemyChatRepository(...),
            backend=LlamaIndexBackend(...) 或 LightRAGBackend(...) 或自定义,
        )

    职责分工：
        - memory_ai 管：会话 CRUD、历史持久化、tenant 隔离
        - backend 管：prompt 构造、检索、LLM 调用、生成回复

    与旧版的关键区别：
        - chat() / stream_chat() 是异步方法（LightRAG 要求 async）
        - 不再在内存里长期持有 ChatMemoryBuffer；历史每次 chat 时按需从 DB 加载
    """

    def __init__(
        self,
        config: AIConfig,
        repository: IChatRepository,
        backend: IChatBackend,
    ):
        self.config = config
        self.repository = repository
        self._backend = backend
        self._sessions: Dict[str, Dict[str, Any]] = {}

    @property
    def _system_prompt(self) -> str:
        return self.config.system_prompt or DEFAULT_SYSTEM_PROMPT

    def get_or_create_session(
        self,
        *,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取现有会话或创建新会话。

        三段查找：进程内缓存 → 持久化层恢复元数据 → 新建。
        与旧版不同：不再构建引擎/加载历史到内存；历史每次 chat 时按需加载。
        """
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            session["last_active"] = time.time()
            return session

        if session_id and self.repository.session_exists(
            session_id=session_id, tenant_id=tenant_id
        ):
            metadata = self.repository.get_session_metadata(
                session_id=session_id, tenant_id=tenant_id
            )
            session = {
                "session_id": session_id,
                "tenant_id": tenant_id,
                "title": (metadata.title if metadata and metadata.title
                          else self.config.default_session_title),
                "created_at": metadata.created_at if metadata else time.time(),
                "last_active": time.time(),
            }
            self._sessions[session_id] = session
            return session

        new_id = session_id or str(uuid.uuid4())
        session = {
            "session_id": new_id,
            "tenant_id": tenant_id,
            "title": self.config.default_session_title,
            "created_at": time.time(),
            "last_active": time.time(),
        }
        self._sessions[new_id] = session
        return session

    async def chat(
        self,
        *,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        message: str,
        save: bool = True,
    ) -> str:
        """异步聊天。返回助手回复字符串，自动落库。"""
        session = self.get_or_create_session(
            session_id=session_id, tenant_id=tenant_id
        )
        sid = session["session_id"]

        history = self.repository.load_history(
            session_id=sid, tenant_id=tenant_id
        )

        try:
            reply = await self._backend.chat(
                query=message,
                history=history,
                system_prompt=self._system_prompt,
            )
        except MemoryAIError:
            raise
        except Exception as e:
            raise MemoryAIError("对话后端调用失败", details=str(e))

        reply = reply or ""
        session["last_active"] = time.time()

        if save:
            self._save_round(session, tenant_id, message, reply)

        return reply

    async def stream_chat(
        self,
        *,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        message: str,
        save: bool = True,
    ) -> AsyncIterator[str]:
        """流式聊天。yield 增量文本，结束后整段落库。"""
        session = self.get_or_create_session(
            session_id=session_id, tenant_id=tenant_id
        )
        sid = session["session_id"]

        history = self.repository.load_history(
            session_id=sid, tenant_id=tenant_id
        )

        chunks: List[str] = []
        try:
            async for token in self._backend.stream_chat(
                query=message,
                history=history,
                system_prompt=self._system_prompt,
            ):
                chunks.append(token)
                yield token
        except MemoryAIError:
            raise
        except Exception as e:
            raise MemoryAIError("对话后端流式调用失败", details=str(e))

        full_reply = "".join(chunks)
        session["last_active"] = time.time()

        if save:
            self._save_round(session, tenant_id, message, full_reply)

    def _save_round(
        self,
        session: Dict[str, Any],
        tenant_id: Optional[str],
        user_message: str,
        assistant_reply: str,
    ) -> None:
        sid = session["session_id"]
        title = session.get("title")
        self.repository.save_message(
            session_id=sid,
            role="user",
            content=user_message,
            tenant_id=tenant_id,
            title=title,
        )
        self.repository.save_message(
            session_id=sid,
            role="assistant",
            content=assistant_reply,
            tenant_id=tenant_id,
            title=title,
        )

    def list_sessions(
        self,
        *,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[SessionSummary]:
        return self.repository.list_sessions(tenant_id=tenant_id, limit=limit)

    def delete_session(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        self._sessions.pop(session_id, None)
        return self.repository.delete_session(
            session_id=session_id, tenant_id=tenant_id
        )

    def update_session_title(
        self,
        *,
        session_id: str,
        new_title: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        if session_id in self._sessions:
            self._sessions[session_id]["title"] = new_title
        return self.repository.update_session_title(
            session_id=session_id,
            new_title=new_title,
            tenant_id=tenant_id,
        )

    def clear_cache(self, session_id: Optional[str] = None) -> None:
        """清除进程内会话缓存（不影响持久化数据）。"""
        if session_id is None:
            self._sessions.clear()
        else:
            self._sessions.pop(session_id, None)
