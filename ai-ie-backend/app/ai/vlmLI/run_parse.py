import asyncio

from app.ai.vlmLI.processor import process_file, process_folder


TEST_FILE = "D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data/知识填写表-v2.xlsx"
TEST_IMAGE = "D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data/test.png"
TEST_FOLDER = "D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data"


async def run_parse_demo(
    target_type: str = "file",
    mode: str = "parse",
    file_path: str | None = None,
    folder_path: str | None = None,
    recursive: bool = True,
):
    """
    只做解析/识别，不做问答，所以不需要 question。

    target_type:
    - file
    - folder

    mode:
    - auto
    - parse
    - ocr
    - recognize
    """
    if target_type == "file":
        return await process_file(
            file_path=file_path or TEST_FILE,
            mode=mode,
        )

    if target_type == "folder":
        return await process_folder(
            folder_path=folder_path or TEST_FOLDER,
            mode=mode,
            recursive=recursive,
        )

    raise ValueError(f"不支持的 target_type: {target_type}")


async def main():
    result = await run_parse_demo(
        target_type="file",
        mode="parse",
        file_path=TEST_FILE,
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())