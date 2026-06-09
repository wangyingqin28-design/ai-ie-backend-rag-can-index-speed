from pydantic import BaseModel,Field
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic
from typing import Optional
from app.models.models import DocumentIndex, DocumentIndexStatus, DocumentIndexType
from app.schemas.system_manage.sys_schema import SearchResponse
import datetime

# ==================== 请求模型 ====================

# ==================== 响应模型 ====================
# 假设SearchResponse已定义
class DocumentIndexSearchResponseBase(BaseModel):
    id: Optional[str] = Field(None, description="ID")
    status: Optional[DocumentIndexStatus] = Field(None,description="")
    rule_type: Optional[int] = Field(None, description="箱包规则类型")
    rule_type_name: Optional[str] = Field(None,description="")
    rule: Optional[str] = Field(None, description="箱包规则")
    user_id: Optional[int] = Field(None, description="用户ID")
    gmt_created: Optional[datetime.datetime] = Field(None, description="创建时间")
    update_user_id: Optional[int] = Field(None, description="更新用户ID")
    gmt_updated: Optional[datetime.datetime] = Field(None, description="更新时间")
    in_user_name: Optional[str] = Field(None,description="")
    up_user_name: Optional[str] = Field(None,description="")

class DocumentIndexGetSearchResponseBase(BaseModel):
    id: Optional[str] = Field(None, description="ID")
    status: Optional[DocumentIndexStatus] = Field(None,description="")
    rule_type: Optional[int] = Field(None, description="箱包规则类型")
    rule_type_name: Optional[str] = Field(None,description="")
    rule: Optional[str] = Field(None, description="箱包规则")
    user_id: Optional[int] = Field(None, description="用户ID")
    gmt_created: Optional[datetime.datetime] = Field(None, description="创建时间")
    update_user_id: Optional[int] = Field(None, description="更新用户ID")
    gmt_updated: Optional[datetime.datetime] = Field(None, description="更新时间")
    in_user_name: Optional[str] = Field(None,description="")
    up_user_name: Optional[str] = Field(None,description="")
    gongSi:Optional[str] = Field(None,description="")

class DocumentIndexDetailsSearchResponse(BaseModel):
    id: Optional[str] = Field(None, description="ID")
    rule_type: Optional[int] = Field(None, description="箱包规则类型")
    rule: Optional[str] = Field(None, description="箱包规则")  # 修正为str类型
    status: Optional[DocumentIndexStatus] = Field(None, description="索引状态")

# 修正语法错误，移除逗号
DocumentIndexSearchResponse = SearchResponse[DocumentIndexSearchResponseBase]