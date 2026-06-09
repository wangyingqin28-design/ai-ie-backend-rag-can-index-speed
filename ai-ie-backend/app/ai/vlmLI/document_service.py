from pathlib import Path
from typing import Any

from .llm_client import llm_model_func
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, OcrAutoOptions


def _safe_export_to_markdown(document: Any) -> str:
    """安全导出 Markdown；Docling 版本差异导致方法不存在时返回空字符串。"""
    if hasattr(document, "export_to_markdown"):
        return document.export_to_markdown()
    return ""


def _safe_export_to_dict(document: Any) -> dict[str, Any]:
    """安全导出结构化 dict；用于保留 Docling 的原始解析结构。"""
    if hasattr(document, "export_to_dict"):
        return document.export_to_dict()
    return {}


def build_docling_converter(parse_method: str = "auto") -> DocumentConverter:
    """创建 Docling 转换器，并按 parse_method 配置 PDF OCR 管线。"""
    pipeline_options = PdfPipelineOptions()

    # do_ocr=True 会启用 OCR；force_full_page_ocr=True 会强制整页 OCR。
    # 这对扫描版 PDF、图片型 PDF 最有用；普通 docx/xlsx 通常走原生解析。
    pipeline_options.do_ocr = parse_method == "ocr"
    pipeline_options.do_table_structure = True
    pipeline_options.do_formula_enrichment = True
    pipeline_options.generate_picture_images = True
    pipeline_options.generate_page_images = True

    if parse_method == "ocr":
        pipeline_options.ocr_options = OcrAutoOptions(
            lang=["ch_sim", "en"],
            force_full_page_ocr=True,
        )

    return DocumentConverter(
        format_options={
            # 当前 OCR 配置主要作用在 PDF 格式上；Word/Excel/PPT 仍由 Docling
            # 对应的原生后端处理。
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            ),
        }
    )


async def parse_document_with_docling(
    file_path: str,
    parse_method: str = "auto",
) -> dict[str, Any]:
    """使用 Docling 解析文档，并返回 markdown 与 json 两种结果。"""
    file = Path(file_path)
    #生成转换器
    converter = build_docling_converter(parse_method=parse_method)
    #得到DoclingDocument 对象
    result = converter.convert(str(file))

    document = result.document
    #后续用于 LlamaIndex 索引的文本，保留了标题、表格、公式等结构
    markdown = _safe_export_to_markdown(document)
    #备用接口
    document_json = _safe_export_to_dict(document)

    #markdown索引结果，parse_method读取模式
    return {
        "file_path": str(file),
        "file_name": file.name,
        "engine": "docling",
        "parse_method": parse_method,
        "markdown": markdown,
        "json": document_json,
    }


async def process_document_file(
    file_path: str,
    parse_method: str = "auto",
) -> dict[str, Any]:
    """文档解析入口，供 processor.py 调用。"""
    return await parse_document_with_docling(
        file_path=file_path,
        parse_method=parse_method,
    )

async def query_document_with_llamaindex(
    file_path: str,
    question: str,
    parse_method: str = "auto",
    similarity_top_k: int = 3,
) -> dict[str, Any]:
    """单文档问答：先用 Docling 解析，再把 markdown 交给 LlamaIndex 检索问答。"""
    parsed = await process_document_file(
        file_path=file_path,
        parse_method=parse_method,
    )
    # 延迟导入，避免只做文档解析时也强依赖 LlamaIndex。
    from .llamaindex_service import query_items_with_llamaindex

    result = query_items_with_llamaindex(
        items=[{
            "file_path": parsed["file_path"],
            "file_name": parsed["file_name"],
            "file_type": "document",
            "engine": parsed["engine"],
            "markdown": parsed["markdown"],
        }],
        question=question,
        similarity_top_k=similarity_top_k,
    )

    return {
        "file_path": parsed["file_path"],
        "file_name": parsed["file_name"],
        "engine": "docling+llamaindex",
        "parse_method": parse_method,
        **result,
    }


async def process_text_file(file_path: str) -> dict[str, str]:
    """读取纯文本类文件内容，例如 txt/md/csv/json。"""
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    return {
        "text": content,
    }
