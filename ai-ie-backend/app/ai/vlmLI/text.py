import asyncio
import os

from app.ai.vlmLI.processor import  index_folder_to_qdrant


TEST_FILE = "D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data/知识填写表-v2.xlsx"
TEST_FOLDER = "E:/录音文件/录音文件/5李科杨"
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

async def main():
    # result = await index_file_to_qdrant(
    #     file_path=TEST_FILE,
    #     mode="audio",
    #     collection_name="vlmcopy_default",
    #     kb_id="default",
    # )
    #
    # print(result)

    #文件夹批量入库
    result = await index_folder_to_qdrant(
        folder_path=TEST_FOLDER,
        mode="audio",
        recursive=True,
        collection_name="vlmcopy",
        kb_id="default",
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())