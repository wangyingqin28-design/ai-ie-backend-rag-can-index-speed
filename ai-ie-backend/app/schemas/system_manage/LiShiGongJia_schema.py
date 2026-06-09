from pydantic import BaseModel, Field, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic
from app.models.orm_models import AILiShiGongJia
from typing import Optional

from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================
LiShiGongJiaResponseBase = sqlalchemy_to_pydantic(
    AILiShiGongJia,
)  # 公司工价response基类
# 搜索响应类型别名
# ==================== 请求模型 ====================
#公司工价创建Request
LiShiGongJiaCreateRequest = sqlalchemy_to_pydantic(
    AILiShiGongJia,
    exclude=["in_time","lsgjId"],
)
# ==================== 响应模型 ====================
#===================================================================
LiShiGongJiaSearch = sqlalchemy_to_pydantic(
    AILiShiGongJia,
)
class LiShiGongJiaSearchResponse(LiShiGongJiaSearch):
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
class LiShiGongJiaGetSearchResponse(LiShiGongJiaSearch):
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    gongSi:Optional[str] = Field(...,description="公司名称")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True

class LiShiGongJiaRequest(BaseModel):
    """
    专用的分页搜索请求模型
    包含字段：
    params:
        page:int,限制：大于等于1
        page_size:int，限制：0-100
        userid:int，限制：16位正整数
        gjId:int，限制：16位正整数
    """
    page: int = Field(default=1,ge=1, description="当前页码")
    page_size: int = Field(default=10,gt=0,le=100, description="每页数量")
    userid:int = Field(...,description="用户ID")
    gjId: int = Field(..., description="工价ID")
    @field_validator('userid', 'gjId')
    @classmethod
    def validate_16_digit(cls, v: int) -> int:
        if not (10**15 <= v < 10**16):
            raise ValidationException(
                message='必须为16位正整数'
    )
        return v
