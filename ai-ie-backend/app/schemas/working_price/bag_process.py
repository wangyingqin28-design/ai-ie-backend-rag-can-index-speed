from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic

from app.models.orm_models import AIXiangBaoGongXu
from app.schemas.system_manage.sys_schema import SearchResponse
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================

XiangBaoGongXuResponseBase = sqlalchemy_to_pydantic(
    AIXiangBaoGongXu,
    exclude=["del_flag", "del_time"],
)  # 标准工序response基类
# 搜索响应类型别名

# ==================== 搜索模型 ====================
#标准工序创建Request
class XiangBaoGongXuSearchResponse(XiangBaoGongXuResponseBase):
    GongZhong: str = Field(...,description="工种名称")
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
        model_config = ConfigDict(
            from_attributes=True,
        )
XiangBaoGongXuResponse = SearchResponse[XiangBaoGongXuSearchResponse]
