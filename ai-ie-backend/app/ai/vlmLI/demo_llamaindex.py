import asyncio

from app.ai.vlmLI.processor import query_file, query_folder


async def demo_single_file():
    """演示：解析单个文件，并基于解析结果做 LlamaIndex 问答。"""
    result = await query_file(
        file_path="E:/录音文件/录音文件/1蔡小姐/20260505_151407详和开会2.m4a",
        question="请总结这个语音内容",
        mode="audio",
        similarity_top_k=3,
    )

    print("单文件 LlamaIndex 问答结果：")
    print(result["answer"])


async def demo_folder():
    """演示：解析整个文件夹，并基于多个文件做 LlamaIndex 问答。"""
    result = await query_folder(
        folder_path="D:/getsoftAI/rag/ai-ie-backend/app/services/rag/data",
        question="这些文件主要讲了什么？请按来源概括。",
        mode="auto",
        recursive=True,
        similarity_top_k=5,
    )

    print("文件夹 LlamaIndex 问答结果：")
    print(result["answer"])


async def main():
    # 默认只跑单文件示例。需要测试文件夹时，取消下一行注释即可。
    await demo_single_file()
    # await demo_folder()


if __name__ == "__main__":
    asyncio.run(main())
