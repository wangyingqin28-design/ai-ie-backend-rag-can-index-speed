from  typing import Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic
from app.schemas.system_manage.sys_schema import SearchResponse
from app.models.orm_models import AIXiangBaoBuWei
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================
XiangBaoBuWeiResponseBase = sqlalchemy_to_pydantic(
    AIXiangBaoBuWei,
    exclude=["del_flag", "del_time","gsId"]
)  # 工种response基类
# 搜索响应类型别名
class XiangBaoBuWeiSearchResponse (XiangBaoBuWeiResponseBase):
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
# 搜索响应类型别名
class XiangBaoBuWeiGetSearchResponse (XiangBaoBuWeiResponseBase):
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    gongSi:Optional[str] = Field(None,description="公司名称")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
XiangBaoBuWeiResponse = SearchResponse[XiangBaoBuWeiResponseBase]

# ==================== 请求模型 ====================
#工种创建Request
XiangBaoBuWeiCreateRequestBase = sqlalchemy_to_pydantic(
    AIXiangBaoBuWei,
    exclude=["del_flag", "del_time","in_time","up_userid","up_time","xbbwId","gsId"],
)
class XiangBaoBuWeiCreateRequest(XiangBaoBuWeiCreateRequestBase):
    buWeiMingCheng: str = Field(...,description="")
    in_userid :int = Field(...,description="")
    @field_validator('in_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('buWeiMingCheng', mode='after')
    @classmethod
    def validate_in_buWeiMingCheng(cls, v):
        if  v == "" or v == "string":
            raise ValidationException(
                message="部位名称写入有误",
                details={"部位名称": v, "error": "部位名称不能为空或string"}
            )
        return v
#标准工种更新Request
XiangBaoBuWeiUpdateRequestBase = sqlalchemy_to_pydantic(
    AIXiangBaoBuWei,
    exclude=["del_flag", "del_time","in_userid","in_time","up_time","gsId"],
)
class XiangBaoBuWeiUpdateRequest(XiangBaoBuWeiUpdateRequestBase):
    xbbwId: int = Field(...,description="")
    up_userid: int = Field(...,description="")
    @field_validator('up_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('xbbwId', mode='after')
    @classmethod
    def validate_in_xbbwId(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="部位ID必须为16位正整数",
                details={"部位Id": v, "error": "部位ID必须为16位正整数"}
            )
        return v
    @field_validator('buWeiMingCheng', mode='after')
    @classmethod
    def validate_in_buWeiMingCheng(cls, v):
        if  v == "" or v == "string":
            raise ValidationException(
                message="部位名称写入有误",
                details={"部位名称": v, "error": "部位名称不能为空或string"}
            )
        return v


#批量删除Request
class XiangBaoBuWeiBatchDeleteRequest(BaseModel):
    del_userid: int
    xbbw_ids: list[int]
    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('xbbw_ids', mode='after')
    @classmethod
    def validate_in_xbbw_ids(cls, v):
        for xbbw_id in v:
            if xbbw_id <= 0 or len(str(xbbw_id)) != 16:
                raise ValidationException(
                    message="部位ID必须为16位正整数",
                    details={"部位Id": xbbw_id, "error": "部位ID必须为16位正整数"}
            )
        return v
# ==================== 响应模型 ====================
class XiangBaoBuWeiCreateResponse(XiangBaoBuWeiResponseBase):
    message: str = "创建成功"

class XiangBaoBuWeiUpdateResponse(XiangBaoBuWeiResponseBase):
    message: str = "更新成功"