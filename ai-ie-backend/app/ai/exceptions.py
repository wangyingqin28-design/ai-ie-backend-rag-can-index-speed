from typing import Any, Optional


class MemoryAIError(Exception):
    """Unified exception for the AI memory module."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details is not None:
            return f"{self.message} | details={self.details}"
        return self.message
