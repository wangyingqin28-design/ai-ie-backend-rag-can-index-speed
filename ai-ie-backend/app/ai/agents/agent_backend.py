from typing import AsyncIterator, List

from llama_index.core.agent import ReActAgent
from llama_index.core.base.llms.types import ChatMessage
from llama_index.core.llms import LLM

from app.ai.repositories.schemas import ChatRecord
from app.ai.rag.base import IChatBackend


class AgentBackend(IChatBackend):
    """Agent backend that can be plugged into ChatAI like any other backend."""

    def __init__(self, llm: LLM, tools: list, *, verbose: bool = False):
        self._llm = llm
        self._tools = tools
        self._verbose = verbose

    @staticmethod
    def _to_chat_messages(history: List[ChatRecord]) -> list[ChatMessage]:
        return [
            ChatMessage(role=record.role, content=record.content)
            for record in history
        ]

    async def chat(self, *, query, history, system_prompt):
        agent = ReActAgent.from_tools(
            tools=self._tools,
            llm=self._llm,
            verbose=self._verbose,
            system_prompt=system_prompt,
        )
        response = await agent.achat(
            query,
            chat_history=self._to_chat_messages(history),
        )
        return str(response)

    async def stream_chat(self, *, query, history, system_prompt) -> AsyncIterator[str]:
        result = await self.chat(
            query=query,
            history=history,
            system_prompt=system_prompt,
        )
        yield result
