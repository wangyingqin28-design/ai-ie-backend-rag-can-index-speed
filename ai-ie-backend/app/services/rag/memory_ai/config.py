from dataclasses import dataclass
from typing import Optional


@dataclass
class AIConfig:
    model: str
    api_key: str
    base_url: str

    context_window: int = 128000
    timeout: float = 120.0
    is_chat_model: bool = True

    memory_token_limit: int = 3000
    history_token_limit: int = 6000

    system_prompt: Optional[str] = None
    default_session_title: str = "新对话"
