from typing import Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic
from app.models.orm_models import AIXiangBaoCaiZhi
from app.schemas.system_manage.sys_schema import SearchResponse
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================
XiangBaoCaiZhiResponseBase = sqlalchemy_to_pydantic(
    AIXiangBaoCaiZhi,
    exclude=["del_flag", "del_time","gsId"]
)  # 包型response基类
# 搜索响应类型别名
class XiangBaoCaiZhiSearchResponse(XiangBaoCaiZhiResponseBase):
    caiZhiLeiXing:Optional[str] = Field(None,description="")
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
class XiangBaoCaiZhiGetSearchResponse(XiangBaoCaiZhiResponseBase):
    caiZhiLeiXing:Optional[str] = Field(None,description="")
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    gongSi:Optional[str] = Field(None,description="公司名称")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
XiangBaoCaiZhiResponse = SearchResponse[XiangBaoCaiZhiSearchResponse]

# ==================== 请求模型 ====================
#包型创建Request
XiangBaoCaiZhiCreateRequestBase = sqlalchemy_to_pydantic(
    AIXiangBaoCaiZhi,
    exclude=["del_flag", "del_time","in_time","up_userid","up_time","xbczId","gsId"],
)
class XiangBaoCaiZhiCreateRequest(XiangBaoCaiZhiCreateRequestBase):
    caiZhiMingCheng: str = Field(...,description="")
    caiZhiMiaoShu:str = Field(...,description="")
    czlxId: int = Field(...,description="")
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
    @field_validator('czlxId', mode='after')
    @classmethod
    def validate_in_czlxid(cls, v):
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="材质类型ID必须为16位正整数",
                details={"材质类型Id": v, "error": "材质类型ID必须为16位正整数"}
            )
        return v
    @field_validator('caiZhiMingCheng', mode='after')
    @classmethod
    def validate_in_caiZhiMingCheng(cls, v):
        if  v == "" or v == "string":
            raise ValidationException(
                message="材质名称写入有误",
                details={"材质名称": v, "error": "材质名称不能为空或string"}
            )
        return v
#包型更新Request
XiangBaoCaiZhiUpdateRequestBase = sqlalchemy_to_pydantic(
    AIXiangBaoCaiZhi,
    exclude=["del_flag", "del_time","in_userid","in_time","up_time","gsId"],
)
#批量删除Request
class XiangBaoCaiZhiUpdateRequest(XiangBaoCaiZhiUpdateRequestBase):
    xbczId: int = Field(...,description="")
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
    @field_validator('caiZhiMingCheng', mode='after')
    @classmethod
    def validate_in_caiZhiMingCheng(cls, v):
        if  v == "" or v == "string":
            raise ValidationException(
                message="材质名称写入有误",
                details={"材质名称": v, "error": "材质类型不能为空或string"}
            )
        return v
    @field_validator('xbczId', mode='after')
    @classmethod
    def validate_in_xbczId(cls, v):
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="材质ID必须为16位正整数",
                details={"材质Id": v, "error": "材质ID必须为16位正整数"}
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
class XiangBaoCaiZhiBatchDeleteRequest(BaseModel):
    del_userid: int
    xbcz_ids: list[int]
    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('xbcz_ids', mode='after')
    @classmethod
    def validate_in_xbcz_ids(cls, v):
        for xbcz_id in v:
            if xbcz_id <= 0 or len(str(xbcz_id)) != 16:
                raise ValidationException(
                    message="材质ID必须为16位正整数",
                    details={"材质Id": xbcz_id, "error": "材质ID必须为16位正整数"}
            )
        return v
# ==================== 响应模型 ====================
class XiangBaoCaiZhiCreateResponse(XiangBaoCaiZhiResponseBase):
    message: str = "创建成功"

class XiangBaoCaiZhiUpdateResponse(XiangBaoCaiZhiResponseBase):
    message: str = "更新成功"





