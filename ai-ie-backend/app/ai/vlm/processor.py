from typing import Literal

from .file_utils import get_file_type, get_supported_files, validate_file
from .image_service import recognize_image, ocr_image
from .document_service import process_document_to_rag, process_text_file


ProcessMode = Literal["auto", "recognize", "ocr", "rag"]


async def process_file(file_path: str, mode: ProcessMode = "auto"):
    file = validate_file(file_path)
    file_path = str(file)

    file_type = get_file_type(file_path)

    if file_type == "image":
        if mode == "ocr":
            result = await ocr_image(file_path)
        elif mode == "rag":
            result = await process_document_to_rag(
                file_path=file_path,
                parse_method="auto",
                query="这张图片里有什么？请总结这个图的内容。",
            )
        else:
            result = await recognize_image(file_path)

        return {
            "file_path": file_path,
            "file_name": file.name,
            "file_type": "image",
            "engine": "vision",
            "mode": mode,
            "result": result,
        }

    if file_type == "document":
        parse_method = "ocr" if mode == "ocr" else "auto"

        result = await process_document_to_rag(
            file_path=file_path,
            parse_method=parse_method,
            query="请总结这个文档的主要内容，如果其中图片、表格、公式表达的信息，也请解析。",
        )

        return {
            "file_path": file_path,
            "file_name": file.name,
            "file_type": "document",
            "engine": "docling",
            "mode": mode,
            "result": result,
        }

    if file_type == "text":
        result = await process_text_file(file_path)

        return {
            "file_path": file_path,
            "file_name": file.name,
            "file_type": "text",
            "engine": "text",
            "mode": mode,
            "result": result,
        }

    return {
        "file_path": file_path,
        "file_name": file.name,
        "file_type": "unsupported",
        "engine": "unsupported",
        "mode": mode,
        "error": "不支持的文件类型",
    }


async def process_folder(
    folder_path: str,
    mode: ProcessMode = "auto",
    recursive: bool = False,
):
    files = get_supported_files(folder_path, recursive=recursive)

    results = []

    for file_path in files:
        try:
            result = await process_file(
                file_path=file_path,
                mode=mode,
            )

            results.append({
                "success": True,
                **result,
            })

        except Exception as e:
            results.append({
                "success": False,
                "file_path": file_path,
                "mode": mode,
                "error": str(e),
            })

    return results