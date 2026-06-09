import asyncio

from app.ai.vlmLI.processor import query_file, query_folder


TEST_FILE = "D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data/知识填写表-v2.xlsx"
TEST_IMAGE = "D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data/test.png"
TEST_AUDIO = r"E:\录音文件\录音文件\1蔡小姐\20260505_151407详和开会2.m4a"
TEST_FOLDER = "D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data"


PROMPTS = {
    "auto": "这里填写 auto 模式固定提示词",
    "ocr": "这里填写 ocr 模式固定提示词",
    "recognize": "这里填写 recognize 模式固定提示词",
    "audio": "这里填写 audio 音频总结固定提示词",
}


def get_question_by_prompt_type(
    prompt_type: str,
    use_default_prompt: bool,
    question: str | None = None,
) -> str:
    if use_default_prompt:
        default_prompt = PROMPTS.get(prompt_type)

        if not default_prompt:
            raise ValueError(f"prompt_type={prompt_type} 没有配置固定提示词")

        return default_prompt

    if not question:
        raise ValueError("use_default_prompt=False 时，必须手动传入 question")

    return question


async def run_query_demo(
    target_type: str = "file",
    mode: str = "auto",
    prompt_type: str | None = None,
    file_path: str | None = None,
    folder_path: str | None = None,
    use_default_prompt: bool = True,
    question: str | None = None,
    recursive: bool = True,
    similarity_top_k: int = 3,
):
    """
    mode:
    - auto
    - parse
    - ocr
    - recognize

    prompt_type:
    - auto
    - ocr
    - recognize
    - audio

    prompt_type 不传时，默认等于 mode。
    音频场景建议传 prompt_type="audio"。
    """
    final_prompt_type = prompt_type or mode

    final_question = get_question_by_prompt_type(
        prompt_type=final_prompt_type,
        use_default_prompt=use_default_prompt,
        question=question,
    )

    if target_type == "file":
        return await query_file(
            file_path=file_path or TEST_FILE,
            question=final_question,
            mode=mode,
            similarity_top_k=similarity_top_k,
        )

    if target_type == "folder":
        return await query_folder(
            folder_path=folder_path or TEST_FOLDER,
            question=final_question,
            mode=mode,
            recursive=recursive,
            similarity_top_k=similarity_top_k,
        )

    raise ValueError(f"不支持的 target_type: {target_type}")


async def main():
    result = await run_query_demo(
        target_type="file",
        mode="parse",
        prompt_type="audio",
        file_path=TEST_AUDIO,
        use_default_prompt=True,
        similarity_top_k=3,
    )

    print(result["answer"])


if __name__ == "__main__":
    asyncio.run(main())