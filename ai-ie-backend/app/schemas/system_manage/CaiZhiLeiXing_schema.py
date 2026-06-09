from typing import Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic
from app.models.orm_models import AICaiZhiLeiXing
from app.schemas.system_manage.sys_schema import SearchResponse
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================
CaiZhiLeiXingResponseBase = sqlalchemy_to_pydantic(
    AICaiZhiLeiXing,
    exclude=["del_flag", "del_time"]
)  #  response基类
# 搜索响应类型别名
class CaiZhiLeiXingSearchResponse(CaiZhiLeiXingResponseBase):
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
CaiZhiLeiXingResponse = SearchResponse[CaiZhiLeiXingSearchResponse]

# ==================== 请求模型 ====================
# 创建Request
CaiZhiLeiXingCreateRequestBase = sqlalchemy_to_pydantic(
    AICaiZhiLeiXing,
    exclude=["del_flag", "del_time","in_time","up_userid","up_time","czlxId"],
)
class CaiZhiLeiXingCreateRequest(CaiZhiLeiXingCreateRequestBase):
    leiXIngMingCheng: str = Field(...,description="")
    in_userid: int = Field(...,description="")
    @field_validator('in_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('leiXingMingCheng', mode='after')
    @classmethod
    def validate_in_caiZhiMingCheng(cls, v):
        if  v == "" or v == "string":
            raise ValidationException(
                message="材质类型名称写入有误",
                details={"材质类型名称": v, "error": "材质名称不能为空或string"}
            )
        return v

#更新Request
CaiZhiLeiXingUpdateRequestBase = sqlalchemy_to_pydantic(
    AICaiZhiLeiXing,
    exclude=["del_flag", "del_time","in_userid","in_time","up_time"],
)
#批量删除Request
class CaiZhiLeiXingUpdateRequest(CaiZhiLeiXingUpdateRequestBase):
    czlxId: int = Field(...,description="")
    up_userid: int = Field(...,description="")
    @field_validator('up_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('leiXingMingCheng', mode='after')
    @classmethod
    def validate_in_caiZhiMingCheng(cls, v):
        if  v == "" or v == "string":
            raise ValidationException(
                message="材质名称写入有误",
                details={"材质名称": v, "error": "材质类型不能为空或string"}
            )
        return v
    @field_validator('czlxId', mode='after')
    @classmethod
    def validate_in_czlxId(cls, v):
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="材质类型ID必须为16位正整数",
                details={"材质类型Id": v, "error": "材质类型ID必须为16位正整数"}
            )
        return v
class CaiZhiLeiXingBatchDeleteRequest(BaseModel):
    del_userid: int
    czlx_ids: list[int]
    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('czlx_ids', mode='after')
    @classmethod
    def validate_in_czlx_ids(cls, v):
        for czlx_id in v:
            if czlx_id <= 0 or len(str(czlx_id)) != 16:
                raise ValidationException(
                    message="材质类型ID必须为16位正整数",
                    details={"材质类型Id": czlx_id, "error": "材质ID必须为16位正整数"}
            )
        return v
# ==================== 响应模型 ====================
class CaiZhiLeiXingCreateResponse(CaiZhiLeiXingResponseBase):
    message: str = "创建成功"

class CaiZhiLeiXingUpdateResponse(CaiZhiLeiXingResponseBase):
    message: str = "更新成功"





