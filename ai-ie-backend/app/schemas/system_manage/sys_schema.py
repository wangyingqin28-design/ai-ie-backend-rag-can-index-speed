from typing import List, TypeVar, Generic, Any, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from app.utils.exceptions import ValidationException

# ==================== 通用搜索响应模型 ====================
# 泛型类型变量，用于表示items中元素的类型
T = TypeVar('T')
class SearchResponse(BaseModel, Generic[T]):
    """
    通用的分页搜索响应模型
    """
    items: List[T] = Field(..., description="数据列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")
    has_previous: bool = Field(..., description="是否有上一页")
    has_next: bool = Field(..., description="是否有下一页")
    search_keyword: str = Field("", description="搜索关键词")  # 必填，默认空字符串

    model_config = ConfigDict(
       from_attributes=True,
    )
class SearchRequest(BaseModel):
    """
    通用的分页搜索请求模型
    page:int
    page_size:int
    search_keyword:str
    user_id:int
    """
    page: int = Field(default=1,ge=1, description="当前页码")
    page_size: int = Field(default=10,gt=0,le=100, description="每页数量")
    search_keyword: Optional[str] = Field("", description="搜索关键词")
    userid :int = Field(...,description="用户ID")

    @model_validator(mode='before')
    @classmethod
    def check_userid_required(cls, data: Any) -> Any:
        """模型级验证：确保userid存在且不为null"""
        if isinstance(data, dict):
            if 'userid' not in data:
                raise ValueError("userid为必填项")
        return data

    @field_validator('userid')
    @classmethod
    def validate_userid_format(cls, v: int) -> int:
        """字段级验证：确保格式正确"""
        # 检查是否为正整数
        if v <= 0:
            raise ValueError("用户ID必须为正整数")

        # 检查是否为16位（1e15到1e16-1之间）
        if not (10 ** 15 <= v < 10 ** 16):
            raise ValueError("用户ID必须为16位正整数")

        return v
    @classmethod
    def validate_page_size(cls, v):
        if v <1 or v>100:
            raise ValidationException(
                message="每页数量必须在1-100之间",
                details={"page_size": v}
            )
        return v
    @classmethod
    def validate_page(cls, v):
        if v <1 :
            raise ValidationException(
                message="页码必须大于0",
                details={"page": v}
            )
        return v
    model_config = ConfigDict(
       from_attributes=True,
    )