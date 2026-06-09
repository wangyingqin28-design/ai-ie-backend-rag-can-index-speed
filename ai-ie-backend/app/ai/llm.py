from llama_index.llms.openai_like import OpenAILike

from .config import AIConfig


def build_llm(config: AIConfig) -> OpenAILike:
    """Build an OpenAI-compatible LlamaIndex LLM instance."""

    return OpenAILike(
        model=config.model,
        api_base=config.base_url,
        api_key=config.api_key,
        context_window=config.context_window,
        is_chat_model=config.is_chat_model,
        timeout=config.timeout,
    )
