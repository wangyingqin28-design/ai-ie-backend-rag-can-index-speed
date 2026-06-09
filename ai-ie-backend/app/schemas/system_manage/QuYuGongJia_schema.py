from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic

from app.models.orm_models import AIQuYuGongJia
from app.schemas.system_manage.sys_schema import SearchResponse
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================
QuYuGongJiaResponseBase = sqlalchemy_to_pydantic(
    AIQuYuGongJia,
    exclude=["del_flag", "del_time"]
)  # 区域工价response基类
# 搜索响应类型别名


# ==================== 请求模型 ====================
#区域工价创建Request
QuYuGongJiaCreateRequestBase = sqlalchemy_to_pydantic(
    AIQuYuGongJia,
    exclude=["del_flag", "del_time","in_time","up_userid","up_time","qygjId"],
)
class  QuYuGongJiaCreateRequest (QuYuGongJiaCreateRequestBase):
    dqbmId: str = Field(...,description="")
    xbgzId: int = Field(...,description="")
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
    @field_validator('dqbmId', mode='after')
    @classmethod
    def validate_in_dqbmId(cls, v):
        if  len(v) != 6:
            raise ValidationException(
                message="地区编码ID必须为66位正整数",
                details={"地区编码Id": v, "error": "地区编码ID必须为6位正整数"}
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
#区域工价更新Request
QuYuGongJiaUpdateRequestBase = sqlalchemy_to_pydantic(
    # 通常更新时所有字段都是可选的
    AIQuYuGongJia,
    exclude=["del_flag", "del_time","in_time","in_userid","up_time"]
)
class QuYuGongJiaUpdateRequest(QuYuGongJiaUpdateRequestBase):
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
    @field_validator('dqbmId', mode='after')
    @classmethod
    def validate_in_dqbmId(cls, v):
        if  len(v) != 6:
            raise ValidationException(
                message="地区编码ID必须为16位正整数",
                details={"地区编码Id": v, "error": "地区编码ID必须为6位正整数"}
            )
        return v
    @field_validator('xbgzId', mode='after')
    @classmethod
    def validate_in_xbgzId(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="工种ID必须为16位正整数",
                details={"工种Id": v, "error": "工种ID必须为16位正整数"}
            )
        return v
    @field_validator('qygjId', mode='after')
    @classmethod
    def validate_in_qygjId(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="区域工价ID必须为16位正整数",
                details={"区域工价Id": v, "error": "区域工价ID必须为16位正整数"}
            )
        return v
#批量删除Request
class QuYuGongJiaBatchDeleteRequest(BaseModel):
    del_userid: int
    qygj_ids: list[int]
    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('qygj_ids', mode='after')
    @classmethod
    def validate_in_qygj_ids(cls, v):
        for qygj_id in v:
            if qygj_id <= 0 or len(str(qygj_id)) != 16:
                raise ValidationException(
                    message="区域工价ID必须为16位正整数",
                    details={"区域工价Id": qygj_id, "error": "区域工价ID必须为16位正整数"}
            )
        return v
# ==================== 响应模型 ====================
class QuYuGongJiaCreateResponse(QuYuGongJiaResponseBase):
    message: str = "创建成功"

class QuYuGongJiaUpdateResponse(QuYuGongJiaResponseBase):
    message: str = "更新成功"


#===================================================================
QuYuGongJiaSearch = sqlalchemy_to_pydantic(
    AIQuYuGongJia,
    exclude=["del_flag", "del_time"],
)
class QuYuGongJiaSearchResponse(QuYuGongJiaSearch):
    GongZhong: str = Field(...,description="工种名称")
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    diQuMingCheng:Optional[str] = Field(None,description="")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True

QuYuGongJiaResponse = SearchResponse[QuYuGongJiaSearchResponse]

