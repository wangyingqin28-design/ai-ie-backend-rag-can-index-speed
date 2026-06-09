from pathlib import Path
from app.config import Config

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}

SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS | TEXT_EXTENSIONS | AUDIO_EXTENSIONS
config = Config()


def get_file_type(file_path: str) -> str:
    """根据文件后缀判断处理类型：image/document/text/unsupported。"""
    suffix = Path(file_path).suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        return "image"

    if suffix in DOCUMENT_EXTENSIONS:
        return "document"

    if suffix in TEXT_EXTENSIONS:
        return "text"

    if suffix in AUDIO_EXTENSIONS:
        return "audio"

    return "unsupported"


def validate_file(file_path: str) -> Path:
    """校验单文件路径，防止把不存在的路径或文件夹传入处理流程。"""
    file = Path(file_path)

    if not file.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if not file.is_file():
        raise IsADirectoryError(f"不是有效文件: {file_path}")

    return file


def get_supported_files(folder_path: str, recursive: bool = False) -> list[str]:
    """扫描文件夹并返回当前模块支持处理的文件列表。"""
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")

    if not folder.is_dir():
        raise NotADirectoryError(f"不是有效文件夹: {folder_path}")

    pattern = "**/*" if recursive else "*"

    # recursive=True 时使用 **/* 递归子目录；否则只读取当前目录一层。
    return [
        str(file)
        for file in folder.glob(pattern)
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
