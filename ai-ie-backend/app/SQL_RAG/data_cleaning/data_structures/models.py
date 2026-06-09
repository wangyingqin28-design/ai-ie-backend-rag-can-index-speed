# -*- coding: utf-8 -*-
"""LlamaIndex 官方数据结构别名与运行摘要结构。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：补齐正式 RAG 入库 payload 和聚类 payload schema，替代只有 dict[str, Any] 的松散数据契约。
# 修改日期：2026-06-01 13:29:35。
# 修改理由：补齐多文档全局入库需要的任务、版本、全局聚类、实体、融合、校验和 RAG 同步状态结构。

# 导入 dataclass 和 field，仅用于入口运行摘要和可选 Neo4j 三元组列表默认值。
from dataclasses import dataclass, field
# 导入任意类型，用于 JSON payload 类型标注。
from typing import Any

# 导入 Pydantic BaseModel，用于定义稳定 JSON 数据契约。
from pydantic import BaseModel, Field

# 导入 LlamaIndex 官方 BaseNode，作为节点基类。
from llama_index.core.schema import BaseNode
# 导入 LlamaIndex 官方 Document，作为 Markdown 源文档结构。
from llama_index.core.schema import Document
# 导入 LlamaIndex 官方 TextNode，作为清洗、分块、问答、向量化后的统一节点结构。
from llama_index.core.schema import TextNode

# 源文档结构使用 LlamaIndex 官方 Document。
SourceDocument = Document
# 清洗后的章节节点使用 LlamaIndex 官方 TextNode。
CleanedSectionNode = TextNode
# 语义分块节点使用 LlamaIndex 官方 TextNode。
SemanticChunkNode = TextNode
# 问答结构化节点使用 LlamaIndex 官方 TextNode。
QANode = TextNode
# 向量化节点使用 LlamaIndex 官方 TextNode。
VectorizedNode = TextNode
# 通用节点类型使用 LlamaIndex 官方 BaseNode。
LlamaIndexNode = BaseNode
# 入库前 JSON payload 使用普通字典承载官方节点序列化结果。
StoragePayload = dict[str, Any]


class RagQAPayloadModel(BaseModel):
    # 定义 payload schema 版本。
    payload_schema_version: str = Field(default="qa-rag-payload-v3")
    # 定义 RAG 消费契约版本。
    rag_contract_version: str = "qa-rag-contract-v1"
    # 定义问答 chunk ID。
    chunk_id: str
    # 定义所属文档 ID。
    document_id: str
    # 定义音频编号。
    audio_no: int = 0
    # 定义音频标题。
    audio_title: str = ""
    # 定义 chunk 序号。
    chunk_index: int = 0
    # 定义问答对 ID。
    qa_pair_id: str = ""
    # 定义问答对序号。
    qa_pair_index: int = 0
    # 定义问答相似度分数。
    qa_similarity_score: float = 0.0
    # 定义问答相似度阈值。
    qa_similarity_threshold: float = 0.0
    # 定义问答是否通过官方 evaluator 检测。
    qa_pair_validated: bool = False
    # 定义聚类 ID。
    cluster_id: str = ""
    # 定义聚类标签。
    cluster_label: str = ""
    # 定义聚类层级。
    cluster_level: str = ""
    # 定义聚类路径。
    cluster_path: list[str] = Field(default_factory=list)
    # 定义全局聚类 ID。
    global_cluster_id: str = ""
    # 定义全局聚类标签。
    global_cluster_label: str = ""
    # 定义全局聚类层级。
    global_cluster_level: str = ""
    # 定义全局聚类路径。
    global_cluster_path: list[str] = Field(default_factory=list)
    # 定义问题归一化哈希。
    question_hash: str = ""
    # 定义答案归一化哈希。
    answer_hash: str = ""
    # 定义融合后的规范 chunk ID。
    canonical_chunk_id: str = ""
    # 定义融合状态。
    fusion_status: str = "canonical"
    # 定义业务场景。
    scene: str = ""
    # 定义问题文本。
    question: str = ""
    # 定义答案文本。
    answer: str = ""
    # 定义规范问题文本。
    canonical_question: str = ""
    # 定义答案优先字段，供通用 RAG/LLM 直接消费。
    answer_text: str = ""
    # 定义 query 口语和业务别名。
    query_aliases: list[str] = Field(default_factory=list)
    # 定义解决步骤。
    resolution_steps: list[str] = Field(default_factory=list)
    # 定义关键词。
    keywords: list[str] = Field(default_factory=list)
    # 定义实体 JSON。
    entities: dict[str, Any] = Field(default_factory=dict)
    # 定义清洗文本。
    cleaned_text: str = ""
    # 定义来源摘录。
    source_excerpt: str = ""
    # 定义完整来源摘录。
    source_excerpt_full: str = ""
    # 定义 LLM 消费文本。
    llm_text: str = ""
    # 定义向量检索文本。
    retrieval_text: str = ""
    # 定义被融合重复 chunk 的完整上下文。
    duplicate_contexts: list[dict[str, Any]] = Field(default_factory=list)
    # 定义已经合入 canonical 的重复 chunk ID。
    merged_duplicate_chunk_ids: list[str] = Field(default_factory=list)
    # 定义是否满足同步到 Qdrant 的契约。
    qdrant_ready: bool = True
    # 定义校验标记。
    validation_flags: list[str] = Field(default_factory=list)
    # 定义内容哈希。
    content_hash: str = ""
    # 定义向量模型名。
    vector_model: str = ""
    # 定义向量维度。
    vector_dim: int = 0
    # 定义向量。
    vector: list[float] = Field(default_factory=list)
    # 定义 LlamaIndex 官方 TextNode.to_dict() 结果。
    llamaindex_node: dict[str, Any] = Field(default_factory=dict)


class RagClusterPayloadModel(BaseModel):
    # 定义聚类 schema 版本。
    cluster_schema_version: str = Field(default="qa-rag-cluster-v1")
    # 定义所属文档 ID。
    document_id: str
    # 定义聚类 ID。
    cluster_id: str
    # 定义聚类标签。
    cluster_label: str
    # 定义聚类层级。
    cluster_level: str = "document_scene"
    # 定义聚类类型。
    cluster_type: str = "qa_scene_cluster"
    # 定义聚类关键词。
    cluster_keywords: list[str] = Field(default_factory=list)
    # 定义聚类成员数量。
    cluster_member_count: int = 0
    # 定义聚类成员 chunk_id 列表。
    cluster_member_chunk_ids: list[str] = Field(default_factory=list)
    # 定义 LlamaIndex 官方聚类 TextNode.to_dict() 结果。
    cluster_node_json: dict[str, Any] = Field(default_factory=dict)


class IngestionJobPayloadModel(BaseModel):
    # 定义摄取任务 ID。
    job_id: str
    # 定义输入路径。
    input_path: str
    # 定义任务状态。
    job_status: str = "completed"
    # 定义本次处理文档数量。
    document_count: int = 0
    # 定义本次处理 chunk 数量。
    chunk_count: int = 0
    # 定义本次处理全局聚类数量。
    global_cluster_count: int = 0
    # 定义本次处理融合关系数量。
    fusion_count: int = 0
    # 定义本次校验问题数量。
    validation_issue_count: int = 0
    # 定义任务参数 JSON。
    job_options_json: dict[str, Any] = Field(default_factory=dict)


class DocumentVersionPayloadModel(BaseModel):
    # 定义文档版本 ID。
    version_id: str
    # 定义文档 ID。
    document_id: str
    # 定义源路径。
    source_path: str
    # 定义源文件名。
    source_name: str
    # 定义内容哈希。
    content_hash: str
    # 定义摄取任务 ID。
    job_id: str
    # 定义是否为当前版本。
    is_current: bool = True


class RagGlobalClusterPayloadModel(BaseModel):
    # 定义全局聚类 ID。
    global_cluster_id: str
    # 定义全局聚类标签。
    global_cluster_label: str
    # 定义全局聚类层级。
    global_cluster_level: str = "global_scene"
    # 定义全局聚类类型。
    global_cluster_type: str = "cross_document_scene_cluster"
    # 定义全局聚类关键词。
    global_cluster_keywords: list[str] = Field(default_factory=list)
    # 定义成员文档 ID。
    member_document_ids: list[str] = Field(default_factory=list)
    # 定义成员文档内聚类 ID。
    member_cluster_ids: list[str] = Field(default_factory=list)
    # 定义成员 chunk ID。
    member_chunk_ids: list[str] = Field(default_factory=list)
    # 定义成员数量。
    global_member_count: int = 0
    # 定义全局聚类摘要节点 JSON。
    global_cluster_node_json: dict[str, Any] = Field(default_factory=dict)


class RagEntityMentionPayloadModel(BaseModel):
    # 定义实体提及 ID。
    mention_id: str
    # 定义文档 ID。
    document_id: str
    # 定义 chunk ID。
    chunk_id: str
    # 定义实体类型。
    entity_type: str
    # 定义实体原始值。
    entity_value: str
    # 定义实体规范值。
    canonical_entity: str
    # 定义实体哈希。
    entity_hash: str
    # 定义全局聚类 ID。
    global_cluster_id: str = ""


class RagEntityAliasPayloadModel(BaseModel):
    # 定义别名 ID。
    alias_id: str
    # 定义实体类型。
    entity_type: str
    # 定义别名值。
    alias_value: str
    # 定义规范实体值。
    canonical_entity: str
    # 定义实体哈希。
    entity_hash: str


class RagChunkFusionPayloadModel(BaseModel):
    # 定义融合关系 ID。
    fusion_id: str
    # 定义规范 chunk ID。
    canonical_chunk_id: str
    # 定义重复或可融合 chunk ID。
    duplicate_chunk_id: str
    # 定义规范 chunk 所属文档 ID。
    canonical_document_id: str
    # 定义重复 chunk 所属文档 ID。
    duplicate_document_id: str
    # 定义全局聚类 ID。
    global_cluster_id: str
    # 定义问题哈希。
    question_hash: str
    # 定义答案哈希。
    answer_hash: str
    # 定义融合分数。
    fusion_score: float = 0.0
    # 定义融合规则。
    fusion_rule: str = ""
    # 定义重复 chunk 的问题文本。
    duplicate_question: str = ""
    # 定义重复 chunk 的答案文本。
    duplicate_answer: str = ""
    # 定义重复 chunk 的完整清洗文本。
    duplicate_cleaned_text: str = ""
    # 定义重复 chunk 的操作步骤。
    duplicate_resolution_steps: list[str] = Field(default_factory=list)
    # 定义融合策略。
    merge_policy: str = "merge_duplicate_context_into_canonical"
    # 定义融合补充 payload。
    merge_payload: dict[str, Any] = Field(default_factory=dict)


class RagValidationIssuePayloadModel(BaseModel):
    # 定义校验问题 ID。
    issue_id: str
    # 定义文档 ID。
    document_id: str = ""
    # 定义 chunk ID。
    chunk_id: str = ""
    # 定义问题类型。
    issue_type: str
    # 定义严重等级。
    issue_level: str = "warning"
    # 定义问题说明。
    issue_message: str
    # 定义相关 payload JSON。
    issue_payload: dict[str, Any] = Field(default_factory=dict)


class RagSyncStatePayloadModel(BaseModel):
    # 定义同步状态 ID。
    sync_id: str
    # 定义文档 ID。
    document_id: str
    # 定义源内容哈希。
    content_hash: str
    # 定义同步目标。
    sync_target: str = "llamaindex_vector_store"
    # 定义同步状态。
    sync_status: str = "pending"
    # 定义 chunk 数量。
    chunk_count: int = 0
    # 定义是否需要后续 RAG 重建索引。
    needs_reindex: bool = True
    # 定义同步说明。
    sync_message: str = ""


class RagNeo4jTriplePayloadModel(BaseModel):
    # 2026-06-04 16:22:03 新增原因：定义 Neo4j 三元组 ID，保证 MERGE 幂等。
    triple_id: str
    # 2026-06-04 16:22:03 新增原因：定义三元组主语。
    subject: str
    # 2026-06-04 16:22:03 新增原因：定义三元组谓词。
    predicate: str
    # 2026-06-04 16:22:03 新增原因：定义三元组宾语。
    object: str
    # 2026-06-04 16:22:03 新增原因：定义主语类型，供 Neo4j 节点 kind 使用。
    subject_type: str = "entity"
    # 2026-06-04 16:22:03 新增原因：定义宾语类型，供 Neo4j 节点 kind 使用。
    object_type: str = "entity"
    # 2026-06-04 16:22:03 新增原因：绑定证据 chunk，支持从图谱路径回到 RAG 证据。
    chunk_id: str = ""
    # 2026-06-04 16:22:03 新增原因：绑定文档 ID，支持按文档版本清理图谱。
    document_id: str = ""
    # 2026-06-04 16:22:03 新增原因：绑定全局聚类 ID，支持跨文档业务场景多跳。
    global_cluster_id: str = ""
    # 2026-06-04 16:22:03 新增原因：保存证据文本，供 Prompt Builder 消费。
    evidence_text: str = ""
    # 2026-06-04 16:22:03 新增原因：保存补充属性，兼容 fusion_score、question、answer 等信息。
    properties: dict[str, Any] = Field(default_factory=dict)


@dataclass
class DatabaseWriteBundle:
    # 本次摄取任务 payload。
    ingestion_job: StoragePayload
    # 本次处理的 LlamaIndex 官方文档。
    documents: list[SourceDocument]
    # 文档版本 payload。
    document_versions: list[StoragePayload]
    # 问答 chunk payload。
    chunk_payloads: list[StoragePayload]
    # 文档内聚类 payload。
    document_cluster_payloads: list[StoragePayload]
    # 跨文档全局聚类 payload。
    global_cluster_payloads: list[StoragePayload]
    # 实体提及 payload。
    entity_mention_payloads: list[StoragePayload]
    # 实体别名 payload。
    entity_alias_payloads: list[StoragePayload]
    # chunk 融合关系 payload。
    fusion_payloads: list[StoragePayload]
    # 校验问题 payload。
    validation_issue_payloads: list[StoragePayload]
    # 后续 RAG 同步状态 payload。
    rag_sync_payloads: list[StoragePayload]
    # 2026-06-04 16:22:03 新增原因：Neo4j 三元组 payload，清洗链路总是生成，写入由配置控制。
    neo4j_triple_payloads: list[StoragePayload] = field(default_factory=list)


@dataclass
class PipelineSummary:
    # 本次摄取任务 ID。
    job_id: str
    # 文档数量。
    document_count: int
    # 文档稳定 ID 列表。
    document_ids: list[str]
    # 源文件内容哈希列表。
    source_hashes: list[str]
    # Markdown 解析出的问答章节数量。
    sections: int
    # 官方 evaluator 通过后的问答对数量。
    qa_pairs: int
    # LlamaIndex 语义分块数量。
    chunks: int
    # 最终入库 JSON payload 数量。
    records: int
    # 最终 RAG 聚类数量。
    clusters: int
    # 跨文档全局聚类数量。
    global_clusters: int
    # 融合关系数量。
    fusion_links: int
    # 校验问题数量。
    validation_issues: int
    # JSON 输出文件路径。
    output_json: str
    # JSONL 输出文件路径。
    output_jsonl: str
    # 数据库后端。
    db_backend: str
    # 数据库写入结果。
    db_message: str
