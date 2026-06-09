# -*- coding: utf-8 -*-
"""Neo4j 三元组图谱写入器。"""

# 2026-06-04 16:27:31 新增原因：导入 JSON 用于把三元组属性稳定写入 Neo4j。
import json
# 2026-06-04 16:27:31 新增原因：导入 Any 用于 Neo4j 参数类型标注。
from typing import Any

# 2026-06-04 16:27:31 新增原因：导入 Neo4j 官方驱动，真实写入多跳图谱。
from neo4j import GraphDatabase

# 2026-06-04 16:27:31 新增原因：导入数据库 bundle 类型，读取清洗链路生成的三元组。
from data_structures.models import DatabaseWriteBundle, StoragePayload


def _neo4j_node_id(raw_value: Any) -> str:
    # 2026-06-04 16:27:31 新增原因：把 Neo4j 节点 ID 统一转为字符串。
    return str(raw_value or "").strip()


def _neo4j_node_name(raw_value: Any) -> str:
    # 2026-06-04 16:27:31 新增原因：节点展示名与 ID 同源，避免前端/Prompt Builder 看不到实体名。
    return _neo4j_node_id(raw_value)


def _neo4j_properties_json(properties: Any) -> str:
    # 2026-06-04 16:27:31 新增原因：属性字典统一 JSON 化，方便后续审计和 replay。
    return json.dumps(properties if isinstance(properties, dict) else {}, ensure_ascii=False, default=str)


def ensure_neo4j_schema(driver: Any, database: str) -> None:
    # 2026-06-04 16:27:31 新增原因：打开 Neo4j session 准备建约束和索引。
    with driver.session(database=database) as session:
        # 2026-06-04 16:27:31 新增原因：节点 ID 唯一约束保证 MERGE 速度和幂等。
        session.run("CREATE CONSTRAINT sqlrag_node_id IF NOT EXISTS FOR (n:SqlRagNode) REQUIRE n.id IS UNIQUE")
        # 2026-06-04 16:27:31 新增原因：节点名称索引支持关键词实体检索。
        session.run("CREATE INDEX sqlrag_node_name IF NOT EXISTS FOR (n:SqlRagNode) ON (n.name)")
        # 2026-06-04 16:27:31 新增原因：节点类型索引支持按 entity/chunk/global_cluster 过滤。
        session.run("CREATE INDEX sqlrag_node_kind IF NOT EXISTS FOR (n:SqlRagNode) ON (n.kind)")
        # 2026-06-04 16:27:31 新增原因：关系 triple_id 索引支持审计定位。
        session.run("CREATE INDEX sqlrag_rel_triple_id IF NOT EXISTS FOR ()-[r:SQL_RAG_RELATION]-() ON (r.triple_id)")


def merge_neo4j_triples(driver: Any, database: str, triples: list[StoragePayload]) -> int:
    # 2026-06-04 16:27:31 新增原因：没有三元组时直接返回 0，避免打开无意义事务。
    if not triples:
        # 2026-06-04 16:27:31 新增原因：返回写入数量 0。
        return 0
    # 2026-06-04 16:27:31 新增原因：构造 Neo4j 批量 MERGE 参数。
    rows = [
        {
            "triple_id": _neo4j_node_id(triple.get("triple_id")),
            "subject": _neo4j_node_id(triple.get("subject")),
            "predicate": _neo4j_node_id(triple.get("predicate")),
            "object": _neo4j_node_id(triple.get("object")),
            "subject_type": _neo4j_node_id(triple.get("subject_type") or "entity"),
            "object_type": _neo4j_node_id(triple.get("object_type") or "entity"),
            "chunk_id": _neo4j_node_id(triple.get("chunk_id")),
            "document_id": _neo4j_node_id(triple.get("document_id")),
            "global_cluster_id": _neo4j_node_id(triple.get("global_cluster_id")),
            "evidence_text": str(triple.get("evidence_text") or ""),
            "properties_json": _neo4j_properties_json(triple.get("properties")),
        }
        for triple in triples
        if _neo4j_node_id(triple.get("triple_id")) and _neo4j_node_id(triple.get("subject")) and _neo4j_node_id(triple.get("object"))
    ]
    # 2026-06-04 16:27:31 新增原因：过滤后为空则无需写库。
    if not rows:
        # 2026-06-04 16:27:31 新增原因：返回写入数量 0。
        return 0
    # 2026-06-04 16:27:31 新增原因：打开 Neo4j session 执行批量写入。
    with driver.session(database=database) as session:
        # 2026-06-04 16:27:31 新增原因：UNWIND 批量 MERGE 实体、chunk、聚类和关系。
        session.run(
            """
            UNWIND $rows AS row
            MERGE (subject:SqlRagNode {id: row.subject})
            SET subject.name = row.subject,
                subject.kind = row.subject_type,
                subject.updated_at = datetime()
            MERGE (object:SqlRagNode {id: row.object})
            SET object.name = row.object,
                object.kind = row.object_type,
                object.updated_at = datetime()
            MERGE (subject)-[rel:SQL_RAG_RELATION {triple_id: row.triple_id}]->(object)
            SET rel.predicate = row.predicate,
                rel.chunk_id = row.chunk_id,
                rel.document_id = row.document_id,
                rel.global_cluster_id = row.global_cluster_id,
                rel.evidence_text = row.evidence_text,
                rel.properties_json = row.properties_json,
                rel.updated_at = datetime()
            """,
            rows=rows,
        )
    # 2026-06-04 16:27:31 新增原因：返回实际提交的关系数量。
    return len(rows)


def save_to_neo4j(uri: str, user: str, password: str, database: str, bundle: DatabaseWriteBundle) -> str:
    # 2026-06-04 16:27:31 新增原因：缺少 URI 或密码时明确报错，避免以为已经建图。
    if not uri or not password:
        # 2026-06-04 16:27:31 新增原因：抛出配置错误。
        raise RuntimeError("Neo4j 写入已启用，但 NEO4J_URI/NEO4J_PASSWORD 未配置。")
    # 2026-06-04 16:27:31 新增原因：创建 Neo4j driver。
    driver = GraphDatabase.driver(uri, auth=(user, password))
    # 2026-06-04 16:27:31 新增原因：确保 driver 最终关闭。
    try:
        # 2026-06-04 16:27:31 新增原因：验证连通性，避免静默跳过图谱写入。
        driver.verify_connectivity()
        # 2026-06-04 16:27:31 新增原因：确保约束和索引存在。
        ensure_neo4j_schema(driver, database)
        # 2026-06-04 16:27:31 新增原因：批量写入三元组。
        count = merge_neo4j_triples(driver, database, bundle.neo4j_triple_payloads)
    # 2026-06-04 16:27:31 新增原因：无论成功失败都释放 Neo4j 连接。
    finally:
        # 2026-06-04 16:27:31 新增原因：关闭 driver。
        driver.close()
    # 2026-06-04 16:27:31 新增原因：返回写入摘要。
    return f"Neo4j 三元组写入完成：{count} 条关系，database={database}"
