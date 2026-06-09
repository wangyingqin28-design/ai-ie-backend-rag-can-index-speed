from abc import ABC, abstractmethod
from typing import AsyncIterator, List

from app.ai.repositories.schemas import ChatRecord


class IChatBackend(ABC):
    """Generation backend used by ChatAI."""

    @abstractmethod
    async def chat(
        self,
        *,
        query: str,
        history: List[ChatRecord],
        system_prompt: str,
    ) -> str: ...

    @abstractmethod
    async def stream_chat(
        self,
        *,
        query: str,
        history: List[ChatRecord],
        system_prompt: str,
    ) -> AsyncIterator[str]: ...
