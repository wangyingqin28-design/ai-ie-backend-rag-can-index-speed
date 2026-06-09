from typing import List, Optional

from llama_index.core.base.llms.types import ChatMessage
from llama_index.core.chat_engine import ContextChatEngine, SimpleChatEngine
from llama_index.core.llms import LLM
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.retrievers import BaseRetriever

from app.ai.repositories.schemas import ChatRecord
from app.ai.rag.base import IChatBackend


class LlamaIndexBackend(IChatBackend):
    """LlamaIndex backend for simple chat or retriever-augmented chat."""

    def __init__(
        self,
        llm: LLM,
        *,
        retriever: Optional[BaseRetriever] = None,
        node_postprocessors: Optional[List[BaseNodePostprocessor]] = None,
        memory_token_limit: int = 3000,
        context_template: Optional[str] = None,
    ):
        self._llm = llm
        self._retriever = retriever
        self._node_postprocessors = node_postprocessors or []
        self._memory_token_limit = memory_token_limit
        self._context_template = context_template

    def _build_engine(self, history: List[ChatRecord], system_prompt: str):
        memory = ChatMemoryBuffer.from_defaults(token_limit=self._memory_token_limit)
        for record in history:
            memory.put(ChatMessage(role=record.role, content=record.content))

        if self._retriever is not None:
            return ContextChatEngine.from_defaults(
                retriever=self._retriever,
                llm=self._llm,
                memory=memory,
                system_prompt=system_prompt,
                context_template=self._context_template,
                node_postprocessors=self._node_postprocessors,
            )

        return SimpleChatEngine.from_defaults(
            llm=self._llm,
            memory=memory,
            system_prompt=system_prompt,
        )

    async def chat(self, *, query, history, system_prompt):
        engine = self._build_engine(history, system_prompt)
        response = await engine.achat(query)
        return str(response.response)

    async def stream_chat(self, *, query, history, system_prompt):
        engine = self._build_engine(history, system_prompt)
        response = await engine.astream_chat(query)
        async for token in response.async_response_gen():
            yield token
