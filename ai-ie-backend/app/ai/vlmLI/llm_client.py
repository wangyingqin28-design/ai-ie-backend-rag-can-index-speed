from typing import Any

from openai import AsyncOpenAI

from app.config import Config


config = Config()


def build_openai_client() -> AsyncOpenAI:
    """创建异步 OpenAI 兼容客户端，当前配置指向外部模型服务。"""
    return AsyncOpenAI(
        api_key=config.embedding_service_api_key,
        base_url=config.embedding_service_url,
    )


async def chat_complete(
    model: str,
    messages: list[dict[str, Any]],
    **kwargs,
) -> str:
    """通用聊天补全方法，文本模型和视觉模型最终都会走这里。"""
    client = build_openai_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        **kwargs,
    )

    return response.choices[0].message.content or ""


async def llm_model_func(
    prompt,
    system_prompt=None,
    history_messages=None,
    **kwargs,
):
    """普通文本大模型调用，供文本摘要、兜底回答等场景使用。"""
    history_messages = history_messages or []
    messages = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt,
        })

    messages.extend(history_messages)
    messages.append({
        "role": "user",
        "content": prompt,
    })

    return await chat_complete(
        model=config.LLM_MODEL,
        messages=messages,
        **kwargs,
    )


async def vision_model_func(
    prompt,
    system_prompt=None,
    history_messages=None,
    image_data=None,
    messages=None,
    **kwargs,
):
    """视觉模型调用，兼容直接传 messages 或传单张 base64 图片两种形式。"""
    if messages:
        # 上游已经构造好多模态 messages 时，直接透传给模型。
        return await chat_complete(
            model=config.VISION_MODEL,
            messages=messages,
            **kwargs,
        )

    if image_data:
        # RAG/解析框架常见输入是 image_data，这里转换成 OpenAI 多模态格式。
        message_list = []

        if system_prompt:
            message_list.append({
                "role": "system",
                "content": system_prompt,
            })

        message_list.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}",
                    },
                },
            ],
        })

        return await chat_complete(
            model=config.VISION_MODEL,
            messages=message_list,
            **kwargs,
        )

    # 没有图片输入时，退化为普通文本模型调用。
    return await llm_model_func(
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        **kwargs,
    )
