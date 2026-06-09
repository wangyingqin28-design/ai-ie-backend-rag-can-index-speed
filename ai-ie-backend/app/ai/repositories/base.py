from abc import ABC, abstractmethod
from typing import List, Optional
from app.ai.repositories.schemas import ChatRecord, SessionSummary,SessionMetadata

class IChatRepository(ABC):
    """Persistence interface for chat sessions and messages."""

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