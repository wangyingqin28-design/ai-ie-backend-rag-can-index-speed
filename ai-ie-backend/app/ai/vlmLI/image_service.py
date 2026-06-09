import base64
import mimetypes

from app.config import Config
from app.ai.prompts import OCR_PROMPT, IMAGE_PROMPT
from .llm_client import chat_complete


config = Config()


def image_to_base64(image_path: str) -> tuple[str, str]:
    """读取本地图片并转换成视觉模型可接收的 base64 data URL 数据。"""
    mime_type, _ = mimetypes.guess_type(image_path)

    if not mime_type:
        mime_type = "image/jpeg"

    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    return image_base64, mime_type


def build_image_messages(image_base64: str, mime_type: str, prompt: str):
    """构造 OpenAI 兼容多模态 messages，包含文本 prompt 和图片内容。"""
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
    """调用视觉模型；图片识别和图片 OCR 都复用这个底层方法。"""
    image_base64, mime_type = image_to_base64(image_path)

    messages = build_image_messages(
        image_base64=image_base64,
        mime_type=mime_type,
        prompt=prompt,
    )

    return await chat_complete(
        model=config.VISION_MODEL,
        messages=messages,
    )


async def recognize_image(image_path: str):
    """图片理解：描述图片中的对象、场景、关系和重要细节。"""
    prompt = IMAGE_PROMPT

    return await call_vision_model(image_path, prompt)


async def ocr_image(image_path: str):
    """图片 OCR：只提取图片中的可见文字。"""
    prompt = OCR_PROMPT

    return await call_vision_model(image_path, prompt)
