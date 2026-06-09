from typing import List, Optional

from app.ai.repositories.redis_cache import RedisChatMemoryCache
from app.ai.repositories.base import IChatRepository
from app.ai.repositories.schemas import ChatRecord, SessionMetadata, SessionSummary


class HybridChatRepository(IChatRepository):
    """Repository with Redis short-term cache + DB long-term storage."""

    def __init__(
        self,
        *,
        db_repository: IChatRepository,
        cache: RedisChatMemoryCache,
    ):
        self.db = db_repository
        self.cache = cache

    def save_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        tenant_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool:
        saved = self.db.save_message(
            session_id=session_id,
            role=role,
            content=content,
            tenant_id=tenant_id,
            title=title,
        )

        if saved:
            self.cache.append_message(
                session_id=session_id,
                role=role,
                content=content,
                tenant_id=tenant_id,
            )

        return saved

    def load_history(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[ChatRecord]:
        cached = self.cache.load_history(
            session_id=session_id,
            tenant_id=tenant_id,
        )

        if cached:
            return cached

        history = self.db.load_history(
            session_id=session_id,
            tenant_id=tenant_id,
        )

        if history:
            self.cache.seed_history(
                session_id=session_id,
                tenant_id=tenant_id,
                history=history,
            )

        return history

    def session_exists(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        return self.db.session_exists(
            session_id=session_id,
            tenant_id=tenant_id,
        )

    def get_session_metadata(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[SessionMetadata]:
        return self.db.get_session_metadata(
            session_id=session_id,
            tenant_id=tenant_id,
        )

    def list_sessions(
        self,
        *,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[SessionSummary]:
        return self.db.list_sessions(
            tenant_id=tenant_id,
            limit=limit,
        )

    def delete_session(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        deleted = self.db.delete_session(
            session_id=session_id,
            tenant_id=tenant_id,
        )

        if deleted:
            self.cache.delete_session(
                session_id=session_id,
                tenant_id=tenant_id,
            )

        return deleted

    def update_session_title(
        self,
        *,
        session_id: str,
        new_title: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        return self.db.update_session_title(
            session_id=session_id,
            new_title=new_title,
            tenant_id=tenant_id,
        )