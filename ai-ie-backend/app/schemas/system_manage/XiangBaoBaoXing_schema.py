from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic
from app.models.orm_models import AIXiangBaoBaoXing
from app.schemas.system_manage.sys_schema import SearchResponse, SearchRequest
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================
XiangBaoBaoXingResponseBase = sqlalchemy_to_pydantic(
    AIXiangBaoBaoXing,
    exclude=["del_flag", "del_time","gsId"]
)  # 包型response基类
# 搜索响应类型别名


# ==================== 请求模型 ====================
#包型创建Request
XiangBaoBaoXingCreateRequestBase = sqlalchemy_to_pydantic(
    AIXiangBaoBaoXing,
    exclude=["del_flag", "del_time","in_time","up_userid","up_time","xbbxId","gsId"],
)
class XiangBaoBaoXingCreateRequest(XiangBaoBaoXingCreateRequestBase):
    baoXingMingCheng : str = Field(...,description="")
    parent_id:int = Field(...,description="")
    fubxId:int = Field(...,description="")
    in_userid:int = Field(...,description="")
    @field_validator('in_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('parent_id', mode='after')
    @classmethod
    def validate_in_parent_id(cls, v):
        if v!=0 and v!=1 :
            raise ValidationException(
                message="包型等级必须为0或者1",
                details={"包型等级": v, "error": "包型等级必须为0或1"}
            )
        return v
    @field_validator('fubxId', mode='after')
    @classmethod
    def validate_in_fubxId(cls, v):
        if v ==0:
            return v
        else:
            if v<0 or len(str(v)) != 16 :
                raise ValidationException(
                    message="父包型ID必须为0或者16位正整数",
                    details={"父包型ID": v, "error": "父包型ID必须为0或16位正整数"}
                )
            return v
    @field_validator('baoXingMiaoShu', mode='after')
    @classmethod
    def validate_in_baoXingMiaoShu(cls, v):
        if  v == "string":
            raise ValidationException(
                message="包型描述写入有误",
                details={"包型描述": v, "error": "包型描述不能为string"}
            )
        return v
    @field_validator('baoXingMingCheng', mode='after')
    @classmethod
    def validate_in_baoXingMingCheng(cls, v):
        if  v == "" or v == "string":
            raise ValidationException(
                message="包型名称写入有误",
                details={"包型名称": v, "error": "包型名称不能为空或string"}
            )
        return v
#包型更新Request
XiangBaoBaoXingUpdateRequestBase = sqlalchemy_to_pydantic(
    AIXiangBaoBaoXing,
    exclude=["del_flag", "del_time","in_userid","in_time","up_time","gsId"],
)
class XiangBaoBaoXingUpdateRequest (XiangBaoBaoXingUpdateRequestBase):
    xbbxId:int = Field(...,description="")
    up_userid:int = Field(...,description="")
    @field_validator('up_userid', mode='after')
    @classmethod
    def validate_up_userid(cls, v):
        if v <0 or len(str(v)) != 16 :
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('xbbxId', mode='after')
    @classmethod
    def validate_xbbxId(cls, v):
        if v <0 or len(str(v)) != 16 :
            raise ValidationException(
                message="包型ID必须为16位正整数",
                details={"包型Id": v, "error": "包型ID必须为16位正整数"}
            )
        return v
    @field_validator('parent_id', mode='after')
    @classmethod
    def validate_in_parent_id(cls, v):
        if v!=0 and v!=1 :
            raise ValidationException(
                message="包型等级必须为0或者1",
                details={"包型等级": v, "error": "包型等级必须为0或1"}
            )
        return v
    @field_validator('fubxId', mode='after')
    @classmethod
    def validate_in_fubxId(cls, v):
        if v==0:
            return v
        else:
            if v<0 or len(str(v)) != 16 :
                raise ValidationException(
                    message="父包型ID必须为0或者16位正整数",
                    details={"父包型ID": v, "error": "父包型ID必须为0或16位正整数"}
                )
            return v
    @field_validator('baoXingMiaoShu', mode='after')
    @classmethod
    def validate_in_baoXingMiaoShu(cls, v):
        if  v == "string":
            raise ValidationException(
                message="包型描述写入有误",
                details={"包型描述": v, "error": "包型描述不能为string"}
            )
        return v
    @field_validator('baoXingMingCheng', mode='after')
    @classmethod
    def validate_in_baoXingMingCheng(cls, v):
        if  v == "" or v == "string":
            raise ValidationException(
                message="包型名称写入有误",
                details={"包型名称": v, "error": "包型名称不能为空或string"}
            )
        return v

#批量删除Request
class XiangBaoBaoXingBatchDeleteRequest(BaseModel):
    del_userid: int
    xbbx_ids: list[int]
    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('xbbx_ids', mode='after')
    @classmethod
    def validate_in_xbbx_ids(cls, v):
        for xbbx_id in v:
            if xbbx_id <= 0 or len(str(xbbx_id)) != 16:
                raise ValidationException(
                    message="包型ID必须为16位正整数",
                    details={"包型Id": xbbx_id, "error": "包型ID必须为16位正整数"}
            )
        return v
# ==================== 响应模型 ====================
class XiangBaoBaoXingSearchResponse(XiangBaoBaoXingResponseBase):
    """包型搜索项模型（包含父类名称）"""
    parent_BaoXingMingCheng: str | None = Field(
        default=None,
        description="父类包型名称"
    )
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
class XiangBaoBaoXingGetSearchResponse(XiangBaoBaoXingResponseBase):
    """包型搜索项模型（包含父类名称）"""
    parent_BaoXingMingCheng: str | None = Field(
        default=None,
        description="父类包型名称"
    )
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    gongSi:Optional[str] = Field(None,description="公司名称")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
XiangBaoBaoXingResponse = SearchResponse[XiangBaoBaoXingSearchResponse]
class XiangBaoBaoXingSearchRequest(SearchRequest):
    parent_id: Optional[int] = Field(None,description="包型等级")
    fubxId:Optional[int] = Field(None,description="父级包型ID")
    @field_validator('fubxId')
    @classmethod
    def validate_fubxId(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v != 0:
            if v < 0:
                raise ValidationException(
                    message='父类包型ID必须为正整数')
            if len(str(v)) != 16:
                raise ValidationException(
                    message='父类包型ID必须为16位正整数')
        return v

class XiangBaoBaoXingCreateResponse(XiangBaoBaoXingResponseBase):
    message: str = "创建成功"

class XiangBaoBaoXingUpdateResponse(XiangBaoBaoXingResponseBase):
    message: str = "更新成功"

