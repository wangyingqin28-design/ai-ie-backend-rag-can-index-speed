# app/schemas/caoZuoRiZhi_schema.py
from typing import Optional, Dict, Any, List,Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic
from app.models.orm_models import AICaoZuoRiZhi
import json
from app.schemas.system_manage.sys_schema import SearchRequest, SearchResponse

# ==================== 基础模型 ====================
CaoZuoRiZhiBase = sqlalchemy_to_pydantic(AICaoZuoRiZhi)


# ==================== 请求模型 ====================
class CaoZuoRiZhiCreateRequest(BaseModel):
    """创建操作日志请求"""
    biaoMing: str = Field(..., description="表名")
    caoZuoZhuJian: int = Field(..., description="操作行数据的主键")
    caoZuoLeiXing: Optional[int] = Field(0, description="操作类型 0:创建, 1:修改, 2:删除")
    liShiShuJu: Optional[Dict[str, Any]] = Field(None, description="历史数据")
    in_userid: Optional[int] = Field(None, description="插入人编号")

    model_config = ConfigDict(from_attributes=True)


class CaoZuoRiZhiSearchRequest(SearchRequest):
    """搜索操作日志请求"""

    model_config = ConfigDict(from_attributes=True)


# ==================== 响应模型 ====================
class CaoZuoRiZhiResponse(CaoZuoRiZhiBase):
    """操作日志响应"""

    # 正确定义字段类型
    liShiShuJu: Optional[Union[dict, list, str]] = Field(default=None)

    @field_validator('liShiShuJu', mode='before')
    @classmethod
    def parse_history(cls, v):
        """解析历史数据"""
        if isinstance(v, str) and v:
            try:
                return json.loads(v)
            except Exception:
                return v
        return v

    model_config = ConfigDict(from_attributes=True)


class CaoZuoRiZhiRecoverResponse(BaseModel):
    """恢复数据响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Dict[str, Any]] = Field(None, description="历史数据")
    table_name: Optional[str] = Field(None, description="表名")
    operation_type: Optional[str] = Field(None, description="原操作类型")

    model_config = ConfigDict(from_attributes=True)

CaoZuoRiZhiSearchResponse = SearchResponse[CaoZuoRiZhiBase]
# ==================== 搜索响应包装 ====================
# class CaoZuoRiZhiSearchResponse(BaseModel):
#     """搜索响应包装器"""
#     data: List[CaoZuoRiZhiResponse] = Field(..., description="数据列表")
#     total: int = Field(..., description="总记录数")
#     page: int = Field(..., description="当前页码")
#     size: int = Field(..., description="每页大小")
#     total_pages: int = Field(..., description="总页数")
#
#     model_config = ConfigDict(from_attributes=True)
