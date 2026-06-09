import re

from pydantic import field_validator, BaseModel
from sqlalchemy_to_pydantic import sqlalchemy_to_pydantic

from app.models.orm_models import AIGongSiYongHu
from app.utils.exceptions import ValidationException

# 1. 生成ORM基础响应模型
AIGongSiYongHuResponseBase = sqlalchemy_to_pydantic(AIGongSiYongHu)#公司用户response基类

AIGongSiYongHuRequestBase = sqlalchemy_to_pydantic(AIGongSiYongHu,exclude=["del_time","del_flag","in_time","up_time","in_userid","up_userid","gsyhId"])#公司用户request基类


# 2. 继承添加自定义属性（ORM里没有的）
#公司用户response
class AIGongSiYongHuResponse(AIGongSiYongHuResponseBase):
    pass


#公司用户request
class AIGongSiYongHuRequest(AIGongSiYongHuRequestBase):

    # 1. 手机号校验器（限制11位长度）
    # Pydantic v2 写法：field_validator + mode='before'
    @field_validator('dianHua', mode='before')  # mode='before' 确保在校验前执行
    @classmethod  # v2 要求必须加classmethod
    def validate_phone_format(cls, v):
        # 1. 处理空值
        if v is None:
            raise ValidationException(
                message="手机号格式校验失败",
                details={"dianHua": v, "error": "手机号不能为空"}
            )
        # 2. 统一转字符串并去空格（兼容前端传数字的情况）
        v_str = str(v).strip()
        if not v_str:
            raise ValidationException(
                message="手机号格式校验失败",
                details={"dianHua": v, "error": "手机号不能为空白字符串"}
            )
        # 3. 校验11位纯数字
        if not re.match(r'^[0-9]{11}$', v_str):
            raise ValidationException(
                message="手机号格式校验失败",
                details={
                    "dianHua": v,
                    "dianHua_stripped": v_str,
                    "error": "手机号必须是11位纯数字",
                    "received_length": len(v_str)
                }
            )
        # 4. 返回处理后的干净值
        return v_str


    # 2. 密码校验器（限制8位长度）
    @field_validator('miMa', mode='before')
    @classmethod
    def validate_password_length(cls, v):
        # 处理空值
        if v is None:
            raise ValidationException(
                message="密码格式校验失败",
                details={"miMa": v, "error": "密码不能为空"}
            )
        # 统一转字符串并去空格（避免全空格的情况）
        pwd_str = str(v).strip()
        if not pwd_str:
            raise ValidationException(
                message="密码格式校验失败",
                details={"miMa": v, "error": "密码不能为空白字符串"}
            )
        # 校验长度必须为8位
        if len(pwd_str) != 8:
            raise ValidationException(
                message="密码格式校验失败",
                details={
                    "miMa": v,
                    "miMa_stripped": pwd_str,
                    "error": "密码必须为8位长度",
                    "received_length": len(pwd_str)
                }
            )
        # 返回处理后的密码（去空格）
        return pwd_str


    # 3.gsId 校验器(16位正整数)
    @field_validator('gsId', mode='before')  # mode='before' 确保在校验类型前执行
    @classmethod
    def validate_gsId(cls, v):
        # 1. 校验是否为整数且是正整数
        if not isinstance(v, int) or v <= 0:
            raise ValidationException(
                message="企业ID必须为16位正整数",
                details={"gsId": v, "error": "ID非正整数"}
            )

        # 2. 校验长度是否为16位
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


    # 3. 性别校验器（限制只能取0、1、2）
    @field_validator('xingBie', mode='after')  # mode='after'：确保先校验是int类型，再判断值范围
    @classmethod
    def validate_gender_value(cls, v):
        # 定义合法的性别值集合
        valid_gender_values = {0, 1, 2}
        if v not in valid_gender_values:
            raise ValidationException(
                message="性别设置失败",
                details={
                    "xingBie": v,
                    "error": f"性别只能为“未知”，“男”，“女”",
                    "valid_values": list(valid_gender_values)
                }
            )
        return v


#用户登录request
class LoginRequest(BaseModel):
    dianHua: str
    miMa: str

    # 1. 手机号校验器（限制11位长度）
    # Pydantic v2 写法：field_validator + mode='before'
    @field_validator('dianHua', mode='before')  # mode='before' 确保在校验前执行
    @classmethod  # v2 要求必须加classmethod
    def validate_phone_format(cls, v):
        # 1. 处理空值
        if v is None:
            raise ValidationException(
                message="手机号格式校验失败",
                details={"dianHua": v, "error": "手机号不能为空"}
            )
        # 2. 统一转字符串并去空格（兼容前端传数字的情况）
        v_str = str(v).strip()
        if not v_str:
            raise ValidationException(
                message="手机号格式校验失败",
                details={"dianHua": v, "error": "手机号不能为空白字符串"}
            )
        # 3. 校验11位纯数字
        if not re.match(r'^[0-9]{11}$', v_str):
            raise ValidationException(
                message="手机号格式校验失败",
                details={
                    "dianHua": v,
                    "dianHua_stripped": v_str,
                    "error": "手机号必须是11位纯数字",
                    "received_length": len(v_str)
                }
            )
        # 4. 返回处理后的干净值
        return v_str


    # 2. 密码校验器（限制8位长度）
    @field_validator('miMa', mode='before')
    @classmethod
    def validate_password_length(cls, v):
        # 处理空值
        if v is None:
            raise ValidationException(
                message="密码格式校验失败",
                details={"miMa": v, "error": "密码不能为空"}
            )
        # 统一转字符串并去空格（避免全空格的情况）
        pwd_str = str(v).strip()
        if not pwd_str:
            raise ValidationException(
                message="密码格式校验失败",
                details={"miMa": v, "error": "密码不能为空白字符串"}
            )
        # 校验长度必须为8位
        if len(pwd_str) != 8:
            raise ValidationException(
                message="密码格式校验失败",
                details={
                    "miMa": v,
                    "miMa_stripped": pwd_str,
                    "error": "密码必须为8位长度",
                    "received_length": len(pwd_str)
                }
            )
        # 返回处理后的密码（去空格）
        return pwd_str




