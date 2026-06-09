from typing import Optional
import datetime
import decimal
from enum import Enum
from sqlalchemy import BigInteger, Boolean, DECIMAL, DateTime, Float, Identity, Integer, PrimaryKeyConstraint, String, text,Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.models.base import Base
from app.utils.utils import random_id
from app.utils.snowflake_generator import snowflake
from uuid_extensions import uuid7
from sqlalchemy import inspect

# Helper function for creating enum columns that store values as varchar instead of database enum
def EnumColumn(enum_class, **kwargs):
    """Create a String column for enum values to avoid database enum constraints"""
    # Remove enum-specific kwargs that don't apply to String columns
    kwargs.pop("name", None)

    # Determine the maximum length needed for enum values
    max_length = max(len(e.value) for e in enum_class) if enum_class and len(enum_class) > 0 else 50
    # Add some buffer for future enum values
    max_length = max(max_length + 20, 50)

    # Set default length if not specified
    kwargs.setdefault("length", max_length)

    return String(**kwargs)

class DocumentIndexStatus(str, Enum):
    """Document index lifecycle status"""

    PENDING = "PENDING"  # Awaiting processing (create/update)
    CREATING = "CREATING"  # Task claimed, creation/update in progress
    ACTIVE = "ACTIVE"  # Index is up-to-date and ready for use
    DELETING = "DELETING"  # Deletion has been requested
    DELETION_IN_PROGRESS = "DELETION_IN_PROGRESS"  # Task claimed, deletion in progress
    FAILED = "FAILED"  # The last operation failed    
    FAILED_CREATING = "FAILED_CREATING"  # Failed to create index
    FAILED_UPDATING = "FAILED_UPDATING"  # Failed to update index
    FAILED_DELETING = "FAILED_DELETING"  # Failed to delete index

class DocumentIndexType(str, Enum):
    """Document index type enumeration"""
    '''VECTOR必选'''
    VECTOR = "VECTOR"
    FULLTEXT = "FULLTEXT"
    GRAPH = "GRAPH"
    SUMMARY = "SUMMARY"
    VISION = "VISION"

class DocumentIndex(Base):
    __tablename__ = 'AI_XiangBaoGuiZe'
    __table_args__ = ( {'comment': '箱包规则表（向量化）'} ) 
        
    id = mapped_column('id', String(50), primary_key=True, default=lambda: str(uuid7()))
    user_id = mapped_column('yongHuId', BigInteger, nullable=False, comment="用户id")
    enterprise_id = mapped_column('qiYeId', BigInteger, comment="企业id")
    standard_id = mapped_column('biaoZhunId', BigInteger, comment="标准id")
    update_user_id = mapped_column('gengXinYongHuId', BigInteger, comment="更新用户id")
    rule_type = mapped_column('xiangBaoGuiZeLeiXing', BigInteger, nullable=False, comment="箱包规则类型")
    rule = mapped_column('xiangBaoGuiZe', Text, nullable=False, comment="箱包规则")

    upsert_id = mapped_column('gengXinChaRuId', String(24), nullable=False, comment="更新插入id")
    document_id = mapped_column('wenDangId', String(24), nullable=False, default=lambda: "doc" + random_id(), comment="文档id")    
    index_type = mapped_column('suoYinLeiXing', EnumColumn(DocumentIndexType), nullable=False, comment="索引类型")    
    status = mapped_column('suoYinZhuangTai', EnumColumn(DocumentIndexStatus), nullable=False, default=DocumentIndexStatus.PENDING, comment="索引状态")
    version = mapped_column('banBen', Integer, nullable=False, default=1, comment="期望的索引版本（每次文档更新时 +1）")
    observed_version = mapped_column('chuLiDeBanBen', Integer, nullable=False, default=0, comment="已处理的版本号")
    error_message = mapped_column('cuoWuXinXi', Text, comment="错误信息")
    gmt_created = mapped_column('chuangJianShiJian', DateTime, default=datetime.datetime.now, nullable=False, comment="创建时间")
    gmt_updated = mapped_column('gengXinShiJian', DateTime, default=datetime.datetime.now, nullable=False, comment="更新时间")
    gmt_last_reconciled = mapped_column('xieTiaoShiJian', DateTime, comment="协调时间")
    gmt_deleted = mapped_column('shanChuShiJian', DateTime, comment="删除时间")
    content_hash = mapped_column('xiangBaoGuiZeHash', String(64), nullable=False, comment="箱包规则哈希值")
    
    def update_version(self):
        """Update the version to trigger reconciliation"""
        self.version += 1
        self.gmt_updated = datetime.datetime.now()   

    def to_dict(self) -> dict:
        """将模型实例转换为字典，仅包含数据库列（不含 relationship）"""
        result = {}
        for c in inspect(self).mapper.column_attrs:
            value = getattr(self, c.key)
            if isinstance(value, datetime.datetime):
                result[c.key] = value.isoformat()
            elif isinstance(value, datetime.date):
                result[c.key] = value.isoformat()
            elif isinstance(value, decimal.Decimal):
                result[c.key] = float(value)
            else:
                result[c.key] = value
        return result       


class RuleType(Base):
    __tablename__ = 'AI_XiangBaoGuiZeLeiXing'
    __table_args__ = ( {'comment': '箱包规则类型表'} ) 
    
    id = mapped_column('id', BigInteger, primary_key=True, autoincrement=False, default=lambda: snowflake())
    rule_type = mapped_column('xiangBaoGuiZeLeiXing', String(20), nullable=False, comment="箱包规则类型")
    gmt_created = mapped_column('chuangJianShiJian', DateTime, default=datetime.datetime.now, nullable=False, comment="创建时间")
    gmt_updated = mapped_column('gengXinShiJian', DateTime, default=datetime.datetime.now, nullable=False, comment="更新时间")
    gmt_deleted = mapped_column('shanChuShiJian', DateTime, comment="删除时间")

