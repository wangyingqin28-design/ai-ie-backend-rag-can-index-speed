# -*- coding: utf-8 -*-
"""基于 LlamaIndex pipeline/evaluator 的项目 Markdown 问答成对适配器。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：先把 Markdown 口语转写中的问题和答案强相关成对绑定，再进入后续清洗、分块、向量化和入库流程。

# 导入正则库，用于识别同类 Markdown 音频章节标题。
import re
# 导入类型标注，保证 LlamaIndex transformation 入参清晰。
from typing import Any, Sequence

# 导入 Pydantic 私有属性，避免把 embedding 模型序列化到节点 metadata。
from pydantic import PrivateAttr

# 导入 LlamaIndex 官方 embedding 基类，供官方相似度评估器使用。
from llama_index.core.embeddings import BaseEmbedding
# 导入 LlamaIndex 官方语义相似度评估器，作为问答绑定检测机制。
from llama_index.core.evaluation import SemanticSimilarityEvaluator
# 导入 LlamaIndex 官方摄取流水线。
from llama_index.core.ingestion import IngestionPipeline
# 导入 LlamaIndex 官方节点与 transformation 基类。
from llama_index.core.schema import BaseNode, TextNode, TransformComponent

# 导入已有问句判断函数，只做口语 Markdown 格式适配。
from cleaning_extraction.qa_extractor import is_meaningful_question
# 导入句子切分函数，只做转写文本边界拆分。
from cleaning_extraction.text_cleaner import split_markdown_sentences
# 导入哈希工具，生成稳定的 TextNode 节点 ID。
from common.utils import sha256_text, stable_id


class QuestionAnswerPairingTransform(TransformComponent):
    # 设置官方 SemanticSimilarityEvaluator 的最低通过阈值。
    min_similarity: float = 0.08
    # 设置每个问题最多向后吸收的答案句数量。
    max_answer_sentences: int = 6
    # 保存 embedding 模型私有属性。
    _embed_model: BaseEmbedding | None = PrivateAttr(default=None)
    # 保存官方语义相似度评估器私有属性。
    _evaluator: SemanticSimilarityEvaluator | None = PrivateAttr(default=None)

    def __init__(self, embed_model: BaseEmbedding, min_similarity: float = 0.08, max_answer_sentences: int = 6) -> None:
        # 初始化 LlamaIndex 官方 TransformComponent 字段。
        super().__init__(min_similarity=min_similarity, max_answer_sentences=max_answer_sentences)
        # 记录 embedding 模型实例。
        self._embed_model = embed_model
        # 创建 LlamaIndex 官方语义相似度评估器。
        self._evaluator = SemanticSimilarityEvaluator(embed_model=embed_model, similarity_threshold=min_similarity)

    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> Sequence[BaseNode]:
        # 创建问答成对后的 LlamaIndex TextNode 列表。
        pair_nodes: list[TextNode] = []
        # 遍历 LlamaIndex Document/BaseNode。
        for source_node in nodes:
            # 获取源节点文本。
            source_text = source_node.get_content()
            # 解析 Markdown 音频章节。
            sections = self._parse_audio_sections(source_text)
            # 如果没有章节标题，则把全文作为一个通用章节。
            if not sections:
                # 写入兜底章节。
                sections = [(0, "未分段问答文档", source_text)]
            # 遍历章节并抽取强相关问答对。
            for section_index, section in enumerate(sections, start=1):
                # 读取音频编号。
                audio_no = section[0]
                # 读取音频标题。
                audio_title = section[1]
                # 读取章节原文。
                raw_text = section[2]
                # 使用句子切分函数把转写文本拆成候选问答句。
                sentences = split_markdown_sentences(raw_text)
                # 遍历候选句子下标。
                for sentence_index, sentence in enumerate(sentences):
                    # 跳过非问题句。
                    if not is_meaningful_question(sentence):
                        # 继续找下一个问题句。
                        continue
                    # 从问题之后收集候选答案句。
                    answer_sentences = self._collect_answer_sentences(sentences, sentence_index)
                    # 没有候选答案时跳过。
                    if not answer_sentences:
                        # 继续下一个问题句。
                        continue
                    # 拼出候选答案文本。
                    answer_text = "。".join(answer_sentences).strip("。") + "。"
                    # 使用 LlamaIndex 官方 evaluator 计算问答相关性。
                    similarity_score = self._score_pair(sentence, answer_text)
                    # 相似度不达标时禁止绑定。
                    if similarity_score < self.min_similarity:
                        # 继续下一个问题句。
                        continue
                    # 生成问答对文本。
                    pair_text = f"问题：{sentence}\n答案：{answer_text}"
                    # 计算问答对内容哈希。
                    content_hash = sha256_text(pair_text)
                    # 生成问答对序号。
                    pair_index = len(pair_nodes) + 1
                    # 生成稳定问答对 ID。
                    pair_id = stable_id("qapair", source_node.node_id, audio_no, section_index, sentence_index, content_hash)
                    # 继承源文档 metadata。
                    metadata = dict(source_node.metadata)
                    # 写入稳定文档 ID。
                    metadata["document_id"] = source_node.node_id
                    # 写入音频编号。
                    metadata["audio_no"] = audio_no
                    # 写入音频标题。
                    metadata["audio_title"] = audio_title
                    # 写入章节序号。
                    metadata["section_index"] = section_index
                    # 写入问答对 ID。
                    metadata["qa_pair_id"] = pair_id
                    # 写入问答对序号。
                    metadata["qa_pair_index"] = pair_index
                    # 写入原始问题。
                    metadata["raw_question"] = sentence
                    # 写入原始答案。
                    metadata["raw_answer"] = answer_text
                    # 写入当前问题。
                    metadata["question"] = sentence
                    # 写入当前答案。
                    metadata["answer"] = answer_text
                    # 写入官方 evaluator 相似度分数。
                    metadata["qa_similarity_score"] = round(similarity_score, 6)
                    # 写入官方 evaluator 阈值。
                    metadata["qa_similarity_threshold"] = self.min_similarity
                    # 标记该问答对已经通过官方 evaluator 检测。
                    metadata["qa_pair_validated"] = True
                    # 写入问答对检测方法。
                    metadata["qa_pairing_method"] = "llamaindex.SemanticSimilarityEvaluator"
                    # 写入原始句子位置。
                    metadata["source_sentence_index"] = sentence_index
                    # 写入问答对内容哈希。
                    metadata["content_hash"] = content_hash
                    # 写入完整来源摘录，后续 Qdrant/RAG 消费不得只拿截断版。
                    metadata["source_excerpt"] = pair_text
                    metadata["source_excerpt_full"] = pair_text
                    metadata["answer_text"] = answer_text
                    metadata["llm_text"] = pair_text
                    metadata["retrieval_text"] = pair_text
                    # 创建 LlamaIndex TextNode。
                    pair_nodes.append(TextNode(id_=pair_id, text=pair_text, metadata=metadata))
        # 返回节点序列。
        return pair_nodes

    def _collect_answer_sentences(self, sentences: list[str], question_index: int) -> list[str]:
        # 创建答案句列表。
        answer_sentences: list[str] = []
        # 从问题句之后开始扫描。
        for next_sentence in sentences[question_index + 1 :]:
            # 遇到下一个明确问题句时停止，避免串到别的问题。
            if is_meaningful_question(next_sentence):
                # 停止收集答案。
                break
            # 追加候选答案句。
            answer_sentences.append(next_sentence)
            # 达到最大答案句数量时停止。
            if len(answer_sentences) >= self.max_answer_sentences:
                # 停止收集答案。
                break
        # 返回候选答案句。
        return answer_sentences

    def _score_pair(self, question: str, answer: str) -> float:
        # 如果官方 evaluator 未初始化则拒绝绑定。
        if self._evaluator is None:
            # 返回零分。
            return 0.0
        # 调用 LlamaIndex 官方 SemanticSimilarityEvaluator。
        result = self._evaluator.evaluate(response=answer, reference=question)
        # 返回官方评估分数。
        return float(result.score or 0.0)

    def _parse_audio_sections(self, markdown_text: str) -> list[tuple[int, str, str]]:
        # 编译“# 音频 N: 标题”章节标题正则。
        header_re = re.compile(r"^#\s*音频\s*(\d+)\s*:\s*(.+?)\s*$")
        # 创建章节结果列表。
        sections: list[tuple[int, str, str]] = []
        # 初始化当前音频编号。
        current_no: int | None = None
        # 初始化当前音频标题。
        current_title = ""
        # 初始化当前正文行缓存。
        current_lines: list[str] = []
        # 逐行扫描 Markdown 文本。
        for raw_line in markdown_text.splitlines():
            # 去除行尾空白。
            line = raw_line.rstrip()
            # 匹配章节标题。
            match = header_re.match(line)
            # 如果命中新章节标题。
            if match:
                # 当前已有章节时先收尾。
                if current_no is not None:
                    # 追加上一章节。
                    sections.append((current_no, current_title, "\n".join(current_lines).strip()))
                # 更新章节编号。
                current_no = int(match.group(1))
                # 更新章节标题。
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
            # 只在章节内收集正文。
            if current_no is not None:
                # 加入正文缓存。
                current_lines.append(line)
        # 收尾最后一个章节。
        if current_no is not None:
            # 追加最后章节。
            sections.append((current_no, current_title, "\n".join(current_lines).strip()))
        # 返回章节列表。
        return sections


def pair_markdown_questions_answers(
    documents: list[BaseNode],
    embed_model: BaseEmbedding,
    min_similarity: float,
    max_answer_sentences: int,
) -> list[TextNode]:
    """Run the project QA-pairing transform through LlamaIndex IngestionPipeline."""
    # 创建 LlamaIndex IngestionPipeline。
    pipeline = IngestionPipeline(
        transformations=[
            QuestionAnswerPairingTransform(
                embed_model=embed_model,
                min_similarity=min_similarity,
                max_answer_sentences=max_answer_sentences,
            )
        ]
    )
    # 运行摄取管线进行问答成对分离。
    nodes = pipeline.run(documents=documents)
    # 返回 LlamaIndex TextNode 列表。
    return [node for node in nodes if isinstance(node, TextNode)]


def pair_markdown_questions_answers_with_llamaindex(
    documents: list[BaseNode],
    embed_model: BaseEmbedding,
    min_similarity: float,
    max_answer_sentences: int,
) -> list[TextNode]:
    """Compatibility alias; this is a project wrapper, not a LlamaIndex API."""
    return pair_markdown_questions_answers(
        documents=documents,
        embed_model=embed_model,
        min_similarity=min_similarity,
        max_answer_sentences=max_answer_sentences,
    )
