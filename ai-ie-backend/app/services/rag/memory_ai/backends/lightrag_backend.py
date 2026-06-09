from typing import AsyncIterator, List, Any
from ..repositories.base import ChatRecord
from .base import IChatBackend


class LightRAGBackend(IChatBackend):
    """把 memory_ai 的会话历史喂给 LightRAG。"""

    def __init__(
        self,
        rag: Any,
        *,
        mode: str = "hybrid",          # naive / local / global / hybrid / mix
        history_turns: int = 3,
        top_k: int = 60,
    ):
        from lightrag import QueryParam  # 延迟 import
        self._rag = rag
        self._QueryParam = QueryParam
        self._mode = mode
        self._history_turns = history_turns
        self._top_k = top_k

    @staticmethod
    def _history_to_lightrag(history: List[ChatRecord]) -> list[dict]:
        return [{"role": r.role, "content": r.content} for r in history]

    def _build_param(self, history: List[ChatRecord], stream: bool):
        return self._QueryParam(
            mode=self._mode,
            history_turns=self._history_turns,
            top_k=self._top_k,
            stream=stream,
            conversation_history=self._history_to_lightrag(history),  # ← 关键
        )

    async def chat(self, *, query, history, system_prompt):
        param = self._build_param(history, stream=False)
        result = await self._rag.aquery(query, param=param, system_prompt=system_prompt)
        return str(result)

    async def stream_chat(self, *, query, history, system_prompt):
        param = self._build_param(history, stream=True)
        result = await self._rag.aquery(query, param=param, system_prompt=system_prompt)
        # stream=True 时 aquery 返回 AsyncIterator；stream=False 时返回 str
        async for chunk in result:
            yield chunk
