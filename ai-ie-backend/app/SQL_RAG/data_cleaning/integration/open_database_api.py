# -*- coding: utf-8 -*-
"""开放给其他机台读写 RAG 清洗数据的 FastAPI 接口。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：补齐“给别人库名和集成接口能连和读写”的服务器侧开放接口程序。
# 修改日期：2026-06-01 11:07:00。
# 修改理由：默认后端切换到当前 Docker SQL Server 2022，并补齐外部机台 CRUD 测试端点，避免接口误读 SQLite 旧逻辑。
# 修改日期：2026-06-01 13:29:35。
# 修改理由：开放多文档全局聚类、融合、校验、任务和 RAG 同步状态查询接口，保证后续 RAG 能消费完整关系结构。

# 导入 JSON 库，用于处理 payload_json。
import json
# 导入环境变量库，用于读取 SQL Server 接口配置。
import os
# 导入 sys，用于把 data_cleaning 功能包加入模块搜索路径。
import sys
# 导入 SQLite 标准库，用于本地和测试环境读写。
import sqlite3
# 导入子进程库，用于通过 Docker sqlcmd 访问 SQL Server。
import subprocess
# 导入路径类型。
from pathlib import Path
# 导入任意 JSON 类型标注。
from typing import Any

# 导入 dotenv，用于固定加载 SQL_RAG 根目录的 .env。
from dotenv import load_dotenv

# 2026-06-02 10:06:01 修改：定位当前 integration 目录，保证从 SQL_RAG 根目录启动时路径稳定。
CURRENT_DIR = Path(__file__).resolve().parent
# 2026-06-02 10:06:01 修改：定位 data_cleaning 功能包目录，供 storage 等兄弟包导入。
DATA_CLEANING_DIR = CURRENT_DIR.parent
# 2026-06-02 10:06:01 修改：定位 SQL_RAG 根目录，开放 API 只读取这一套后端配置。
SQL_RAG_DIR = DATA_CLEANING_DIR.parent
# 2026-06-02 10:06:01 修改：固定 SQL_RAG 独立后端的环境配置文件。
ENV_PATH = SQL_RAG_DIR / ".env"
# 2026-06-02 10:06:01 修改：从 SQL_RAG 根目录启动 uvicorn 时，让 storage.sqlserver_writer 仍能被导入。
if str(DATA_CLEANING_DIR) not in sys.path:
    # 把 data_cleaning 放到最前，避免误读外层同名模块。
    sys.path.insert(0, str(DATA_CLEANING_DIR))
# 2026-06-03 00:00:00 修改：开放 Agent 本地业务动作读接口时需要导入 overall_planning。
if str(SQL_RAG_DIR) not in sys.path:
    # 把 SQL_RAG 根目录加入搜索路径，保证 uvicorn 从任意目录启动都能加载业务动作模块。
    sys.path.insert(0, str(SQL_RAG_DIR))
# 2026-06-02 10:06:01 修改：模块导入阶段加载 SQL_RAG/.env，保证 create_app_from_env 能读到数据库配置。
if ENV_PATH.exists():
    # override=False 保留命令行显式注入的环境变量优先级。
    load_dotenv(ENV_PATH, override=False)

# 导入 FastAPI 官方接口类。
from fastapi import FastAPI, HTTPException, Query
# 导入 Pydantic BaseModel，用于定义外部机台请求结构。
from pydantic import BaseModel, Field

# 导入 SQL Server 字面量工具，避免拼 SQL 时中文和单引号出错。
from storage.sqlserver_writer import sql_bit, sql_float, sql_int, sql_literal
# 导入 Agent 本地业务表建表工具，保证开放 API 能查询动作、工单和纠错样本。
from overall_planning.agent_Business_Brain.local_business_store import (
    ensure_local_business_sqlite_schema,
    ensure_local_business_sqlserver_schema_script,
)


class MachineWriteRequest(BaseModel):
    # 定义外部机台 ID。
    machine_id: str = Field(min_length=1)
    # 定义外部机台写入的测试数据。
    payload: dict[str, Any] = Field(default_factory=dict)


class ChunkUpsertRequest(BaseModel):
    # 定义标准 RAG chunk payload。
    payload: dict[str, Any]


class MachinePatchRequest(BaseModel):
    # 定义外部机台更新后的测试数据。
    payload: dict[str, Any] = Field(default_factory=dict)


class ChunkPatchRequest(BaseModel):
    # 定义允许更新的问题文本。
    question: str | None = None
    # 定义允许更新的答案文本。
    answer: str | None = None
    # 定义允许更新的场景标签。
    scene: str | None = None
    # 定义允许更新的聚类标签。
    cluster_label: str | None = None


class SqlcmdConfig(BaseModel):
    # 定义 Docker SQL Server 容器名。
    container: str = "sql-rag-sqlserver-2022"
    # 定义 SQL Server 地址，容器内访问本机实例用 localhost。
    server: str = "localhost"
    # 定义数据库名。
    database: str = "getai"
    # 定义数据库用户名。
    user: str = "dev"
    # 定义数据库密码。
    password: str = "123456"


def _extract_json_from_sqlcmd(stdout: str) -> Any:
    # 去掉 sqlcmd 输出两端空白。
    text = stdout.strip()
    # 寻找 JSON 数组起点。
    array_start = text.find("[")
    # 寻找 JSON 对象起点。
    object_start = text.find("{")
    # 收集所有有效起点。
    starts = [index for index in [array_start, object_start] if index >= 0]
    # 没有 JSON 时返回空列表。
    if not starts:
        # 返回空列表。
        return []
    # 使用最靠前的 JSON 起点。
    start = min(starts)
    # 寻找 JSON 数组终点。
    array_end = text.rfind("]")
    # 寻找 JSON 对象终点。
    object_end = text.rfind("}")
    # 使用最靠后的 JSON 终点。
    end = max(array_end, object_end)
    # 解析 JSON 文本。
    return json.loads(text[start : end + 1])


def _run_sqlcmd(config: SqlcmdConfig, sql_text: str) -> str:
    # 组装 Docker 容器内 sqlcmd 命令。
    command = [
        "docker",
        "exec",
        "-i",
        config.container,
        "/opt/mssql-tools18/bin/sqlcmd",
        "-S",
        config.server,
        "-U",
        config.user,
        "-P",
        config.password,
        "-C",
        "-d",
        config.database,
        "-b",
        "-w",
        "65535",
        "-y",
        "0",
    ]
    # 通过 stdin 传入 SQL 文本。
    result = subprocess.run(command, input=f"SET NOCOUNT ON;\n{sql_text}", text=True, encoding="utf-8", capture_output=True)
    # 非 0 返回码表示 SQL 执行失败。
    if result.returncode != 0:
        # 抛出运行错误。
        raise RuntimeError(f"SQL Server 接口执行失败：{result.stderr or result.stdout}")
    # 返回标准输出。
    return result.stdout


def _run_sqlcmd_json(config: SqlcmdConfig, sql_text: str) -> Any:
    # 执行 SQL Server 查询。
    stdout = _run_sqlcmd(config, sql_text)
    # 从 sqlcmd 输出中解析 JSON。
    return _extract_json_from_sqlcmd(stdout)


def _build_sqlserver_chunk_replace_sql(payload: dict[str, Any]) -> str:
    # 序列化完整 payload。
    payload_json = json.dumps(payload, ensure_ascii=False)
    # 序列化官方 LlamaIndex node。
    llamaindex_node_json = json.dumps(payload.get("llamaindex_node", {}), ensure_ascii=False)
    # 序列化步骤 JSON。
    steps_json = json.dumps(payload.get("resolution_steps", []), ensure_ascii=False)
    # 序列化关键词 JSON。
    keywords_json = json.dumps(payload.get("keywords", []), ensure_ascii=False)
    # 序列化实体 JSON。
    entities_json = json.dumps(payload.get("entities", {}), ensure_ascii=False)
    # 序列化向量 JSON。
    vector_json = json.dumps(payload.get("vector", []), ensure_ascii=False)
    # 序列化聚类路径 JSON。
    cluster_path_json = json.dumps(payload.get("cluster_path", []), ensure_ascii=False)
    # 序列化全局聚类路径 JSON。
    global_cluster_path_json = json.dumps(payload.get("global_cluster_path", []), ensure_ascii=False)
    # 返回先删后插的 upsert SQL。
    return f"""
BEGIN TRANSACTION;
DELETE FROM dbo.rag_qa_chunks WHERE chunk_id = {sql_literal(payload.get("chunk_id"))};
INSERT INTO dbo.rag_qa_chunks (
    chunk_id, document_id, audio_no, audio_title, chunk_index, scene,
    payload_schema_version, qa_pair_id, qa_pair_index,
    qa_similarity_score, qa_similarity_threshold, qa_pair_validated,
    cluster_id, cluster_label, cluster_level, cluster_path,
    global_cluster_id, global_cluster_label, global_cluster_level, global_cluster_path,
    question_hash, answer_hash, canonical_chunk_id, fusion_status,
    question, answer, resolution_steps, keywords, entities_json,
    cleaned_text, source_excerpt, content_hash, payload_json,
    llamaindex_node_json, vector_json, vector_dim, vector_model
) VALUES (
    {sql_literal(payload.get("chunk_id"))}, {sql_literal(payload.get("document_id"))}, {sql_int(payload.get("audio_no"))}, {sql_literal(payload.get("audio_title"))}, {sql_int(payload.get("chunk_index"))}, {sql_literal(payload.get("scene"))},
    {sql_literal(payload.get("payload_schema_version"))}, {sql_literal(payload.get("qa_pair_id"))}, {sql_int(payload.get("qa_pair_index"))},
    {sql_float(payload.get("qa_similarity_score"))}, {sql_float(payload.get("qa_similarity_threshold"))}, {sql_bit(payload.get("qa_pair_validated"))},
    {sql_literal(payload.get("cluster_id"))}, {sql_literal(payload.get("cluster_label"))}, {sql_literal(payload.get("cluster_level"))}, {sql_literal(cluster_path_json)},
    {sql_literal(payload.get("global_cluster_id"))}, {sql_literal(payload.get("global_cluster_label"))}, {sql_literal(payload.get("global_cluster_level"))}, {sql_literal(global_cluster_path_json)},
    {sql_literal(payload.get("question_hash"))}, {sql_literal(payload.get("answer_hash"))}, {sql_literal(payload.get("canonical_chunk_id"))}, {sql_literal(payload.get("fusion_status"))},
    {sql_literal(payload.get("question"))}, {sql_literal(payload.get("answer"))}, {sql_literal(steps_json)}, {sql_literal(keywords_json)}, {sql_literal(entities_json)},
    {sql_literal(payload.get("cleaned_text"))}, {sql_literal(payload.get("source_excerpt"))}, {sql_literal(payload.get("content_hash"))}, {sql_literal(payload_json)},
    {sql_literal(llamaindex_node_json)}, {sql_literal(vector_json)}, {sql_int(payload.get("vector_dim", 0))}, {sql_literal(payload.get("vector_model"))}
);
COMMIT TRANSACTION;
SELECT {sql_literal(payload.get("chunk_id"))} AS upserted_chunk_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER;
"""


def create_app(
    sqlite_path: Path | None = None,
    database_name: str = "getai",
    backend: str = "sqlserver",
    sqlcmd_config: SqlcmdConfig | None = None,
) -> FastAPI:
    # 创建 FastAPI 应用。
    app = FastAPI(title="QA RAG Open Database Integration API", version="1.0.0")
    # 标准化后端类型。
    backend_name = backend.lower()
    # 解析 SQLite 绝对路径。
    resolved_sqlite_path = sqlite_path.expanduser().resolve() if sqlite_path else Path(__file__).resolve().parents[1] / "qa_cleaned_chunks.sqlite"
    # 设置 SQL Server sqlcmd 配置。
    resolved_sqlcmd_config = sqlcmd_config or SqlcmdConfig(database=database_name)

    def connect() -> sqlite3.Connection:
        # 创建父目录。
        resolved_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        # 打开 SQLite 连接。
        connection = sqlite3.connect(resolved_sqlite_path)
        # 设置按列名读取。
        connection.row_factory = sqlite3.Row
        # 返回连接。
        return connection

    def ensure_machine_test_table(connection: sqlite3.Connection) -> None:
        # 创建外部机台读写测试表。
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_machine_integration_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # 提交建表。
        connection.commit()

    def ensure_sqlserver_machine_test_table() -> None:
        # 创建 SQL Server 外部机台读写测试表。
        _run_sqlcmd(
            resolved_sqlcmd_config,
            """
IF OBJECT_ID(N'dbo.rag_machine_integration_tests', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_machine_integration_tests (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        machine_id NVARCHAR(120) NOT NULL,
        payload_json NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_machine_integration_tests_created_at DEFAULT SYSUTCDATETIME()
    );
END;
""",
        )

    def ensure_sqlserver_agent_tables() -> None:
        # 创建 SQL Server Agent 本地业务动作表。
        _run_sqlcmd(resolved_sqlcmd_config, ensure_local_business_sqlserver_schema_script())

    def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        # 把 SQLite Row 转成普通字典。
        return {key: row[key] for key in row.keys()}

    def list_agent_table(table_key: str, user_id: str, limit: int) -> dict[str, Any]:
        # Agent 本地业务表只允许从静态白名单查询，避免动态表名风险。
        table_configs = {
            "actions": {
                "sqlserver_table": "dbo.rag_agent_action_events",
                "sqlite_table": "rag_agent_action_events",
                "columns": "action_id, user_id, thread_id, action_name, action_status, subject, order_no, contact, priority, payload_json, result_json, source_question, created_at",
                "order_by": "created_at DESC",
                "result_key": "actions",
            },
            "tickets": {
                "sqlserver_table": "dbo.rag_customer_service_tickets",
                "sqlite_table": "rag_customer_service_tickets",
                "columns": "ticket_id, user_id, thread_id, ticket_type, status, priority, subject, description, order_no, contact, payload_json, source_question, created_at, updated_at",
                "order_by": "updated_at DESC",
                "result_key": "tickets",
            },
            "handoffs": {
                "sqlserver_table": "dbo.rag_customer_handoff_queue",
                "sqlite_table": "rag_customer_handoff_queue",
                "columns": "handoff_id, ticket_id, user_id, thread_id, reason, priority, status, payload_json, created_at, updated_at",
                "order_by": "updated_at DESC",
                "result_key": "handoffs",
            },
            "followups": {
                "sqlserver_table": "dbo.rag_agent_followups",
                "sqlite_table": "rag_agent_followups",
                "columns": "followup_id, ticket_id, user_id, thread_id, due_at, channel, status, message, payload_json, created_at, updated_at",
                "order_by": "updated_at DESC",
                "result_key": "followups",
            },
            "profile-memory": {
                "sqlserver_table": "dbo.rag_customer_profile_memory",
                "sqlite_table": "rag_customer_profile_memory",
                "columns": "memory_id, user_id, memory_key, value_json, source_id, confidence, updated_at, expiry, consent_scope",
                "order_by": "updated_at DESC",
                "result_key": "profile_memory",
            },
            "correction-samples": {
                "sqlserver_table": "dbo.rag_agent_correction_samples",
                "sqlite_table": "rag_agent_correction_samples",
                "columns": "sample_id, user_id, thread_id, question, answer, failure_branch, verifier_score, mark_json, verifier_json, created_at",
                "order_by": "created_at DESC",
                "result_key": "correction_samples",
            },
        }
        config = table_configs[table_key]
        # SQL Server 后端查询 Agent 本地业务表。
        if backend_name == "sqlserver":
            ensure_sqlserver_agent_tables()
            where_sql = f"WHERE user_id = {sql_literal(user_id)}" if user_id else ""
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
SELECT TOP ({int(limit)}) {config["columns"]}
FROM {config["sqlserver_table"]}
{where_sql}
ORDER BY {config["order_by"]}
FOR JSON PATH;
""",
            )
            return {"database_name": database_name, config["result_key"]: rows}
        # SQLite 后端查询 Agent 本地业务表。
        connection = connect()
        try:
            ensure_local_business_sqlite_schema(connection)
            where_sql = "WHERE user_id = ?" if user_id else ""
            params: list[Any] = [user_id, limit] if user_id else [limit]
            rows = connection.execute(
                f"""
                SELECT {config["columns"]}
                FROM {config["sqlite_table"]}
                {where_sql}
                ORDER BY {config["order_by"]}
                LIMIT ?
                """,
                params,
            ).fetchall()
            return {"database_name": database_name, config["result_key"]: [row_to_dict(row) for row in rows]}
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            connection.close()

    @app.get("/health")
    def health() -> dict[str, Any]:
        # SQL Server 后端返回真实 SQL Server 连接状态。
        if backend_name == "sqlserver":
            # 查询当前数据库和用户。
            sql_status = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                "SELECT DB_NAME() AS database_name, USER_NAME() AS database_user FOR JSON PATH, WITHOUT_ARRAY_WRAPPER;",
            )
            # 返回 SQL Server 健康状态。
            return {
                "status": "ok",
                "backend": "sqlserver",
                "database_name": sql_status.get("database_name", database_name),
                "database_user": sql_status.get("database_user", resolved_sqlcmd_config.user),
                "container": resolved_sqlcmd_config.container,
                "read_endpoint": "/chunks",
                "global_clusters_endpoint": "/global-clusters",
                "fusion_endpoint": "/fusion-links",
                "validation_endpoint": "/validation-issues",
                "rag_sync_endpoint": "/rag-sync-state",
                "write_endpoint": "/chunks/upsert",
                "machine_test_write_endpoint": "/machine-test/write",
                "agent_actions_endpoint": "/agent/actions",
                "agent_tickets_endpoint": "/agent/tickets",
                "agent_correction_samples_endpoint": "/agent/correction-samples",
            }
        # 返回接口健康状态和数据库连接信息。
        return {
            "status": "ok",
            "backend": "sqlite",
            "database_name": database_name,
            "sqlite_path": str(resolved_sqlite_path),
            "read_endpoint": "/chunks",
            "global_clusters_endpoint": "/global-clusters",
            "fusion_endpoint": "/fusion-links",
            "validation_endpoint": "/validation-issues",
            "rag_sync_endpoint": "/rag-sync-state",
            "write_endpoint": "/chunks/upsert",
            "machine_test_write_endpoint": "/machine-test/write",
            "agent_actions_endpoint": "/agent/actions",
            "agent_tickets_endpoint": "/agent/tickets",
            "agent_correction_samples_endpoint": "/agent/correction-samples",
        }

    @app.get("/documents")
    def list_documents() -> dict[str, Any]:
        # SQL Server 后端查询文档表。
        if backend_name == "sqlserver":
            # 查询 SQL Server 文档列表。
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                """
SELECT document_id, source_name, title, content_hash,
       CONVERT(varchar(19), created_at, 120) AS created_at,
       CONVERT(varchar(19), updated_at, 120) AS updated_at
FROM dbo.rag_qa_documents
ORDER BY updated_at DESC
FOR JSON PATH;
""",
            )
            # 返回文档列表。
            return {"database_name": database_name, "documents": rows}
        # 打开数据库连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 查询文档表。
            rows = connection.execute(
                "SELECT document_id, source_name, title, content_hash, created_at, updated_at FROM rag_qa_documents ORDER BY updated_at DESC"
            ).fetchall()
            # 返回文档列表。
            return {"database_name": database_name, "documents": [row_to_dict(row) for row in rows]}
        # 捕获缺表错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.get("/chunks")
    def list_chunks(document_id: str = "", limit: int = Query(default=20, ge=1, le=500)) -> dict[str, Any]:
        # SQL Server 后端查询 chunk 表。
        if backend_name == "sqlserver":
            # 拼接 WHERE 条件。
            where_sql = f"WHERE document_id = {sql_literal(document_id)}" if document_id else ""
            # 查询 SQL Server chunk 列表。
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
SELECT TOP ({int(limit)}) chunk_id, document_id, chunk_index, cluster_id, cluster_label,
       global_cluster_id, global_cluster_label, canonical_chunk_id, fusion_status,
       question, answer, qa_similarity_score, qa_pair_validated
FROM dbo.rag_qa_chunks
{where_sql}
ORDER BY document_id, chunk_index
FOR JSON PATH;
""",
            )
            # 返回 chunk 列表。
            return {"database_name": database_name, "chunks": rows}
        # 打开数据库连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 有文档 ID 时按文档过滤。
            if document_id:
                # 查询指定文档 chunk。
                rows = connection.execute(
                    """
                    SELECT chunk_id, document_id, chunk_index, cluster_id, cluster_label,
                           global_cluster_id, global_cluster_label, canonical_chunk_id, fusion_status,
                           question, answer, qa_similarity_score, qa_pair_validated
                    FROM rag_qa_chunks
                    WHERE document_id = ?
                    ORDER BY chunk_index
                    LIMIT ?
                    """,
                    (document_id, limit),
                ).fetchall()
            # 无文档 ID 时查询全库最新 chunk。
            else:
                # 查询 chunk。
                rows = connection.execute(
                    """
                    SELECT chunk_id, document_id, chunk_index, cluster_id, cluster_label,
                           global_cluster_id, global_cluster_label, canonical_chunk_id, fusion_status,
                           question, answer, qa_similarity_score, qa_pair_validated
                    FROM rag_qa_chunks
                    ORDER BY document_id, chunk_index
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            # 返回 chunk 列表。
            return {"database_name": database_name, "chunks": [row_to_dict(row) for row in rows]}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.get("/ingestion-jobs")
    def list_ingestion_jobs(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
        # SQL Server 后端查询摄取任务表。
        if backend_name == "sqlserver":
            # 查询 SQL Server 摄取任务。
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
SELECT TOP ({int(limit)}) job_id, input_path, job_status, document_count,
       chunk_count, global_cluster_count, fusion_count, validation_issue_count,
       CONVERT(varchar(19), updated_at, 120) AS updated_at
FROM dbo.rag_ingestion_jobs
ORDER BY updated_at DESC
FOR JSON PATH;
""",
            )
            # 返回任务列表。
            return {"database_name": database_name, "jobs": rows}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 查询 SQLite 摄取任务。
            rows = connection.execute(
                """
                SELECT job_id, input_path, job_status, document_count,
                       chunk_count, global_cluster_count, fusion_count,
                       validation_issue_count, updated_at
                FROM rag_ingestion_jobs
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            # 返回任务列表。
            return {"database_name": database_name, "jobs": [row_to_dict(row) for row in rows]}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.get("/global-clusters")
    def list_global_clusters(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # SQL Server 后端查询全局聚类。
        if backend_name == "sqlserver":
            # 查询 SQL Server 全局聚类。
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
SELECT TOP ({int(limit)}) global_cluster_id, global_cluster_label,
       global_cluster_level, global_cluster_type, global_member_count
FROM dbo.rag_global_clusters
ORDER BY global_member_count DESC, global_cluster_label
FOR JSON PATH;
""",
            )
            # 返回全局聚类。
            return {"database_name": database_name, "global_clusters": rows}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 查询 SQLite 全局聚类。
            rows = connection.execute(
                """
                SELECT global_cluster_id, global_cluster_label, global_cluster_level,
                       global_cluster_type, global_member_count
                FROM rag_global_clusters
                ORDER BY global_member_count DESC, global_cluster_label
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            # 返回全局聚类。
            return {"database_name": database_name, "global_clusters": [row_to_dict(row) for row in rows]}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.get("/fusion-links")
    def list_fusion_links(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # SQL Server 后端查询融合关系。
        if backend_name == "sqlserver":
            # 查询 SQL Server 融合关系。
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
SELECT TOP ({int(limit)}) fusion_id, canonical_chunk_id, duplicate_chunk_id,
       canonical_document_id, duplicate_document_id, global_cluster_id,
       fusion_score, fusion_rule
FROM dbo.rag_chunk_fusion_map
ORDER BY created_at DESC
FOR JSON PATH;
""",
            )
            # 返回融合关系。
            return {"database_name": database_name, "fusion_links": rows}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 查询 SQLite 融合关系。
            rows = connection.execute(
                """
                SELECT fusion_id, canonical_chunk_id, duplicate_chunk_id,
                       canonical_document_id, duplicate_document_id,
                       global_cluster_id, fusion_score, fusion_rule
                FROM rag_chunk_fusion_map
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            # 返回融合关系。
            return {"database_name": database_name, "fusion_links": [row_to_dict(row) for row in rows]}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.get("/validation-issues")
    def list_validation_issues(issue_level: str = "", limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # SQL Server 后端查询校验问题。
        if backend_name == "sqlserver":
            # 拼接 WHERE 条件。
            where_sql = f"WHERE issue_level = {sql_literal(issue_level)}" if issue_level else ""
            # 查询 SQL Server 校验问题。
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
SELECT TOP ({int(limit)}) issue_id, document_id, chunk_id, issue_type,
       issue_level, issue_message, issue_payload_json,
       CONVERT(varchar(19), created_at, 120) AS created_at
FROM dbo.rag_validation_issues
{where_sql}
ORDER BY created_at DESC
FOR JSON PATH;
""",
            )
            # 返回校验问题。
            return {"database_name": database_name, "validation_issues": rows}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 有严重级别时过滤。
            if issue_level:
                # 查询指定级别问题。
                rows = connection.execute(
                    """
                    SELECT issue_id, document_id, chunk_id, issue_type,
                           issue_level, issue_message, issue_payload_json, created_at
                    FROM rag_validation_issues
                    WHERE issue_level = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (issue_level, limit),
                ).fetchall()
            # 无严重级别时查询全部。
            else:
                # 查询全部校验问题。
                rows = connection.execute(
                    """
                    SELECT issue_id, document_id, chunk_id, issue_type,
                           issue_level, issue_message, issue_payload_json, created_at
                    FROM rag_validation_issues
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            # 返回校验问题。
            return {"database_name": database_name, "validation_issues": [row_to_dict(row) for row in rows]}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.get("/rag-sync-state")
    def list_rag_sync_state(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # SQL Server 后端查询 RAG 同步状态。
        if backend_name == "sqlserver":
            # 查询 SQL Server 同步状态。
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
SELECT TOP ({int(limit)}) sync_id, document_id, content_hash, sync_target,
       sync_status, chunk_count, needs_reindex, sync_message,
       CONVERT(varchar(19), updated_at, 120) AS updated_at
FROM dbo.rag_rag_sync_state
ORDER BY updated_at DESC
FOR JSON PATH;
""",
            )
            # 返回同步状态。
            return {"database_name": database_name, "rag_sync_state": rows}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 查询 SQLite 同步状态。
            rows = connection.execute(
                """
                SELECT sync_id, document_id, content_hash, sync_target,
                       sync_status, chunk_count, needs_reindex, sync_message, updated_at
                FROM rag_rag_sync_state
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            # 返回同步状态。
            return {"database_name": database_name, "rag_sync_state": [row_to_dict(row) for row in rows]}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.get("/agent/actions")
    def list_agent_actions(user_id: str = "", limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # 查询 Agent 实际执行动作事件。
        return list_agent_table("actions", user_id, limit)

    @app.get("/agent/tickets")
    def list_agent_tickets(user_id: str = "", limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # 查询 Agent 创建或更新的本地客服工单。
        return list_agent_table("tickets", user_id, limit)

    @app.get("/agent/handoffs")
    def list_agent_handoffs(user_id: str = "", limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # 查询 Agent 触发的转人工队列。
        return list_agent_table("handoffs", user_id, limit)

    @app.get("/agent/followups")
    def list_agent_followups(user_id: str = "", limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # 查询 Agent 创建的跟进任务。
        return list_agent_table("followups", user_id, limit)

    @app.get("/agent/profile-memory")
    def list_agent_profile_memory(user_id: str = "", limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # 查询 Agent 本地结构化客户画像记忆。
        return list_agent_table("profile-memory", user_id, limit)

    @app.get("/agent/correction-samples")
    def list_agent_correction_samples(user_id: str = "", limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        # 查询 Agent 低置信和跑偏纠错样本。
        return list_agent_table("correction-samples", user_id, limit)

    @app.post("/machine-test/write")
    def write_machine_test(request: MachineWriteRequest) -> dict[str, Any]:
        # SQL Server 后端写入机台测试数据。
        if backend_name == "sqlserver":
            # 确保 SQL Server 测试表存在。
            ensure_sqlserver_machine_test_table()
            # 序列化机台 payload。
            payload_json = json.dumps(request.payload, ensure_ascii=False)
            # 插入并返回新 ID。
            row = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
DECLARE @inserted TABLE (inserted_id INT, machine_id NVARCHAR(120));
INSERT INTO dbo.rag_machine_integration_tests (machine_id, payload_json)
OUTPUT INSERTED.id, INSERTED.machine_id INTO @inserted
VALUES ({sql_literal(request.machine_id)}, {sql_literal(payload_json)});
SELECT inserted_id, machine_id FROM @inserted FOR JSON PATH, WITHOUT_ARRAY_WRAPPER;
""",
            )
            # 返回写入结果。
            return {"database_name": database_name, "inserted_id": row.get("inserted_id"), "machine_id": row.get("machine_id")}
        # 打开数据库连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 确保测试表存在。
            ensure_machine_test_table(connection)
            # 写入外部机台测试数据。
            cursor = connection.execute(
                "INSERT INTO rag_machine_integration_tests (machine_id, payload_json) VALUES (?, ?)",
                (request.machine_id, json.dumps(request.payload, ensure_ascii=False)),
            )
            # 提交写入。
            connection.commit()
            # 返回写入结果。
            return {"database_name": database_name, "inserted_id": cursor.lastrowid, "machine_id": request.machine_id}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.get("/machine-test/read")
    def read_machine_test(machine_id: str = "") -> dict[str, Any]:
        # SQL Server 后端读取机台测试数据。
        if backend_name == "sqlserver":
            # 确保 SQL Server 测试表存在。
            ensure_sqlserver_machine_test_table()
            # 拼接 WHERE 条件。
            where_sql = f"WHERE machine_id = {sql_literal(machine_id)}" if machine_id else ""
            # 查询测试数据。
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
SELECT id, machine_id, payload_json, CONVERT(varchar(19), created_at, 120) AS created_at
FROM dbo.rag_machine_integration_tests
{where_sql}
ORDER BY id DESC
FOR JSON PATH;
""",
            )
            # 返回测试数据。
            return {"database_name": database_name, "items": rows}
        # 打开数据库连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 确保测试表存在。
            ensure_machine_test_table(connection)
            # 有机台 ID 时过滤。
            if machine_id:
                # 查询指定机台测试数据。
                rows = connection.execute(
                    "SELECT id, machine_id, payload_json, created_at FROM rag_machine_integration_tests WHERE machine_id = ? ORDER BY id DESC",
                    (machine_id,),
                ).fetchall()
            # 无机台 ID 时读取全部测试数据。
            else:
                # 查询全部测试数据。
                rows = connection.execute(
                    "SELECT id, machine_id, payload_json, created_at FROM rag_machine_integration_tests ORDER BY id DESC"
                ).fetchall()
            # 返回测试数据。
            return {"database_name": database_name, "items": [row_to_dict(row) for row in rows]}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.patch("/machine-test/{item_id}")
    def update_machine_test(item_id: int, request: MachinePatchRequest) -> dict[str, Any]:
        # SQL Server 后端更新机台测试数据。
        if backend_name == "sqlserver":
            # 确保 SQL Server 测试表存在。
            ensure_sqlserver_machine_test_table()
            # 序列化更新 payload。
            payload_json = json.dumps(request.payload, ensure_ascii=False)
            # 更新并返回新数据。
            rows = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
UPDATE dbo.rag_machine_integration_tests
SET payload_json = {sql_literal(payload_json)}
WHERE id = {sql_int(item_id)};
SELECT id, machine_id, payload_json, CONVERT(varchar(19), created_at, 120) AS created_at
FROM dbo.rag_machine_integration_tests
WHERE id = {sql_int(item_id)}
FOR JSON PATH, WITHOUT_ARRAY_WRAPPER;
""",
            )
            # 返回更新结果。
            return {"database_name": database_name, "item": rows}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 确保测试表存在。
            ensure_machine_test_table(connection)
            # 更新测试数据。
            connection.execute(
                "UPDATE rag_machine_integration_tests SET payload_json = ? WHERE id = ?",
                (json.dumps(request.payload, ensure_ascii=False), item_id),
            )
            # 提交更新。
            connection.commit()
            # 查询更新后的数据。
            row = connection.execute(
                "SELECT id, machine_id, payload_json, created_at FROM rag_machine_integration_tests WHERE id = ?",
                (item_id,),
            ).fetchone()
            # 返回更新结果。
            return {"database_name": database_name, "item": row_to_dict(row) if row else None}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.delete("/machine-test/{item_id}")
    def delete_machine_test(item_id: int) -> dict[str, Any]:
        # SQL Server 后端删除机台测试数据。
        if backend_name == "sqlserver":
            # 确保 SQL Server 测试表存在。
            ensure_sqlserver_machine_test_table()
            # 删除并返回影响行数。
            row = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
DECLARE @deleted INT;
DELETE FROM dbo.rag_machine_integration_tests WHERE id = {sql_int(item_id)};
SET @deleted = @@ROWCOUNT;
SELECT @deleted AS deleted FOR JSON PATH, WITHOUT_ARRAY_WRAPPER;
""",
            )
            # 返回删除结果。
            return {"database_name": database_name, "deleted": row.get("deleted", 0)}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 确保测试表存在。
            ensure_machine_test_table(connection)
            # 删除测试数据。
            cursor = connection.execute("DELETE FROM rag_machine_integration_tests WHERE id = ?", (item_id,))
            # 提交删除。
            connection.commit()
            # 返回删除结果。
            return {"database_name": database_name, "deleted": cursor.rowcount}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.get("/chunks/{chunk_id}")
    def get_chunk(chunk_id: str) -> dict[str, Any]:
        # SQL Server 后端读取单条 chunk。
        if backend_name == "sqlserver":
            # 查询指定 chunk。
            row = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
SELECT TOP (1)
       chunk_id, document_id, audio_no, audio_title, chunk_index, scene,
       payload_schema_version, qa_pair_id, qa_pair_index,
       qa_similarity_score, qa_similarity_threshold, qa_pair_validated,
       cluster_id, cluster_label, cluster_level,
       global_cluster_id, global_cluster_label, canonical_chunk_id, fusion_status,
       question, answer, vector_dim, vector_model
FROM dbo.rag_qa_chunks
WHERE chunk_id = {sql_literal(chunk_id)}
FOR JSON PATH, WITHOUT_ARRAY_WRAPPER;
""",
            )
            # 返回 chunk。
            return {"database_name": database_name, "chunk": row}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 查询指定 chunk。
            row = connection.execute("SELECT * FROM rag_qa_chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
            # 返回 chunk。
            return {"database_name": database_name, "chunk": row_to_dict(row) if row else None}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.patch("/chunks/{chunk_id}")
    def patch_chunk(chunk_id: str, request: ChunkPatchRequest) -> dict[str, Any]:
        # 组装允许更新的字段。
        updates = {
            key: value
            for key, value in {
                "question": request.question,
                "answer": request.answer,
                "scene": request.scene,
                "cluster_label": request.cluster_label,
            }.items()
            if value is not None
        }
        # 没有可更新字段时抛出错误。
        if not updates:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=400, detail="没有可更新字段")
        # SQL Server 后端更新 chunk。
        if backend_name == "sqlserver":
            # 拼接 SET 子句。
            set_sql = ", ".join(f"{key} = {sql_literal(value)}" for key, value in updates.items())
            # 更新并返回单条 chunk。
            row = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
UPDATE dbo.rag_qa_chunks SET {set_sql} WHERE chunk_id = {sql_literal(chunk_id)};
SELECT TOP (1) chunk_id, document_id, question, answer, scene, cluster_label
FROM dbo.rag_qa_chunks
WHERE chunk_id = {sql_literal(chunk_id)}
FOR JSON PATH, WITHOUT_ARRAY_WRAPPER;
""",
            )
            # 返回更新结果。
            return {"database_name": database_name, "chunk": row}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 拼接 SQLite SET 子句。
            set_sql = ", ".join(f"{key} = ?" for key in updates)
            # 执行更新。
            connection.execute(f"UPDATE rag_qa_chunks SET {set_sql} WHERE chunk_id = ?", [*updates.values(), chunk_id])
            # 提交更新。
            connection.commit()
            # 查询更新结果。
            row = connection.execute(
                "SELECT chunk_id, document_id, question, answer, scene, cluster_label FROM rag_qa_chunks WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
            # 返回更新结果。
            return {"database_name": database_name, "chunk": row_to_dict(row) if row else None}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.delete("/chunks/{chunk_id}")
    def delete_chunk(chunk_id: str) -> dict[str, Any]:
        # SQL Server 后端删除 chunk。
        if backend_name == "sqlserver":
            # 删除并返回影响行数。
            row = _run_sqlcmd_json(
                resolved_sqlcmd_config,
                f"""
DECLARE @deleted INT;
DELETE FROM dbo.rag_qa_chunks WHERE chunk_id = {sql_literal(chunk_id)};
SET @deleted = @@ROWCOUNT;
SELECT @deleted AS deleted FOR JSON PATH, WITHOUT_ARRAY_WRAPPER;
""",
            )
            # 返回删除结果。
            return {"database_name": database_name, "deleted": row.get("deleted", 0)}
        # 打开 SQLite 连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 删除 chunk。
            cursor = connection.execute("DELETE FROM rag_qa_chunks WHERE chunk_id = ?", (chunk_id,))
            # 提交删除。
            connection.commit()
            # 返回删除结果。
            return {"database_name": database_name, "deleted": cursor.rowcount}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    @app.post("/chunks/upsert")
    def upsert_chunk(request: ChunkUpsertRequest) -> dict[str, Any]:
        # 读取标准 RAG payload。
        payload = request.payload
        # SQL Server 后端 upsert chunk。
        if backend_name == "sqlserver":
            # 校验 chunk_id。
            if not payload.get("chunk_id"):
                # 抛出 HTTP 错误。
                raise HTTPException(status_code=400, detail="payload.chunk_id 不能为空")
            # 执行 SQL Server upsert。
            row = _run_sqlcmd_json(resolved_sqlcmd_config, _build_sqlserver_chunk_replace_sql(payload))
            # 返回 upsert 结果。
            return {"database_name": database_name, "upserted_chunk_id": row.get("upserted_chunk_id")}
        # 打开数据库连接。
        connection = connect()
        # 确保连接关闭。
        try:
            # 执行 chunk upsert。
            connection.execute(
                """
                INSERT OR REPLACE INTO rag_qa_chunks (
                    chunk_id, document_id, audio_no, audio_title, chunk_index, scene,
                    payload_schema_version, qa_pair_id, qa_pair_index,
                    qa_similarity_score, qa_similarity_threshold, qa_pair_validated,
                    cluster_id, cluster_label, cluster_level, cluster_path,
                    global_cluster_id, global_cluster_label, global_cluster_level, global_cluster_path,
                    question_hash, answer_hash, canonical_chunk_id, fusion_status,
                    question, answer, resolution_steps, keywords, entities_json,
                    cleaned_text, source_excerpt, content_hash, payload_json,
                    llamaindex_node_json, vector_json, vector_dim, vector_model, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    payload.get("chunk_id"),
                    payload.get("document_id"),
                    payload.get("audio_no", 0),
                    payload.get("audio_title", ""),
                    payload.get("chunk_index", 0),
                    payload.get("scene", ""),
                    payload.get("payload_schema_version", ""),
                    payload.get("qa_pair_id", ""),
                    payload.get("qa_pair_index", 0),
                    payload.get("qa_similarity_score", 0.0),
                    payload.get("qa_similarity_threshold", 0.0),
                    1 if payload.get("qa_pair_validated") else 0,
                    payload.get("cluster_id", ""),
                    payload.get("cluster_label", ""),
                    payload.get("cluster_level", ""),
                    json.dumps(payload.get("cluster_path", []), ensure_ascii=False),
                    payload.get("global_cluster_id", ""),
                    payload.get("global_cluster_label", ""),
                    payload.get("global_cluster_level", ""),
                    json.dumps(payload.get("global_cluster_path", []), ensure_ascii=False),
                    payload.get("question_hash", ""),
                    payload.get("answer_hash", ""),
                    payload.get("canonical_chunk_id", payload.get("chunk_id", "")),
                    payload.get("fusion_status", "canonical"),
                    payload.get("question", ""),
                    payload.get("answer", ""),
                    json.dumps(payload.get("resolution_steps", []), ensure_ascii=False),
                    json.dumps(payload.get("keywords", []), ensure_ascii=False),
                    json.dumps(payload.get("entities", {}), ensure_ascii=False),
                    payload.get("cleaned_text", ""),
                    payload.get("source_excerpt", ""),
                    payload.get("content_hash", ""),
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(payload.get("llamaindex_node", {}), ensure_ascii=False),
                    json.dumps(payload.get("vector", []), ensure_ascii=False),
                    payload.get("vector_dim", 0),
                    payload.get("vector_model", ""),
                ),
            )
            # 提交写入。
            connection.commit()
            # 返回 upsert 结果。
            return {"database_name": database_name, "upserted_chunk_id": payload.get("chunk_id")}
        # 捕获 SQLite 错误。
        except sqlite3.Error as exc:
            # 抛出 HTTP 错误。
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # 最终关闭连接。
        finally:
            # 关闭连接。
            connection.close()

    # 返回 FastAPI 应用。
    return app


def create_app_from_env() -> FastAPI:
    # 从环境变量读取开放接口后端类型。
    backend = os.getenv("RAG_OPEN_API_BACKEND", "sqlserver").lower()
    # 从环境变量读取数据库名。
    database_name = os.getenv("RAG_SQL_DB", "getai")
    # 从环境变量读取 SQLite 路径。
    sqlite_path = Path(os.getenv("RAG_SQLITE_PATH", str(Path(__file__).resolve().parents[1] / "qa_cleaned_chunks.sqlite")))
    # 从环境变量读取 SQL Server sqlcmd 配置。
    sqlcmd_config = SqlcmdConfig(
        container=os.getenv("RAG_SQLCMD_CONTAINER", "sql-rag-sqlserver-2022"),
        server=os.getenv("RAG_SQL_SERVER", "localhost"),
        database=database_name,
        user=os.getenv("RAG_SQL_USER", "dev"),
        password=os.getenv("RAG_SQL_PASSWORD", "123456"),
    )
    # 创建应用。
    return create_app(sqlite_path=sqlite_path, database_name=database_name, backend=backend, sqlcmd_config=sqlcmd_config)


# 默认 SQLite 文件路径，便于 uvicorn 直接启动。
DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[1] / "qa_cleaned_chunks.sqlite"
# 创建默认应用实例。
app = create_app_from_env()
