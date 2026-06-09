from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ChatRecord:
    role: str
    content: str
    timestamp: datetime


@dataclass
class SessionMetadata:
    session_id: str
    title: str
    created_at: float
    last_active: float


@dataclass
class SessionSummary:
    session_id: str
    title: str
    created_at: float
    last_active: float
    message_count: int


class IChatRepository(ABC):
    """聊天持久化抽象接口。

    新项目可基于 Redis / Postgres / MongoDB / 内存等任意后端实现，
    只需继承本类并实现以下方法。所有方法的参数均为 keyword-only，
    避免位置参数误用。
    """

    @abstractmethod
    def save_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        tenant_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool: ...

    @abstractmethod
    def load_history(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[ChatRecord]: ...

    @abstractmethod
    def session_exists(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool: ...

    @abstractmethod
    def get_session_metadata(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[SessionMetadata]: ...

    @abstractmethod
    def list_sessions(
        self,
        *,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[SessionSummary]: ...

    @abstractmethod
    def delete_session(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool: ...

    @abstractmethod
    def update_session_title(
        self,
        *,
        session_id: str,
        new_title: str,
        tenant_id: Optional[str] = None,
    ) -> bool: ...
