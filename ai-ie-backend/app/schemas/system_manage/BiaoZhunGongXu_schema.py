from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic

from app.models.orm_models import AIBiaoZhunGongXu
from app.schemas.system_manage.sys_schema import SearchResponse
from app.utils.exceptions import ValidationException

# ==================== 生成ORM基础模型 ====================

BiaoZhunGongXuResponseBase = sqlalchemy_to_pydantic(
    AIBiaoZhunGongXu,
    exclude=["del_flag", "del_time"],
)  # 标准工序response基类
# 搜索响应类型别名


# ==================== 请求模型 ====================
#标准工序创建Request
BiaoZhunGongXuCreateRequestBase = sqlalchemy_to_pydantic(
    AIBiaoZhunGongXu,
    exclude=["del_flag", "del_time","in_time","up_userid","up_time",'bzgxId','gsId'],
)
class BiaoZhunGongXuCreateRequest(BiaoZhunGongXuCreateRequestBase):
    # 校验1：工序名称不能为空（None）
    gongXuMingCheng :str = Field(...,description="")
    xbgzId :int = Field(...,description="")
    in_userid:int =Field(...,description="")
    @field_validator('gongXuMingCheng', mode='after')
    @classmethod
    def validate_gongXuMingCheng_not_none(cls, v):
        if v is None or v == 'string':
            raise ValidationException(
                message="工序名称为必填项，不能为空",
                details={"工序名称": v, "error": "工序名称为空（None）"}
            )
        return v

    # 校验2：工种ID
    @field_validator('xbgzId', mode='after')
    @classmethod
    def validate_xbgzId(cls, v):
        if v is None:
            raise ValidationException(
                message="工种为必填项，不能为空",
                details={"工种": v, "error": "工种为空（None）"}
            )
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="工种ID必须为16位正整数",
                details={"工种": v, "error": "工种ID必须为16位正整数"}
            )
        return v
    @field_validator('in_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v is None:
            raise ValidationException(
                message="userid为必填项",
                details={"":v,"error":"操作人员必填"}
            )
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
#标准工序更新Request
BiaoZhunGongXuUpdateRequestBase = sqlalchemy_to_pydantic(
    AIBiaoZhunGongXu,
    exclude=["del_flag", "del_time","in_userid","in_time","up_time",'gsId'],
)
class BiaoZhunGongXuUpdateRequest(BiaoZhunGongXuUpdateRequestBase):
    up_userid : int = Field(...,description="")
    @field_validator('gongXuMingCheng', mode='after')
    @classmethod
    def validate_gongXuMingCheng_not_none(cls, v):
        if v is None or v == 'string':
            raise ValidationException(
                message="工序名称为必填项，不能为空",
                details={"工序名称": v, "error": "工序名称为空（None）或string"}
            )
        return v

    # 校验2：工种ID
    @field_validator('xbgzId', mode='after')
    @classmethod
    def validate_xbgzId(cls, v):
        if v is None:
            raise ValidationException(
                message="工种为必填项，不能为空",
                details={"工种": v, "error": "工种为空（None）"}
            )
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="工种ID必须为16位正整数",
                details={"工种": v, "error": "工种ID必须为16位正整数"}
            )
        return v
    @field_validator('up_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v is None :
            raise ValidationException(
                message="userid为必填项",
                details={"":v,"error":"操作人员必填"}
            )
        if v <= 0 and len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
#批量删除Request
class BiaoZhunGongXuBatchDeleteRequest(BaseModel):
    del_userid: int
    bzgx_ids: list[int]
    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_in_userid(cls, v):
        if v <= 0 or len(str(v)) != 16:
            raise ValidationException(
                message="用户ID必须为16位正整数",
                details={"用户Id": v, "error": "用户ID必须为16位正整数"}
            )
        return v
    @field_validator('bzgx_ids', mode='after')
    @classmethod
    def validate_in_bzgx_ids(cls, v):
        for bzgx_id in v:
            if bzgx_id <= 0 or len(str(bzgx_id)) != 16:
                raise ValidationException(
                    message="工序ID必须为16位正整数",
                    details={"工序Id": bzgx_id, "error": "工序ID必须为16位正整数"}
            )
        return v
# ==================== 响应模型 ====================
class BiaoZhunGongXuCreateResponse(BiaoZhunGongXuResponseBase):
    message: str = "创建成功"
    model_config = ConfigDict(
        from_attributes=True
    )

class BiaoZhunGongXuUpdateResponse(BiaoZhunGongXuResponseBase):
    message: str = "更新成功"
    model_config = ConfigDict(
        from_attributes=True,
    )


#===================================================================
BiaoZhunGongXuSearch = sqlalchemy_to_pydantic(
    AIBiaoZhunGongXu,
    exclude=["del_flag", "del_time"],
)
class BiaoZhunGongXuSearchResponse(BiaoZhunGongXuSearch):
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
class BiaoZhunGongXuGetSearchResponse(BiaoZhunGongXuSearch):
    GongZhong: str = Field(...,description="工种名称")
    in_username:Optional[str] = Field(None, description="创建用户姓名")
    up_username: Optional[str] = Field(None, description="更新用户姓名")
    gongSi : Optional[str] = Field(None,description="公司名")
    class Config:
        # 允许从属性创建
        from_attributes = True
        # 当字段为None时，不包含在输出中（可选）
        # exclude_none = True
        model_config = ConfigDict(
            from_attributes=True,
        )

BiaoZhunGongXuResponse = SearchResponse[BiaoZhunGongXuSearchResponse]

