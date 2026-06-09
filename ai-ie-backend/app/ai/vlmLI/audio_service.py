from openai import OpenAI

from app.config import Config


config = Config()



def build_audio_client() -> OpenAI:
    return OpenAI(
        api_key=config.embedding_service_api_key,
        base_url=config.embedding_service_url,
    )


async def transcribe_audio(audio_path: str) -> dict:
    """
    音频转文字。
    当前使用硅基流动 OpenAI 兼容接口：
    model = FunAudioLLM/SenseVoiceSmall
    """
    client = build_audio_client()

    with open(audio_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=config.AUDIO_TRANSCRIPTION_MODEL,
            file=audio_file,
        )

    return {
        "text": result.text,
        "model": config.AUDIO_TRANSCRIPTION_MODEL,
    }