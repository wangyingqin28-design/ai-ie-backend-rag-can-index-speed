from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MemoryAIMessage(Base):
    __tablename__ = "memory_ai_message"

    id = Column(String(36), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=True, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
