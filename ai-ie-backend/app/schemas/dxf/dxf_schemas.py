from datetime import datetime
from typing import List, Optional

from pydantic import Field, BaseModel, field_validator, model_validator, ConfigDict
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic

from app.models.orm_models import AICaiPianGongYi, AIXiangBaoCaiPian, AIXiangBaoKuanHao
from app.utils.exceptions import ValidationException

# 基础：生成包含所有字段的模型
# UserPydanticBase = sqlalchemy_to_pydantic(UserORM)
#
# # 排除敏感字段、指定可选字段
# UserResponse = sqlalchemy_to_pydantic(
#     UserORM,
#     exclude=["password"],  # 排除字段
#     optional=["age"]       # 标记age为可选字段（None）


def datetime_to_str(dt: datetime) -> str:
    if dt is None:
        return None
    # 转为 "YYYY-MM-DD HH:MM:SS" 格式
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# 1. 生成ORM基础响应模型
aiCaiPianGongYiResponseBase = sqlalchemy_to_pydantic(AICaiPianGongYi)#裁片工艺response基类

aiXiangBaoCaiPianResponseBase = sqlalchemy_to_pydantic(AIXiangBaoCaiPian)#箱包裁片response基类

aiXiangBaoKuanHaoResponseBase = sqlalchemy_to_pydantic(AIXiangBaoKuanHao)#箱包款号response基类

aiXiangBaoKuanHaoRequestBase = sqlalchemy_to_pydantic(AIXiangBaoKuanHao,exclude=["dxfURL","del_time","in_userid","in_time","del_flag"])#箱包款号request基类

aiXiangBaoCaiPianRequestBase = sqlalchemy_to_pydantic(AIXiangBaoCaiPian,exclude=["del_flag","caiPianChiCun","nanDuXiShu","imgURL","del_time","in_userid","in_time","up_time"])#箱包裁片request基类

aiCaiPianGongYiRequestBase = sqlalchemy_to_pydantic(AICaiPianGongYi,exclude=["del_flag","gongYiWeiZhi","del_time","in_userid","in_time","up_time"])#裁片工艺request基类

# 2. 继承添加自定义属性（ORM里没有的）
#裁片工艺response
class AICaiPianGongYiResponse(aiCaiPianGongYiResponseBase):

    pass


#箱包裁片response
class AIXiangBaoCaiPianResponse(aiXiangBaoCaiPianResponseBase):
    gongYiLieBiao: List[AICaiPianGongYiResponse] = Field(default_factory=list, description="该裁片下的工艺列表")
    presigned_url: Optional[str] = Field(None,description='裁片图片路径')

    # Pydantic V2 配置：全局时间格式
#     model_config = ConfigDict(
#         from_attributes=True,  # 替代原 orm_mode
#         json_encoders={
#             datetime: datetime_to_str  # 所有 datetime 字段用这个函数序列化
#         })

#箱包款号response
class AIXiangBaoKuanHaoResponse(aiXiangBaoKuanHaoResponseBase):
    yongHuXingMing : Optional[str] = Field(None,description='上传人名称')
    baoXingMingCheng : Optional[str] = Field(None,description='包型名称')
    caiPianLieBiao: List[AIXiangBaoCaiPianResponse] = Field(default_factory=list, description="该纸格下的裁片列表")

# 关键：这里把 dqbmId 不管是 int 还是 str，都统一转成 str
    @field_validator('dqbmId', mode='before')
    @classmethod
    def normalize_dqbmId(cls, v):
        if v is None:
            return None
        return str(v)

#裁片工艺request
class AICaiPianGongYiRequest(aiCaiPianGongYiRequestBase):

    # 校验1：工艺类型不能为空（None）
    @field_validator('gongYiLeiXing', mode='after')
    @classmethod
    def validate_gongYiLeiXing_not_none(cls, v):
        if v is None:
            raise ValidationException(
                message="工艺类型为必填项，不能为空",
                details={"gongYiLeiXing": v, "error": "工艺类型为空（None）"}
            )
        return v

    # 校验2：工艺类型必须是整数
    @field_validator('gongYiLeiXing', mode='after')
    @classmethod
    def validate_gongYiLeiXing_type(cls, v):
        if not isinstance(v, int):
            raise ValidationException(
                message=f"工艺类型不合法，需为整数类型",
                details={
                    "gongYiLeiXing": v,
                    "error": f"当前类型为{type(v).__name__}，需为int"
                }
            )
        return v

    # 校验3：工艺类型只能是0或1
    @field_validator('gongYiLeiXing', mode='after')
    @classmethod
    def validate_gongYiLeiXing_value(cls, v):
        valid_values = [0, 1]
        if v not in valid_values:
            raise ValidationException(
                message="工艺类型值非法（仅允许0-工艺/1-备注）",
                details={
                    "gongYiLeiXing": v,
                    "allowed_values": valid_values,
                    "error": "超出合法取值范围"
                }
            )
        return v

#箱包裁片request
class AIXiangBaoCaiPianRequest(aiXiangBaoCaiPianRequestBase):

    gongYiLieBiao: List[AICaiPianGongYiRequest] = Field(default_factory=list, description="该裁片下的工艺列表")

    # ========== 基础ID校验 ==========
    # 校验1：操作人ID（16位正整数）
    @field_validator('up_userid', mode='after')
    @classmethod
    def validate_up_userid(cls, v):
        if v <= 0:
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"up_userid": v, "error": "用户ID非正整数"}
            )
        if len(str(v)) != 16:
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={
                    "up_userid": v,
                    "error": "用户ID长度非16位",
                    "received_length": len(str(v))
                }
            )
        return v

    # 校验2：企业ID（16位正整数）
    @field_validator('gsId', mode='after')
    @classmethod
    def validate_gsId(cls, v):
        if v <= 0:
            raise ValidationException(
                message="企业ID必须为16位正整数",
                details={"gsId": v, "error": "企业ID非正整数"}
            )
        if len(str(v)) != 16:
            raise ValidationException(
                message="企业ID必须为16位正整数",
                details={
                    "gsId": v,
                    "error": "企业ID长度非16位",
                    "received_length": len(str(v))
                }
            )
        return v

    # 校验3：箱包部位ID（16位正整数）
    @field_validator('xbbwId', mode='after')
    @classmethod
    def validate_xbbwId(cls, v):
        if v <= 0:
            raise ValidationException(
                message="裁片所在部位不能为空",
                details={"xbbwId": v, "error": "箱包部位ID非正整数"}
            )
        if len(str(v)) != 16:
            raise ValidationException(
                message="裁片所在部位不能为空",
                details={
                    "xbbwId": v,
                    "error": "箱包部位ID长度非16位",
                    "received_length": len(str(v))
                }
            )
        return v

    # 校验4：裁片ID（16位正整数）
    @field_validator('xbcpId', mode='after')
    @classmethod
    def validate_xbcpId(cls, v):
        if v <= 0:
            raise ValidationException(
                message="裁片不能为空",
                details={"xbcpId": v, "error": "裁片ID非正整数"}
            )
        if len(str(v)) != 16:
            raise ValidationException(
                message="裁片不能为空",
                details={
                    "xbcpId": v,
                    "error": "裁片ID长度非16位",
                    "received_length": len(str(v))
                }
            )
        return v

    # 校验5：裁片类型必须是整数（非空）
    @field_validator('caiPianLeiXing', mode='after')
    @classmethod
    def validate_caiPianLeiXing(cls, v):
        if not isinstance(v, int):
            raise ValidationException(
                message="裁片类型不能为空",
                details={"caiPianLeiXing": v, "error": "裁片类型非整数类型"}
            )
        return v

    # ========== 裁片厚度校验 ==========
    @field_validator('caiPianHouDu', mode='after')
    @classmethod
    def validate_caiPianHouDu(cls, v):
        if v is None:
            return v  # 未传厚度则跳过校验
        # 定义厚度区间（可提取为常量，方便维护）
        MIN_THICKNESS = 0.01
        MAX_THICKNESS = 100.0
        # 校验类型（int/float都兼容）
        if not isinstance(v, (int, float)):
            raise ValidationException(
                message=f"裁片厚度必须为数字（整数/小数）",
                details={
                    "caiPianHouDu": v,
                    "error": f"类型错误，当前为{type(v).__name__}，需为int/float"
                }
            )
        # 校验区间
        if not (MIN_THICKNESS <= v <= MAX_THICKNESS):
            raise ValidationException(
                message=f"裁片厚度必须在{MIN_THICKNESS}~{MAX_THICKNESS}mm范围内",
                details={
                    "caiPianHouDu": v,
                    "min": MIN_THICKNESS,
                    "max": MAX_THICKNESS,
                    "error": "厚度超出可选范围"
                }
            )
        return v

    # ========== 工艺列表跨字段校验（含索引提示） ==========
    @model_validator(mode='after')
    def validate_gongYiLieBiao(self):
        # 校验1：工艺列表不能为空（根据业务需求，可选）
        # if not self.gongYiLieBiao:
        #     raise ValidationException(
        #         message="工艺列表不能为空",
        #         details={"gongYiLieBiao": self.gongYiLieBiao}
        #     )
        # 校验2：遍历列表，补充索引信息（核心：把子模型的异常补充索引+描述）
        for idx, gong_yi in enumerate(self.gongYiLieBiao):
            try:
                # 触发子模型的所有校验（Pydantic已自动校验，这里仅补充索引信息）
                gong_yi.model_validate(gong_yi.model_dump())
            except ValidationException as e:
                # 捕获子模型异常，补充索引和工艺描述，让错误更精准
                e.details["index"] = idx  # 补充工艺列表的行号
                e.details["gongYiMiaoShu"] = gong_yi.gongYiMiaoShu  # 补充工艺描述
                e.details["xbcpId"] = gong_yi.xbcpId or "未知"  # 补充裁片ID
                # 重写异常消息，更贴合业务
                e.message = f"工艺列表第{idx + 1}条，文本标注：{gong_yi.gongYiMiaoShu} - {e.message}"
                raise e
        return self

#箱包款号request
class AIXiangBaoKuanHaoRequest(aiXiangBaoKuanHaoRequestBase):

    # 校验1：操作人ID必须是16位正整数（Pydantic v2 写法）
    @field_validator('up_userid', mode='after')
    @classmethod
    def validate_up_userid(cls, v):
        # 校验正整数
        if v <= 0:
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"up_userid": v, "error": "用户ID非正整数"}
            )
        # 校验16位长度
        up_userid_str = str(v)
        if len(up_userid_str) != 16:
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={
                    "up_userid": v,
                    "error": "用户ID长度非16位",
                    "received_length": len(up_userid_str)
                }
            )
        return v

    # 校验2：企业ID必须是16位正整数
    @field_validator('gsId', mode='after')
    @classmethod
    def validate_gsId(cls, v):
        if v <= 0:
            raise ValidationException(
                message="企业ID必须为16位正整数",
                details={"gsId": v, "error": "企业ID非正整数"}
            )
        gs_id_str = str(v)
        if len(gs_id_str) != 16:
            raise ValidationException(
                message="企业ID必须为16位正整数",
                details={
                    "gsId": v,
                    "error": "企业ID长度非16位",
                    "received_length": len(gs_id_str)
                }
            )
        return v

    # 校验3：来源类型只能是0或1
    @field_validator('laiYuanLeiXing', mode='after')
    @classmethod
    def validate_laiYuanLeiXing(cls, v):
        valid_values = [0, 1]
        if v not in valid_values:
            raise ValidationException(
                message="来源类型只能是0（单独上传）或1（DXF解析）",
                details={
                    "laiYuanLeiXing": v,
                    "error": f"来源类型只能取{valid_values}中的值",
                    "valid_values": valid_values
                }
            )
        return v

#批量删除dxf请求体
class BatchDeleteDXFRequest(BaseModel):
    del_userid: int = Field(..., description="操作人ID（16位正整数）")
    aiXiangBaoKuanHao_ids: List[int] = Field(..., description="待删除的纸格ID列表")
    gsId: int = Field(..., description="企业ID（16位正整数）")

    # 校验1：操作人ID必须是16位正整数（Pydantic v2 写法）
    @field_validator('del_userid', mode='after')
    @classmethod
    def validate_del_userid(cls, v):
        # 校验正整数
        if v <= 0:
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={"del_userid": v, "error": "ID非正整数"}
            )
        # 校验16位长度
        del_userid_str = str(v)
        if len(del_userid_str) != 16:
            raise ValidationException(
                message="操作人ID必须为16位正整数",
                details={
                    "del_userid": v,
                    "error": "ID长度非16位",
                    "received_length": len(del_userid_str)
                }
            )
        return v

    # 校验2：企业ID必须是16位正整数
    @field_validator('gsId', mode='after')
    @classmethod
    def validate_gsId(cls, v):
        if v <= 0:
            raise ValidationException(
                message="企业ID必须为16位正整数",
                details={"gsId": v, "error": "ID非正整数"}
            )
        gs_id_str = str(v)
        if len(gs_id_str) != 16:
            raise ValidationException(
                message="企业ID必须为16位正整数",
                details={
                    "gsId": v,
                    "error": "ID长度非16位",
                    "received_length": len(gs_id_str)
                }
            )
        return v

    # 校验3：纸格ID列表不能为空
    @field_validator('aiXiangBaoKuanHao_ids', mode='after')
    @classmethod
    def validate_ids_not_empty(cls, v):
        if not v:  # 空列表/None 都会触发
            raise ValidationException(
                message="待删除的纸格不能为空",
                details={"aiXiangBaoKuanHao_ids": v}
            )
        # 额外校验列表中的ID都是正整数（增强校验）
        for id_val in v:
            if not isinstance(id_val, int) or id_val <= 0:
                raise ValidationException(
                    message="待删除的纸格ID必须为16位正整数",
                    details={
                        "aiXiangBaoKuanHao_ids": v,
                        "invalid_id": id_val,
                        "error": "ID非正整数"
                    }
                )
        return v

#分页批量获取dxf请求体
class PageRequest(BaseModel):
    gsId: int = Field(..., description="企业唯一标识")
    page: int = Field(1, ge=1, description="页码，默认1")
    page_size: int = Field(10, ge=1, le=100, description="每页条数，默认10，最大100")
    keyword: Optional[str] = Field(None, description="模糊查询关键词")
    start_time: Optional[str] = Field(None, description="上传开始时间（格式：YYYY-MM-DD HH:MM:SS）")
    end_time: Optional[str] = Field(None, description="上传结束时间（格式：YYYY-MM-DD HH:MM:SS）")

    # ===== 新增解析后的datetime属性（校验+解析一体化）=====
    @property
    def start_dt(self) -> Optional[datetime]:
        """解析后的开始时间datetime对象（直接给Service层用）"""
        if self.start_time:
            return datetime.strptime(self.start_time, "%Y-%m-%d %H:%M:%S")
        return None

    @property
    def end_dt(self) -> Optional[datetime]:
        """解析后的结束时间datetime对象（直接给Service层用）"""
        if self.end_time:
            return datetime.strptime(self.end_time, "%Y-%m-%d %H:%M:%S")
        return None

    # 1. 校验企业ID：16位正整数（核心自定义校验）
    @field_validator('gsId', mode='after')
    @classmethod
    def validate_gsId(cls, v):
        # 校验正整数（兜底，防止负数值）
        if v <= 0:
            raise ValidationException(
                message="企业ID必须为16位正整数",
                details={"gsId": v, "error": "ID非正整数"}
            )
        # 校验16位长度
        gs_id_str = str(v)
        if len(gs_id_str) != 16:
            raise ValidationException(
                message="企业ID必须为16位正整数",
                details={
                    "gsId": v,
                    "error": "ID长度非16位",
                    "received_length": len(gs_id_str)
                }
            )
        return v

    # 2. 校验开始时间格式
    @field_validator('start_time', mode='before')
    @classmethod
    def validate_start_time(cls, v):
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
            return v
        except ValueError:
            raise ValidationException(
                message="开始时间格式错误，需为YYYY-MM-DD HH:MM:SS",
                details={"start_time": v}
            )

    # 3. 校验结束时间格式
    @field_validator('end_time', mode='before')
    @classmethod
    def validate_end_time(cls, v):
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
            return v
        except ValueError:
            raise ValidationException(
                message="结束时间格式错误，需为YYYY-MM-DD HH:MM:SS",
                details={"end_time": v}
            )

    # 4. 跨字段校验：结束时间不能早于开始时间（Pydantic v2 用 model_validator）
    @model_validator(mode='after')
    def validate_time_order(self):
        if self.start_time and self.end_time:
            start_dt = datetime.strptime(self.start_time, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(self.end_time, "%Y-%m-%d %H:%M:%S")
            if end_dt < start_dt:
                raise ValidationException(
                    message="结束时间不能早于开始时间",
                    details={"start_time": self.start_time, "end_time": self.end_time}
                )
        return self


















