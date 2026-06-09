#分页批量获取dxf请求体
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.exceptions import ValidationException


class AdminPageRequest(BaseModel):

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

#批量删除dxf请求体
class AdminBatchDeleteDXFRequest(BaseModel):
    del_userid: int = Field(..., description="操作人ID（16位正整数）")
    aiXiangBaoKuanHao_ids: List[int] = Field(..., description="待删除的纸格ID列表")

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