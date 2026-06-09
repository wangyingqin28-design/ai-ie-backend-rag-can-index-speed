# -*- coding: utf-8 -*-
"""基于 LlamaIndex TransformComponent 的问答元数据提取。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：问答成对已前移，本模块只做官方 IngestionPipeline 元数据增强，不再覆盖已验证的 question/answer。

# 导入 JSON 库，用于调试元数据稳定化。
import json
# 导入正则库，用于实体抽取和问句识别。
import re
# 导入任意类型和序列类型。
from typing import Any, Sequence

# 导入 LlamaIndex 官方 IngestionPipeline。
from llama_index.core.ingestion import IngestionPipeline
# 导入 LlamaIndex 官方节点和 transformation 基类。
from llama_index.core.schema import BaseNode, TextNode, TransformComponent

# 2026-06-06 10:45:58 修改原因：导入动态场景常量和提示词，不再依赖固定业务场景关键词白名单。
from common.constants import BUSINESS_TERM_ALIASES, DYNAMIC_SCENE_PREFIX, GENERIC_SCENE_FALLBACK, QUESTION_HINTS, SOLUTION_HINTS
# 导入稳定哈希与 ID 工具。
from common.utils import sha256_text, stable_id, unique_keep_order
# 导入清洗包内句子切分接口。
from cleaning_extraction.text_cleaner import split_markdown_sentences
# 2026-06-06 10:45:58 新增原因：复用 Agent 侧泛化语义工具，让入库抽词和 Prompt Builder 抽词保持同源。
from overall_planning.semantic_evidence import extract_semantic_terms


def detect_scene(text: str) -> str:
    # 2026-06-06 10:45:58 修改原因：从当前文本动态抽主题词，替代固定场景打分。
    terms = extract_semantic_terms(text, limit=4)
    # 2026-06-06 10:45:58 修改原因：有主题词时组合动态场景名，避免未知业务都落到同一个兜底类。
    if terms:
        # 2026-06-06 10:45:58 修改原因：只取前三个主题词控制 scene 长度，防止 payload 过长。
        return f"{DYNAMIC_SCENE_PREFIX}：{'、'.join(terms[:3])}"
    # 2026-06-06 10:45:58 修改原因：确实没有主题时才返回通用问答兜底。
    return GENERIC_SCENE_FALLBACK


def is_meaningful_question(sentence: str) -> bool:
    # 没有问句提示词时不是问句。
    if not any(hint in sentence for hint in QUESTION_HINTS):
        # 返回否。
        return False
    # 过滤过短确认句。
    if len(sentence) < 10 and not any(hint in sentence for hint in ["为什么", "怎么", "哪个", "哪里", "多少", "什么", "能不能"]):
        # 返回否。
        return False
    # 过滤纯语气确认句。
    if re.fullmatch(r"[对是好嗯啊哦吧吗呢？?，,。 ]+", sentence):
        # 返回否。
        return False
    # 返回是。
    return True


def is_solution_sentence(sentence: str) -> bool:
    # 命中解决方案提示词时返回是。
    return any(hint in sentence for hint in SOLUTION_HINTS)


def apply_business_term_aliases(text: str) -> str:
    # 2026-06-06 10:45:58 修改原因：创建规范化文本，默认只做格式清理不做业务语义改写。
    canonical_text = str(text or "")
    # 2026-06-06 10:45:58 修改原因：保留未来外部配置别名扩展口，但当前内置别名字典为空，避免固定场景污染。
    for alias, canonical in BUSINESS_TERM_ALIASES.items():
        # 2026-06-06 10:45:58 修改原因：只有显式配置别名时才替换，生产默认不硬编码业务别名。
        if alias in canonical_text:
            # 2026-06-06 10:45:58 修改原因：执行外部配置的别名规范化。
            canonical_text = canonical_text.replace(alias, canonical)
    # 2026-06-06 10:45:58 修改原因：压缩空白，保留原始业务词本身。
    canonical_text = re.sub(r"\s+", " ", canonical_text).strip()
    # 2026-06-06 10:45:58 修改原因：返回通用规范化文本。
    return canonical_text


def build_query_aliases(question: str, entities: dict[str, list[str]]) -> list[str]:
    # 初始化别名候选。
    aliases: list[str] = []
    # 读取原问题。
    raw_question = str(question or "")
    # 写入规范问题。
    canonical_question = apply_business_term_aliases(raw_question)
    # 规范问题不同于原问题时加入。
    if canonical_question and canonical_question != raw_question:
        aliases.append(canonical_question)
    # 2026-06-06 10:45:58 修改原因：实体术语作为检索别名，来源是当前问题动态抽取结果。
    aliases.extend(entities.get("system_terms", []))
    # 2026-06-06 10:45:58 新增原因：从当前问题直接抽动态主题，替代固定 alias/canonical 互换模板。
    aliases.extend(extract_semantic_terms(raw_question, entities, limit=16))
    # 返回去重后的别名。
    return unique_keep_order([alias for alias in aliases if alias])[:16]


def build_answer_first_text(question: str, answer: str, scene: str, resolution_steps: list[str], query_aliases: list[str]) -> str:
    # 拼出步骤文本。
    steps_text = "；".join(step for step in resolution_steps if step)
    # 拼出别名文本。
    aliases_text = "；".join(alias for alias in query_aliases if alias)
    # 使用答案优先的文本，让通用 RAG/LLM 默认读取 text 时不会先看到摘要残片。
    parts = [
        f"标准答案：{answer}",
        f"用户问题：{question}",
        f"规范问题：{apply_business_term_aliases(question)}",
        f"业务场景：{scene}",
    ]
    # 有步骤时追加。
    if steps_text:
        parts.append(f"操作步骤：{steps_text}")
    # 有别名时追加。
    if aliases_text:
        parts.append(f"相关问法：{aliases_text}")
    # 返回完整消费文本。
    return "\n".join(part for part in parts if part.strip())


def extract_entities(text: str) -> dict[str, list[str]]:
    # 抽取订单号、款号等字母数字串。
    order_like = re.findall(r"\b[A-Za-z]?\d{2,}[A-Za-z0-9-]*\b", text)
    # 抽取尺寸规格。
    dimensions = re.findall(r"\d+(?:\.\d+)?\s*(?:乘以|x|X|\*)\s*\d+(?:\.\d+)?", text)
    # 抽取中文日期。
    dates = re.findall(r"\d{1,2}月\d{1,2}号?", text)
    # 抽取数量金额耗时。
    amounts = re.findall(r"\d+(?:\.\d+)?\s*(?:个|件|张|元|块钱|小时|分钟|%)", text)
    # 2026-06-06 10:45:58 修改原因：从当前文本动态抽取系统术语，替代固定场景词池。
    terms = extract_semantic_terms(text, limit=24)
    # 返回实体字典。
    return {
        "order_like": unique_keep_order(order_like),
        "dimensions": unique_keep_order(dimensions),
        "dates": unique_keep_order(dates),
        "amounts": unique_keep_order(amounts),
        "system_terms": unique_keep_order(terms),
    }


def extract_keywords(text: str, scene: str, entities: dict[str, list[str]]) -> list[str]:
    # 2026-06-06 10:45:58 修改原因：初始化关键词，动态场景有意义时加入，兜底场景不作为强关键词。
    keywords = [scene] if scene and scene != GENERIC_SCENE_FALLBACK else []
    # 加入实体中的系统术语。
    keywords.extend(entities.get("system_terms", []))
    # 2026-06-06 10:45:58 修改原因：从全文、场景和实体共同抽动态关键词，不再靠固定场景补词。
    keywords.extend(extract_semantic_terms(text, scene, entities, limit=20))
    # 去重并限制数量。
    return unique_keep_order(keywords)[:16]


def summarize_question(sentences: list[str]) -> str:
    # 抽取有效问句。
    questions = [sentence for sentence in sentences if is_meaningful_question(sentence)]
    # 有问句时返回前两个。
    if questions:
        # 拼接问句。
        return "；".join(questions[:2])
    # 无问句时返回第一句作为上下文。
    return sentences[0] if sentences else ""


def summarize_answer(sentences: list[str]) -> str:
    # 找到第一个有效问句位置。
    question_index = next((idx for idx, sentence in enumerate(sentences) if is_meaningful_question(sentence)), -1)
    # 答案优先从问题后面抽。
    answer_scope = sentences[question_index + 1 :] if question_index >= 0 else sentences
    # 抽取解决方案句。
    solution_sentences = [sentence for sentence in answer_scope if is_solution_sentence(sentence) and not is_meaningful_question(sentence)]
    # 有解决句时返回前四句。
    if solution_sentences:
        # 拼接答案。
        return "；".join(solution_sentences[:4])
    # 没有解决句时取问题后的前几句。
    return "；".join(answer_scope[:4] or sentences[-3:]) if sentences else ""


def extract_steps(sentences: list[str]) -> list[str]:
    # 找到第一个有效问句位置。
    question_index = next((idx for idx, sentence in enumerate(sentences) if is_meaningful_question(sentence)), -1)
    # 步骤优先从问题后面抽。
    step_scope = sentences[question_index + 1 :] if question_index >= 0 else sentences
    # 抽取解决步骤句。
    steps = [sentence for sentence in step_scope if is_solution_sentence(sentence) and not is_meaningful_question(sentence)]
    # 没抽到时使用兜底句子。
    if not steps:
        # 取问题后前几句或末尾句子。
        steps = step_scope[:4] or sentences[-3:]
    # 去重并限制数量。
    return unique_keep_order(steps)[:8]


def is_low_value_node(text: str, scene: str) -> bool:
    # 2026-06-06 10:45:58 修改原因：只有通用兜底场景的短文本才按噪声处理，动态业务场景不能被误删。
    if scene == GENERIC_SCENE_FALLBACK and len(text) < 120:
        # 返回低价值。
        return True
    # 抽取实体。
    entities = extract_entities(text)
    # 判断是否有业务术语。
    has_term = bool(entities.get("system_terms"))
    # 判断是否有有效问句。
    has_question = any(is_meaningful_question(sentence) for sentence in split_markdown_sentences(text))
    # 短文本、无业务术语、无问题时过滤。
    return len(text) < 90 and not has_term and not has_question


class QuestionAnswerMetadataExtractor(TransformComponent):
    # LlamaIndex 官方 TransformComponent 入口，给语义节点写入 QA 元数据。
    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> Sequence[BaseNode]:
        # 创建结果节点列表。
        qa_nodes: list[TextNode] = []
        # 初始化分块序号。
        chunk_index = 0
        # 遍历 LlamaIndex 语义分块节点。
        for node in nodes:
            # 获取节点文本。
            text = node.get_content()
            # 生成业务别名扩展文本，用于场景、实体和关键词识别。
            analysis_text = f"{text}\n{apply_business_term_aliases(text)}"
            # 识别业务场景。
            scene = detect_scene(analysis_text)
            # 过滤低价值节点。
            if is_low_value_node(analysis_text, scene):
                # 继续下一个节点。
                continue
            # 分块序号加一。
            chunk_index += 1
            # 切分句子。
            sentences = split_markdown_sentences(text)
            # 抽取实体。
            entities = extract_entities(analysis_text)
            # 抽取关键词。
            keywords = extract_keywords(analysis_text, scene, entities)
            # 读取源文档 ID。
            document_id = str(node.metadata.get("document_id") or node.ref_doc_id or "")
            # 复制原 metadata。
            metadata = dict(node.metadata)
            # 写入稳定文档 ID。
            metadata["document_id"] = document_id
            # 写入全局分块序号。
            metadata["chunk_index"] = chunk_index
            # 写入业务场景。
            metadata["scene"] = scene
            # 判断是否已经完成官方 evaluator 问答绑定。
            if metadata.get("qa_pair_validated"):
                # 保留前置问答成对节点中的问题。
                metadata["question"] = str(metadata.get("question", ""))
                # 保留前置问答成对节点中的答案。
                metadata["answer"] = str(metadata.get("answer", ""))
                # 只从答案文本中抽取解决步骤。
                metadata["resolution_steps"] = extract_steps(split_markdown_sentences(metadata["answer"]))
            # 未经过前置成对的历史节点才走兜底摘要。
            else:
                # 写入问题。
                metadata["question"] = summarize_question(sentences)
                # 写入答案。
                metadata["answer"] = summarize_answer(sentences)
                # 写入解决步骤。
                metadata["resolution_steps"] = extract_steps(sentences)
            # 读取最终问题。
            question = str(metadata.get("question", ""))
            # 读取最终答案。
            answer = str(metadata.get("answer", ""))
            # 生成规范问题。
            canonical_question = apply_business_term_aliases(question)
            # 生成 query alias。
            query_aliases = build_query_aliases(question, entities)
            # 生成答案优先的完整消费文本。
            llm_text = build_answer_first_text(question, answer, scene, metadata["resolution_steps"], query_aliases)
            # 生成检索文本，和 LLM 消费文本保持同源但保留原始问答格式。
            retrieval_text = f"问题：{question}\n规范问题：{canonical_question}\n答案：{answer}\n{llm_text}"
            # 计算内容哈希。
            content_hash = sha256_text(retrieval_text)
            # 用消费契约重算 chunk_id，保证同文档同问答稳定。
            chunk_id = stable_id("qachunk", document_id, node.metadata.get("audio_no", ""), chunk_index, content_hash)
            # 写入 LlamaIndex 官方问答元数据字段名，兼容 QuestionsAnsweredExtractor 下游约定。
            metadata["questions_this_excerpt_can_answer"] = "；".join(unique_keep_order([question, canonical_question, *query_aliases]))
            # 写入规范问题。
            metadata["canonical_question"] = canonical_question
            # 写入 query aliases。
            metadata["query_aliases"] = query_aliases
            # 写入直接答案字段。
            metadata["answer_text"] = answer
            # 写入 RAG 消费文本。
            metadata["llm_text"] = llm_text
            # 写入向量检索文本。
            metadata["retrieval_text"] = retrieval_text
            # 写入完整来源摘录。
            metadata["source_excerpt_full"] = f"问题：{question}\n答案：{answer}"
            # 写入兼容清洗文本。
            metadata["cleaned_text"] = f"问题：{question}\n答案：{answer}"
            # 写入关键词。
            metadata["keywords"] = keywords
            # 写入实体。
            metadata["entities"] = entities
            # 写入元数据增强方式。
            metadata["qa_metadata_method"] = "llamaindex.IngestionPipeline.TransformComponent"
            # 写入摘录，保留完整问答，不再截断。
            metadata["source_excerpt"] = metadata["source_excerpt_full"]
            # 写入内容哈希。
            metadata["content_hash"] = content_hash
            # 写入元数据 JSON 快照，方便调试。
            metadata["qa_metadata_json"] = json.dumps(metadata, ensure_ascii=False, default=str)
            # 构造 LlamaIndex 官方 TextNode，继承文本并使用稳定 chunk_id。
            qa_nodes.append(TextNode(id_=chunk_id, text=text, metadata=metadata, relationships=node.relationships))
        # 返回 QA 节点。
        return qa_nodes


def extract_qa_metadata_with_llamaindex(nodes: list[BaseNode]) -> list[TextNode]:
    # 创建 LlamaIndex 官方 IngestionPipeline，问答提取器作为 transformation 执行。
    pipeline = IngestionPipeline(transformations=[QuestionAnswerMetadataExtractor()])
    # 执行 LlamaIndex pipeline。
    qa_nodes = pipeline.run(nodes=nodes)
    # 返回 TextNode 列表。
    return [node for node in qa_nodes if isinstance(node, TextNode)]
