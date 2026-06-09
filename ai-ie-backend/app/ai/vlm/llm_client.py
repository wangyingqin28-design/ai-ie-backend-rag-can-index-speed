from lightrag.llm.openai import openai_complete_if_cache
from app.config import Config

config = Config()
async def llm_model_func(
    prompt,
    system_prompt=None,
    history_messages=None,
    **kwargs,
):
    history_messages = history_messages or []

    return await openai_complete_if_cache(
        config.LLM_MODEL,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        api_key=config.embedding_service_api_key,
        base_url=config.embedding_service_url,
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
    if messages:
        return await openai_complete_if_cache(
            config.VISION_MODEL,
            "",
            messages=messages,
            api_key=config.embedding_service_api_key,
            base_url=config.embedding_service_url,
            **kwargs,
        )

    if image_data:
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

        return await openai_complete_if_cache(
            config.VISION_MODEL,
            "",
            messages=message_list,
            api_key=config.embedding_service_api_key,
            base_url=config.embedding_service_url,
            **kwargs,
        )

    return await llm_model_func(
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        **kwargs,
    )