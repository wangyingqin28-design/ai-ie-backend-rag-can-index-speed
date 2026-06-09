import base64
import mimetypes

from lightrag.llm.openai import openai_complete_if_cache
from app.config import Config
from app.ai.prompts import OCR_PROMPT, IMAGE_PROMPT
config = Config()
def image_to_base64(image_path: str) -> tuple[str, str]:
    mime_type, _ = mimetypes.guess_type(image_path)

    if not mime_type:
        mime_type = "image/jpeg"

    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    return image_base64, mime_type


def build_image_messages(image_base64: str, mime_type: str, prompt: str):
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}",
                    },
                },
            ],
        }
    ]


async def call_vision_model(image_path: str, prompt: str):
    image_base64, mime_type = image_to_base64(image_path)

    messages = build_image_messages(
        image_base64=image_base64,
        mime_type=mime_type,
        prompt=prompt,
    )

    return await openai_complete_if_cache(
        config.VISION_MODEL,
        "",
        messages=messages,
        api_key=config.embedding_service_api_key,
        base_url=config.embedding_service_url,
    )


async def recognize_image(image_path: str):
    prompt = IMAGE_PROMPT

    return await call_vision_model(image_path, prompt)


async def ocr_image(image_path: str):
    prompt =OCR_PROMPT

    return await call_vision_model(image_path, prompt)