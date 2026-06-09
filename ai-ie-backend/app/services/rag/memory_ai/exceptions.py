from typing import Any, Optional


class MemoryAIError(Exception):
    """memory_ai 模块统一异常类型，与项目特定的异常体系解耦。"""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details is not None:
            return f"{self.message} | details={self.details}"
        return self.message
