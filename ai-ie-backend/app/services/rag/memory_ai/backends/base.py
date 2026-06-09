from abc import ABC, abstractmethod
from typing import AsyncIterator, List
from ..repositories.base import ChatRecord


class IChatBackend(ABC):
    """对话生成后端抽象。决定'如何从历史+当前问题生成回复'。"""

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
