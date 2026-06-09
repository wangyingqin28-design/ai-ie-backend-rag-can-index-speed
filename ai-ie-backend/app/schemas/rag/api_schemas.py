from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
# 模型定义
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


# class ChatResponse(BaseModel):
#     response: str
#     session_id: str


class SessionListResponse(BaseModel):
    sessions: List[Dict[str, Any]]


class TitleUpdateRequest(BaseModel):
    """标题更新请求体"""
    new_title: str = Field(..., min_length=1, max_length=300, description="新标题内容")

class ExcelRequest(BaseModel):
    text: Any
    person_name: str


class ChatMessageResponse(BaseModel):
    """单条聊天消息的响应模型（不含时间戳）"""
    role: str
    content: str

class ChatHistoryResponse(BaseModel):
    """聊天历史记录的响应模型"""
    session_id: str
    messages: List[ChatMessageResponse]
    total_count: int