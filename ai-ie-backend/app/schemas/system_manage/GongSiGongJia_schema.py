import decimal
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic

from app.models.orm_models import AIGongSiGongJia
from app.schemas.system_manage.sys_schema import SearchResponse
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================
GongSiGongJiaResponseBase = sqlalchemy_to_pydantic(
    AIGongSiGongJia,
    exclude=["del_flag", "del_time"]
)  # 公司工价response基类
# 搜索响应类型别名


# ==================== 请求模型 ====================
#公司工价创建Request
GongSiGongJiaCreateRequestBase = sqlalchemy_to_pydantic(
    AIGongSiGongJia,
    exclude=["del_flag", "del_time","in_time","up_userid","up_time","gsgjId",'gsId'],
)
class GongSiGongJiaCreateRequest(GongSiGongJiaCreateRequestBase):
    xbgzId:int = Field(...,description="")
    gongJia:decimal.Decimal = Field(...,description="")
    in_userid:int = Field(...,description="")
    @field_validator('in_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v is None:
            raise ValidationException(
                message="用户为必填项",
                details={"":v,"error":"操作人员必填"}
            )
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('xbgzId', mode='after')
    @classmethod
    def validate_in_xbgzId(cls, v):
        if v is None:
            raise ValidationException(
                message="工种ID为必填项",
                details={"工种":v,"error":"工种必填"}
            )
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="工种ID必须为16位正整数",
                details={"工种Id": v, "error": "工种ID必须为16位正整数"}
            )
        return v
#公司工价更新Request
class GongSiGongJiaUpdateRequest(BaseModel):
    # 通常更新时所有字段都是可选的
    gsgjId: int
    xbgzId: int = Field(None, description="工种ID")
    gongJia: Optional[Decimal] = Field(None, max_digits=10, decimal_places=4, description="工价（元/月）")
    bianGengYuanYin: Optional[str] = Field(None, max_length=255, description="变更原因")
    up_userid: int = Field(None, description="最后更新人员")
    @field_validator('up_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('xbgzId', mode='after')
    @classmethod
    def validate_in_xbgzId(cls, v):
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="工种ID必须为16位正整数",
                details={"工种Id": v, "error": "工种ID必须为16位正整数"}
            )
        return v
    @field_validator('gsgjId', mode='after')
    @classmethod
    def validate_in_gsgjId(cls, v):
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="公司工价ID必须为16位正整数",
                details={"公司工价Id": v, "error": "公司工价ID必须为16位正整数"}
            )
        return v


#批量删除Request
class GongSiGongJiaBatchDeleteRequest(BaseModel):
    del_userid: int
    gsgj_ids: list[int]
    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('gsgj_ids', mode='after')
    @classmethod
    def validate_in_gsgj_ids(cls, v):
        for gsgj_id in v:
            if gsgj_id <= 0 or len(str(gsgj_id)) != 16:
                raise ValidationException(
                    message="公司工价ID必须为16位正整数",
                    details={"公司工价Id": gsgj_id, "error": "公司工价ID必须为16位正整数"}
            )
        return v
# ==================== 响应模型 ====================
class GongSiGongJiaCreateResponse(GongSiGongJiaResponseBase):
    message: str = "创建成功"

class GongSiGongJiaUpdateResponse(GongSiGongJiaResponseBase):
    message: str = "更新成功"


#===================================================================
GongSiGongJiaSearch = sqlalchemy_to_pydantic(
    AIGongSiGongJia,
    exclude=["del_flag", "del_time","gsId"],
)
class GongSiGongJiaSearchResponse(GongSiGongJiaSearch):
    gongZhong: str = Field(...,description="工种名称")
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
class GongSiGongJiaGetSearchResponse(GongSiGongJiaSearch):
    gongZhong: str = Field(...,description="工种名称")
    gongSi: str = Field(...,description="公司名称")
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
class GongSiGongJiaSearchRequest(BaseModel):
    """
    专用的分页搜索请求模型
    """
    page: int = Field(default=1,ge=1, description="当前页码")
    page_size: int = Field(default=10,gt=0,le=100, description="每页数量")
    search_keyword: int = Field(..., description="搜索关键词")

GongSiGongJiaResponse = SearchResponse[GongSiGongJiaSearchResponse]