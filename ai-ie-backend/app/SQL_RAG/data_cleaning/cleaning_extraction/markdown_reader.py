# -*- coding: utf-8 -*-
"""基于 LlamaIndex 官方 SimpleDirectoryReader/Document 的 Markdown 读取。"""

# 修改日期：2026-06-01 13:29:35。
# 修改理由：把单 Markdown 文件读取升级为文件/目录多 Markdown 批量读取，支撑全局多文档入库。

# 导入路径类型，用于处理输入文件。
from pathlib import Path

# 导入 LlamaIndex 官方 SimpleDirectoryReader。
from llama_index.core import SimpleDirectoryReader
# 导入 LlamaIndex 官方 Document 结构。
from llama_index.core.schema import Document

# 导入框架参考常量。
from common.constants import FRAMEWORK_REFERENCES
# 导入稳定哈希与 ID 工具。
from common.utils import sha256_text, stable_id


def discover_markdown_input_paths(input_path: Path) -> list[Path]:
    # 把用户传入路径转换成绝对路径。
    source_path = input_path.expanduser().resolve()
    # 如果路径不存在，直接抛出明确异常。
    if not source_path.exists():
        # 抛出文件不存在错误。
        raise FileNotFoundError(f"输入路径不存在：{source_path}")
    # 单文件输入时校验 Markdown 后缀。
    if source_path.is_file():
        # 判断文件是否为 Markdown。
        if source_path.suffix.lower() not in {".md", ".markdown"}:
            # 抛出后缀错误。
            raise ValueError(f"输入文件不是 Markdown：{source_path}")
        # 返回单文件列表。
        return [source_path]
    # 目录输入时递归发现所有 Markdown 文件。
    markdown_paths = sorted(
        # 只保留 .md 和 .markdown 文件。
        path
        # 递归遍历目录。
        for path in source_path.rglob("*")
        # 判断文件类型和后缀。
        if path.is_file() and path.suffix.lower() in {".md", ".markdown"}
    )
    # 目录里没有 Markdown 时抛出明确异常。
    if not markdown_paths:
        # 抛出值错误。
        raise ValueError(f"输入目录下没有 Markdown 文档：{source_path}")
    # 返回排序后的 Markdown 文件列表，保证多机台执行结果稳定。
    return markdown_paths


def load_markdown_documents(input_path: Path) -> list[Document]:
    # 发现单文件或目录下的全部 Markdown 路径。
    markdown_paths = discover_markdown_input_paths(input_path)
    # 使用 LlamaIndex 官方 SimpleDirectoryReader 批量读取 Markdown 文件。
    documents = SimpleDirectoryReader(input_files=[str(path) for path in markdown_paths]).load_data()
    # LlamaIndex 读取不到内容时抛出错误。
    if not documents:
        # 抛出值错误。
        raise ValueError(f"LlamaIndex 未读取到 Markdown 文档：{input_path}")
    # 创建规范化后的 Document 列表。
    normalized_documents: list[Document] = []
    # 创建文件名到路径的兜底索引。
    source_name_index = {path.name: path for path in markdown_paths}
    # 遍历 LlamaIndex 读取出来的文档。
    for index, document in enumerate(documents, start=1):
        # 从 LlamaIndex metadata 读取源文件路径。
        metadata_source_path = document.metadata.get("file_path") or document.metadata.get("source_path")
        # metadata 中有源路径时优先使用。
        if metadata_source_path:
            # 规范化 metadata 源路径。
            source_path = Path(str(metadata_source_path)).expanduser().resolve()
        # metadata 中只有文件名时从兜底索引恢复路径。
        elif document.metadata.get("file_name") in source_name_index:
            # 使用文件名映射路径。
            source_path = source_name_index[str(document.metadata.get("file_name"))]
        # metadata 不完整时按读取顺序兜底。
        else:
            # 使用输入文件顺序兜底。
            source_path = markdown_paths[min(index - 1, len(markdown_paths) - 1)]
        # 获取官方 Document 文本内容。
        text = document.get_content()
        # 计算内容哈希。
        source_hash = sha256_text(text)
        # 生成稳定 document_id。
        document_id = stable_id("qadoc", str(source_path), index, source_hash)
        # 更新官方 Document 的稳定 ID。
        document.id_ = document_id
        # 写入源文件绝对路径元数据。
        document.metadata["source_path"] = str(source_path)
        # 写入源文件名元数据。
        document.metadata["source_name"] = source_path.name
        # 写入源内容哈希元数据。
        document.metadata["source_hash"] = source_hash
        # 写入 LlamaIndex 框架参考元数据。
        document.metadata["framework_references"] = FRAMEWORK_REFERENCES
        # 追加规范化文档。
        normalized_documents.append(document)
    # 返回 LlamaIndex 官方 Document 列表。
    return normalized_documents
