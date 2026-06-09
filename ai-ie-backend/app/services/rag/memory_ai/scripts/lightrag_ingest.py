"""一次性脚本：把 app/services/rag/data/ 下的 md 文档灌入 LightRAG 图谱。

用法：
    python -m scripts.lightrag_ingest

增量：新增文档后重跑即可（LightRAG 内部有 content hash 去重）。
"""
import asyncio
from pathlib import Path
from loguru import logger

from app.services.rag.memory_ai.scripts.Lightrag_step import init_lightrag

DATA_DIR = Path("D:/getsoftAI/rag/ai-ie-backend/app\services/rag/data")


async def main():
    rag = await init_lightrag()

    md_files = sorted(DATA_DIR.glob("*.md"))
    logger.info(f"发现 {len(md_files)} 个文档待灌入")

    for idx, md in enumerate(md_files, 1):
        text = md.read_text(encoding="utf-8")
        logger.info(f"[{idx}/{len(md_files)}] 灌入 {md.name}（{len(text)} 字）")
        try:
            # file_paths 用于溯源，可选
            await rag.ainsert(text, file_paths=[str(md)])
        except Exception as e:
            logger.exception(f"灌入失败 | {md.name}: {e}")

    logger.success("全部文档灌入完成")


if __name__ == "__main__":
    asyncio.run(main())
