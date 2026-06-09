# -*- coding: utf-8 -*-
"""基于 LlamaIndex TransformComponent 的 Markdown 清洗与章节提取。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：新增“问答强相关成对之后再清洗”的官方 IngestionPipeline 清洗入口，保留旧章节清洗函数兼容历史调用。

# 导入正则库，用于清洗和解析同类 Markdown 问答格式。
import re
# 导入任意类型标注。
from typing import Any, Sequence

# 导入 LlamaIndex 官方 IngestionPipeline。
from llama_index.core.ingestion import IngestionPipeline
# 导入 LlamaIndex 官方 BaseNode/TextNode/TransformComponent。
from llama_index.core.schema import BaseNode, TextNode, TransformComponent

# 导入稳定哈希与 ID 工具。
from common.utils import sha256_text, stable_id


def normalize_markdown_text(text: str) -> str:
    # 统一全角空格和不可见空白。
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    # 移除 Markdown 图片引用。
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", " ", text)
    # 保留 Markdown 链接文字，删除链接 URL。
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    # 移除表情和非业务符号，保留中文、英文、数字和常见业务标点。
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9，。！？；：、,.!?;:()\[\]（）/%+\-*=年月日号块元张个件小时分钟款单价_\s]", " ", text)
    # 删除常见英文口语占位词。
    text = re.sub(r"\b(ok|OK|Okay|Yes|No|Yeah)\b", " ", text)
    # 把连续空白压缩成单个空格。
    text = re.sub(r"\s+", " ", text)
    # 去掉句首多余标点。
    text = re.sub(r"^[\s.。；;，,]+", "", text)
    # 返回清洗后文本。
    return text.strip()


def split_markdown_sentences(text: str) -> list[str]:
    # 把换行转换成句号，保留转写文档自然边界。
    text = re.sub(r"[\r\n]+", "。", text)
    # 按中英文句末标点切成句子。
    parts = re.findall(r"[^。！？!?；;]+[。！？!?；;]?", text)
    # 保留句末标点，因为 LlamaIndex SemanticSplitterNodeParser 会按返回句子拼回节点文本。
    sentences = [part.strip(" ，,") for part in parts if len(part.strip(" ，,。；;!?！？")) >= 4]
    # 返回句子列表。
    return sentences


class MarkdownQuestionAnswerCleaner(TransformComponent):
    # LlamaIndex 官方 TransformComponent 入口，接收 Document/BaseNode，返回 TextNode。
    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> Sequence[BaseNode]:
        # 创建清洗后的章节节点列表。
        cleaned_nodes: list[TextNode] = []
        # 遍历 LlamaIndex 传入的文档节点。
        for source_node in nodes:
            # 获取源文档文本。
            source_text = source_node.get_content()
            # 解析同类 Markdown 问答章节。
            sections = self._parse_sections(source_text)
            # 如果没有标准章节，则把全文作为一个章节。
            if not sections:
                # 创建兜底章节。
                sections = [(0, "未分段问答文档", source_text)]
            # 遍历章节生成 LlamaIndex TextNode。
            for section_index, (audio_no, audio_title, raw_text) in enumerate(sections, start=1):
                # 清洗章节文本。
                cleaned_text = normalize_markdown_text(raw_text)
                # 过短章节跳过。
                if len(cleaned_text) < 20:
                    # 继续下一章节。
                    continue
                # 计算章节内容哈希。
                section_hash = sha256_text(cleaned_text)
                # 生成章节节点稳定 ID。
                node_id = stable_id("qasection", source_node.node_id, section_index, section_hash)
                # 继承源文档元数据。
                metadata = dict(source_node.metadata)
                # 写入源文档 ID。
                metadata["document_id"] = source_node.node_id
                # 写入音频段编号。
                metadata["audio_no"] = audio_no
                # 写入音频段标题。
                metadata["audio_title"] = audio_title
                # 写入章节序号。
                metadata["section_index"] = section_index
                # 写入章节内容哈希。
                metadata["section_hash"] = section_hash
                # 写入句子数量，方便后续调试。
                metadata["sentence_count"] = len(split_markdown_sentences(cleaned_text))
                # 构造 LlamaIndex 官方 TextNode。
                cleaned_nodes.append(TextNode(id_=node_id, text=cleaned_text, metadata=metadata))
        # 返回 LlamaIndex 节点列表。
        return cleaned_nodes

    # 解析 Markdown 中的“# 音频 N: 标题”章节。
    def _parse_sections(self, markdown_text: str) -> list[tuple[int, str, str]]:
        # 编译章节标题正则。
        header_re = re.compile(r"^#\s*音频\s*(\d+)\s*:\s*(.+?)\s*$")
        # 创建结果列表。
        sections: list[tuple[int, str, str]] = []
        # 当前章节编号。
        current_no: int | None = None
        # 当前章节标题。
        current_title = ""
        # 当前章节正文行。
        current_lines: list[str] = []
        # 逐行扫描 Markdown。
        for raw_line in markdown_text.splitlines():
            # 去掉行尾空白。
            line = raw_line.rstrip()
            # 尝试匹配音频标题。
            match = header_re.match(line)
            # 如果匹配到新标题，先保存旧章节。
            if match:
                # 当前已有章节时写入结果。
                if current_no is not None:
                    # 追加旧章节。
                    sections.append((current_no, current_title, "\n".join(current_lines).strip()))
                # 更新当前编号。
                current_no = int(match.group(1))
                # 更新当前标题。
                current_title = match.group(2).strip()
                # 清空正文缓存。
                current_lines = []
                # 继续下一行。
                continue
            # 跳过 Markdown 分隔线。
            if line.strip() == "---":
                # 继续下一行。
                continue
            # 跳过总标题。
            if line.startswith("# 音频原始转写"):
                # 继续下一行。
                continue
            # 只有进入章节后才收集正文。
            if current_no is not None:
                # 收集正文行。
                current_lines.append(line)
        # 收尾最后一个章节。
        if current_no is not None:
            # 追加最后章节。
            sections.append((current_no, current_title, "\n".join(current_lines).strip()))
        # 返回章节列表。
        return sections


class QAPairCleaningTransform(TransformComponent):
    # LlamaIndex 官方 TransformComponent 入口，接收已经成对的问答 TextNode。
    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> Sequence[BaseNode]:
        # 创建清洗后的问答对节点列表。
        cleaned_nodes: list[TextNode] = []
        # 遍历官方节点。
        for node in nodes:
            # 复制节点 metadata。
            metadata = dict(node.metadata)
            # 读取已通过官方 evaluator 绑定的问题。
            raw_question = str(metadata.get("raw_question") or metadata.get("question") or "")
            # 读取已通过官方 evaluator 绑定的答案。
            raw_answer = str(metadata.get("raw_answer") or metadata.get("answer") or "")
            # 清洗问题文本。
            clean_question = normalize_markdown_text(raw_question)
            # 清洗答案文本。
            clean_answer = normalize_markdown_text(raw_answer)
            # 问题或答案清洗后为空时跳过。
            if not clean_question or not clean_answer:
                # 继续下一节点。
                continue
            # 组装清洗后的问答文本。
            cleaned_text = f"问题：{clean_question}\n答案：{clean_answer}"
            # 写入清洗后的问题。
            metadata["question"] = clean_question
            # 写入清洗后的答案。
            metadata["answer"] = clean_answer
            # 写入清洗后的问题副本。
            metadata["cleaned_question"] = clean_question
            # 写入清洗后的答案副本。
            metadata["cleaned_answer"] = clean_answer
            # 写入下游 RAG 直接消费的完整答案契约字段。
            metadata["cleaned_text"] = cleaned_text
            metadata["answer_text"] = clean_answer
            metadata["source_excerpt"] = cleaned_text
            metadata["source_excerpt_full"] = cleaned_text
            metadata["llm_text"] = cleaned_text
            metadata["retrieval_text"] = cleaned_text
            # 写入官方管线清洗方法。
            metadata["cleaning_method"] = "llamaindex.IngestionPipeline.TransformComponent"
            # 写入修改时间。
            metadata["cleaning_modified_at"] = "2026-06-01 10:14:00"
            # 写入修改理由。
            metadata["cleaning_modified_reason"] = "问答已成对后再执行清洗，避免先分块导致问题答案错配。"
            # 构造新的 LlamaIndex 官方 TextNode，保留原问答对 ID。
            cleaned_nodes.append(TextNode(id_=node.node_id, text=cleaned_text, metadata=metadata))
        # 返回官方节点序列。
        return cleaned_nodes


def clean_markdown_documents_with_llamaindex(documents: list[BaseNode]) -> list[TextNode]:
    # 创建 LlamaIndex 官方 IngestionPipeline，清洗器作为官方 transformation 执行。
    pipeline = IngestionPipeline(transformations=[MarkdownQuestionAnswerCleaner()])
    # 运行 LlamaIndex 摄取管线。
    nodes = pipeline.run(documents=documents)
    # 返回 TextNode 列表。
    return [node for node in nodes if isinstance(node, TextNode)]


def clean_qa_pair_nodes_with_llamaindex(nodes: list[BaseNode]) -> list[TextNode]:
    # 创建 LlamaIndex 官方 IngestionPipeline。
    pipeline = IngestionPipeline(transformations=[QAPairCleaningTransform()])
    # 运行官方摄取管线清洗已经成对的问答节点。
    cleaned_nodes = pipeline.run(nodes=nodes)
    # 返回 LlamaIndex 官方 TextNode 列表。
    return [node for node in cleaned_nodes if isinstance(node, TextNode)]
