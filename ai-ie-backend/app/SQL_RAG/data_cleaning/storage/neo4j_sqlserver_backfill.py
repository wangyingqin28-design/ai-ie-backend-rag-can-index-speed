# -*- coding: utf-8 -*-
"""从 SQL Server 现有 RAG 表回填 Neo4j 多跳三元组图谱。"""

# 2026-06-04 17:48:33 新增原因：导入 argparse，提供可重复执行的历史图谱回填命令。
import argparse
# 2026-06-04 17:48:33 新增原因：导入 hashlib，生成稳定 triple_id，确保 Neo4j MERGE 幂等。
import hashlib
# 2026-06-04 17:48:33 新增原因：导入 json，解析 SQL Server 中的 JSON 字段并写入审计属性。
import json
# 2026-06-04 17:48:33 新增原因：导入 os，读取已由 .env 加载的数据库配置。
import os
# 2026-06-04 17:48:33 新增原因：导入 sys，将 data_cleaning 根目录加入模块搜索路径。
import sys
# 2026-06-04 17:48:33 新增原因：导入 combinations，按同一 chunk 内实体生成共现边。
from itertools import combinations
# 2026-06-04 17:48:33 新增原因：导入 Path，定位 SQL_RAG 项目根和 .env 文件。
from pathlib import Path
# 2026-06-04 17:48:33 新增原因：导入 Any，给 SQL 行和三元组 payload 做类型标注。
from typing import Any

# 2026-06-04 17:48:33 新增原因：计算当前文件所在目录，兼容直接 python 执行和模块执行。
CURRENT_DIR = Path(__file__).resolve().parent
# 2026-06-04 17:48:33 新增原因：定位 data_cleaning 根目录，供 storage/data_structures 绝对导入使用。
DATA_CLEANING_DIR = CURRENT_DIR.parent
# 2026-06-04 17:48:33 新增原因：定位 SQL_RAG 根目录，读取同目录 .env。
SQL_RAG_DIR = DATA_CLEANING_DIR.parent
# 2026-06-04 17:48:33 新增原因：确保 data_cleaning 根目录进入 sys.path，避免从不同工作目录运行时报 import 错。
if str(DATA_CLEANING_DIR) not in sys.path:
    # 2026-06-04 17:48:33 新增原因：插到最前面，优先使用当前项目源码。
    sys.path.insert(0, str(DATA_CLEANING_DIR))

# 2026-06-04 17:48:33 新增原因：导入 dotenv，让项目内 .env 覆盖机器全局变量。
from dotenv import load_dotenv
# 2026-06-04 17:48:33 新增原因：导入 Neo4j 官方 driver，执行 schema 和三元组写入。
from neo4j import GraphDatabase

# 2026-06-04 17:48:33 新增原因：导入 pyodbc，读取现有 SQL Server RAG 表。
import pyodbc
# 2026-06-04 17:48:33 新增原因：复用 Neo4j writer 的 schema/merge 逻辑，保持新入库和回填写法一致。
from storage.neo4j_writer import ensure_neo4j_schema, merge_neo4j_triples


def _text(value: Any) -> str:
    # 2026-06-04 17:48:33 新增原因：把 SQL Server 返回值统一转成去空白字符串。
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    # 2026-06-04 17:48:33 新增原因：拼接三元组关键字段，作为幂等哈希输入。
    raw = "||".join(_text(part) for part in parts)
    # 2026-06-04 17:48:33 新增原因：使用 SHA1 前 24 位，和现有 qachunk/qamention 风格保持短 ID。
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    # 2026-06-04 17:48:33 新增原因：返回带业务前缀的稳定 ID，方便审计定位。
    return f"{prefix}_{digest}"


def _json_dict(value: Any) -> dict[str, Any]:
    # 2026-06-04 17:48:33 新增原因：空 JSON 字段直接给空字典，避免 json.loads 抛错。
    if not _text(value):
        # 2026-06-04 17:48:33 新增原因：返回空字典表示没有额外属性。
        return {}
    # 2026-06-04 17:48:33 新增原因：尝试解析 SQL Server 中保存的 JSON 字符串。
    try:
        # 2026-06-04 17:48:33 新增原因：仅当解析结果为字典时保留。
        parsed = json.loads(_text(value))
    # 2026-06-04 17:48:33 新增原因：历史数据可能有非严格 JSON，解析失败不阻断回填。
    except Exception:
        # 2026-06-04 17:48:33 新增原因：返回空字典，保留主链回填能力。
        return {}
    # 2026-06-04 17:48:33 新增原因：只接受 dict，避免 list/string 污染属性结构。
    return parsed if isinstance(parsed, dict) else {}


def _row_dict(cursor: Any, row: Any) -> dict[str, Any]:
    # 2026-06-04 17:48:33 新增原因：读取 cursor.description 中的列名。
    columns = [item[0] for item in cursor.description]
    # 2026-06-04 17:48:33 新增原因：把 pyodbc Row 转成普通 dict，方便后续构造三元组。
    return dict(zip(columns, row))


def _connection_string(driver: str, server: str, port: str, database: str, user: str, password: str) -> str:
    # 2026-06-04 17:48:33 新增原因：构建 SQL Server ODBC 连接串，显式关闭 Encrypt 兼容本地容器。
    return (
        f"DRIVER={{{driver}}};SERVER={server},{port};DATABASE={database};"
        f"UID={user};PWD={password};TrustServerCertificate=yes;Encrypt=no"
    )


def _read_rows(connection: Any, sql: str) -> list[dict[str, Any]]:
    # 2026-06-04 17:48:33 新增原因：创建游标执行只读 SQL。
    cursor = connection.cursor()
    # 2026-06-04 17:48:33 新增原因：执行查询并读取所有结果。
    rows = cursor.execute(sql).fetchall()
    # 2026-06-04 17:48:33 新增原因：转成 dict 列表，便于脱离 cursor 使用。
    return [_row_dict(cursor, row) for row in rows]


def _chunk_evidence(chunk: dict[str, Any]) -> str:
    # 2026-06-04 17:48:33 新增原因：优先使用 cleaned_text 作为图谱边证据。
    cleaned_text = _text(chunk.get("cleaned_text"))
    # 2026-06-04 17:48:33 新增原因：cleaned_text 存在时直接返回。
    if cleaned_text:
        # 2026-06-04 17:48:33 新增原因：截断超长证据，避免 Neo4j 关系属性过大。
        return cleaned_text[:1200]
    # 2026-06-04 17:48:33 新增原因：兜底用 question/answer 组合，保证 Prompt Builder 有证据文本。
    return f"问题：{_text(chunk.get('question'))}\n答案：{_text(chunk.get('answer'))}"[:1200]


def _add_triple(triples: dict[str, dict[str, Any]], triple: dict[str, Any]) -> None:
    # 2026-06-04 17:48:33 新增原因：读取三元组 ID。
    triple_id = _text(triple.get("triple_id"))
    # 2026-06-04 17:48:33 新增原因：缺少 ID/主语/宾语时跳过脏数据。
    if not triple_id or not _text(triple.get("subject")) or not _text(triple.get("object")):
        # 2026-06-04 17:48:33 新增原因：直接返回，不让脏数据进入 Neo4j。
        return
    # 2026-06-04 17:48:33 新增原因：按 triple_id 去重，保证回填幂等。
    triples[triple_id] = triple


def build_triples_from_sqlserver_rows(
    chunk_rows: list[dict[str, Any]],
    mention_rows: list[dict[str, Any]],
    alias_rows: list[dict[str, Any]],
    fusion_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # 2026-06-04 17:48:33 新增原因：按 chunk_id 建索引，给 mention/fusion 边补证据文本。
    chunks_by_id = {_text(chunk.get("chunk_id")): chunk for chunk in chunk_rows if _text(chunk.get("chunk_id"))}
    # 2026-06-04 17:48:33 新增原因：初始化三元组去重表。
    triples: dict[str, dict[str, Any]] = {}
    # 2026-06-04 17:48:33 新增原因：初始化 chunk 到实体集合的映射，用于共现边。
    entities_by_chunk: dict[str, dict[str, dict[str, Any]]] = {}

    # 2026-06-04 17:48:33 新增原因：遍历 chunk，建立 chunk 到全局聚类的多跳桥接边。
    for chunk in chunk_rows:
        # 2026-06-04 17:48:33 新增原因：读取 chunk ID。
        chunk_id = _text(chunk.get("chunk_id"))
        # 2026-06-04 17:48:33 新增原因：读取全局聚类 ID。
        global_cluster_id = _text(chunk.get("global_cluster_id"))
        # 2026-06-04 17:48:33 新增原因：chunk 或聚类缺失时不能建 CHUNK_IN_GLOBAL_CLUSTER。
        if not chunk_id or not global_cluster_id:
            # 2026-06-04 17:48:33 新增原因：继续处理下一个 chunk。
            continue
        # 2026-06-04 17:48:33 新增原因：写入 chunk -> global_cluster 边，供 Neo4j 多跳扩展。
        _add_triple(
            triples,
            {
                "triple_id": _stable_id("qatriple", chunk_id, "CHUNK_IN_GLOBAL_CLUSTER", global_cluster_id),
                "subject": chunk_id,
                "predicate": "CHUNK_IN_GLOBAL_CLUSTER",
                "object": global_cluster_id,
                "subject_type": "chunk",
                "object_type": "global_cluster",
                "chunk_id": chunk_id,
                "document_id": _text(chunk.get("document_id")),
                "global_cluster_id": global_cluster_id,
                "evidence_text": _chunk_evidence(chunk),
                "properties": {"global_cluster_label": _text(chunk.get("global_cluster_label"))},
            },
        )

    # 2026-06-04 17:48:33 新增原因：遍历 mention，把真实实体挂到 chunk。
    for mention in mention_rows:
        # 2026-06-04 17:48:33 新增原因：读取 mention 所属 chunk。
        chunk_id = _text(mention.get("chunk_id"))
        # 2026-06-04 17:48:33 新增原因：优先使用 canonical_entity，避免同义词碎片化。
        entity = _text(mention.get("canonical_entity")) or _text(mention.get("entity_value"))
        # 2026-06-04 17:48:33 新增原因：缺少实体或 chunk 时跳过。
        if not chunk_id or not entity:
            # 2026-06-04 17:48:33 新增原因：继续处理下一个 mention。
            continue
        # 2026-06-04 17:48:33 新增原因：读取 chunk 证据，缺失时用 mention 自身字段兜底。
        chunk = chunks_by_id.get(chunk_id, {})
        # 2026-06-04 17:48:33 新增原因：记录 chunk 内实体，后面构造 CO_OCCURS_WITH。
        entities_by_chunk.setdefault(chunk_id, {})[entity] = mention
        # 2026-06-04 17:48:33 新增原因：写入 entity -> chunk 的 MENTIONED_IN_CHUNK 边。
        _add_triple(
            triples,
            {
                "triple_id": _stable_id("qatriple", entity, "MENTIONED_IN_CHUNK", chunk_id),
                "subject": entity,
                "predicate": "MENTIONED_IN_CHUNK",
                "object": chunk_id,
                "subject_type": _text(mention.get("entity_type")) or "entity",
                "object_type": "chunk",
                "chunk_id": chunk_id,
                "document_id": _text(mention.get("document_id")),
                "global_cluster_id": _text(mention.get("global_cluster_id")) or _text(chunk.get("global_cluster_id")),
                "evidence_text": _chunk_evidence(chunk),
                "properties": {
                    "mention_id": _text(mention.get("mention_id")),
                    "entity_value": _text(mention.get("entity_value")),
                    "entity_hash": _text(mention.get("entity_hash")),
                },
            },
        )

    # 2026-06-04 17:48:33 新增原因：按同一 chunk 内实体生成共现边，让模型看到实体之间的业务邻接关系。
    for chunk_id, entity_map in entities_by_chunk.items():
        # 2026-06-04 17:48:33 新增原因：按名称排序，保证共现边方向稳定。
        entities = sorted(entity_map.keys())
        # 2026-06-04 17:48:33 新增原因：读取 chunk 证据。
        chunk = chunks_by_id.get(chunk_id, {})
        # 2026-06-04 17:48:33 新增原因：两两组合生成 CO_OCCURS_WITH。
        for left, right in combinations(entities, 2):
            # 2026-06-04 17:48:33 新增原因：写入实体共现边，支持多跳检索。
            _add_triple(
                triples,
                {
                    "triple_id": _stable_id("qatriple", left, "CO_OCCURS_WITH", right, chunk_id),
                    "subject": left,
                    "predicate": "CO_OCCURS_WITH",
                    "object": right,
                    "subject_type": _text(entity_map[left].get("entity_type")) or "entity",
                    "object_type": _text(entity_map[right].get("entity_type")) or "entity",
                    "chunk_id": chunk_id,
                    "document_id": _text(chunk.get("document_id")),
                    "global_cluster_id": _text(chunk.get("global_cluster_id")),
                    "evidence_text": _chunk_evidence(chunk),
                    "properties": {"co_occurrence_source": "sqlserver.rag_entity_mentions"},
                },
            )

    # 2026-06-04 17:48:33 新增原因：遍历 alias 表，建立 alias -> canonical 的归一化边。
    for alias in alias_rows:
        # 2026-06-04 17:48:33 新增原因：读取别名值。
        alias_value = _text(alias.get("alias_value"))
        # 2026-06-04 17:48:33 新增原因：读取标准实体。
        canonical_entity = _text(alias.get("canonical_entity"))
        # 2026-06-04 17:48:33 新增原因：无效 alias 或同名 alias 不需要建边。
        if not alias_value or not canonical_entity or alias_value == canonical_entity:
            # 2026-06-04 17:48:33 新增原因：继续处理下一个 alias。
            continue
        # 2026-06-04 17:48:33 新增原因：写入 ALIAS_OF，避免问法差异导致图谱召回断裂。
        _add_triple(
            triples,
            {
                "triple_id": _stable_id("qatriple", alias_value, "ALIAS_OF", canonical_entity),
                "subject": alias_value,
                "predicate": "ALIAS_OF",
                "object": canonical_entity,
                "subject_type": _text(alias.get("entity_type")) or "alias",
                "object_type": _text(alias.get("entity_type")) or "entity",
                "chunk_id": "",
                "document_id": "",
                "global_cluster_id": "",
                "evidence_text": "实体别名归一化关系来自 dbo.rag_entity_aliases。",
                "properties": {"alias_id": _text(alias.get("alias_id")), "entity_hash": _text(alias.get("entity_hash"))},
            },
        )

    # 2026-06-04 17:48:33 新增原因：遍历 fusion map，建立重复 chunk 到 canonical chunk 的归并边。
    for fusion in fusion_rows:
        # 2026-06-04 17:48:33 新增原因：读取 canonical chunk。
        canonical_chunk_id = _text(fusion.get("canonical_chunk_id"))
        # 2026-06-04 17:48:33 新增原因：读取 duplicate chunk。
        duplicate_chunk_id = _text(fusion.get("duplicate_chunk_id"))
        # 2026-06-04 17:48:33 新增原因：缺少任一端或同 ID 时跳过。
        if not canonical_chunk_id or not duplicate_chunk_id or canonical_chunk_id == duplicate_chunk_id:
            # 2026-06-04 17:48:33 新增原因：继续处理下一条 fusion。
            continue
        # 2026-06-04 17:48:33 新增原因：读取 duplicate chunk 证据。
        duplicate_chunk = chunks_by_id.get(duplicate_chunk_id, {})
        # 2026-06-04 17:48:33 新增原因：写入 duplicate -> canonical 的 FUSED_INTO 边。
        _add_triple(
            triples,
            {
                "triple_id": _stable_id("qatriple", duplicate_chunk_id, "FUSED_INTO", canonical_chunk_id),
                "subject": duplicate_chunk_id,
                "predicate": "FUSED_INTO",
                "object": canonical_chunk_id,
                "subject_type": "chunk",
                "object_type": "chunk",
                "chunk_id": duplicate_chunk_id,
                "document_id": _text(fusion.get("duplicate_document_id")),
                "global_cluster_id": _text(fusion.get("global_cluster_id")),
                "evidence_text": _chunk_evidence(duplicate_chunk) or _text(fusion.get("duplicate_cleaned_text"))[:1200],
                "properties": {
                    "fusion_id": _text(fusion.get("fusion_id")),
                    "fusion_score": _text(fusion.get("fusion_score")),
                    "fusion_rule": _text(fusion.get("fusion_rule")),
                    "merge_payload": _json_dict(fusion.get("merge_payload_json")),
                },
            },
        )

    # 2026-06-04 17:48:33 新增原因：返回稳定排序后的三元组列表，方便测试和审计。
    return [triples[key] for key in sorted(triples.keys())]


def load_sqlserver_graph_rows(connection: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    # 2026-06-04 17:48:33 新增原因：读取 chunk 主表，包含证据文本和全局聚类字段。
    chunk_rows = _read_rows(
        connection,
        """
        SELECT chunk_id, document_id, question, answer, cleaned_text, global_cluster_id,
               global_cluster_label, canonical_chunk_id, fusion_status
        FROM dbo.rag_qa_chunks
        """,
    )
    # 2026-06-04 17:48:33 新增原因：读取实体 mention 表，作为图谱实体入口。
    mention_rows = _read_rows(
        connection,
        """
        SELECT mention_id, document_id, chunk_id, entity_type, entity_value,
               canonical_entity, entity_hash, global_cluster_id
        FROM dbo.rag_entity_mentions
        """,
    )
    # 2026-06-04 17:48:33 新增原因：读取别名表，保证图谱查询可跨同义词命中。
    alias_rows = _read_rows(
        connection,
        """
        SELECT alias_id, entity_type, alias_value, canonical_entity, entity_hash
        FROM dbo.rag_entity_aliases
        """,
    )
    # 2026-06-04 17:48:33 新增原因：读取融合表，让重复问答和 canonical chunk 形成多跳链路。
    fusion_rows = _read_rows(
        connection,
        """
        SELECT fusion_id, canonical_chunk_id, duplicate_chunk_id, canonical_document_id,
               duplicate_document_id, global_cluster_id, fusion_score, fusion_rule,
               duplicate_cleaned_text, merge_payload_json
        FROM dbo.rag_chunk_fusion_map
        """,
    )
    # 2026-06-04 17:48:33 新增原因：返回四类 SQL 行，交给纯构造函数生成三元组。
    return chunk_rows, mention_rows, alias_rows, fusion_rows


def run_backfill(args: argparse.Namespace) -> dict[str, Any]:
    # 2026-06-04 17:48:33 新增原因：加载项目 .env 并覆盖机器环境，避免连到旧 Neo4j/SQL Server。
    load_dotenv(SQL_RAG_DIR / ".env", override=True)
    # 2026-06-04 17:48:33 新增原因：构建 SQL Server 连接串。
    sql_connection_string = _connection_string(
        driver=args.sql_driver or os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server"),
        server=args.sql_server or os.getenv("DB_HOST", "127.0.0.1"),
        port=args.sql_port or os.getenv("DB_PORT", "1433"),
        database=args.sql_database or os.getenv("DB_NAME", "getai"),
        user=args.sql_user or os.getenv("DB_USER", "dev"),
        password=args.sql_password or os.getenv("DB_PASSWORD", "123456"),
    )
    # 2026-06-04 17:48:33 新增原因：读取 Neo4j 配置。
    neo4j_uri = args.neo4j_uri or os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    # 2026-06-04 17:48:33 新增原因：读取 Neo4j 用户。
    neo4j_user = args.neo4j_user or os.getenv("NEO4J_USER", "neo4j")
    # 2026-06-04 17:48:33 新增原因：读取 Neo4j 密码。
    neo4j_password = args.neo4j_password or os.getenv("NEO4J_PASSWORD", "")
    # 2026-06-04 17:48:33 新增原因：读取 Neo4j database。
    neo4j_database = args.neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")
    # 2026-06-04 17:48:33 新增原因：缺少密码时直接报错，避免误以为回填完成。
    if not neo4j_password:
        # 2026-06-04 17:48:33 新增原因：抛出明确配置错误。
        raise RuntimeError("缺少 NEO4J_PASSWORD，无法回填 Neo4j。")

    # 2026-06-04 17:48:33 新增原因：连接 SQL Server 读取历史 RAG 表。
    with pyodbc.connect(sql_connection_string, timeout=args.sql_timeout) as connection:
        # 2026-06-04 17:48:33 新增原因：读取四类图谱输入行。
        chunk_rows, mention_rows, alias_rows, fusion_rows = load_sqlserver_graph_rows(connection)
    # 2026-06-04 17:48:33 新增原因：把 SQL 行转换成 Neo4j 三元组 payload。
    triples = build_triples_from_sqlserver_rows(chunk_rows, mention_rows, alias_rows, fusion_rows)
    # 2026-06-04 17:48:33 新增原因：创建 Neo4j driver。
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    # 2026-06-04 17:48:33 新增原因：确保 driver 最终关闭。
    try:
        # 2026-06-04 17:48:33 新增原因：先验证连接，失败则阻断回填。
        driver.verify_connectivity()
        # 2026-06-04 17:48:33 新增原因：确保约束和索引存在。
        ensure_neo4j_schema(driver, neo4j_database)
        # 2026-06-04 17:48:33 新增原因：批量 MERGE 写入三元组。
        relationship_count = merge_neo4j_triples(driver, neo4j_database, triples)
    # 2026-06-04 17:48:33 新增原因：无论成功失败都关闭 Neo4j 连接。
    finally:
        # 2026-06-04 17:48:33 新增原因：释放 Neo4j driver 资源。
        driver.close()
    # 2026-06-04 17:48:33 新增原因：返回可审计摘要，供命令行和测试使用。
    return {
        "chunks": len(chunk_rows),
        "mentions": len(mention_rows),
        "aliases": len(alias_rows),
        "fusions": len(fusion_rows),
        "triples": len(triples),
        "relationships_written": relationship_count,
        "neo4j_uri": neo4j_uri,
        "neo4j_database": neo4j_database,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    # 2026-06-04 17:48:33 新增原因：创建命令行解析器。
    parser = argparse.ArgumentParser(description="从 SQL Server 现有 RAG 表回填 Neo4j 多跳三元组图谱。")
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 SQL Server 地址。
    parser.add_argument("--sql-server", default="")
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 SQL Server 端口。
    parser.add_argument("--sql-port", default="")
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 SQL Server 数据库。
    parser.add_argument("--sql-database", default="")
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 SQL Server 用户。
    parser.add_argument("--sql-user", default="")
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 SQL Server 密码。
    parser.add_argument("--sql-password", default="")
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 ODBC driver。
    parser.add_argument("--sql-driver", default="")
    # 2026-06-04 17:48:33 新增原因：控制 SQL Server 连接超时，避免命令卡死。
    parser.add_argument("--sql-timeout", type=int, default=10)
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 Neo4j URI。
    parser.add_argument("--neo4j-uri", default="")
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 Neo4j 用户。
    parser.add_argument("--neo4j-user", default="")
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 Neo4j 密码。
    parser.add_argument("--neo4j-password", default="")
    # 2026-06-04 17:48:33 新增原因：允许命令行覆盖 Neo4j database。
    parser.add_argument("--neo4j-database", default="")
    # 2026-06-04 17:48:33 新增原因：返回解析器。
    return parser


def main() -> int:
    # 2026-06-04 17:48:33 新增原因：解析命令行参数。
    args = build_arg_parser().parse_args()
    # 2026-06-04 17:48:33 新增原因：执行回填并获取摘要。
    summary = run_backfill(args)
    # 2026-06-04 17:48:33 新增原因：以 JSON 输出摘要，方便自动化检查。
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # 2026-06-04 17:48:33 新增原因：返回成功状态码。
    return 0


# 2026-06-04 17:48:33 新增原因：支持直接运行该脚本。
if __name__ == "__main__":
    # 2026-06-04 17:48:33 新增原因：把 main 返回值交给系统退出码。
    raise SystemExit(main())
