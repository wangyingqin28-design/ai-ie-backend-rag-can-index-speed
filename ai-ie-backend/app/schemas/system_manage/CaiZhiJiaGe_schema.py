import decimal
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic

from app.models.orm_models import AICaiZhiJiaGe
from app.schemas.system_manage.sys_schema import SearchResponse
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================
CaiZhiJiaGeResponseBase = sqlalchemy_to_pydantic(
    AICaiZhiJiaGe,
    exclude=["del_flag"]
)  # 材质价格response基类

# ==================== 请求模型 ====================
# 材质价格创建Request
CaiZhiJiaGeCreateRequestBase = sqlalchemy_to_pydantic(
    AICaiZhiJiaGe,
    exclude=["del_flag", "in_time", "up_userid", "up_time", "czjgId", "gsId"],
)

class CaiZhiJiaGeCreateRequest(CaiZhiJiaGeCreateRequestBase):
    xbczId: int = Field(..., description="材质ID")
    czjg: decimal.Decimal = Field(..., description="材质价格")
    in_userid: int = Field(..., description="创建人ID")

    @field_validator('in_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v is None:
            raise ValidationException(
                message="用户为必填项",
                details={"": v, "error": "操作人员必填"}
            )
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v

    @field_validator('xbczId', mode='after')
    @classmethod
    def validate_xbczId(cls, v):
        if v is None:
            raise ValidationException(
                message="材质ID为必填项",
                details={"材质": v, "error": "材质必填"}
            )
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="材质ID必须为16位正整数",
                details={"材质Id": v, "error": "材质ID必须为16位正整数"}
            )
        return v


# 材质价格更新Request
class CaiZhiJiaGeUpdateRequest(BaseModel):
    czjgId: int
    xbczId: Optional[int] = Field(None, description="材质ID")
    czjg: Optional[Decimal] = Field(None, max_digits=10, decimal_places=4, description="材质价格")
    bianGengYuanYin: Optional[str] = Field(None, max_length=255, description="变更原因")
    up_userid: Optional[int] = Field(None, description="最后更新人员")

    @field_validator('up_userid', mode='after')
    @classmethod
    def validate_up_userid(cls, v):
        if v is not None and (v <= 0 or len(str(v)) != 16):
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v

    @field_validator('xbczId', mode='after')
    @classmethod
    def validate_xbczId(cls, v):
        if v is not None and (v <= 0 or len(str(v)) != 16):
            raise ValidationException(
                message="材质ID必须为16位正整数",
                details={"材质Id": v, "error": "材质ID必须为16位正整数"}
            )
        return v

    @field_validator('czjgId', mode='after')
    @classmethod
    def validate_czjgId(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="材质价格ID必须为16位正整数",
                details={"材质价格Id": v, "error": "材质价格ID必须为16位正整数"}
            )
        return v


# 批量删除Request
class CaiZhiJiaGeBatchDeleteRequest(BaseModel):
    del_userid: int
    czjg_ids: list[int]

    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_del_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v

    @field_validator('czjg_ids', mode='after')
    @classmethod
    def validate_czjg_ids(cls, v):
        for czjg_id in v:
            if czjg_id <= 0 or len(str(czjg_id)) != 16:
                raise ValidationException(
                    message="材质价格ID必须为16位正整数",
                    details={"材质价格Id": czjg_id, "error": "材质价格ID必须为16位正整数"}
                )
        return v


# ==================== 响应模型 ====================
class CaiZhiJiaGeCreateResponse(CaiZhiJiaGeResponseBase):
    message: str = "创建成功"


class CaiZhiJiaGeUpdateResponse(CaiZhiJiaGeResponseBase):
    message: str = "更新成功"


# ==================== 搜索模型 ====================
CaiZhiJiaGeSearch = sqlalchemy_to_pydantic(
    AICaiZhiJiaGe,
    exclude=["del_flag", "gsId"],
)


class CaiZhiJiaGeSearchResponse(CaiZhiJiaGeSearch):
    caiZhi: str = Field(..., description="材质名称")
    in_username: Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")

    class Config:
        from_attributes = True


class CaiZhiJiaGeGetSearchResponse(CaiZhiJiaGeSearch):
    caiZhi: str = Field(..., description="材质名称")
    gongSi: str = Field(..., description="公司名称")
    in_username: Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")

    class Config:
        from_attributes = True


class CaiZhiJiaGeSearchRequest(BaseModel):
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=10, gt=0, le=100, description="每页数量")
    search_keyword: int = Field(..., description="搜索关键词")


CaiZhiJiaGeResponse = SearchResponse[CaiZhiJiaGeSearchResponse]