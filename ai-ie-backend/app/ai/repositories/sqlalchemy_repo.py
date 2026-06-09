import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Callable, Iterator, List, Optional

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from ..exceptions import MemoryAIError
from .base import (
    ChatRecord,
    IChatRepository,
    SessionMetadata,
    SessionSummary,
)
from .orm_model import MemoryAIMessage
from app.utils.snowflake_generator import snowflake

class SQLAlchemyChatRepository(IChatRepository):
    """SQLAlchemy implementation for chat history persistence."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @contextmanager
    def _db_scope(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _tenant_filter(tenant_id: Optional[str]):
        if tenant_id is None:
            return MemoryAIMessage.tenant_id.is_(None)
        return MemoryAIMessage.tenant_id == tenant_id

    def save_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        tenant_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool:
        try:
            with self._db_scope() as db:
                time=datetime.now()
                db.add(
                    MemoryAIMessage(
                        id=snowflake.generate_id(),
                        session_id=session_id,
                        tenant_id=tenant_id,
                        role=role,
                        content=content,
                        title=(title.strip()[:255] if title and title.strip() else None),
                        created_at=time,
                        deleted_at=None,
                        deleted_flag=False
                    )
                )
            return True
        except Exception as exc:
            raise MemoryAIError("保存消息失败", details=str(exc))

    def load_history(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[ChatRecord]:
        try:
            with self._db_scope() as db:
                rows = (
                    db.query(MemoryAIMessage)
                    .filter(
                        MemoryAIMessage.session_id == session_id,
                        self._tenant_filter(tenant_id),
                        MemoryAIMessage.deleted_flag==False,
                        MemoryAIMessage.role.in_(["user", "assistant", "system"]),
                    )
                    .order_by(MemoryAIMessage.created_at.asc())
                    .all()
                )
                return [
                    ChatRecord(role=row.role, content=row.content, timestamp=row.created_at)
                    for row in rows
                ]
        except Exception as exc:
            raise MemoryAIError("加载会话历史失败", details=str(exc))

    def session_exists(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        try:
            with self._db_scope() as db:
                count = (
                    db.query(func.count(MemoryAIMessage.id))
                    .filter(
                        MemoryAIMessage.session_id == session_id,
                        self._tenant_filter(tenant_id),
                        MemoryAIMessage.deleted_flag==False,
                    )
                    .scalar()
                    or 0
                )
                return count > 0
        except Exception as exc:
            raise MemoryAIError("检查会话是否存在失败", details=str(exc))

    def get_session_metadata(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[SessionMetadata]:
        try:
            with self._db_scope() as db:
                first = (
                    db.query(MemoryAIMessage.created_at, MemoryAIMessage.title)
                    .filter(
                        MemoryAIMessage.session_id == session_id,
                        self._tenant_filter(tenant_id),
                        MemoryAIMessage.deleted_flag==False,
                    )
                    .order_by(MemoryAIMessage.created_at.asc())
                    .first()
                )
                if first is None:
                    return None

                last_active = (
                    db.query(func.max(MemoryAIMessage.created_at))
                    .filter(
                        MemoryAIMessage.session_id == session_id,
                        self._tenant_filter(tenant_id),
                        MemoryAIMessage.deleted_flag==False,
                    )
                    .scalar()
                )

                return SessionMetadata(
                    session_id=session_id,
                    title=first.title or "",
                    created_at=first.created_at.timestamp(),
                    last_active=(last_active or first.created_at).timestamp(),
                )
        except Exception as exc:
            raise MemoryAIError("获取会话元数据失败", details=str(exc))

    def list_sessions(
        self,
        *,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[SessionSummary]:
        try:
            with self._db_scope() as db:
                rows = (
                    db.query(
                        MemoryAIMessage.session_id.label("session_id"),
                        func.min(MemoryAIMessage.created_at).label("created_at"),
                        func.max(MemoryAIMessage.created_at).label("last_active"),
                        func.count().label("message_count"),
                        func.max(MemoryAIMessage.title).label("title"),
                    )
                    .filter(
                        self._tenant_filter(tenant_id),
                        MemoryAIMessage.deleted_flag==False,
                    )
                    .group_by(MemoryAIMessage.session_id)
                    .order_by(func.max(MemoryAIMessage.created_at).desc())
                    .limit(limit)
                    .all()
                )
                return [
                    SessionSummary(
                        session_id=row.session_id,
                        title=row.title or "",
                        created_at=row.created_at.timestamp(),
                        last_active=row.last_active.timestamp(),
                        message_count=row.message_count,
                    )
                    for row in rows
                ]
        except Exception as exc:
            raise MemoryAIError("获取会话列表失败", details=str(exc))

    def delete_session(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        try:
            with self._db_scope() as db:
                stmt = (
                    update(MemoryAIMessage)
                    .where(
                        MemoryAIMessage.session_id == session_id,
                        self._tenant_filter(tenant_id),
                        MemoryAIMessage.deleted_flag==False,
                    )
                    .values(deleted_at=datetime.now())
                )
                result = db.execute(stmt)
                return result.rowcount > 0
        except Exception as exc:
            raise MemoryAIError("删除会话失败", details=str(exc))

    def update_session_title(
        self,
        *,
        session_id: str,
        new_title: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        safe_title = (new_title.strip() or "未命名")[:255]
        try:
            with self._db_scope() as db:
                stmt = (
                    update(MemoryAIMessage)
                    .where(
                        MemoryAIMessage.session_id == session_id,
                        self._tenant_filter(tenant_id),
                        MemoryAIMessage.deleted_flag==False,
                    )
                    .values(title=safe_title)
                )
                result = db.execute(stmt)
                return result.rowcount > 0
        except Exception as exc:
            raise MemoryAIError("更新会话标题失败", details=str(exc))
