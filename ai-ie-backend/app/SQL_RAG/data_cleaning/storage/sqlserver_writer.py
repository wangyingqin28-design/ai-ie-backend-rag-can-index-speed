# -*- coding: utf-8 -*-
"""SQL Server 2022 入库逻辑，入库内容来自 LlamaIndex TextNode JSON payload。"""

# 修改日期：2026-06-01 13:29:35。
# 修改理由：把单文档入库升级为多文档全局关系入库，补齐任务、版本、全局聚类、实体、融合、校验和 RAG 同步表。

# 导入 JSON 库，用于写入 JSON 字段。
import json
# 导入子进程库，用于调用 Docker 容器内 sqlcmd。
import subprocess
# 导入路径类型。
from pathlib import Path
# 导入任意类型。
from typing import Any

# 导入 LlamaIndex 官方 Document。
from llama_index.core.schema import Document

# 导入数据库写入 bundle 和通用 payload 类型。
from data_structures.models import DatabaseWriteBundle, StoragePayload


def sql_literal(value: Any) -> str:
    # None 写入 SQL NULL。
    if value is None:
        # 返回 SQL NULL。
        return "NULL"
    # 非字符串先转 JSON 字符串。
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    # SQL Server 不接受 NUL 字符。
    text = text.replace("\x00", "")
    # 单引号按 T-SQL 规则转义。
    text = text.replace("'", "''")
    # 使用 N 前缀保证中文正常写入。
    return f"N'{text}'"


def sql_int(value: Any) -> str:
    # 空值统一写 0。
    if value in (None, ""):
        # 返回 0。
        return "0"
    # 转成 SQL 整数字面量。
    return str(int(value))


def sql_bit(value: Any) -> str:
    # 布尔真值写入 1。
    if bool(value):
        # 返回 SQL bit 真值。
        return "1"
    # 布尔假值写入 0。
    return "0"


def sql_float(value: Any) -> str:
    # 空值统一写 0.0。
    if value in (None, ""):
        # 返回 0.0。
        return "0.0"
    # 转成 SQL 浮点字面量。
    return str(float(value))


def ensure_column_script(table_name: str, column_name: str, column_definition: str) -> str:
    # 返回 SQL Server 安全补列脚本。
    return f"""
IF COL_LENGTH(N'{table_name}', N'{column_name}') IS NULL
BEGIN
    ALTER TABLE {table_name} ADD {column_name} {column_definition};
END;
"""


def ensure_sqlserver_schema_script() -> str:
    # 返回建表和补列脚本。
    return f"""
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.rag_ingestion_jobs', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_ingestion_jobs (
        job_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        input_path NVARCHAR(800) NOT NULL,
        job_status NVARCHAR(40) NOT NULL,
        document_count INT NOT NULL,
        chunk_count INT NOT NULL,
        global_cluster_count INT NOT NULL,
        fusion_count INT NOT NULL,
        validation_issue_count INT NOT NULL,
        job_options_json NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_ingestion_jobs_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_ingestion_jobs_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_qa_documents', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_qa_documents (
        document_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        source_path NVARCHAR(800) NOT NULL,
        source_name NVARCHAR(260) NOT NULL,
        title NVARCHAR(260) NOT NULL,
        content_hash NVARCHAR(64) NOT NULL,
        framework_reference NVARCHAR(MAX) NULL,
        llamaindex_document_json NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_qa_documents_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_qa_documents_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_document_versions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_document_versions (
        version_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        document_id NVARCHAR(80) NOT NULL,
        source_path NVARCHAR(800) NOT NULL,
        source_name NVARCHAR(260) NOT NULL,
        content_hash NVARCHAR(64) NOT NULL,
        job_id NVARCHAR(80) NOT NULL,
        is_current BIT NOT NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_document_versions_created_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_qa_chunks', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_qa_chunks (
        chunk_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        document_id NVARCHAR(80) NOT NULL,
        audio_no INT NOT NULL,
        audio_title NVARCHAR(260) NOT NULL,
        chunk_index INT NOT NULL,
        payload_schema_version NVARCHAR(60) NULL,
        rag_contract_version NVARCHAR(60) NULL,
        qa_pair_id NVARCHAR(80) NULL,
        qa_pair_index INT NULL,
        qa_similarity_score FLOAT NULL,
        qa_similarity_threshold FLOAT NULL,
        qa_pair_validated BIT NULL,
        cluster_id NVARCHAR(80) NULL,
        cluster_label NVARCHAR(100) NULL,
        cluster_level NVARCHAR(60) NULL,
        cluster_path NVARCHAR(MAX) NULL,
        global_cluster_id NVARCHAR(80) NULL,
        global_cluster_label NVARCHAR(100) NULL,
        global_cluster_level NVARCHAR(60) NULL,
        global_cluster_path NVARCHAR(MAX) NULL,
        question_hash NVARCHAR(64) NULL,
        answer_hash NVARCHAR(64) NULL,
        canonical_chunk_id NVARCHAR(80) NULL,
        fusion_status NVARCHAR(40) NULL,
        scene NVARCHAR(100) NOT NULL,
        question NVARCHAR(MAX) NOT NULL,
        answer NVARCHAR(MAX) NOT NULL,
        canonical_question NVARCHAR(MAX) NULL,
        answer_text NVARCHAR(MAX) NULL,
        query_aliases_json NVARCHAR(MAX) NULL,
        resolution_steps NVARCHAR(MAX) NULL,
        keywords NVARCHAR(MAX) NULL,
        entities_json NVARCHAR(MAX) NULL,
        cleaned_text NVARCHAR(MAX) NOT NULL,
        source_excerpt NVARCHAR(MAX) NULL,
        source_excerpt_full NVARCHAR(MAX) NULL,
        llm_text NVARCHAR(MAX) NULL,
        retrieval_text NVARCHAR(MAX) NULL,
        duplicate_contexts_json NVARCHAR(MAX) NULL,
        merged_duplicate_chunk_ids_json NVARCHAR(MAX) NULL,
        qdrant_ready BIT NULL,
        validation_flags_json NVARCHAR(MAX) NULL,
        content_hash NVARCHAR(64) NOT NULL,
        payload_json NVARCHAR(MAX) NULL,
        llamaindex_node_json NVARCHAR(MAX) NULL,
        vector_json NVARCHAR(MAX) NULL,
        vector_dim INT NULL,
        vector_model NVARCHAR(120) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_qa_chunks_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_rag_qa_chunks_documents FOREIGN KEY (document_id)
            REFERENCES dbo.rag_qa_documents(document_id)
    );
END;

IF OBJECT_ID(N'dbo.rag_qa_clusters', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_qa_clusters (
        cluster_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        document_id NVARCHAR(80) NOT NULL,
        cluster_label NVARCHAR(100) NOT NULL,
        cluster_level NVARCHAR(60) NOT NULL,
        cluster_type NVARCHAR(80) NOT NULL,
        cluster_keywords NVARCHAR(MAX) NULL,
        cluster_member_count INT NOT NULL,
        cluster_member_chunk_ids NVARCHAR(MAX) NULL,
        cluster_node_json NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_qa_clusters_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_rag_qa_clusters_documents FOREIGN KEY (document_id)
            REFERENCES dbo.rag_qa_documents(document_id)
    );
END;

IF OBJECT_ID(N'dbo.rag_global_clusters', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_global_clusters (
        global_cluster_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        global_cluster_label NVARCHAR(100) NOT NULL,
        global_cluster_level NVARCHAR(60) NOT NULL,
        global_cluster_type NVARCHAR(100) NOT NULL,
        global_cluster_keywords NVARCHAR(MAX) NULL,
        member_document_ids NVARCHAR(MAX) NULL,
        member_cluster_ids NVARCHAR(MAX) NULL,
        member_chunk_ids NVARCHAR(MAX) NULL,
        global_member_count INT NOT NULL,
        global_cluster_node_json NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_global_clusters_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_global_clusters_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_entity_mentions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_entity_mentions (
        mention_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        document_id NVARCHAR(80) NOT NULL,
        chunk_id NVARCHAR(80) NOT NULL,
        entity_type NVARCHAR(80) NOT NULL,
        entity_value NVARCHAR(260) NOT NULL,
        canonical_entity NVARCHAR(260) NOT NULL,
        entity_hash NVARCHAR(64) NOT NULL,
        global_cluster_id NVARCHAR(80) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_entity_mentions_created_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_entity_aliases', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_entity_aliases (
        alias_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        entity_type NVARCHAR(80) NOT NULL,
        alias_value NVARCHAR(260) NOT NULL,
        canonical_entity NVARCHAR(260) NOT NULL,
        entity_hash NVARCHAR(64) NOT NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_entity_aliases_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_entity_aliases_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_chunk_fusion_map', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_chunk_fusion_map (
        fusion_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        canonical_chunk_id NVARCHAR(80) NOT NULL,
        duplicate_chunk_id NVARCHAR(80) NOT NULL,
        canonical_document_id NVARCHAR(80) NOT NULL,
        duplicate_document_id NVARCHAR(80) NOT NULL,
        global_cluster_id NVARCHAR(80) NULL,
        question_hash NVARCHAR(64) NULL,
        answer_hash NVARCHAR(64) NULL,
        fusion_score FLOAT NOT NULL,
        fusion_rule NVARCHAR(120) NOT NULL,
        duplicate_question NVARCHAR(MAX) NULL,
        duplicate_answer NVARCHAR(MAX) NULL,
        duplicate_cleaned_text NVARCHAR(MAX) NULL,
        duplicate_resolution_steps_json NVARCHAR(MAX) NULL,
        merge_policy NVARCHAR(120) NULL,
        merge_payload_json NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_chunk_fusion_map_created_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_validation_issues', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_validation_issues (
        issue_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        document_id NVARCHAR(80) NULL,
        chunk_id NVARCHAR(80) NULL,
        issue_type NVARCHAR(80) NOT NULL,
        issue_level NVARCHAR(40) NOT NULL,
        issue_message NVARCHAR(MAX) NOT NULL,
        issue_payload_json NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_validation_issues_created_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_rag_sync_state', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_rag_sync_state (
        sync_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        document_id NVARCHAR(80) NOT NULL,
        content_hash NVARCHAR(64) NOT NULL,
        sync_target NVARCHAR(120) NOT NULL,
        sync_status NVARCHAR(40) NOT NULL,
        chunk_count INT NOT NULL,
        needs_reindex BIT NOT NULL,
        sync_message NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_rag_sync_state_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_rag_sync_state_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

{ensure_column_script("dbo.rag_qa_documents", "llamaindex_document_json", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "payload_schema_version", "NVARCHAR(60) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "rag_contract_version", "NVARCHAR(60) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "qa_pair_id", "NVARCHAR(80) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "qa_pair_index", "INT NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "qa_similarity_score", "FLOAT NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "qa_similarity_threshold", "FLOAT NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "qa_pair_validated", "BIT NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "cluster_id", "NVARCHAR(80) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "cluster_label", "NVARCHAR(100) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "cluster_level", "NVARCHAR(60) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "cluster_path", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "global_cluster_id", "NVARCHAR(80) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "global_cluster_label", "NVARCHAR(100) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "global_cluster_level", "NVARCHAR(60) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "global_cluster_path", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "question_hash", "NVARCHAR(64) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "answer_hash", "NVARCHAR(64) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "canonical_chunk_id", "NVARCHAR(80) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "fusion_status", "NVARCHAR(40) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "canonical_question", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "answer_text", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "query_aliases_json", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "source_excerpt_full", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "llm_text", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "retrieval_text", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "duplicate_contexts_json", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "merged_duplicate_chunk_ids_json", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "qdrant_ready", "BIT NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "validation_flags_json", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "payload_json", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "llamaindex_node_json", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "vector_json", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "vector_dim", "INT NULL")}
{ensure_column_script("dbo.rag_qa_chunks", "vector_model", "NVARCHAR(120) NULL")}
{ensure_column_script("dbo.rag_chunk_fusion_map", "duplicate_question", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_chunk_fusion_map", "duplicate_answer", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_chunk_fusion_map", "duplicate_cleaned_text", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_chunk_fusion_map", "duplicate_resolution_steps_json", "NVARCHAR(MAX) NULL")}
{ensure_column_script("dbo.rag_chunk_fusion_map", "merge_policy", "NVARCHAR(120) NULL")}
{ensure_column_script("dbo.rag_chunk_fusion_map", "merge_payload_json", "NVARCHAR(MAX) NULL")}

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_qa_chunks_document_id' AND object_id = OBJECT_ID(N'dbo.rag_qa_chunks'))
BEGIN
    CREATE INDEX IX_rag_qa_chunks_document_id ON dbo.rag_qa_chunks(document_id, chunk_index);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_qa_chunks_scene' AND object_id = OBJECT_ID(N'dbo.rag_qa_chunks'))
BEGIN
    CREATE INDEX IX_rag_qa_chunks_scene ON dbo.rag_qa_chunks(scene, audio_no);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_qa_chunks_global_cluster' AND object_id = OBJECT_ID(N'dbo.rag_qa_chunks'))
BEGIN
    CREATE INDEX IX_rag_qa_chunks_global_cluster ON dbo.rag_qa_chunks(global_cluster_id, document_id);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_qa_chunks_question_hash' AND object_id = OBJECT_ID(N'dbo.rag_qa_chunks'))
BEGIN
    CREATE INDEX IX_rag_qa_chunks_question_hash ON dbo.rag_qa_chunks(question_hash);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_qa_chunks_contract_ready' AND object_id = OBJECT_ID(N'dbo.rag_qa_chunks'))
BEGIN
    CREATE INDEX IX_rag_qa_chunks_contract_ready ON dbo.rag_qa_chunks(rag_contract_version, qdrant_ready, fusion_status);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_qa_clusters_document_id' AND object_id = OBJECT_ID(N'dbo.rag_qa_clusters'))
BEGIN
    CREATE INDEX IX_rag_qa_clusters_document_id ON dbo.rag_qa_clusters(document_id, cluster_label);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_entity_mentions_entity_hash' AND object_id = OBJECT_ID(N'dbo.rag_entity_mentions'))
BEGIN
    CREATE INDEX IX_rag_entity_mentions_entity_hash ON dbo.rag_entity_mentions(entity_hash, document_id);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_validation_issues_document_id' AND object_id = OBJECT_ID(N'dbo.rag_validation_issues'))
BEGIN
    CREATE INDEX IX_rag_validation_issues_document_id ON dbo.rag_validation_issues(document_id, issue_type);
END;
"""


def build_ingestion_job_merge_script(payload: StoragePayload) -> str:
    # 序列化任务参数 JSON。
    job_options_json = json.dumps(payload.get("job_options_json", {}), ensure_ascii=False)
    # 返回任务 upsert SQL。
    return f"""
MERGE dbo.rag_ingestion_jobs AS target
USING (
    SELECT
        {sql_literal(payload.get("job_id"))} AS job_id,
        {sql_literal(payload.get("input_path"))} AS input_path,
        {sql_literal(payload.get("job_status"))} AS job_status,
        {sql_int(payload.get("document_count"))} AS document_count,
        {sql_int(payload.get("chunk_count"))} AS chunk_count,
        {sql_int(payload.get("global_cluster_count"))} AS global_cluster_count,
        {sql_int(payload.get("fusion_count"))} AS fusion_count,
        {sql_int(payload.get("validation_issue_count"))} AS validation_issue_count,
        {sql_literal(job_options_json)} AS job_options_json
) AS source
ON target.job_id = source.job_id
WHEN MATCHED THEN
    UPDATE SET
        input_path = source.input_path,
        job_status = source.job_status,
        document_count = source.document_count,
        chunk_count = source.chunk_count,
        global_cluster_count = source.global_cluster_count,
        fusion_count = source.fusion_count,
        validation_issue_count = source.validation_issue_count,
        job_options_json = source.job_options_json,
        updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (job_id, input_path, job_status, document_count, chunk_count, global_cluster_count, fusion_count, validation_issue_count, job_options_json)
    VALUES (source.job_id, source.input_path, source.job_status, source.document_count, source.chunk_count, source.global_cluster_count, source.fusion_count, source.validation_issue_count, source.job_options_json);
"""


def build_document_merge_script(document: Document) -> str:
    # 读取文档元数据。
    metadata = dict(document.metadata)
    # 转换框架参考 JSON。
    framework_json = json.dumps(metadata.get("framework_references", []), ensure_ascii=False)
    # 转换 LlamaIndex 官方 Document JSON。
    llamaindex_document_json = json.dumps(document.to_dict(), ensure_ascii=False, default=str)
    # 返回文档 upsert 和旧关系清理脚本。
    return f"""
MERGE dbo.rag_qa_documents AS target
USING (
    SELECT
        {sql_literal(document.node_id)} AS document_id,
        {sql_literal(metadata.get("source_path", ""))} AS source_path,
        {sql_literal(metadata.get("source_name", ""))} AS source_name,
        {sql_literal(metadata.get("source_name", ""))} AS title,
        {sql_literal(metadata.get("source_hash", ""))} AS content_hash,
        {sql_literal(framework_json)} AS framework_reference,
        {sql_literal(llamaindex_document_json)} AS llamaindex_document_json
) AS source
ON target.document_id = source.document_id
WHEN MATCHED THEN
    UPDATE SET
        source_path = source.source_path,
        source_name = source.source_name,
        title = source.title,
        content_hash = source.content_hash,
        framework_reference = source.framework_reference,
        llamaindex_document_json = source.llamaindex_document_json,
        updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (document_id, source_path, source_name, title, content_hash, framework_reference, llamaindex_document_json)
    VALUES (source.document_id, source.source_path, source.source_name, source.title, source.content_hash, source.framework_reference, source.llamaindex_document_json);

UPDATE dbo.rag_document_versions
SET is_current = 0
WHERE document_id = {sql_literal(document.node_id)};

DELETE FROM dbo.rag_validation_issues
WHERE document_id = {sql_literal(document.node_id)};

DELETE FROM dbo.rag_entity_mentions
WHERE document_id = {sql_literal(document.node_id)};

DELETE FROM dbo.rag_chunk_fusion_map
WHERE canonical_document_id = {sql_literal(document.node_id)}
   OR duplicate_document_id = {sql_literal(document.node_id)};

DELETE FROM dbo.rag_rag_sync_state
WHERE document_id = {sql_literal(document.node_id)};

DELETE FROM dbo.rag_qa_chunks
WHERE document_id = {sql_literal(document.node_id)};

DELETE FROM dbo.rag_qa_clusters
WHERE document_id = {sql_literal(document.node_id)};
"""


def build_document_version_insert_script(payloads: list[StoragePayload]) -> str:
    # 创建 INSERT 片段列表。
    inserts: list[str] = []
    # 遍历文档版本 payload。
    for payload in payloads:
        # 追加单条 MERGE。
        inserts.append(
            f"""
MERGE dbo.rag_document_versions AS target
USING (
    SELECT
        {sql_literal(payload.get("version_id"))} AS version_id,
        {sql_literal(payload.get("document_id"))} AS document_id,
        {sql_literal(payload.get("source_path"))} AS source_path,
        {sql_literal(payload.get("source_name"))} AS source_name,
        {sql_literal(payload.get("content_hash"))} AS content_hash,
        {sql_literal(payload.get("job_id"))} AS job_id,
        {sql_bit(payload.get("is_current"))} AS is_current
) AS source
ON target.version_id = source.version_id
WHEN MATCHED THEN
    UPDATE SET is_current = source.is_current, job_id = source.job_id
WHEN NOT MATCHED THEN
    INSERT (version_id, document_id, source_path, source_name, content_hash, job_id, is_current)
    VALUES (source.version_id, source.document_id, source.source_path, source.source_name, source.content_hash, source.job_id, source.is_current);
"""
        )
    # 返回全部版本 SQL。
    return "\n".join(inserts)


def build_cluster_insert_script(cluster_payloads: list[StoragePayload]) -> str:
    # 创建聚类 INSERT 片段列表。
    inserts: list[str] = []
    # 遍历所有聚类 payload。
    for payload in cluster_payloads:
        # 序列化聚类关键词。
        cluster_keywords_json = json.dumps(payload.get("cluster_keywords", []), ensure_ascii=False)
        # 序列化聚类成员 chunk_id。
        member_ids_json = json.dumps(payload.get("cluster_member_chunk_ids", []), ensure_ascii=False)
        # 序列化 LlamaIndex 官方聚类节点。
        cluster_node_json = json.dumps(payload.get("cluster_node_json", {}), ensure_ascii=False)
        # 追加聚类 INSERT。
        inserts.append(
            f"""
INSERT INTO dbo.rag_qa_clusters (
    cluster_id, document_id, cluster_label, cluster_level, cluster_type,
    cluster_keywords, cluster_member_count, cluster_member_chunk_ids, cluster_node_json
) VALUES (
    {sql_literal(payload.get("cluster_id"))}, {sql_literal(payload.get("document_id"))}, {sql_literal(payload.get("cluster_label"))},
    {sql_literal(payload.get("cluster_level"))}, {sql_literal(payload.get("cluster_type"))},
    {sql_literal(cluster_keywords_json)}, {sql_int(payload.get("cluster_member_count"))},
    {sql_literal(member_ids_json)}, {sql_literal(cluster_node_json)}
);
"""
        )
    # 返回全部聚类 INSERT。
    return "\n".join(inserts)


def build_chunk_insert_script(payloads: list[StoragePayload]) -> str:
    # 创建 INSERT 片段列表。
    inserts: list[str] = []
    # 遍历所有 JSON payload。
    for payload in payloads:
        # 序列化完整 payload。
        payload_json = json.dumps(payload, ensure_ascii=False)
        # 序列化 LlamaIndex 官方 node JSON。
        llamaindex_node_json = json.dumps(payload.get("llamaindex_node", {}), ensure_ascii=False)
        # 序列化步骤。
        steps_json = json.dumps(payload.get("resolution_steps", []), ensure_ascii=False)
        # 序列化关键词。
        keywords_json = json.dumps(payload.get("keywords", []), ensure_ascii=False)
        # 序列化实体。
        entities_json = json.dumps(payload.get("entities", {}), ensure_ascii=False)
        # 序列化向量。
        vector_json = json.dumps(payload.get("vector", []), ensure_ascii=False)
        # 序列化聚类路径。
        cluster_path_json = json.dumps(payload.get("cluster_path", []), ensure_ascii=False)
        # 序列化全局聚类路径。
        global_cluster_path_json = json.dumps(payload.get("global_cluster_path", []), ensure_ascii=False)
        # 序列化 query aliases。
        query_aliases_json = json.dumps(payload.get("query_aliases", []), ensure_ascii=False)
        # 序列化 duplicate 上下文。
        duplicate_contexts_json = json.dumps(payload.get("duplicate_contexts", []), ensure_ascii=False)
        # 序列化已合并 duplicate chunk IDs。
        merged_duplicate_chunk_ids_json = json.dumps(payload.get("merged_duplicate_chunk_ids", []), ensure_ascii=False)
        # 序列化校验标记。
        validation_flags_json = json.dumps(payload.get("validation_flags", []), ensure_ascii=False)
        # 追加单条 INSERT。
        inserts.append(
            f"""
INSERT INTO dbo.rag_qa_chunks (
    chunk_id, document_id, audio_no, audio_title, chunk_index, scene,
    payload_schema_version, rag_contract_version, qa_pair_id, qa_pair_index,
    qa_similarity_score, qa_similarity_threshold, qa_pair_validated,
    cluster_id, cluster_label, cluster_level, cluster_path,
    global_cluster_id, global_cluster_label, global_cluster_level, global_cluster_path,
    question_hash, answer_hash, canonical_chunk_id, fusion_status,
    question, answer, canonical_question, answer_text, query_aliases_json,
    resolution_steps, keywords, entities_json,
    cleaned_text, source_excerpt, source_excerpt_full, llm_text, retrieval_text,
    duplicate_contexts_json, merged_duplicate_chunk_ids_json, qdrant_ready, validation_flags_json,
    content_hash, payload_json,
    llamaindex_node_json, vector_json, vector_dim, vector_model
) VALUES (
    {sql_literal(payload.get("chunk_id"))}, {sql_literal(payload.get("document_id"))}, {sql_int(payload.get("audio_no"))}, {sql_literal(payload.get("audio_title"))}, {sql_int(payload.get("chunk_index"))}, {sql_literal(payload.get("scene"))},
    {sql_literal(payload.get("payload_schema_version"))}, {sql_literal(payload.get("rag_contract_version"))}, {sql_literal(payload.get("qa_pair_id"))}, {sql_int(payload.get("qa_pair_index"))},
    {sql_float(payload.get("qa_similarity_score"))}, {sql_float(payload.get("qa_similarity_threshold"))}, {sql_bit(payload.get("qa_pair_validated"))},
    {sql_literal(payload.get("cluster_id"))}, {sql_literal(payload.get("cluster_label"))}, {sql_literal(payload.get("cluster_level"))}, {sql_literal(cluster_path_json)},
    {sql_literal(payload.get("global_cluster_id"))}, {sql_literal(payload.get("global_cluster_label"))}, {sql_literal(payload.get("global_cluster_level"))}, {sql_literal(global_cluster_path_json)},
    {sql_literal(payload.get("question_hash"))}, {sql_literal(payload.get("answer_hash"))}, {sql_literal(payload.get("canonical_chunk_id"))}, {sql_literal(payload.get("fusion_status"))},
    {sql_literal(payload.get("question"))}, {sql_literal(payload.get("answer"))}, {sql_literal(payload.get("canonical_question"))}, {sql_literal(payload.get("answer_text"))}, {sql_literal(query_aliases_json)},
    {sql_literal(steps_json)}, {sql_literal(keywords_json)}, {sql_literal(entities_json)},
    {sql_literal(payload.get("cleaned_text"))}, {sql_literal(payload.get("source_excerpt"))}, {sql_literal(payload.get("source_excerpt_full"))}, {sql_literal(payload.get("llm_text"))}, {sql_literal(payload.get("retrieval_text"))},
    {sql_literal(duplicate_contexts_json)}, {sql_literal(merged_duplicate_chunk_ids_json)}, {sql_bit(payload.get("qdrant_ready"))}, {sql_literal(validation_flags_json)},
    {sql_literal(payload.get("content_hash"))}, {sql_literal(payload_json)},
    {sql_literal(llamaindex_node_json)}, {sql_literal(vector_json)}, {sql_int(payload.get("vector_dim", 0))}, {sql_literal(payload.get("vector_model"))}
);
"""
        )
    # 返回全部 INSERT。
    return "\n".join(inserts)


def build_global_cluster_insert_script(payloads: list[StoragePayload]) -> str:
    # 创建全局聚类 MERGE 片段列表。
    merges: list[str] = []
    # 遍历全局聚类 payload。
    for payload in payloads:
        # 序列化关键词。
        keywords_json = json.dumps(payload.get("global_cluster_keywords", []), ensure_ascii=False)
        # 序列化成员文档。
        document_ids_json = json.dumps(payload.get("member_document_ids", []), ensure_ascii=False)
        # 序列化成员文档内聚类。
        cluster_ids_json = json.dumps(payload.get("member_cluster_ids", []), ensure_ascii=False)
        # 序列化成员 chunk。
        chunk_ids_json = json.dumps(payload.get("member_chunk_ids", []), ensure_ascii=False)
        # 序列化 LlamaIndex 官方全局聚类节点。
        node_json = json.dumps(payload.get("global_cluster_node_json", {}), ensure_ascii=False)
        # 追加 MERGE。
        merges.append(
            f"""
MERGE dbo.rag_global_clusters AS target
USING (
    SELECT
        {sql_literal(payload.get("global_cluster_id"))} AS global_cluster_id,
        {sql_literal(payload.get("global_cluster_label"))} AS global_cluster_label,
        {sql_literal(payload.get("global_cluster_level"))} AS global_cluster_level,
        {sql_literal(payload.get("global_cluster_type"))} AS global_cluster_type,
        {sql_literal(keywords_json)} AS global_cluster_keywords,
        {sql_literal(document_ids_json)} AS member_document_ids,
        {sql_literal(cluster_ids_json)} AS member_cluster_ids,
        {sql_literal(chunk_ids_json)} AS member_chunk_ids,
        {sql_int(payload.get("global_member_count"))} AS global_member_count,
        {sql_literal(node_json)} AS global_cluster_node_json
) AS source
ON target.global_cluster_id = source.global_cluster_id
WHEN MATCHED THEN
    UPDATE SET
        global_cluster_label = source.global_cluster_label,
        global_cluster_level = source.global_cluster_level,
        global_cluster_type = source.global_cluster_type,
        global_cluster_keywords = source.global_cluster_keywords,
        member_document_ids = source.member_document_ids,
        member_cluster_ids = source.member_cluster_ids,
        member_chunk_ids = source.member_chunk_ids,
        global_member_count = source.global_member_count,
        global_cluster_node_json = source.global_cluster_node_json,
        updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (global_cluster_id, global_cluster_label, global_cluster_level, global_cluster_type, global_cluster_keywords, member_document_ids, member_cluster_ids, member_chunk_ids, global_member_count, global_cluster_node_json)
    VALUES (source.global_cluster_id, source.global_cluster_label, source.global_cluster_level, source.global_cluster_type, source.global_cluster_keywords, source.member_document_ids, source.member_cluster_ids, source.member_chunk_ids, source.global_member_count, source.global_cluster_node_json);
"""
        )
    # 返回全部全局聚类 MERGE。
    return "\n".join(merges)


def build_entity_mention_insert_script(payloads: list[StoragePayload]) -> str:
    # 创建 INSERT 片段列表。
    inserts: list[str] = []
    # 遍历实体提及 payload。
    for payload in payloads:
        # 追加 INSERT。
        inserts.append(
            f"""
INSERT INTO dbo.rag_entity_mentions (
    mention_id, document_id, chunk_id, entity_type, entity_value,
    canonical_entity, entity_hash, global_cluster_id
) VALUES (
    {sql_literal(payload.get("mention_id"))}, {sql_literal(payload.get("document_id"))}, {sql_literal(payload.get("chunk_id"))},
    {sql_literal(payload.get("entity_type"))}, {sql_literal(payload.get("entity_value"))},
    {sql_literal(payload.get("canonical_entity"))}, {sql_literal(payload.get("entity_hash"))}, {sql_literal(payload.get("global_cluster_id"))}
);
"""
        )
    # 返回全部实体提及 INSERT。
    return "\n".join(inserts)


def build_entity_alias_merge_script(payloads: list[StoragePayload]) -> str:
    # 创建 MERGE 片段列表。
    merges: list[str] = []
    # 遍历实体别名 payload。
    for payload in payloads:
        # 追加 MERGE。
        merges.append(
            f"""
MERGE dbo.rag_entity_aliases AS target
USING (
    SELECT
        {sql_literal(payload.get("alias_id"))} AS alias_id,
        {sql_literal(payload.get("entity_type"))} AS entity_type,
        {sql_literal(payload.get("alias_value"))} AS alias_value,
        {sql_literal(payload.get("canonical_entity"))} AS canonical_entity,
        {sql_literal(payload.get("entity_hash"))} AS entity_hash
) AS source
ON target.alias_id = source.alias_id
WHEN MATCHED THEN
    UPDATE SET
        entity_type = source.entity_type,
        alias_value = source.alias_value,
        canonical_entity = source.canonical_entity,
        entity_hash = source.entity_hash,
        updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (alias_id, entity_type, alias_value, canonical_entity, entity_hash)
    VALUES (source.alias_id, source.entity_type, source.alias_value, source.canonical_entity, source.entity_hash);
"""
        )
    # 返回全部实体别名 MERGE。
    return "\n".join(merges)


def build_fusion_insert_script(payloads: list[StoragePayload]) -> str:
    # 创建融合 INSERT 片段列表。
    inserts: list[str] = []
    # 遍历融合 payload。
    for payload in payloads:
        # 序列化 duplicate 步骤。
        duplicate_steps_json = json.dumps(payload.get("duplicate_resolution_steps", []), ensure_ascii=False)
        # 序列化融合补充 payload。
        merge_payload_json = json.dumps(payload.get("merge_payload", {}), ensure_ascii=False)
        # 追加 MERGE，避免同一融合关系重复写入。
        inserts.append(
            f"""
MERGE dbo.rag_chunk_fusion_map AS target
USING (
    SELECT
        {sql_literal(payload.get("fusion_id"))} AS fusion_id,
        {sql_literal(payload.get("canonical_chunk_id"))} AS canonical_chunk_id,
        {sql_literal(payload.get("duplicate_chunk_id"))} AS duplicate_chunk_id,
        {sql_literal(payload.get("canonical_document_id"))} AS canonical_document_id,
        {sql_literal(payload.get("duplicate_document_id"))} AS duplicate_document_id,
        {sql_literal(payload.get("global_cluster_id"))} AS global_cluster_id,
        {sql_literal(payload.get("question_hash"))} AS question_hash,
        {sql_literal(payload.get("answer_hash"))} AS answer_hash,
        {sql_float(payload.get("fusion_score"))} AS fusion_score,
        {sql_literal(payload.get("fusion_rule"))} AS fusion_rule,
        {sql_literal(payload.get("duplicate_question"))} AS duplicate_question,
        {sql_literal(payload.get("duplicate_answer"))} AS duplicate_answer,
        {sql_literal(payload.get("duplicate_cleaned_text"))} AS duplicate_cleaned_text,
        {sql_literal(duplicate_steps_json)} AS duplicate_resolution_steps_json,
        {sql_literal(payload.get("merge_policy"))} AS merge_policy,
        {sql_literal(merge_payload_json)} AS merge_payload_json
) AS source
ON target.fusion_id = source.fusion_id
WHEN NOT MATCHED THEN
    INSERT (
        fusion_id, canonical_chunk_id, duplicate_chunk_id, canonical_document_id, duplicate_document_id,
        global_cluster_id, question_hash, answer_hash, fusion_score, fusion_rule,
        duplicate_question, duplicate_answer, duplicate_cleaned_text, duplicate_resolution_steps_json,
        merge_policy, merge_payload_json
    )
    VALUES (
        source.fusion_id, source.canonical_chunk_id, source.duplicate_chunk_id, source.canonical_document_id, source.duplicate_document_id,
        source.global_cluster_id, source.question_hash, source.answer_hash, source.fusion_score, source.fusion_rule,
        source.duplicate_question, source.duplicate_answer, source.duplicate_cleaned_text, source.duplicate_resolution_steps_json,
        source.merge_policy, source.merge_payload_json
    );
"""
        )
    # 返回全部融合 SQL。
    return "\n".join(inserts)


def build_validation_issue_insert_script(payloads: list[StoragePayload]) -> str:
    # 创建校验问题 MERGE 片段列表。
    inserts: list[str] = []
    # 遍历校验问题 payload。
    for payload in payloads:
        # 序列化问题 payload。
        issue_payload_json = json.dumps(payload.get("issue_payload", {}), ensure_ascii=False)
        # 追加 MERGE。
        inserts.append(
            f"""
MERGE dbo.rag_validation_issues AS target
USING (
    SELECT
        {sql_literal(payload.get("issue_id"))} AS issue_id,
        {sql_literal(payload.get("document_id"))} AS document_id,
        {sql_literal(payload.get("chunk_id"))} AS chunk_id,
        {sql_literal(payload.get("issue_type"))} AS issue_type,
        {sql_literal(payload.get("issue_level"))} AS issue_level,
        {sql_literal(payload.get("issue_message"))} AS issue_message,
        {sql_literal(issue_payload_json)} AS issue_payload_json
) AS source
ON target.issue_id = source.issue_id
WHEN NOT MATCHED THEN
    INSERT (issue_id, document_id, chunk_id, issue_type, issue_level, issue_message, issue_payload_json)
    VALUES (source.issue_id, source.document_id, source.chunk_id, source.issue_type, source.issue_level, source.issue_message, source.issue_payload_json);
"""
        )
    # 返回全部校验问题 SQL。
    return "\n".join(inserts)


def build_rag_sync_merge_script(payloads: list[StoragePayload]) -> str:
    # 创建同步状态 MERGE 片段列表。
    merges: list[str] = []
    # 遍历同步状态 payload。
    for payload in payloads:
        # 追加 MERGE。
        merges.append(
            f"""
MERGE dbo.rag_rag_sync_state AS target
USING (
    SELECT
        {sql_literal(payload.get("sync_id"))} AS sync_id,
        {sql_literal(payload.get("document_id"))} AS document_id,
        {sql_literal(payload.get("content_hash"))} AS content_hash,
        {sql_literal(payload.get("sync_target"))} AS sync_target,
        {sql_literal(payload.get("sync_status"))} AS sync_status,
        {sql_int(payload.get("chunk_count"))} AS chunk_count,
        {sql_bit(payload.get("needs_reindex"))} AS needs_reindex,
        {sql_literal(payload.get("sync_message"))} AS sync_message
) AS source
ON target.sync_id = source.sync_id
WHEN MATCHED THEN
    UPDATE SET
        content_hash = source.content_hash,
        sync_status = source.sync_status,
        chunk_count = source.chunk_count,
        needs_reindex = source.needs_reindex,
        sync_message = source.sync_message,
        updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (sync_id, document_id, content_hash, sync_target, sync_status, chunk_count, needs_reindex, sync_message)
    VALUES (source.sync_id, source.document_id, source.content_hash, source.sync_target, source.sync_status, source.chunk_count, source.needs_reindex, source.sync_message);
"""
        )
    # 返回全部同步状态 SQL。
    return "\n".join(merges)


def rebuild_global_relations_from_chunks_script() -> str:
    # 返回 SQL Server 侧基于所有 chunk 重建全局关系的脚本。
    return """
;WITH cluster_stats AS (
    SELECT
        global_cluster_id,
        MAX(global_cluster_label) AS global_cluster_label,
        MAX(global_cluster_level) AS global_cluster_level,
        N'cross_document_scene_cluster' AS global_cluster_type,
        STRING_AGG(CONVERT(NVARCHAR(MAX), document_id), N',') AS member_document_ids,
        STRING_AGG(CONVERT(NVARCHAR(MAX), cluster_id), N',') AS member_cluster_ids,
        STRING_AGG(CONVERT(NVARCHAR(MAX), chunk_id), N',') AS member_chunk_ids,
        COUNT(*) AS global_member_count
    FROM dbo.rag_qa_chunks
    WHERE global_cluster_id IS NOT NULL AND global_cluster_id <> N''
    GROUP BY global_cluster_id
)
MERGE dbo.rag_global_clusters AS target
USING cluster_stats AS source
ON target.global_cluster_id = source.global_cluster_id
WHEN MATCHED THEN
    UPDATE SET
        global_cluster_label = source.global_cluster_label,
        global_cluster_level = source.global_cluster_level,
        global_cluster_type = source.global_cluster_type,
        member_document_ids = source.member_document_ids,
        member_cluster_ids = source.member_cluster_ids,
        member_chunk_ids = source.member_chunk_ids,
        global_member_count = source.global_member_count,
        updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (global_cluster_id, global_cluster_label, global_cluster_level, global_cluster_type, member_document_ids, member_cluster_ids, member_chunk_ids, global_member_count)
    VALUES (source.global_cluster_id, source.global_cluster_label, source.global_cluster_level, source.global_cluster_type, source.member_document_ids, source.member_cluster_ids, source.member_chunk_ids, source.global_member_count);

DELETE target
FROM dbo.rag_global_clusters AS target
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.rag_qa_chunks AS chunks
    WHERE chunks.global_cluster_id = target.global_cluster_id
);

;WITH duplicate_questions AS (
    SELECT
        chunk_id,
        document_id,
        global_cluster_id,
        question_hash,
        answer_hash,
        MIN(chunk_id) OVER (PARTITION BY question_hash) AS canonical_chunk_id
    FROM dbo.rag_qa_chunks
    WHERE question_hash IS NOT NULL AND question_hash <> N''
)
INSERT INTO dbo.rag_chunk_fusion_map (
    fusion_id, canonical_chunk_id, duplicate_chunk_id, canonical_document_id,
    duplicate_document_id, global_cluster_id, question_hash, answer_hash,
    fusion_score, fusion_rule
)
SELECT
    N'qafusion_' + LOWER(SUBSTRING(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT(duplicate_questions.canonical_chunk_id, N'|', duplicate_questions.chunk_id, N'|sqlserver_same_question_hash_global')), 2), 1, 24)) AS fusion_id,
    duplicate_questions.canonical_chunk_id,
    duplicate_questions.chunk_id AS duplicate_chunk_id,
    canonical.document_id AS canonical_document_id,
    duplicate_questions.document_id AS duplicate_document_id,
    duplicate_questions.global_cluster_id,
    duplicate_questions.question_hash,
    duplicate_questions.answer_hash,
    1.0 AS fusion_score,
    N'sqlserver_same_question_hash_global' AS fusion_rule
FROM duplicate_questions
INNER JOIN dbo.rag_qa_chunks AS canonical
    ON canonical.chunk_id = duplicate_questions.canonical_chunk_id
WHERE duplicate_questions.chunk_id <> duplicate_questions.canonical_chunk_id
  AND duplicate_questions.answer_hash = canonical.answer_hash
  AND NOT EXISTS (
      SELECT 1
      FROM dbo.rag_chunk_fusion_map AS existing
      WHERE existing.duplicate_chunk_id = duplicate_questions.chunk_id
  );

UPDATE chunks
SET canonical_chunk_id = fusion.canonical_chunk_id,
    fusion_status = N'duplicate'
FROM dbo.rag_qa_chunks AS chunks
INNER JOIN dbo.rag_chunk_fusion_map AS fusion
    ON fusion.duplicate_chunk_id = chunks.chunk_id;

UPDATE dbo.rag_qa_chunks
SET canonical_chunk_id = chunk_id,
    fusion_status = N'canonical'
WHERE canonical_chunk_id IS NULL OR canonical_chunk_id = N'';

;WITH conflict_questions AS (
    SELECT question_hash
    FROM dbo.rag_qa_chunks
    WHERE question_hash IS NOT NULL AND question_hash <> N''
    GROUP BY question_hash
    HAVING COUNT(DISTINCT answer_hash) > 1
)
INSERT INTO dbo.rag_validation_issues (
    issue_id, document_id, chunk_id, issue_type, issue_level,
    issue_message, issue_payload_json
)
SELECT
    N'qaissue_' + LOWER(SUBSTRING(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT(chunks.chunk_id, N'|sqlserver_conflicting_answer_global')), 2), 1, 24)) AS issue_id,
    chunks.document_id,
    chunks.chunk_id,
    N'conflicting_answer_global' AS issue_type,
    N'warning' AS issue_level,
    N'SQL Server 全局检查发现同一规范问题存在不同答案，需要消歧或融合后再喂给后续 RAG。' AS issue_message,
    CONCAT(N'{"question_hash":"', chunks.question_hash, N'","answer_hash":"', chunks.answer_hash, N'"}') AS issue_payload_json
FROM dbo.rag_qa_chunks AS chunks
INNER JOIN conflict_questions
    ON conflict_questions.question_hash = chunks.question_hash
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.rag_validation_issues AS existing
    WHERE existing.issue_id = N'qaissue_' + LOWER(SUBSTRING(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT(chunks.chunk_id, N'|sqlserver_conflicting_answer_global')), 2), 1, 24))
);
"""


def build_sqlserver_script(bundle: DatabaseWriteBundle) -> str:
    # 生成建表补列脚本。
    schema_sql = ensure_sqlserver_schema_script()
    # 生成任务 upsert 脚本。
    job_sql = build_ingestion_job_merge_script(bundle.ingestion_job)
    # 生成所有文档 upsert 和旧关系清理脚本。
    document_sql = "\n".join(build_document_merge_script(document) for document in bundle.documents)
    # 生成文档版本脚本。
    version_sql = build_document_version_insert_script(bundle.document_versions)
    # 生成文档内聚类脚本。
    cluster_sql = build_cluster_insert_script(bundle.document_cluster_payloads)
    # 生成 chunk 脚本。
    chunk_sql = build_chunk_insert_script(bundle.chunk_payloads)
    # 生成全局聚类脚本。
    global_cluster_sql = build_global_cluster_insert_script(bundle.global_cluster_payloads)
    # 生成实体提及脚本。
    entity_mention_sql = build_entity_mention_insert_script(bundle.entity_mention_payloads)
    # 生成实体别名脚本。
    entity_alias_sql = build_entity_alias_merge_script(bundle.entity_alias_payloads)
    # 生成融合关系脚本。
    fusion_sql = build_fusion_insert_script(bundle.fusion_payloads)
    # 生成校验问题脚本。
    validation_sql = build_validation_issue_insert_script(bundle.validation_issue_payloads)
    # 生成 RAG 同步状态脚本。
    rag_sync_sql = build_rag_sync_merge_script(bundle.rag_sync_payloads)
    # 生成 SQL Server 侧全局关系重建脚本。
    rebuild_sql = rebuild_global_relations_from_chunks_script()
    # 生成结果计数查询。
    summary_sql = f"""
SELECT COUNT(*) AS batch_documents
FROM dbo.rag_qa_documents
WHERE document_id IN ({",".join(sql_literal(document.node_id) for document in bundle.documents)});

SELECT COUNT(*) AS batch_chunks
FROM dbo.rag_qa_chunks
WHERE document_id IN ({",".join(sql_literal(document.node_id) for document in bundle.documents)});

SELECT COUNT(*) AS global_clusters
FROM dbo.rag_global_clusters;

SELECT COUNT(*) AS fusion_links
FROM dbo.rag_chunk_fusion_map;

SELECT COUNT(*) AS validation_issues
FROM dbo.rag_validation_issues;
"""
    # GO 用于让 SQL Server 先编译建表批次，再编译新列 INSERT 批次。
    return f"{schema_sql}\nGO\nBEGIN TRANSACTION;\n{job_sql}\n{document_sql}\n{version_sql}\n{cluster_sql}\n{chunk_sql}\n{global_cluster_sql}\n{entity_mention_sql}\n{entity_alias_sql}\n{fusion_sql}\n{validation_sql}\n{rag_sync_sql}\n{rebuild_sql}\nCOMMIT TRANSACTION;\n{summary_sql}"


def split_sql_batches(sql_text: str) -> list[str]:
    # 创建批次列表。
    batches: list[str] = []
    # 创建当前批次行缓存。
    current_lines: list[str] = []
    # 逐行扫描 SQL。
    for line in sql_text.splitlines():
        # 单独一行 GO 表示批次结束。
        if line.strip().upper() == "GO":
            # 当前批次非空时保存。
            if "\n".join(current_lines).strip():
                # 追加批次。
                batches.append("\n".join(current_lines))
            # 清空当前批次。
            current_lines = []
            # 继续下一行。
            continue
        # 普通 SQL 行进入当前批次。
        current_lines.append(line)
    # 保存最后批次。
    if "\n".join(current_lines).strip():
        # 追加最后批次。
        batches.append("\n".join(current_lines))
    # 返回批次列表。
    return batches


def run_sqlcmd(sql_text: str, container: str, server: str, database: str, user: str, password: str) -> str:
    # 组装 Docker 容器内 sqlcmd 命令。
    command = [
        "docker",
        "exec",
        "-i",
        container,
        "/opt/mssql-tools18/bin/sqlcmd",
        "-S",
        server,
        "-U",
        user,
        "-P",
        password,
        "-C",
        "-d",
        database,
        "-b",
        "-W",
    ]
    # 通过 stdin 执行 SQL 文本。
    result = subprocess.run(command, input=sql_text, text=True, encoding="utf-8", capture_output=True)
    # 非 0 退出码表示失败。
    if result.returncode != 0:
        # 抛出详细错误。
        raise RuntimeError(f"sqlcmd 入库失败：\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    # 返回 sqlcmd 输出。
    return result.stdout.strip()


def save_to_sqlserver_sqlcmd(bundle: DatabaseWriteBundle, container: str, server: str, database: str, user: str, password: str) -> str:
    # 构造 SQL Server 入库脚本。
    sql_text = build_sqlserver_script(bundle)
    # 调用 sqlcmd 执行。
    return run_sqlcmd(sql_text, container, server, database, user, password)


def save_to_sqlserver_pyodbc(bundle: DatabaseWriteBundle, server: str, database: str, user: str, password: str, driver: str) -> str:
    # 尝试导入 pyodbc。
    try:
        # 导入 SQL Server ODBC 驱动。
        import pyodbc  # type: ignore
    # 没安装时给出明确错误。
    except ImportError as exc:
        # 抛出运行错误。
        raise RuntimeError("当前 Python 环境没有安装 pyodbc，请改用 --db-backend sqlcmd 或安装 pyodbc。") from exc
    # 拼接 ODBC 连接串。
    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )
    # 构造 SQL Server 入库脚本。
    sql_text = build_sqlserver_script(bundle)
    # 打开连接。
    with pyodbc.connect(connection_string, autocommit=True) as connection:
        # 创建游标。
        cursor = connection.cursor()
        # pyodbc 不识别 GO，所以手动分批执行。
        for batch in split_sql_batches(sql_text):
            # 执行当前批次。
            cursor.execute(batch)
    # 返回成功信息。
    return f"pyodbc 写入完成，文档数：{len(bundle.documents)}，记录数：{len(bundle.chunk_payloads)}，全局聚类数：{len(bundle.global_cluster_payloads)}"


def write_debug_sql(sql_path: Path, bundle: DatabaseWriteBundle) -> None:
    # 创建父目录。
    sql_path.parent.mkdir(parents=True, exist_ok=True)
    # 写入完整 SQL 脚本。
    sql_path.write_text(build_sqlserver_script(bundle), encoding="utf-8")
