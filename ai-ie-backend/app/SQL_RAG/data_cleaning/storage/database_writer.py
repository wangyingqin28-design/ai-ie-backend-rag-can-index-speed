# -*- coding: utf-8 -*-
"""数据库入库后端分发器。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：入库时同步写入 RAG 聚类结构，保证 chunk 与 cluster 两层数据完整。
# 修改日期：2026-06-01 13:29:35。
# 修改理由：入库分发器升级为写入多文档关系型 bundle，包含全局聚类、融合、校验和 RAG 同步状态。

# 导入命名空间类型，接收 argparse 参数。
from argparse import Namespace
# 导入路径类型。
from pathlib import Path

# 导入数据库写入 bundle。
from data_structures.models import DatabaseWriteBundle
# 导入 SQL Server 入库接口。
from storage.sqlserver_writer import save_to_sqlserver_pyodbc, save_to_sqlserver_sqlcmd, write_debug_sql
# 导入 SQLite 入库接口。
from storage.sqlite_writer import save_to_sqlite
# 2026-06-04 16:31:05 新增原因：导入 Neo4j 三元组写入接口，让图谱写入进入同一清洗主链。
from storage.neo4j_writer import save_to_neo4j


def _truthy_flag(value: object) -> bool:
    # 2026-06-04 16:31:05 新增原因：统一解析命令行和 .env 中的布尔开关。
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _append_neo4j_sync_message(args: Namespace, message: str, bundle: DatabaseWriteBundle) -> str:
    # 2026-06-04 16:31:05 新增原因：未启用 Neo4j 时明确返回原消息，不伪造图谱写入。
    if not _truthy_flag(getattr(args, "neo4j_enabled", "0")):
        # 2026-06-04 16:31:05 新增原因：返回原数据库写入结果。
        return message
    # 2026-06-04 16:31:05 新增原因：读取 Neo4j URI。
    neo4j_uri = str(getattr(args, "neo4j_uri", ""))
    # 2026-06-04 16:31:05 新增原因：读取 Neo4j 用户。
    neo4j_user = str(getattr(args, "neo4j_user", "neo4j"))
    # 2026-06-04 16:31:05 新增原因：读取 Neo4j 密码。
    neo4j_password = str(getattr(args, "neo4j_password", ""))
    # 2026-06-04 16:31:05 新增原因：读取 Neo4j database。
    neo4j_database = str(getattr(args, "neo4j_database", "neo4j"))
    # 2026-06-04 16:31:05 新增原因：执行 Neo4j 写入，失败时直接抛错让用户知道图谱没建成。
    neo4j_message = save_to_neo4j(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        database=neo4j_database,
        bundle=bundle,
    )
    # 2026-06-04 16:31:05 新增原因：把关系库写入和 Neo4j 写入摘要合并返回。
    return f"{message}；{neo4j_message}"


def save_records_to_database(args: Namespace, bundle: DatabaseWriteBundle) -> str:
    # 如果用户指定调试 SQL 输出，则先写 SQL 文件。
    if args.debug_sql:
        # 输出 SQL 文件。
        write_debug_sql(Path(args.debug_sql).resolve(), bundle)
    # 不入库时直接返回提示。
    if args.db_backend == "none":
        # 返回跳过关系库入库但仍按配置同步 Neo4j 的消息。
        return _append_neo4j_sync_message(args, "未入库：--db-backend none", bundle)
    # SQL Server Docker sqlcmd 后端。
    if args.db_backend == "sqlcmd":
        # 调用 sqlcmd 入库。
        sql_message = save_to_sqlserver_sqlcmd(
            bundle=bundle,
            container=args.sqlcmd_container,
            server=args.sql_server,
            database=args.sql_db,
            user=args.sql_user,
            password=args.sql_password,
        )
        # 2026-06-04 16:31:05 新增原因：SQL Server 成功后同步 Neo4j 三元组。
        return _append_neo4j_sync_message(args, sql_message, bundle)
    # SQL Server pyodbc 后端。
    if args.db_backend == "pyodbc":
        # 调用 pyodbc 入库。
        sql_message = save_to_sqlserver_pyodbc(
            bundle=bundle,
            server=args.sql_server,
            database=args.sql_db,
            user=args.sql_user,
            password=args.sql_password,
            driver=args.sql_driver,
        )
        # 2026-06-04 16:31:05 新增原因：SQL Server 成功后同步 Neo4j 三元组。
        return _append_neo4j_sync_message(args, sql_message, bundle)
    # SQLite 兜底验证后端。
    if args.db_backend == "sqlite":
        # 调用 SQLite 入库。
        sqlite_message = save_to_sqlite(Path(args.sqlite_path).resolve(), bundle)
        # 2026-06-04 16:31:05 新增原因：SQLite 测试写入后也可同步 Neo4j，方便本地验图。
        return _append_neo4j_sync_message(args, sqlite_message, bundle)
    # 未知后端抛出错误。
    raise ValueError(f"未知入库后端：{args.db_backend}")
