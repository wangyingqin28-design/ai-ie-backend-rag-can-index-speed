# -*- coding: utf-8 -*-
"""客户问答清洗管线使用的常量配置。"""

# 记录本程序参考的成熟框架，后续会随文档一起写入数据库。
FRAMEWORK_REFERENCES = [
    # LlamaIndex 官方摄取管线，提供文档清洗、切分、元数据提取、向量库写入范式。
    {
        "name": "LlamaIndex IngestionPipeline",
        "url": "https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/",
        "note": "官方摄取流水线，支持清洗、切分、元数据提取、向量库写入。",
    },
    # LlamaIndex 官方语义切分示例，按相邻句向量距离决定分块断点。
    {
        "name": "LlamaIndex Semantic Chunking Pack",
        "url": "https://github.com/run-llama/llama_index/tree/main/llama-index-packs/llama-index-packs-node-parser-semantic-chunking",
        "note": "官方示例包，按句向量相邻余弦距离决定语义断点。",
    },
    # Haystack 官方预处理组件，覆盖文档清洗、句子/段落/语义切分。
    {
        "name": "Haystack DocumentCleaner / DocumentSplitter",
        "url": "https://docs.haystack.deepset.ai/reference/preprocessors-api",
        "note": "官方预处理组件，覆盖文本清洗、句子/段落/语义切分。",
    },
]

# 2026-06-06 10:38:41 修改原因：保留兼容变量名，但停止内置固定业务场景白名单，场景由 qa_extractor 动态抽取。
SCENE_KEYWORDS: dict[str, list[str]] = {}
# 2026-06-06 10:38:41 新增原因：定义动态场景前缀，避免未知业务 chunk 被统一写成固定兜底类目。
DYNAMIC_SCENE_PREFIX = "动态业务场景"
# 2026-06-06 10:38:41 新增原因：定义无明确主题时的通用兜底场景，区别于旧的固定“系统操作问答”分类。
GENERIC_SCENE_FALLBACK = "通用业务问答"

# 定义中文口语问句识别提示词。
QUESTION_HINTS = [
    # 原因类问题。
    "为什么",
    # 操作类问题。
    "怎么",
    # 处理类问题。
    "怎么办",
    # 能力边界类问题。
    "能不能",
    # 可行性问题。
    "可以吗",
    # 判断类问题。
    "是不是",
    # 确认类问题。
    "对不对",
    # 选择类问题。
    "要不要",
    # 选择对象问题。
    "哪个",
    # 位置问题。
    "哪里",
    # 数量金额问题。
    "多少",
    # 概念问题。
    "什么",
    # 书面操作问题。
    "如何",
    # 口语问句尾词。
    "吗",
    # 口语问句尾词。
    "呢",
    # 英文问号。
    "?",
    # 中文问号。
    "？",
]

# 定义解决方案句识别提示词。
SOLUTION_HINTS = [
    # 原因说明。
    "原因",
    # 因果说明。
    "因为",
    # 结论说明。
    "所以",
    # 第一步操作。
    "先",
    # 下一步操作。
    "然后",
    # 后续操作。
    "再",
    # 后置操作。
    "之后",
    # 必要条件。
    "需要",
    # 可行操作。
    "可以",
    # 注意事项。
    "记得",
    # 建议方案。
    "建议",
    # 修改动作。
    "改成",
    # 删除动作。
    "删除",
    # 重做动作。
    "重做",
    # 2026-06-06 11:05:37 修改原因：使用通用处理动作，不再把某个具体业务动作写成全局解决方案提示词。
    "处理",
    # 审核动作。
    "审核",
    # 保存动作。
    "保存",
    # 导入动作。
    "导入",
    # 选择动作。
    "选择",
    # 绑定动作。
    "绑定",
    # 创建动作。
    "创建",
    # 录入动作。
    "录入",
]

# 2026-06-06 10:38:41 修改原因：保留兼容变量名，但停止内置固定业务别名改写，避免把任意 chunk 强行归到旧截图场景。
BUSINESS_TERM_ALIASES: dict[str, str] = {}

# RAG 消费契约字段。Qdrant 同步前会检查这些字段，避免坏 payload 流入后序模型。
RAG_REQUIRED_PAYLOAD_FIELDS = [
    "question",
    "answer",
    "answer_text",
    "llm_text",
    "retrieval_text",
    "source_excerpt_full",
]
