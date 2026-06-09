import os
from typing import Literal

from .audio_service import transcribe_audio
from .document_service import process_document_file, process_text_file
from .file_utils import get_file_type, get_supported_files, validate_file
from .image_service import ocr_image, recognize_image

# 统一的文件处理模式：
# auto      默认模式，按文件类型自动选择处理方式
# recognize 图片理解模式，主要用于图片内容描述
# ocr       OCR 模式，图片提取文字；文档强制走 OCR 解析
# parse     解析模式，主要用于文档/文本的原始解析
# ProcessMode = Literal["auto", "recognize", "ocr", "parse"]
# QueryMode = Literal["auto", "recognize", "ocr", "parse"]
Mode = Literal["auto", "recognize", "ocr", "parse","audio"]


async def process_file(file_path: str, mode: Mode = "auto"):
    """处理单个文件，并按文件后缀自动分发到图片、文档或文本处理链路。"""
    #验证文件是否存在
    file = validate_file(file_path)
    #把 Path 对象转成字符串，后面传给其他函数用。
    file_path = str(file)
    #第二步：判断文件类型
    file_type = get_file_type(file_path)

    if file_type == "image":
        # 图片分两类：ocr 只读文字；其他模式做图片内容理解。
        if mode == "ocr":
            result = await ocr_image(file_path)
            engine = "vision_ocr"
        else:
            result = await recognize_image(file_path)
            engine = "vision"

        return {
            "success": True,
            "file_path": file_path,
            "file_name": file.name,
            "file_type": "image",
            "engine": engine,
            "mode": mode,
            "result": result,
        }

    if file_type == "document":
        # 文档由 Docling 解析。mode=ocr 时会启用 Docling 的 OCR 管线，
        # 适合扫描版 PDF、图片型 PDF；普通 Word/PDF 一般用 auto。
        parse_method = "ocr" if mode == "ocr" else "auto"#修改为ocr则为pdf和图片，auto则为文档

        result = await process_document_file(
            file_path=file_path,
            parse_method=parse_method,
        )

        return {
            "success": True,
            "file_path": file_path,
            "file_name": file.name,
            "file_type": "document",
            "engine": "docling_ocr" if parse_method == "ocr" else "docling",
            "mode": mode,
            "parse_method": parse_method,
            "result": result,
        }
    if file_type == "audio":
        result = await transcribe_audio(file_path)

        return {
            "success": True,
            "file_path": file_path,
            "file_name": file.name,
            "file_type": "audio",
            "engine": "audio_asr",
            "mode": mode,
            "result": result,
        }

    if file_type == "text":
        # txt/md/csv/json 等文本文件不需要 Docling，直接读取文本内容。
        result = await process_text_file(file_path)

        return {
            "success": True,
            "file_path": file_path,
            "file_name": file.name,
            "file_type": "text",
            "engine": "text",
            "mode": mode,
            "result": result,
        }

    return {
        "success": False,
        "file_path": file_path,
        "file_name": file.name,
        "file_type": "unsupported",
        "engine": "unsupported",
        "mode": mode,
        "error": "Unsupported file type",
    }


async def process_folder(
    folder_path: str,
    mode: Mode = "auto",
    recursive: bool = False,
):
    """批量处理文件夹下的支持文件；recursive=True 时递归处理子目录。"""
    files = get_supported_files(folder_path, recursive=recursive)#返回文件列表
    results = []

    for file_path in files:
        try:
            result = await process_file(
                file_path=file_path,
                mode=mode,
            )
            results.append(result)

        except Exception as e:
            results.append({
                "success": False,
                "file_path": file_path,
                "mode": mode,
                "error": str(e),
            })

    return {
        "success": True,
        "folder_path": folder_path,
        "mode": mode,
        "recursive": recursive,
        "total": len(files),
        "results": results,
    }


def _to_index_item(processed: dict) -> dict:
    """把 process_file 的结果转换成 LlamaIndex 可以索引的统一文本结构。"""
    result = processed.get("result")

    if processed.get("file_type") == "document" and isinstance(result, dict):
        # 文档解析结果优先使用 Docling 导出的 markdown，结构更适合切块和问答。
        return {
            "file_path": processed.get("file_path", ""),
            "file_name": processed.get("file_name", ""),
            "file_type": "document",
            "engine": processed.get("engine", ""),
            "markdown": result.get("markdown", ""),
        }

    if processed.get("file_type") == "text" and isinstance(result, dict):
        # 文本文件的内容保存在 result["text"]。
        return {
            "file_path": processed.get("file_path", ""),
            "file_name": processed.get("file_name", ""),
            "file_type": "text",
            "engine": processed.get("engine", ""),
            "text": result.get("text", ""),
        }
    if processed.get("file_type") == "audio" and isinstance(result, dict):
        # 返回语音文本
        return {
            "file_path": processed.get("file_path", ""),
            "file_name": processed.get("file_name", ""),
            "file_type": "audio",
            "engine": processed.get("engine", ""),
            "text": result.get("text", ""),
        }

    if processed.get("file_type") == "image":
        # 图片识别/OCR 返回的是字符串，直接作为可索引文本。
        return {
            "file_path": processed.get("file_path", ""),
            "file_name": processed.get("file_name", ""),
            "file_type": "image",
            "engine": processed.get("engine", ""),
            "text": str(result or ""),
        }

    return {
        "file_path": processed.get("file_path", ""),
        "file_name": processed.get("file_name", ""),
        "file_type": processed.get("file_type", ""),
        "engine": processed.get("engine", ""),
        "text": "",
    }


async def query_file(
    file_path: str,
    question: str,
    mode: Mode = "auto",
    similarity_top_k: int = 3,
):

    """
    先调用 process_file 获取解析结果。
    调用 _to_index_item 转换。
    最后使用 query_items_with_llamaindex 进行检索和生成答案。
    延迟导入 llamaindex_service，避免普通解析时加载问答依赖。
    """
    # 延迟导入：只有真正做问答时才加载 LlamaIndex，避免普通解析也依赖问答组件。
    from .llamaindex_service import query_items_with_llamaindex

    processed = await process_file(
        file_path=file_path,
        mode=mode,
    )

    if not processed.get("success"):
        # 不支持的文件或解析失败时，不继续进入 LlamaIndex。
        return {
            "success": False,
            "scope": "file",
            "processed": processed,
            "error": processed.get("error", "File processing failed"),
        }

    item = _to_index_item(processed)

    answer = query_items_with_llamaindex(
        items=[item],
        question=question,
        similarity_top_k=similarity_top_k,
    )

    return {
        "success": True,
        "scope": "file",
        "processed": processed,
        **answer,
    }


async def query_folder(
    folder_path: str,
    question: str,
    mode: Mode = "auto",
    recursive: bool = False,
    similarity_top_k: int = 3,
):
    """先解析文件夹中的所有支持文件，再用 LlamaIndex 做多文件问答。"""
    # 延迟导入：文件夹只解析时不加载 LlamaIndex。
    from .llamaindex_service import query_items_with_llamaindex

    parsed = await process_folder(
        folder_path=folder_path,
        mode=mode,
        recursive=recursive,
    )

    # 只把成功处理的文件送入索引，失败文件会保留在 process_folder 的结果中。
    success_results = [
        item for item in parsed["results"]
        if item.get("success")
    ]

    items = [
        _to_index_item(item)
        for item in success_results
    ]

    answer = query_items_with_llamaindex(
        items=items,
        question=question,
        similarity_top_k=similarity_top_k,
    )

    return {
        "success": True,
        "scope": "folder",
        "folder_path": folder_path,
        "recursive": recursive,
        "total": parsed["total"],
        "processed_total": len(success_results),
        **answer,
    }
async def index_file_to_qdrant(
    file_path: str,
    mode: Mode = "auto",
    collection_name: str = "vlmcopy_default",
    kb_id: str = "default",
    file_id: str | None = None,
):
    """
    单文件解析后写入 Qdrant 混合索引。
    只负责建索引，不负责查询。
    """
    from .vector_index_service import upsert_items_to_qdrant

    processed = await process_file(
        file_path=file_path,
        mode=mode,
    )

    if not processed.get("success"):
        return {
            "success": False,
            "error": processed.get("error", "文件处理失败"),
            "processed": processed,
        }

    item = _to_index_item(processed)
    item["kb_id"] = kb_id
    item["file_id"] = file_id or processed.get("file_name", "")
    item["mode"] = mode

    result = upsert_items_to_qdrant(
        items=[item],
        collection_name=collection_name,
    )

    return {
        "success": True,
        "scope": "file",
        "processed": processed,
        **result,
    }


async def index_folder_to_qdrant(
    folder_path: str,
    mode: Mode = "auto",
    recursive: bool = True,
    collection_name: str = "vlmcopy_default",
    kb_id: str = "default",
):
    """
    文件夹批量解析后写入 Qdrant 混合索引。
    只负责建索引，不负责查询。
    """
    from .vector_index_service import upsert_items_to_qdrant

    parsed = await process_folder(
        folder_path=folder_path,
        mode=mode,
        recursive=recursive,
    )

    success_results = [
        item for item in parsed["results"]
        if item.get("success")
    ]

    items = []

    for processed in success_results:
        item = _to_index_item(processed)
        item["kb_id"] = kb_id
        item["file_id"] = processed.get("file_name", "")
        item["mode"] = mode
        items.append(item)

    result = upsert_items_to_qdrant(
        items=items,
        collection_name=collection_name,
    )

    return {
        "success": True,
        "scope": "folder",
        "folder_path": folder_path,
        "total": parsed["total"],
        "processed_total": len(success_results),
        **result,
    }
