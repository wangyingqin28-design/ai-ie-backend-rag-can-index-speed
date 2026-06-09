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


class SQLAlchemyChatRepository(IChatRepository):
    """基于 SQLAlchemy 的默认实现。

    构造时注入 session_factory（如 sessionmaker(bind=engine)），
    每次操作内部自管理事务，与 FastAPI Request 完全解耦。
    """

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
                db.add(
                    MemoryAIMessage(
                        id=str(uuid.uuid4()),
                        session_id=session_id,
                        tenant_id=tenant_id,
                        role=role,
                        content=content,
                        title=(title.strip()[:255] if title and title.strip() else None),
                        created_at=datetime.now(),
                        deleted_at=None,
                    )
                )
            return True
        except Exception as e:
            raise MemoryAIError("保存消息失败", details=str(e))

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
                        MemoryAIMessage.deleted_at.is_(None),
                        MemoryAIMessage.role.in_(["user", "assistant", "system"]),
                    )
                    .order_by(MemoryAIMessage.created_at.asc())
                    .all()
                )
                return [
                    ChatRecord(role=r.role, content=r.content, timestamp=r.created_at)
                    for r in rows
                ]
        except Exception as e:
            raise MemoryAIError("加载会话历史失败", details=str(e))

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
                        MemoryAIMessage.deleted_at.is_(None),
                    )
                    .scalar()
                    or 0
                )
                return count > 0
        except Exception as e:
            raise MemoryAIError("会话存在性检查失败", details=str(e))

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
                        MemoryAIMessage.deleted_at.is_(None),
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
                        MemoryAIMessage.deleted_at.is_(None),
                    )
                    .scalar()
                )

                return SessionMetadata(
                    session_id=session_id,
                    title=first.title or "",
                    created_at=first.created_at.timestamp(),
                    last_active=(last_active or first.created_at).timestamp(),
                )
        except Exception as e:
            raise MemoryAIError("获取会话元数据失败", details=str(e))

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
                        MemoryAIMessage.deleted_at.is_(None),
                    )
                    .group_by(MemoryAIMessage.session_id)
                    .order_by(func.max(MemoryAIMessage.created_at).desc())
                    .limit(limit)
                    .all()
                )
                return [
                    SessionSummary(
                        session_id=r.session_id,
                        title=r.title or "",
                        created_at=r.created_at.timestamp(),
                        last_active=r.last_active.timestamp(),
                        message_count=r.message_count,
                    )
                    for r in rows
                ]
        except Exception as e:
            raise MemoryAIError("会话列表获取失败", details=str(e))

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
                        MemoryAIMessage.deleted_at.is_(None),
                    )
                    .values(deleted_at=datetime.now())
                )
                result = db.execute(stmt)
                return result.rowcount > 0
        except Exception as e:
            raise MemoryAIError("会话删除失败", details=str(e))

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
                        MemoryAIMessage.deleted_at.is_(None),
                    )
                    .values(title=safe_title)
                )
                result = db.execute(stmt)
                return result.rowcount > 0
        except Exception as e:
            raise MemoryAIError("会话标题更新失败", details=str(e))
