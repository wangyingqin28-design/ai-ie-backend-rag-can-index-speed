from typing import Any


def build_lightrag_search_tool(rag: Any):
    """Build a LlamaIndex FunctionTool for knowledge-base search."""

    from llama_index.core.tools import FunctionTool

    async def search_knowledge_base(question: str) -> str:
        """Search the knowledge base for product, FAQ, policy, or process facts."""

        result = await rag.aquery(question)
        return str(result)

    return FunctionTool.from_defaults(
        async_fn=search_knowledge_base,
        name="search_knowledge_base",
        description="查询企业知识库、产品资料、FAQ、规则制度等内容。",
    )
