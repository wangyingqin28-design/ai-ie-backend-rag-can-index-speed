from pathlib import Path
from typing import Iterable


def iter_markdown_files(data_dir: str | Path) -> Iterable[Path]:
    """Yield markdown files from a knowledge data directory."""

    root = Path(data_dir)
    if not root.exists():
        return []
    return sorted(root.glob("*.md"))


async def ingest_markdown_dir(rag, data_dir: str | Path) -> int:
    """Insert markdown files into a LightRAG-like instance.

    The rag object is expected to provide `ainsert(text, file_paths=[...])`.
    Returns the number of successfully submitted files.
    """

    count = 0
    for markdown_file in iter_markdown_files(data_dir):
        text = markdown_file.read_text(encoding="utf-8")
        await rag.ainsert(text, file_paths=[str(markdown_file)])
        count += 1
    return count
