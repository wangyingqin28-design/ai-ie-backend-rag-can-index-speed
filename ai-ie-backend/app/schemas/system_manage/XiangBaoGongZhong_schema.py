from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic
from app.models.orm_models import AIXiangBaoGongZhong
from app.schemas.system_manage.sys_schema import SearchResponse
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================
XiangBaoGongZhongResponseBase = sqlalchemy_to_pydantic(
    AIXiangBaoGongZhong,
    exclude=["del_flag", "del_time"]
)  # 工种response基类
# 搜索响应类型别名
XiangBaoGongZhongResponse = SearchResponse[XiangBaoGongZhongResponseBase]

class XiangBaoGongZhongSearchResponse(XiangBaoGongZhongResponseBase):
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
class XiangBaoGongZhongGetSearchResponse(XiangBaoGongZhongSearchResponse):
    gongSi :Optional[str] = Field(None,description="公司名")


# ==================== 请求模型 ====================
#标准工种更新Request
XiangBaoGongZhongUpdateRequestBase = sqlalchemy_to_pydantic(
    AIXiangBaoGongZhong,
    exclude=["del_flag", "del_time","in_userid","in_time","up_time","gsId"],
)
XiangBaoGongZhongCreateRequest = sqlalchemy_to_pydantic(
    AIXiangBaoGongZhong,
    exclude=["del_flag", "del_time","in_time","up_time",'up_userid','xbgzid',"gsId"]
)
class XiangBaoGongZhongUpdateRequest(XiangBaoGongZhongUpdateRequestBase):
    @field_validator('gongZhongMingCheng', mode='after')
    @classmethod
    def validate_gongXuMingCheng_not_none(cls, v):
        if v is None or v == 'string':
            raise ValidationException(
                message="工种名称为必填项，不能为空",
                details={"工种名称": v, "error": "工种名称为空（None）或string"}
            )
        return v
    @field_validator('up_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v is None :
            raise ValidationException(
                message="用户id为必填项",
                details={"":v,"error":"操作人员必填"}
            )
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
#批量删除Request
class XiangBaoGongZhongBatchDeleteRequest(BaseModel):
    del_userid: int
    xbgz_ids: list[int]
    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('xbgz_ids', mode='after')
    @classmethod
    def validate_in_xbgz_ids(cls, v):
        for xbgz_id in v:
            if xbgz_id <= 0 or len(str(xbgz_id)) != 16:
                raise ValidationException(
                    message="工种ID必须为16位正整数",
                    details={"工种Id": xbgz_id, "error": "工种ID必须为16位正整数"}
            )
        return v
# ==================== 响应模型 ====================
class XiangBaoGongZhongCreateResponse(XiangBaoGongZhongResponseBase):
    message: str = "创建成功"

class XiangBaoGongZhongUpdateResponse(XiangBaoGongZhongResponseBase):
    message: str = "更新成功"





