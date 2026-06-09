from llama_index.llms.openai_like import OpenAILike

from .config import AIConfig


def build_llm(config: AIConfig) -> OpenAILike:
    """根据 AIConfig 构建 LLM 实例。

    注意：本函数不再写入 llama_index 的全局 Settings.llm，
    避免污染调用方进程内的其他 llama_index 用户。
    """
    return OpenAILike(
        model=config.model,
        api_base=config.base_url,
        api_key=config.api_key,
        context_window=config.context_window,
        is_chat_model=config.is_chat_model,
        timeout=config.timeout,
    )
