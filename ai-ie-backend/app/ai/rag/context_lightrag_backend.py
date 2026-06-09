from typing import Optional

from lightrag import QueryParam

from app.ai.rag.base import IChatBackend
from app.ai.rag.lightrag_factory import build_lightrag_llm_func
from app.ai.rag.lightrag_retrieval import (
    clear_query_cache,
    format_retrieval_context,
    retrieve_context,
)


FINAL_ANSWER_RULES = (
    "请严格依据下面提供的检索结果回答。\n"
    "1. 只能依据检索到的 chunks、entities、relationships 回答，不要自行补充外部常识。\n"
    "2. 如果 chunks 中已经出现与问题直接匹配的原文，优先采用或紧贴原文给出结论。\n"
    "3. 只有在检索结果里完全没有相关事实时，才回答没有找到。\n"
    "4. 回答格式固定为两句话：第一句给明确结论；第二句以“依据：”开头，引用或紧贴原文事实。"
)


class ContextLightRAGBackend(IChatBackend):
    """LightRAG backend that explicitly retrieves context before final answering."""

    def __init__(
        self,
        rag,
        config,
        *,
        working_dir: Optional[str] = None,
        query_param: Optional[QueryParam] = None,
        final_answer_rules: str = FINAL_ANSWER_RULES,
        clear_cache: bool = False,
    ):
        self._rag = rag
        self._llm_model_func = build_lightrag_llm_func(config)
        self._working_dir = working_dir
        self._query_param = query_param
        self._final_answer_rules = final_answer_rules
        self._clear_cache = clear_cache

    async def chat(self, *, query, history, system_prompt):
        if self._clear_cache and self._working_dir:
            clear_query_cache(self._working_dir, question=query)

        retrieval_result = await retrieve_context(
            self._rag,
            query,
            query_param=self._query_param,
        )
        context = format_retrieval_context(retrieval_result)
        prompt = (
            f"{self._final_answer_rules}\n\n"
            f"[Conversation History]\n{self._format_history(history)}\n\n"
            f"[Question]\n{query}\n\n"
            f"[Retrieved Context]\n{context}\n"
        )
        return await self._llm_model_func(prompt=prompt, system_prompt=system_prompt)

    async def stream_chat(self, *, query, history, system_prompt):
        yield await self.chat(query=query, history=history, system_prompt=system_prompt)

    @staticmethod
    def _format_history(history) -> str:
        if not history:
            return "None"
        return "\n".join(f"{record.role}: {record.content}" for record in history[-12:])
