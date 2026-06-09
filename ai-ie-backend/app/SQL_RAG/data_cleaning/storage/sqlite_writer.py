# -*- coding: utf-8 -*-
"""SQLite 兜底验证入库逻辑，入库内容来自 LlamaIndex TextNode JSON payload。"""

# 修改日期：2026-06-01 13:29:35。
# 修改理由：让 SQLite 测试库同步具备多文档全局聚类、融合、校验和 RAG 同步状态表，避免测试结构落后于 SQL Server。

# 导入 JSON 库。
import json
# 导入 SQLite 标准库。
import sqlite3
# 导入路径类型。
from pathlib import Path

# 导入当前时间工具。
from common.utils import now_iso, stable_id
# 导入数据库写入 bundle。
from data_structures.models import DatabaseWriteBundle, StoragePayload


def ensure_sqlite_column(connection: sqlite3.Connection, table_name: str, column_name: str, column_definition: str) -> None:
    # 读取当前表结构。
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    # 收集已有列名。
    existing_columns = {str(row[1]) for row in rows}
    # 已存在时直接返回。
    if column_name in existing_columns:
        # 不重复补列。
        return
    # 执行 SQLite 补列。
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
    # 创建摄取任务表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_ingestion_jobs (
            job_id TEXT PRIMARY KEY,
            input_path TEXT NOT NULL,
            job_status TEXT NOT NULL,
            document_count INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL,
            global_cluster_count INTEGER NOT NULL,
            fusion_count INTEGER NOT NULL,
            validation_issue_count INTEGER NOT NULL,
            job_options_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    # 创建文档表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_qa_documents (
            document_id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            source_name TEXT NOT NULL,
            title TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            framework_reference TEXT,
            llamaindex_document_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    # 创建文档版本表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_document_versions (
            version_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_name TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            job_id TEXT NOT NULL,
            is_current INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    # 创建分块表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_qa_chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            audio_no INTEGER NOT NULL,
            audio_title TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            payload_schema_version TEXT,
            qa_pair_id TEXT,
            qa_pair_index INTEGER,
            qa_similarity_score REAL,
            qa_similarity_threshold REAL,
            qa_pair_validated INTEGER,
            cluster_id TEXT,
            cluster_label TEXT,
            cluster_level TEXT,
            cluster_path TEXT,
            global_cluster_id TEXT,
            global_cluster_label TEXT,
            global_cluster_level TEXT,
            global_cluster_path TEXT,
            question_hash TEXT,
            answer_hash TEXT,
            canonical_chunk_id TEXT,
            fusion_status TEXT,
            scene TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            resolution_steps TEXT,
            keywords TEXT,
            entities_json TEXT,
            cleaned_text TEXT NOT NULL,
            source_excerpt TEXT,
            content_hash TEXT NOT NULL,
            payload_json TEXT,
            llamaindex_node_json TEXT,
            vector_json TEXT,
            vector_dim INTEGER,
            vector_model TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    # 为历史 SQLite 文件补齐新列。
    for column_name, column_definition in {
        "global_cluster_id": "TEXT",
        "global_cluster_label": "TEXT",
        "global_cluster_level": "TEXT",
        "global_cluster_path": "TEXT",
        "question_hash": "TEXT",
        "answer_hash": "TEXT",
        "canonical_chunk_id": "TEXT",
        "fusion_status": "TEXT",
    }.items():
        # 执行安全补列。
        ensure_sqlite_column(connection, "rag_qa_chunks", column_name, column_definition)
    # 创建文档内聚类表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_qa_clusters (
            cluster_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            cluster_label TEXT NOT NULL,
            cluster_level TEXT NOT NULL,
            cluster_type TEXT NOT NULL,
            cluster_keywords TEXT,
            cluster_member_count INTEGER NOT NULL,
            cluster_member_chunk_ids TEXT,
            cluster_node_json TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    # 创建全局聚类表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_global_clusters (
            global_cluster_id TEXT PRIMARY KEY,
            global_cluster_label TEXT NOT NULL,
            global_cluster_level TEXT NOT NULL,
            global_cluster_type TEXT NOT NULL,
            global_cluster_keywords TEXT,
            member_document_ids TEXT,
            member_cluster_ids TEXT,
            member_chunk_ids TEXT,
            global_member_count INTEGER NOT NULL,
            global_cluster_node_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    # 创建实体提及表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_entity_mentions (
            mention_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_value TEXT NOT NULL,
            canonical_entity TEXT NOT NULL,
            entity_hash TEXT NOT NULL,
            global_cluster_id TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    # 创建实体别名表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_entity_aliases (
            alias_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            alias_value TEXT NOT NULL,
            canonical_entity TEXT NOT NULL,
            entity_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    # 创建 chunk 融合表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_chunk_fusion_map (
            fusion_id TEXT PRIMARY KEY,
            canonical_chunk_id TEXT NOT NULL,
            duplicate_chunk_id TEXT NOT NULL,
            canonical_document_id TEXT NOT NULL,
            duplicate_document_id TEXT NOT NULL,
            global_cluster_id TEXT,
            question_hash TEXT,
            answer_hash TEXT,
            fusion_score REAL NOT NULL,
            fusion_rule TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    # 创建校验问题表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_validation_issues (
            issue_id TEXT PRIMARY KEY,
            document_id TEXT,
            chunk_id TEXT,
            issue_type TEXT NOT NULL,
            issue_level TEXT NOT NULL,
            issue_message TEXT NOT NULL,
            issue_payload_json TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    # 创建 RAG 同步状态表。
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_rag_sync_state (
            sync_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            sync_target TEXT NOT NULL,
            sync_status TEXT NOT NULL,
            chunk_count INTEGER NOT NULL,
            needs_reindex INTEGER NOT NULL,
            sync_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def reset_document_scoped_rows(connection: sqlite3.Connection, document_id: str) -> None:
    # 标记同文档旧版本为非当前。
    connection.execute("UPDATE rag_document_versions SET is_current = 0 WHERE document_id = ?", (document_id,))
    # 删除当前文档旧校验问题。
    connection.execute("DELETE FROM rag_validation_issues WHERE document_id = ?", (document_id,))
    # 删除当前文档旧实体提及。
    connection.execute("DELETE FROM rag_entity_mentions WHERE document_id = ?", (document_id,))
    # 删除当前文档旧融合关系。
    connection.execute("DELETE FROM rag_chunk_fusion_map WHERE canonical_document_id = ? OR duplicate_document_id = ?", (document_id, document_id))
    # 删除当前文档旧 RAG 同步状态。
    connection.execute("DELETE FROM rag_rag_sync_state WHERE document_id = ?", (document_id,))
    # 删除当前文档旧 chunk。
    connection.execute("DELETE FROM rag_qa_chunks WHERE document_id = ?", (document_id,))
    # 删除当前文档旧聚类。
    connection.execute("DELETE FROM rag_qa_clusters WHERE document_id = ?", (document_id,))


def insert_ingestion_job(connection: sqlite3.Connection, payload: StoragePayload) -> None:
    # 写入或替换摄取任务。
    connection.execute(
        """
        INSERT OR REPLACE INTO rag_ingestion_jobs (
            job_id, input_path, job_status, document_count, chunk_count,
            global_cluster_count, fusion_count, validation_issue_count,
            job_options_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("job_id"),
            payload.get("input_path"),
            payload.get("job_status"),
            payload.get("document_count"),
            payload.get("chunk_count"),
            payload.get("global_cluster_count"),
            payload.get("fusion_count"),
            payload.get("validation_issue_count"),
            json.dumps(payload.get("job_options_json", {}), ensure_ascii=False),
            now_iso(),
            now_iso(),
        ),
    )


def refresh_sqlite_fusion_status(connection: sqlite3.Connection) -> None:
    # 读取所有带问题哈希和答案哈希的 chunk。
    rows = connection.execute(
        """
        SELECT chunk_id, document_id, global_cluster_id, question_hash, answer_hash
        FROM rag_qa_chunks
        WHERE question_hash IS NOT NULL AND question_hash <> ''
          AND answer_hash IS NOT NULL AND answer_hash <> ''
        ORDER BY question_hash, answer_hash, chunk_id
        """
    ).fetchall()
    # 创建同问同答分组。
    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    # 遍历查询结果。
    for row in rows:
        # 构造分组键。
        key = (str(row["question_hash"]), str(row["answer_hash"]))
        # 追加当前行。
        groups.setdefault(key, []).append(row)
    # 遍历同问同答分组。
    for (question_hash, answer_hash), members in groups.items():
        # 单成员无需融合。
        if len(members) <= 1:
            # 继续下一组。
            continue
        # 取 chunk_id 最小者作为规范 chunk。
        canonical = sorted(members, key=lambda item: str(item["chunk_id"]))[0]
        # 遍历重复 chunk。
        for duplicate in sorted(members, key=lambda item: str(item["chunk_id"]))[1:]:
            # 如果重复 chunk 已有融合关系，则不重复插入。
            exists = connection.execute(
                "SELECT 1 FROM rag_chunk_fusion_map WHERE duplicate_chunk_id = ? LIMIT 1",
                (duplicate["chunk_id"],),
            ).fetchone()
            # 已存在时跳过。
            if exists:
                # 继续下一重复 chunk。
                continue
            # 生成融合 ID。
            fusion_id = stable_id("qafusion", canonical["chunk_id"], duplicate["chunk_id"], "sqlite_same_question_hash_global")
            # 插入 SQLite 全局同问同答融合关系。
            connection.execute(
                """
                INSERT INTO rag_chunk_fusion_map (
                    fusion_id, canonical_chunk_id, duplicate_chunk_id,
                    canonical_document_id, duplicate_document_id, global_cluster_id,
                    question_hash, answer_hash, fusion_score, fusion_rule, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fusion_id,
                    canonical["chunk_id"],
                    duplicate["chunk_id"],
                    canonical["document_id"],
                    duplicate["document_id"],
                    duplicate["global_cluster_id"],
                    question_hash,
                    answer_hash,
                    1.0,
                    "sqlite_same_question_hash_global",
                    now_iso(),
                ),
            )
    # 把融合映射表中的重复 chunk 标记为 duplicate。
    connection.execute(
        """
        UPDATE rag_qa_chunks
        SET fusion_status = 'duplicate',
            canonical_chunk_id = (
                SELECT canonical_chunk_id
                FROM rag_chunk_fusion_map
                WHERE duplicate_chunk_id = rag_qa_chunks.chunk_id
                LIMIT 1
            )
        WHERE chunk_id IN (SELECT duplicate_chunk_id FROM rag_chunk_fusion_map)
        """
    )
    # 兜底补齐规范 chunk。
    connection.execute(
        """
        UPDATE rag_qa_chunks
        SET fusion_status = COALESCE(fusion_status, 'canonical'),
            canonical_chunk_id = COALESCE(canonical_chunk_id, chunk_id)
        WHERE canonical_chunk_id IS NULL OR canonical_chunk_id = ''
        """
    )


def save_to_sqlite(sqlite_path: Path, bundle: DatabaseWriteBundle) -> str:
    # 创建 SQLite 文件父目录。
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    # 打开 SQLite 连接。
    connection = sqlite3.connect(sqlite_path)
    # 设置按列名读取，便于刷新融合状态。
    connection.row_factory = sqlite3.Row
    # 确保连接最终关闭。
    try:
        # 确保 SQLite 表结构完整。
        ensure_sqlite_schema(connection)
        # 写入摄取任务。
        insert_ingestion_job(connection, bundle.ingestion_job)
        # 遍历文档。
        for document in bundle.documents:
            # 读取文档 metadata。
            metadata = dict(document.metadata)
            # 清理同文档旧数据。
            reset_document_scoped_rows(connection, document.node_id)
            # 幂等写入文档记录。
            connection.execute(
                """
                INSERT OR REPLACE INTO rag_qa_documents (
                    document_id, source_path, source_name, title, content_hash,
                    framework_reference, llamaindex_document_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.node_id,
                    metadata.get("source_path", ""),
                    metadata.get("source_name", ""),
                    metadata.get("source_name", ""),
                    metadata.get("source_hash", ""),
                    json.dumps(metadata.get("framework_references", []), ensure_ascii=False),
                    json.dumps(document.to_dict(), ensure_ascii=False, default=str),
                    now_iso(),
                    now_iso(),
                ),
            )
        # 写入文档版本。
        for payload in bundle.document_versions:
            # 执行版本 upsert。
            connection.execute(
                """
                INSERT OR REPLACE INTO rag_document_versions (
                    version_id, document_id, source_path, source_name,
                    content_hash, job_id, is_current, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("version_id"),
                    payload.get("document_id"),
                    payload.get("source_path"),
                    payload.get("source_name"),
                    payload.get("content_hash"),
                    payload.get("job_id"),
                    1 if payload.get("is_current") else 0,
                    now_iso(),
                ),
            )
        # 逐条写入文档内聚类。
        for cluster_payload in bundle.document_cluster_payloads:
            # 执行聚类 INSERT。
            connection.execute(
                """
                INSERT INTO rag_qa_clusters (
                    cluster_id, document_id, cluster_label, cluster_level, cluster_type,
                    cluster_keywords, cluster_member_count, cluster_member_chunk_ids,
                    cluster_node_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cluster_payload.get("cluster_id"),
                    cluster_payload.get("document_id"),
                    cluster_payload.get("cluster_label"),
                    cluster_payload.get("cluster_level"),
                    cluster_payload.get("cluster_type"),
                    json.dumps(cluster_payload.get("cluster_keywords", []), ensure_ascii=False),
                    cluster_payload.get("cluster_member_count"),
                    json.dumps(cluster_payload.get("cluster_member_chunk_ids", []), ensure_ascii=False),
                    json.dumps(cluster_payload.get("cluster_node_json", {}), ensure_ascii=False),
                    now_iso(),
                ),
            )
        # 逐条写入 chunk。
        for payload in bundle.chunk_payloads:
            # 执行 chunk INSERT。
            connection.execute(
                """
                INSERT INTO rag_qa_chunks (
                    chunk_id, document_id, audio_no, audio_title, chunk_index, scene,
                    payload_schema_version, qa_pair_id, qa_pair_index,
                    qa_similarity_score, qa_similarity_threshold, qa_pair_validated,
                    cluster_id, cluster_label, cluster_level, cluster_path,
                    global_cluster_id, global_cluster_label, global_cluster_level, global_cluster_path,
                    question_hash, answer_hash, canonical_chunk_id, fusion_status,
                    question, answer, resolution_steps, keywords, entities_json,
                    cleaned_text, source_excerpt, content_hash, payload_json,
                    llamaindex_node_json, vector_json, vector_dim, vector_model, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("chunk_id"),
                    payload.get("document_id"),
                    payload.get("audio_no"),
                    payload.get("audio_title"),
                    payload.get("chunk_index"),
                    payload.get("scene"),
                    payload.get("payload_schema_version"),
                    payload.get("qa_pair_id"),
                    payload.get("qa_pair_index"),
                    payload.get("qa_similarity_score"),
                    payload.get("qa_similarity_threshold"),
                    1 if payload.get("qa_pair_validated") else 0,
                    payload.get("cluster_id"),
                    payload.get("cluster_label"),
                    payload.get("cluster_level"),
                    json.dumps(payload.get("cluster_path", []), ensure_ascii=False),
                    payload.get("global_cluster_id"),
                    payload.get("global_cluster_label"),
                    payload.get("global_cluster_level"),
                    json.dumps(payload.get("global_cluster_path", []), ensure_ascii=False),
                    payload.get("question_hash"),
                    payload.get("answer_hash"),
                    payload.get("canonical_chunk_id"),
                    payload.get("fusion_status"),
                    payload.get("question"),
                    payload.get("answer"),
                    json.dumps(payload.get("resolution_steps", []), ensure_ascii=False),
                    json.dumps(payload.get("keywords", []), ensure_ascii=False),
                    json.dumps(payload.get("entities", {}), ensure_ascii=False),
                    payload.get("cleaned_text"),
                    payload.get("source_excerpt"),
                    payload.get("content_hash"),
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(payload.get("llamaindex_node", {}), ensure_ascii=False),
                    json.dumps(payload.get("vector", []), ensure_ascii=False),
                    payload.get("vector_dim"),
                    payload.get("vector_model"),
                    now_iso(),
                ),
            )
        # 写入全局聚类。
        for payload in bundle.global_cluster_payloads:
            # 执行全局聚类 upsert。
            connection.execute(
                """
                INSERT OR REPLACE INTO rag_global_clusters (
                    global_cluster_id, global_cluster_label, global_cluster_level,
                    global_cluster_type, global_cluster_keywords, member_document_ids,
                    member_cluster_ids, member_chunk_ids, global_member_count,
                    global_cluster_node_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("global_cluster_id"),
                    payload.get("global_cluster_label"),
                    payload.get("global_cluster_level"),
                    payload.get("global_cluster_type"),
                    json.dumps(payload.get("global_cluster_keywords", []), ensure_ascii=False),
                    json.dumps(payload.get("member_document_ids", []), ensure_ascii=False),
                    json.dumps(payload.get("member_cluster_ids", []), ensure_ascii=False),
                    json.dumps(payload.get("member_chunk_ids", []), ensure_ascii=False),
                    payload.get("global_member_count"),
                    json.dumps(payload.get("global_cluster_node_json", {}), ensure_ascii=False),
                    now_iso(),
                    now_iso(),
                ),
            )
        # 写入实体提及。
        for payload in bundle.entity_mention_payloads:
            # 执行实体提及 INSERT。
            connection.execute(
                """
                INSERT INTO rag_entity_mentions (
                    mention_id, document_id, chunk_id, entity_type, entity_value,
                    canonical_entity, entity_hash, global_cluster_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("mention_id"),
                    payload.get("document_id"),
                    payload.get("chunk_id"),
                    payload.get("entity_type"),
                    payload.get("entity_value"),
                    payload.get("canonical_entity"),
                    payload.get("entity_hash"),
                    payload.get("global_cluster_id"),
                    now_iso(),
                ),
            )
        # 写入实体别名。
        for payload in bundle.entity_alias_payloads:
            # 执行实体别名 upsert。
            connection.execute(
                """
                INSERT OR REPLACE INTO rag_entity_aliases (
                    alias_id, entity_type, alias_value, canonical_entity,
                    entity_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("alias_id"),
                    payload.get("entity_type"),
                    payload.get("alias_value"),
                    payload.get("canonical_entity"),
                    payload.get("entity_hash"),
                    now_iso(),
                    now_iso(),
                ),
            )
        # 写入融合关系。
        for payload in bundle.fusion_payloads:
            # 执行融合 upsert。
            connection.execute(
                """
                INSERT OR REPLACE INTO rag_chunk_fusion_map (
                    fusion_id, canonical_chunk_id, duplicate_chunk_id,
                    canonical_document_id, duplicate_document_id, global_cluster_id,
                    question_hash, answer_hash, fusion_score, fusion_rule, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("fusion_id"),
                    payload.get("canonical_chunk_id"),
                    payload.get("duplicate_chunk_id"),
                    payload.get("canonical_document_id"),
                    payload.get("duplicate_document_id"),
                    payload.get("global_cluster_id"),
                    payload.get("question_hash"),
                    payload.get("answer_hash"),
                    payload.get("fusion_score"),
                    payload.get("fusion_rule"),
                    now_iso(),
                ),
            )
        # 写入校验问题。
        for payload in bundle.validation_issue_payloads:
            # 执行校验问题 upsert。
            connection.execute(
                """
                INSERT OR REPLACE INTO rag_validation_issues (
                    issue_id, document_id, chunk_id, issue_type, issue_level,
                    issue_message, issue_payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("issue_id"),
                    payload.get("document_id"),
                    payload.get("chunk_id"),
                    payload.get("issue_type"),
                    payload.get("issue_level"),
                    payload.get("issue_message"),
                    json.dumps(payload.get("issue_payload", {}), ensure_ascii=False),
                    now_iso(),
                ),
            )
        # 写入 RAG 同步状态。
        for payload in bundle.rag_sync_payloads:
            # 执行同步状态 upsert。
            connection.execute(
                """
                INSERT OR REPLACE INTO rag_rag_sync_state (
                    sync_id, document_id, content_hash, sync_target, sync_status,
                    chunk_count, needs_reindex, sync_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("sync_id"),
                    payload.get("document_id"),
                    payload.get("content_hash"),
                    payload.get("sync_target"),
                    payload.get("sync_status"),
                    payload.get("chunk_count"),
                    1 if payload.get("needs_reindex") else 0,
                    payload.get("sync_message"),
                    now_iso(),
                    now_iso(),
                ),
            )
        # 刷新 SQLite 全局同问同答融合状态。
        refresh_sqlite_fusion_status(connection)
        # 提交事务。
        connection.commit()
    # 最终关闭连接。
    finally:
        # 关闭 SQLite 连接。
        connection.close()
    # 返回成功信息。
    return f"SQLite 写入完成：{sqlite_path}，文档数：{len(bundle.documents)}，记录数：{len(bundle.chunk_payloads)}，全局聚类数：{len(bundle.global_cluster_payloads)}"
