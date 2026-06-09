from pathlib import Path
from app.config import Config

config = Config()
def get_file_type(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()

    if suffix in config.IMAGE_EXTENSIONS:
        return "image"

    if suffix in config.DOCUMENT_EXTENSIONS:
        return "document"

    if suffix in config.TEXT_EXTENSIONS:
        return "text"

    return "unsupported"


def validate_file(file_path: str) -> Path:
    file = Path(file_path)

    if not file.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if not file.is_file():
        raise IsADirectoryError(f"不是有效文件: {file_path}")

    return file


def get_supported_files(folder_path: str, recursive: bool = False) -> list[str]:
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")

    if not folder.is_dir():
        raise NotADirectoryError(f"不是有效文件夹: {folder_path}")

    pattern = "**/*" if recursive else "*"

    return [
        str(file)
        for file in folder.glob(pattern)
        if file.is_file() and file.suffix.lower() in config.SUPPORTED_EXTENSIONS
    ]