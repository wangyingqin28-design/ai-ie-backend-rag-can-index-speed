from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import declarative_base
from typing import Optional
import datetime
from sqlalchemy import BigInteger, Boolean,DateTime, PrimaryKeyConstraint, String, \
    text
from sqlalchemy.orm import  Mapped, mapped_column
Base = declarative_base()

class MemoryAIMessage(Base):
    __tablename__ = "memory_ai_message"

    __table_args__ = (
        PrimaryKeyConstraint("id", name="PK_memory_ai_message"),
        {"comment": "AI 聊天记忆消息表"},
    )

    id: Mapped[int] = mapped_column("id",BigInteger,primary_key=True,autoincrement=False,comment="聊天消息 ID，建议使用雪花算法生成",)
    session_id: Mapped[str] = mapped_column("session_id",String(64, "Chinese_PRC_CI_AS"),nullable=False,index=True,comment="聊天会话唯一标识符",)
    tenant_id: Mapped[Optional[str]] = mapped_column("tenant_id",String(1000, "Chinese_PRC_CI_AS"),nullable=True,index=True, comment="租户、用户或公司标识 ID",)
    role: Mapped[str] = mapped_column("role",String(16, "Chinese_PRC_CI_AS"),nullable=False,comment="消息角色，例如 user、assistant、system",)
    content: Mapped[str] = mapped_column("content",String(4000, "Chinese_PRC_CI_AS"),nullable=False,comment="聊天消息内容",)
    title: Mapped[Optional[str]] = mapped_column("title",String(255, "Chinese_PRC_CI_AS"),nullable=True,comment="聊天会话标题",)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column("created_at",DateTime,nullable=True,comment="消息创建时间",)
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column("deleted_at",DateTime,nullable=True,comment="消息删除时间",)
    deleted_flag: Mapped[bool] = mapped_column("deleted_flag",Boolean,nullable=False,server_default=text("((0))"),comment="逻辑删除标识，0 表示正常，1 表示已删除",)
