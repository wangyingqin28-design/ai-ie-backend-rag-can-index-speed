import re
from datetime import datetime
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

# 匹配ISO格式时间字符串的正则表达式（如2026-01-20T18:00:36、2026-01-20T18:00:36.123）
ISO_DATETIME_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$')


def format_datetime_recursive(obj: Any) -> Any:
    """
    递归遍历数据结构，处理两种时间格式：
    1. datetime对象 → 转成YYYY-MM-DD HH:MM:SS
    2. ISO格式时间字符串（带T）→ 替换T为空格，去掉毫秒
    """
    # 处理datetime对象
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S") if obj is not None else None

    # 处理ISO格式时间字符串（带T）
    elif isinstance(obj, str) and ISO_DATETIME_PATTERN.match(obj):
        # 替换T为空格，去掉可能的毫秒部分
        return obj.replace('T', ' ').split('.')[0]

    # 处理列表/元组
    elif isinstance(obj, (list, tuple)):
        return [format_datetime_recursive(item) for item in obj]

    # 处理字典（包括Pydantic模型转的字典、SQLAlchemy模型转的字典）
    elif isinstance(obj, dict):
        return {key: format_datetime_recursive(value) for key, value in obj.items()}

    # 处理其他类型（如int/float/bool/None等），直接返回
    else:
        return obj

class Success(JSONResponse):
    """
    自定义成功响应类 - 标准化接口成功返回格式
    继承FastAPI的JSONResponse，统一返回结构：{code: 状态码, msg: 提示信息, data: 业务数据}
    """

    def __init__(
            self,
            code: int = 200,
            msg: Optional[str] = "OK",
            data: Optional[Any] = None,
            **kwargs,
    ):

        # 使用jsonable_encoder处理所有数据（包括datetime/Pydantic/SQLAlchemy）
        # 这一步会把datetime自动转成ISO格式字符串，Pydantic转字典，SQLAlchemy模型转字典
        raw_content  = jsonable_encoder(
            {
                "code": code,
                "msg": msg,
                "data": data,
                **kwargs  # 扩展字段也一起序列化
            },
            # #自定义datetime编码规则，替代默认的ISO格式
            # custom_encoder={
            #
            #     datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if v is not None else None,
            #
            # },
        )

        # 递归处理所有带T的ISO时间字符串
        serialized_content = format_datetime_recursive(raw_content)

        # 直接传入序列化后的字典（无需再处理）
        super().__init__(content=serialized_content, status_code=code)



class SuccessExtra(JSONResponse):
    """
    自定义带分页信息的成功响应类 - 专用于列表/分页查询接口
    继承FastAPI的JSONResponse，返回结构包含分页字段：
    {code: 状态码, msg: 提示信息, data: 业务数据, total: 总条数, page: 当前页, page_size: 每页条数}
    """
    def __init__(
        self,
        code: int = 200,          # HTTP状态码/业务状态码，默认200（成功）
        msg: Optional[str] = None, # 响应提示信息，可选
        data: Optional[Any] = None, # 分页后的业务数据列表
        total: int = 0,           # 数据总条数，用于分页计算（默认0）
        page: int = 1,            # 当前页码，默认第1页
        page_size: int = 20,      # 每页显示条数，默认20条
        **kwargs,                  # 扩展字段，允许动态添加额外返回参数
    ):
        # 构建包含分页信息的标准化响应体
        content = {
            "code": code,
            "msg": msg,
            "data": data,
            "total": total,       # 总记录数
            "page": page,         # 当前页
            "page_size": page_size # 每页条数
        }
        # 合并扩展字段（如有）
        content.update(kwargs)
        # 调用父类构造方法，返回JSON格式响应
        super().__init__(content=content, status_code=code)






































