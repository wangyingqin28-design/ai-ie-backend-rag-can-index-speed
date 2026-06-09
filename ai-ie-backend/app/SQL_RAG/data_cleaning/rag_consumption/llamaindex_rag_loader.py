# -*- coding: utf-8 -*-
"""从清洗生成物还原 LlamaIndex RAG 可消费节点。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：补齐下一步 RAG loader/indexer，使 JSON/SQL 里的 llamaindex_node_json 能直接进入 VectorStoreIndex。
# 修改日期：2026-06-01 13:29:35。
# 修改理由：读取 RAG 数据时默认过滤重复融合 chunk 和严重校验失败 chunk，保证后续 RAG 消费的是规范数据。

# 导入 JSON 库，用于读取 JSON 生成物和 SQL JSON 字段。
import json
# 导入 SQLite 标准库，用于本地验证 SQL 结构读写。
import sqlite3
# 导入路径类型。
from pathlib import Path

# 导入 LlamaIndex 官方向量索引。
from llama_index.core import VectorStoreIndex
# 导入 LlamaIndex 官方 embedding 基类。
from llama_index.core.embeddings import BaseEmbedding
# 导入 LlamaIndex 官方 TextNode。
from llama_index.core.schema import TextNode

# 导入入库 payload 类型。
from data_structures.models import StoragePayload


def filter_payloads_for_rag(payloads: list[StoragePayload], only_canonical: bool = True, require_validated: bool = True) -> list[StoragePayload]:
    # 创建过滤后的 payload 列表。
    filtered_payloads: list[StoragePayload] = []
    # 遍历 payload。
    for payload in payloads:
        # 要求官方 evaluator 已验证时过滤未验证问答。
        if require_validated and not payload.get("qa_pair_validated", False):
            # 跳过未验证问答。
            continue
        # 只消费规范 chunk 时过滤 duplicate。
        if only_canonical and payload.get("fusion_status", "canonical") == "duplicate":
            # 跳过重复融合 chunk。
            continue
        # 追加可消费 payload。
        filtered_payloads.append(payload)
    # 返回过滤后的 payload。
    return filtered_payloads


def load_payloads_from_json(json_path: Path, only_canonical: bool = True, require_validated: bool = True) -> list[StoragePayload]:
    # 读取 JSON 文件文本。
    raw_text = json_path.read_text(encoding="utf-8")
    # 解析 JSON 数组。
    payloads = json.loads(raw_text)
    # 校验顶层必须是列表。
    if not isinstance(payloads, list):
        # 抛出明确错误。
        raise ValueError(f"RAG JSON 生成物必须是数组：{json_path}")
    # 返回 RAG 可消费 payload 列表。
    return filter_payloads_for_rag(payloads, only_canonical=only_canonical, require_validated=require_validated)


def load_payloads_from_sqlite(sqlite_path: Path, document_id: str = "", only_canonical: bool = True, require_validated: bool = True, exclude_error_issues: bool = True) -> list[StoragePayload]:
    # 打开 SQLite 连接。
    connection = sqlite3.connect(sqlite_path)
    # 让查询结果按列名读取。
    connection.row_factory = sqlite3.Row
    # 确保连接最终关闭。
    try:
        # 创建 WHERE 条件列表。
        where_parts: list[str] = []
        # 创建 SQL 参数列表。
        params: list[object] = []
        # 有文档 ID 时按文档过滤。
        if document_id:
            # 添加文档过滤条件。
            where_parts.append("document_id = ?")
            # 追加文档 ID 参数。
            params.append(document_id)
        # 要求官方 evaluator 已验证时添加条件。
        if require_validated:
            # 添加验证条件。
            where_parts.append("qa_pair_validated = 1")
        # 只消费规范 chunk 时添加条件。
        if only_canonical:
            # 添加规范 chunk 条件。
            where_parts.append("(fusion_status IS NULL OR fusion_status <> 'duplicate')")
            # 同步排除融合映射表里的重复 chunk。
            where_parts.append("chunk_id NOT IN (SELECT duplicate_chunk_id FROM rag_chunk_fusion_map)")
        # 排除严重校验问题时添加条件。
        if exclude_error_issues:
            # 添加校验问题排除条件。
            where_parts.append("chunk_id NOT IN (SELECT chunk_id FROM rag_validation_issues WHERE issue_level = 'error')")
        # 拼接 WHERE SQL。
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        # 查询 payload_json。
        rows = connection.execute(f"SELECT payload_json FROM rag_qa_chunks {where_sql} ORDER BY document_id, chunk_index", params).fetchall()
        # 解析每行 payload_json。
        return [json.loads(row["payload_json"]) for row in rows]
    # 最终关闭连接。
    finally:
        # 关闭 SQLite 连接。
        connection.close()


def load_payloads_from_sqlserver_pyodbc(
    server: str,
    database: str,
    user: str,
    password: str,
    driver: str = "ODBC Driver 17 for SQL Server",
    document_id: str = "",
    only_canonical: bool = True,
    require_validated: bool = True,
    exclude_error_issues: bool = True,
) -> list[StoragePayload]:
    # 尝试导入 SQL Server ODBC 驱动包。
    try:
        # 导入 pyodbc。
        import pyodbc  # type: ignore
    # 未安装 pyodbc 时抛出明确错误。
    except ImportError as exc:
        # 抛出运行错误。
        raise RuntimeError("当前 Python 环境没有安装 pyodbc，无法直接从 SQL Server 读取 RAG payload。") from exc
    # 拼接 SQL Server 连接串。
    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )
    # 打开 SQL Server 连接。
    with pyodbc.connect(connection_string) as connection:
        # 创建游标。
        cursor = connection.cursor()
        # 创建 WHERE 条件列表。
        where_parts: list[str] = []
        # 创建 SQL 参数列表。
        params: list[object] = []
        # 有文档 ID 时按文档过滤。
        if document_id:
            # 添加文档过滤条件。
            where_parts.append("document_id = ?")
            # 追加文档 ID 参数。
            params.append(document_id)
        # 要求官方 evaluator 已验证时添加条件。
        if require_validated:
            # 添加验证条件。
            where_parts.append("qa_pair_validated = 1")
        # 只消费规范 chunk 时添加条件。
        if only_canonical:
            # 添加规范 chunk 条件。
            where_parts.append("(fusion_status IS NULL OR fusion_status <> N'duplicate')")
            # 同步排除融合映射表里的重复 chunk。
            where_parts.append("chunk_id NOT IN (SELECT duplicate_chunk_id FROM dbo.rag_chunk_fusion_map)")
        # 排除严重校验问题时添加条件。
        if exclude_error_issues:
            # 添加校验问题排除条件。
            where_parts.append("chunk_id NOT IN (SELECT chunk_id FROM dbo.rag_validation_issues WHERE issue_level = N'error')")
        # 拼接 WHERE SQL。
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        # 查询 payload_json。
        rows = cursor.execute(f"SELECT payload_json FROM dbo.rag_qa_chunks {where_sql} ORDER BY document_id, chunk_index", params).fetchall()
    # 解析 payload_json。
    return [json.loads(row[0]) for row in rows]


def llamaindex_nodes_from_storage_payloads(payloads: list[StoragePayload]) -> list[TextNode]:
    # 创建官方 TextNode 列表。
    nodes: list[TextNode] = []
    # 遍历 storage payload。
    for payload in payloads:
        # 读取官方 llamaindex_node 字段。
        node_payload = payload.get("llamaindex_node") or payload.get("llamaindex_node_json")
        # SQL 字符串形式时先解析 JSON。
        if isinstance(node_payload, str):
            # 解析字符串 JSON。
            node_payload = json.loads(node_payload)
        # 字段缺失时抛出明确错误。
        if not isinstance(node_payload, dict):
            # 抛出值错误。
            raise ValueError(f"payload 缺少 llamaindex_node：{payload.get('chunk_id', '')}")
        # 使用 LlamaIndex 官方 TextNode.from_dict 还原节点。
        nodes.append(TextNode.from_dict(node_payload))
    # 返回官方节点列表。
    return nodes


def build_vector_index_from_storage_payloads(payloads: list[StoragePayload], embed_model: BaseEmbedding) -> VectorStoreIndex:
    # 从 payload 还原 LlamaIndex 官方 TextNode。
    nodes = llamaindex_nodes_from_storage_payloads(payloads)
    # 使用 LlamaIndex 官方 VectorStoreIndex 构建可查询索引。
    return VectorStoreIndex(nodes=nodes, embed_model=embed_model, show_progress=False)
