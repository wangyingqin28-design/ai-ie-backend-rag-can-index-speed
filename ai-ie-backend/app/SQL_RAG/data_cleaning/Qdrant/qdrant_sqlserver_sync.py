# -*- coding: utf-8 -*-
"""把 SQL Server 里的 canonical QA chunk 同步成 Qdrant collection。"""

# 修改日期：2026-06-01 17:52:00。
# 修改理由：把 SQL Server 2022 中已清洗、已校验、已融合后的 canonical QA chunk，用官方 qdrant-client API 封装成 Qdrant 向量检索 collection。

# 导入 argparse，用于把同步参数暴露成命令行接口。
import argparse
# 导入 hashlib，用于生成稳定的同步状态主键。
import hashlib
# 导入 json，用于解析 SQL Server 里的 JSON 字段和构造同步消息。
import json
# 导入 os，用于读取环境变量。
import os
# 导入 textwrap，用于拼接更稳定的向量化文本。
import textwrap
# 导入 uuid，用于把 chunk_id 稳定映射成 Qdrant 支持的 UUID point id。
import uuid
# 导入 dataclass，用于定义同步配置和同步记录结构。
from dataclasses import dataclass
# 导入 datetime，用于记录同步时间。
from datetime import datetime, timezone
# 导入 Path，用于定位项目根目录和 .env 文件。
from pathlib import Path
# 导入 Any，用于标注 SQL/Qdrant payload 的动态字段。
from typing import Any

# 导入 OpenAI 官方 SDK，用 OpenAI-compatible embedding 服务生成生产向量。
from openai import OpenAI
# 导入 python-dotenv，用于读取项目 .env 配置。
from dotenv import load_dotenv
# 导入 pyodbc，用于从 SQL Server 2022 读取主数据。
import pyodbc
# 导入 Qdrant 官方 Python 客户端。
from qdrant_client import QdrantClient
# 导入 Qdrant 官方模型定义，创建 collection、payload index 和 point 时使用。
from qdrant_client import models


# 定义当前同步脚本所在目录。
CURRENT_DIR = Path(__file__).resolve().parent
# 定义 data_cleaning 目录。
DATA_CLEANING_DIR = CURRENT_DIR.parent
# 2026-06-02 10:06:01 修改：SQL_RAG 作为独立后端运行时，配置必须读取 SQL_RAG 根目录。
SQL_RAG_DIR = DATA_CLEANING_DIR.parent
# 2026-06-02 10:06:01 修改：Qdrant 同步不再读取外层 ai-ie-backend/.env，避免拿错数据库和向量库地址。
ENV_PATH = SQL_RAG_DIR / ".env"


@dataclass(frozen=True)
class SqlServerConfig:
    # SQL Server 主机，本机默认走 127.0.0.1。
    server: str
    # SQL Server 数据库名。
    database: str
    # SQL Server 用户名。
    user: str
    # SQL Server 密码。
    password: str
    # SQL Server ODBC 驱动名。
    driver: str


@dataclass(frozen=True)
class EmbeddingConfig:
    # OpenAI-compatible embedding 服务地址。
    api_base: str
    # OpenAI-compatible embedding API key。
    api_key: str
    # embedding 模型名，必须和后续 RAG 查询阶段保持一致。
    model: str
    # Qdrant collection 向量维度，必须和 embedding 返回维度一致。
    dimension: int
    # 每批发送给 embedding 服务的文本数量。
    batch_size: int


@dataclass(frozen=True)
class QdrantSyncConfig:
    # Qdrant HTTP 地址。
    url: str
    # Qdrant collection 名称。
    collection_name: str
    # Qdrant collection 距离度量。
    distance: str
    # 是否重建 collection。
    recreate_collection: bool
    # 每批 upsert 到 Qdrant 的 point 数量。
    upsert_batch_size: int
    # 是否只做 dry-run，不实际写入 Qdrant 和 SQL Server 同步状态。
    dry_run: bool


@dataclass(frozen=True)
class CanonicalChunk:
    # QA chunk 主键。
    chunk_id: str
    # 文档主键。
    document_id: str
    # 音频编号。
    audio_no: int
    # 音频标题。
    audio_title: str
    # chunk 在文档内的序号。
    chunk_index: int
    # 业务场景。
    scene: str
    # 已分离并校验的问题。
    question: str
    # 已分离并校验的答案。
    answer: str
    # 清洗后的问答全文。
    cleaned_text: str
    # 处理步骤。
    resolution_steps: str
    # 关键词文本。
    keywords: str
    # 实体 JSON。
    entities_json: str
    # 来源片段。
    source_excerpt: str
    # 内容 hash。
    content_hash: str
    # QA 成对 ID。
    qa_pair_id: str
    # QA 成对序号。
    qa_pair_index: int
    # QA 相似度分数。
    qa_similarity_score: float
    # QA 相似度阈值。
    qa_similarity_threshold: float
    # QA 是否已通过 LlamaIndex evaluator 校验。
    qa_pair_validated: bool
    # 文档内聚类 ID。
    cluster_id: str
    # 文档内聚类标签。
    cluster_label: str
    # 文档内聚类层级。
    cluster_level: str
    # 文档内聚类路径。
    cluster_path: str
    # 全局聚类 ID。
    global_cluster_id: str
    # 全局聚类标签。
    global_cluster_label: str
    # 全局聚类层级。
    global_cluster_level: str
    # 全局聚类路径。
    global_cluster_path: str
    # 问题 hash。
    question_hash: str
    # 答案 hash。
    answer_hash: str
    # canonical chunk ID。
    canonical_chunk_id: str
    # 融合状态，canonical 才进入 Qdrant。
    fusion_status: str
    # payload schema 版本。
    payload_schema_version: str
    # 原始 payload JSON。
    payload_json: dict[str, Any]
    # RAG 消费契约版本。
    rag_contract_version: str
    # 规范问题。
    canonical_question: str
    # 答案优先字段。
    answer_text: str
    # query 口语/业务别名。
    query_aliases: list[str]
    # 完整来源摘录。
    source_excerpt_full: str
    # LLM 消费文本。
    llm_text: str
    # 向量检索文本。
    retrieval_text: str
    # 已融合 duplicate 上下文。
    duplicate_contexts: list[dict[str, Any]]
    # 已合并 duplicate chunk IDs。
    merged_duplicate_chunk_ids: list[str]
    # 是否满足 Qdrant 同步契约。
    qdrant_ready: bool
    # 校验标记。
    validation_flags: list[str]


def read_env_value(name: str, default: str = "") -> str:
    # 从环境变量读取配置。
    value = os.getenv(name)
    # 环境变量存在时直接返回。
    if value not in (None, ""):
        # 返回环境变量值。
        return value
    # 环境变量不存在时返回默认值。
    return default


def load_project_env() -> None:
    # 如果项目 .env 文件存在，就加载它。
    if ENV_PATH.exists():
        # 加载 .env，override=True 用来处理同一个键在文件里多次出现时取后面的有效值。
        load_dotenv(ENV_PATH, override=True)


def parse_args() -> argparse.Namespace:
    # 创建命令行解析器。
    parser = argparse.ArgumentParser(description="把 SQL Server canonical QA chunks 同步到 Qdrant collection。")
    # 添加 SQL Server 主机参数。
    parser.add_argument("--sql-server", default=read_env_value("DB_HOST", "127.0.0.1"))
    # 添加 SQL Server 数据库参数。
    parser.add_argument("--sql-database", default=read_env_value("DB_NAME", "getai"))
    # 添加 SQL Server 用户参数。
    parser.add_argument("--sql-user", default=read_env_value("DB_USER", "dev"))
    # 添加 SQL Server 密码参数。
    parser.add_argument("--sql-password", default=read_env_value("DB_PASSWORD", "123456"))
    # 添加 SQL Server ODBC 驱动参数。
    parser.add_argument("--sql-driver", default=read_env_value("DB_DRIVER", "ODBC Driver 17 for SQL Server"))
    # 添加 Qdrant URL 参数。
    parser.add_argument("--qdrant-url", default=read_env_value("QDRANT_URL", "http://127.0.0.1:6333"))
    # 添加 Qdrant collection 参数。
    parser.add_argument("--collection", default=read_env_value("QDRANT_COLLECTION", "sql_rag_qa_chunks_v1"))
    # 添加距离度量参数。
    parser.add_argument("--distance", default=read_env_value("QDRANT_DISTANCE", "Cosine"))
    # 添加是否重建 collection 参数。
    parser.add_argument("--recreate", action="store_true", help="删除并重建目标 Qdrant collection。")
    # 添加 embedding 服务地址参数。
    parser.add_argument("--embedding-api-base", default=read_env_value("EMBEDDING_SERVICE_URL", "https://api.siliconflow.cn/v1"))
    # 添加 embedding API key 参数。
    parser.add_argument("--embedding-api-key", default=read_env_value("EMBEDDING_SERVICE_API_KEY", ""))
    # 添加 embedding 模型参数，默认跟现有 RAG.py 的 MODEL_EMBED 保持一致。
    parser.add_argument("--embedding-model", default=read_env_value("MODEL_EMBED", "Qwen/Qwen3-Embedding-0.6B"))
    # 添加 embedding 维度参数，默认 1024，和现有 RAG.py 里的 dimensions=1024 对齐。
    parser.add_argument("--embedding-dimension", type=int, default=int(read_env_value("EMBEDDING_DIMENSIONS", "1024")))
    # 添加 embedding 批量大小参数。
    parser.add_argument("--embedding-batch-size", type=int, default=int(read_env_value("EMBEDDING_MAX_CHUNKS_IN_BATCH", "10")))
    # 添加 Qdrant upsert 批量大小参数。
    parser.add_argument("--upsert-batch-size", type=int, default=64)
    # 添加 dry-run 参数。
    parser.add_argument("--dry-run", action="store_true", help="只读取和生成向量，不写入 Qdrant/SQL Server。")
    # 返回解析后的参数。
    return parser.parse_args()


def build_sqlserver_config(args: argparse.Namespace) -> SqlServerConfig:
    # 根据命令行参数构造 SQL Server 配置。
    return SqlServerConfig(
        # 写入 SQL Server 主机。
        server=args.sql_server,
        # 写入数据库名。
        database=args.sql_database,
        # 写入用户名。
        user=args.sql_user,
        # 写入密码。
        password=args.sql_password,
        # 写入 ODBC 驱动。
        driver=normalize_odbc_driver_name(args.sql_driver),
    )


def normalize_odbc_driver_name(driver_name: str) -> str:
    # URL 连接串常把空格写成加号，这里还原成 pyodbc 可识别的驱动名。
    normalized = driver_name.replace("+", " ").strip()
    # 如果外层已经带花括号，去掉花括号，后续 connection_string 会统一补。
    normalized = normalized.removeprefix("{").removesuffix("}")
    # 返回归一化后的驱动名。
    return normalized


def build_embedding_config(args: argparse.Namespace) -> EmbeddingConfig:
    # 如果没有配置 API key，就立刻报错，避免生成假向量。
    if not args.embedding_api_key:
        # 抛出明确异常。
        raise ValueError("缺少 EMBEDDING_SERVICE_API_KEY，不能生成生产 Qdrant 向量。")
    # 根据命令行参数构造 embedding 配置。
    return EmbeddingConfig(
        # 写入服务地址。
        api_base=args.embedding_api_base,
        # 写入 API key。
        api_key=args.embedding_api_key,
        # 写入模型名。
        model=args.embedding_model,
        # 写入向量维度。
        dimension=args.embedding_dimension,
        # 写入批量大小。
        batch_size=args.embedding_batch_size,
    )


def build_qdrant_config(args: argparse.Namespace) -> QdrantSyncConfig:
    # 根据命令行参数构造 Qdrant 同步配置。
    return QdrantSyncConfig(
        # 写入 Qdrant URL。
        url=args.qdrant_url,
        # 写入 collection 名称。
        collection_name=args.collection,
        # 写入距离度量。
        distance=args.distance,
        # 写入是否重建 collection。
        recreate_collection=args.recreate,
        # 写入 upsert 批量大小。
        upsert_batch_size=args.upsert_batch_size,
        # 写入 dry-run 标记。
        dry_run=args.dry_run,
    )


def sqlserver_connection_string(config: SqlServerConfig) -> str:
    # 拼接 pyodbc 连接字符串。
    return (
        # 设置 ODBC 驱动。
        f"DRIVER={{{config.driver}}};"
        # 设置 SQL Server 地址。
        f"SERVER={config.server};"
        # 设置数据库名。
        f"DATABASE={config.database};"
        # 设置用户名。
        f"UID={config.user};"
        # 设置密码。
        f"PWD={config.password};"
        # 信任本地 SQL Server 证书。
        "TrustServerCertificate=yes;"
        # 关闭加密，匹配当前 Docker SQL Server 测试环境。
        "Encrypt=no;"
    )


def parse_json_object(raw_text: str | None) -> dict[str, Any]:
    # 空字符串直接返回空字典。
    if not raw_text:
        # 返回空字典。
        return {}
    # 尝试把 JSON 字符串解析成字典。
    try:
        # 执行 JSON 解析。
        parsed = json.loads(raw_text)
    # JSON 不合法时保留原文到 raw 字段。
    except json.JSONDecodeError:
        # 返回带 raw 的字典，避免同步中断。
        return {"raw": raw_text}
    # 解析结果是字典时直接返回。
    if isinstance(parsed, dict):
        # 返回字典。
        return parsed
    # 解析结果不是字典时包装成 value。
    return {"value": parsed}


def parse_json_list(raw_value: Any) -> list[Any]:
    # None 或空字符串返回空列表。
    if raw_value in (None, ""):
        return []
    # 已经是列表时直接返回。
    if isinstance(raw_value, list):
        return raw_value
    # 字符串尝试 JSON 解析。
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return [raw_value] if raw_value.strip() else []
        if isinstance(parsed, list):
            return parsed
        if parsed in (None, ""):
            return []
        return [parsed]
    # 其他值作为单项列表。
    return [raw_value]


def normalize_string_list(raw_value: Any) -> list[str]:
    # 转成 JSON/list 后逐项清洗。
    return [str(item).strip() for item in parse_json_list(raw_value) if str(item).strip()]


def normalize_dict_list(raw_value: Any) -> list[dict[str, Any]]:
    # 只保留 dict 项。
    return [item for item in parse_json_list(raw_value) if isinstance(item, dict)]


def normalize_bool(value: Any, default: bool = True) -> bool:
    # None 使用默认值。
    if value is None:
        return default
    # bool 原样返回。
    if isinstance(value, bool):
        return value
    # 数字转 bool。
    if isinstance(value, (int, float)):
        return bool(value)
    # 字符串兼容常见写法。
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    # 其他情况使用默认值。
    return default


def normalize_text(value: Any) -> str:
    # None 转空字符串。
    if value is None:
        # 返回空字符串。
        return ""
    # 非 None 统一转字符串并清理两侧空白。
    return str(value).strip()


def load_canonical_chunks_from_sqlserver(config: SqlServerConfig) -> list[CanonicalChunk]:
    # 定义 canonical chunk 查询 SQL。
    sql = """
SELECT
    chunks.chunk_id,
    chunks.document_id,
    chunks.audio_no,
    chunks.audio_title,
    chunks.chunk_index,
    chunks.scene,
    chunks.question,
    chunks.answer,
    chunks.cleaned_text,
    chunks.resolution_steps,
    chunks.keywords,
    chunks.entities_json,
    chunks.source_excerpt,
    chunks.content_hash,
    chunks.qa_pair_id,
    chunks.qa_pair_index,
    chunks.qa_similarity_score,
    chunks.qa_similarity_threshold,
    chunks.qa_pair_validated,
    chunks.cluster_id,
    chunks.cluster_label,
    chunks.cluster_level,
    chunks.cluster_path,
    chunks.global_cluster_id,
    chunks.global_cluster_label,
    chunks.global_cluster_level,
    chunks.global_cluster_path,
    chunks.question_hash,
    chunks.answer_hash,
    chunks.canonical_chunk_id,
    chunks.fusion_status,
    chunks.payload_schema_version,
    chunks.payload_json
FROM dbo.rag_qa_chunks AS chunks
WHERE chunks.qa_pair_validated = 1
  AND ISNULL(chunks.fusion_status, N'canonical') <> N'duplicate'
  AND chunks.chunk_id NOT IN (
      SELECT fusion.duplicate_chunk_id
      FROM dbo.rag_chunk_fusion_map AS fusion
  )
  AND NOT EXISTS (
      SELECT 1
      FROM dbo.rag_validation_issues AS issues
      WHERE issues.chunk_id = chunks.chunk_id
        AND issues.issue_level = N'error'
  )
ORDER BY chunks.document_id, chunks.chunk_index;
"""
    # 打开 SQL Server 连接。
    with pyodbc.connect(sqlserver_connection_string(config)) as connection:
        # 创建 cursor。
        cursor = connection.cursor()
        # 执行 canonical 查询。
        rows = cursor.execute(sql).fetchall()
    # 创建 chunk 列表。
    chunks: list[CanonicalChunk] = []
    # 遍历 SQL 查询结果。
    for row in rows:
        # 解析 payload_json，优先使用新契约字段。
        payload_json = parse_json_object(row.payload_json)
        # 读取问题。
        question = normalize_text(payload_json.get("question") or row.question)
        # 读取答案。
        answer = normalize_text(payload_json.get("answer_text") or payload_json.get("answer") or row.answer)
        # 读取清洗文本。
        cleaned_text = normalize_text(payload_json.get("cleaned_text") or row.cleaned_text)
        # 读取完整来源摘录。
        source_excerpt_full = normalize_text(payload_json.get("source_excerpt_full") or payload_json.get("source_excerpt") or row.source_excerpt)
        # 旧 v2 数据可能只有截断 source_excerpt，必须用完整 question + answer 重建同步契约。
        if answer and answer not in source_excerpt_full:
            source_excerpt_full = f"问题：{question}\n答案：{answer}"
        # 读取 LLM 消费文本。
        llm_text = normalize_text(payload_json.get("llm_text"))
        # 读取检索文本。
        retrieval_text = normalize_text(payload_json.get("retrieval_text"))
        # 把当前行转换成 CanonicalChunk。
        chunks.append(
            CanonicalChunk(
                # 读取 chunk_id。
                chunk_id=normalize_text(row.chunk_id),
                # 读取 document_id。
                document_id=normalize_text(row.document_id),
                # 读取 audio_no。
                audio_no=int(row.audio_no or 0),
                # 读取 audio_title。
                audio_title=normalize_text(row.audio_title),
                # 读取 chunk_index。
                chunk_index=int(row.chunk_index or 0),
                # 读取 scene。
                scene=normalize_text(row.scene),
                # 读取 question。
                question=question,
                # 读取 answer。
                answer=answer,
                # 读取 cleaned_text。
                cleaned_text=cleaned_text,
                # 读取 resolution_steps。
                resolution_steps=normalize_text(row.resolution_steps),
                # 读取 keywords。
                keywords=normalize_text(row.keywords),
                # 读取 entities_json。
                entities_json=normalize_text(row.entities_json),
                # 读取 source_excerpt。
                source_excerpt=normalize_text(payload_json.get("source_excerpt") or row.source_excerpt),
                # 读取 content_hash。
                content_hash=normalize_text(row.content_hash),
                # 读取 qa_pair_id。
                qa_pair_id=normalize_text(row.qa_pair_id),
                # 读取 qa_pair_index。
                qa_pair_index=int(row.qa_pair_index or 0),
                # 读取 qa_similarity_score。
                qa_similarity_score=float(row.qa_similarity_score or 0.0),
                # 读取 qa_similarity_threshold。
                qa_similarity_threshold=float(row.qa_similarity_threshold or 0.0),
                # 读取 qa_pair_validated。
                qa_pair_validated=bool(row.qa_pair_validated),
                # 读取 cluster_id。
                cluster_id=normalize_text(row.cluster_id),
                # 读取 cluster_label。
                cluster_label=normalize_text(row.cluster_label),
                # 读取 cluster_level。
                cluster_level=normalize_text(row.cluster_level),
                # 读取 cluster_path。
                cluster_path=normalize_text(row.cluster_path),
                # 读取 global_cluster_id。
                global_cluster_id=normalize_text(row.global_cluster_id),
                # 读取 global_cluster_label。
                global_cluster_label=normalize_text(row.global_cluster_label),
                # 读取 global_cluster_level。
                global_cluster_level=normalize_text(row.global_cluster_level),
                # 读取 global_cluster_path。
                global_cluster_path=normalize_text(row.global_cluster_path),
                # 读取 question_hash。
                question_hash=normalize_text(row.question_hash),
                # 读取 answer_hash。
                answer_hash=normalize_text(row.answer_hash),
                # 读取 canonical_chunk_id。
                canonical_chunk_id=normalize_text(row.canonical_chunk_id),
                # 读取 fusion_status。
                fusion_status=normalize_text(row.fusion_status or "canonical"),
                # 读取 payload_schema_version。
                payload_schema_version=normalize_text(payload_json.get("payload_schema_version") or row.payload_schema_version),
                # 解析 payload_json。
                payload_json=payload_json,
                # 读取 RAG 消费契约版本。
                rag_contract_version=normalize_text(payload_json.get("rag_contract_version") or "qa-rag-contract-v1"),
                # 读取规范问题。
                canonical_question=normalize_text(payload_json.get("canonical_question") or question),
                # 读取答案优先字段。
                answer_text=answer,
                # 读取 query aliases。
                query_aliases=normalize_string_list(payload_json.get("query_aliases")),
                # 读取完整来源摘录。
                source_excerpt_full=source_excerpt_full,
                # 读取 LLM 消费文本。
                llm_text=llm_text,
                # 读取向量检索文本。
                retrieval_text=retrieval_text,
                # 读取 duplicate 上下文。
                duplicate_contexts=normalize_dict_list(payload_json.get("duplicate_contexts")),
                # 读取合并 duplicate chunk IDs。
                merged_duplicate_chunk_ids=normalize_string_list(payload_json.get("merged_duplicate_chunk_ids")),
                # 读取 Qdrant ready。
                qdrant_ready=normalize_bool(payload_json.get("qdrant_ready"), default=True),
                # 读取校验标记。
                validation_flags=normalize_string_list(payload_json.get("validation_flags")),
            )
        )
    # 返回 canonical chunks。
    return chunks


def build_answer_first_text(chunk: CanonicalChunk) -> str:
    # 读取答案优先字段。
    answer = chunk.answer_text or chunk.answer
    # 已有 llm_text 且包含完整答案时优先使用。
    if chunk.llm_text and answer and answer in chunk.llm_text:
        return chunk.llm_text
    # 解析操作步骤。
    steps = normalize_string_list(chunk.resolution_steps)
    # 组装 duplicate 融合上下文。
    duplicate_texts = [
        normalize_text(context.get("cleaned_text") or context.get("source_excerpt"))
        for context in chunk.duplicate_contexts
        if normalize_text(context.get("cleaned_text") or context.get("source_excerpt"))
    ]
    # 构造答案优先文本。
    parts = [
        f"标准答案：{answer}",
        f"用户问题：{chunk.question}",
        f"规范问题：{chunk.canonical_question or chunk.question}",
        f"业务场景：{chunk.scene}",
        f"全局主题：{chunk.global_cluster_label}",
    ]
    # 追加操作步骤。
    if steps:
        parts.append("操作步骤：" + "；".join(steps))
    # 追加 query aliases。
    if chunk.query_aliases:
        parts.append("相关问法：" + "；".join(chunk.query_aliases))
    # 追加兼容问答文本。
    if chunk.cleaned_text:
        parts.append("兼容问答文本：" + chunk.cleaned_text)
    # 追加完整来源摘录。
    if chunk.source_excerpt_full and chunk.source_excerpt_full != chunk.cleaned_text:
        parts.append("完整来源摘录：" + chunk.source_excerpt_full)
    # 追加 duplicate 上下文。
    if duplicate_texts:
        parts.append("已融合重复上下文：" + "\n".join(duplicate_texts))
    # 返回完整消费文本。
    return "\n".join(part for part in parts if part and not part.endswith("：")).strip()


def build_embedding_text(chunk: CanonicalChunk) -> str:
    # 读取答案优先字段。
    answer = chunk.answer_text or chunk.answer
    # 优先使用 payload_json 中的 retrieval_text。
    if chunk.retrieval_text and answer and answer in chunk.retrieval_text:
        return chunk.retrieval_text
    # 拼接问题、答案、别名、场景和聚类信息，让向量表达更贴近问答检索。
    return textwrap.dedent(
        f"""
        业务场景：{chunk.scene}
        全局主题：{chunk.global_cluster_label}
        问题：{chunk.question}
        规范问题：{chunk.canonical_question or chunk.question}
        相关问法：{"；".join(chunk.query_aliases)}
        答案：{answer}
        操作/上下文：{build_answer_first_text(chunk)}
        """
    ).strip()


def build_qdrant_point_id(chunk_id: str) -> str:
    # 用 UUID5 把业务 chunk_id 稳定映射成 Qdrant 官方支持的 UUID 字符串。
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sql-rag-qa-chunk:{chunk_id}"))


def build_qdrant_payload(chunk: CanonicalChunk, embedding_config: EmbeddingConfig) -> dict[str, Any]:
    # 构造答案优先 LLM 消费文本。
    llm_text = build_answer_first_text(chunk)
    # 构造向量检索文本。
    retrieval_text = build_embedding_text(chunk)
    # 读取答案优先字段。
    answer_text = chunk.answer_text or chunk.answer
    # 读取完整来源摘录。
    source_excerpt_full = chunk.source_excerpt_full or chunk.source_excerpt or chunk.cleaned_text
    # 构造 Qdrant point payload，payload 只放检索过滤和回表所需的元数据。
    return {
        # 保存原始 chunk_id，RAG 命中后可回 SQL Server 补全完整关系。
        "chunk_id": chunk.chunk_id,
        # 保存 Qdrant point id，方便外部机器直接 retrieve。
        "point_id": build_qdrant_point_id(chunk.chunk_id),
        # 保存 document_id，支持按文档过滤。
        "document_id": chunk.document_id,
        # 保存音频编号。
        "audio_no": chunk.audio_no,
        # 保存音频标题。
        "audio_title": chunk.audio_title,
        # 保存 chunk 序号。
        "chunk_index": chunk.chunk_index,
        # 保存业务场景。
        "scene": chunk.scene,
        # 保存问题文本。
        "question": chunk.question,
        # 保存答案文本。
        "answer": chunk.answer,
        # 保存规范问题。
        "canonical_question": chunk.canonical_question or chunk.question,
        # 保存答案优先字段。
        "answer_text": answer_text,
        # 保存 query aliases。
        "query_aliases": chunk.query_aliases,
        # 保存清洗文本。
        "cleaned_text": chunk.cleaned_text,
        # 保存解决步骤。
        "resolution_steps": chunk.resolution_steps,
        # 保存关键词。
        "keywords": chunk.keywords,
        # 保存实体 JSON 字符串。
        "entities_json": chunk.entities_json,
        # 保存来源片段。
        "source_excerpt": chunk.source_excerpt,
        # 保存完整来源片段。
        "source_excerpt_full": source_excerpt_full,
        # 保存 LLM 直接消费文本。
        "llm_text": llm_text,
        # 保存向量检索文本。
        "retrieval_text": retrieval_text,
        # 保存 duplicate 融合上下文。
        "duplicate_contexts": chunk.duplicate_contexts,
        # 保存已合入 canonical 的 duplicate chunk IDs。
        "merged_duplicate_chunk_ids": chunk.merged_duplicate_chunk_ids,
        # 保存 Qdrant 同步契约状态。
        "qdrant_ready": chunk.qdrant_ready,
        # 保存校验标记。
        "validation_flags": chunk.validation_flags,
        # 保存内容 hash。
        "content_hash": chunk.content_hash,
        # 保存 QA 成对 ID。
        "qa_pair_id": chunk.qa_pair_id,
        # 保存 QA 成对序号。
        "qa_pair_index": chunk.qa_pair_index,
        # 保存 QA 相似度分数。
        "qa_similarity_score": chunk.qa_similarity_score,
        # 保存 QA 相似度阈值。
        "qa_similarity_threshold": chunk.qa_similarity_threshold,
        # 保存 QA 校验状态。
        "qa_pair_validated": chunk.qa_pair_validated,
        # 保存文档内聚类 ID。
        "cluster_id": chunk.cluster_id,
        # 保存文档内聚类标签。
        "cluster_label": chunk.cluster_label,
        # 保存文档内聚类层级。
        "cluster_level": chunk.cluster_level,
        # 保存文档内聚类路径。
        "cluster_path": chunk.cluster_path,
        # 保存全局聚类 ID。
        "global_cluster_id": chunk.global_cluster_id,
        # 保存全局聚类标签。
        "global_cluster_label": chunk.global_cluster_label,
        # 保存全局聚类层级。
        "global_cluster_level": chunk.global_cluster_level,
        # 保存全局聚类路径。
        "global_cluster_path": chunk.global_cluster_path,
        # 保存问题 hash。
        "question_hash": chunk.question_hash,
        # 保存答案 hash。
        "answer_hash": chunk.answer_hash,
        # 保存 canonical chunk ID。
        "canonical_chunk_id": chunk.canonical_chunk_id,
        # 保存融合状态。
        "fusion_status": chunk.fusion_status,
        # 保存 payload schema 版本。
        "payload_schema_version": chunk.payload_schema_version,
        # 保存 RAG 消费契约版本。
        "rag_contract_version": chunk.rag_contract_version,
        # 保存 embedding 模型名。
        "embedding_model": embedding_config.model,
        # 保存 embedding 维度。
        "embedding_dimension": embedding_config.dimension,
        # 保存同步来源。
        "sync_source": "sqlserver:getai.dbo.rag_qa_chunks",
        # 保存文本字段，兼容部分 RAG loader 默认读取 text 的习惯。
        "text": llm_text,
    }


def chunk_list(items: list[Any], batch_size: int) -> list[list[Any]]:
    # 创建批次结果。
    batches: list[list[Any]] = []
    # 按 batch_size 切分列表。
    for start_index in range(0, len(items), batch_size):
        # 追加当前批次。
        batches.append(items[start_index : start_index + batch_size])
    # 返回批次列表。
    return batches


def create_embedding_client(config: EmbeddingConfig) -> OpenAI:
    # 创建 OpenAI-compatible embedding 客户端。
    return OpenAI(api_key=config.api_key, base_url=config.api_base)


def embed_texts(client: OpenAI, texts: list[str], config: EmbeddingConfig) -> list[list[float]]:
    # 调用 OpenAI-compatible embeddings API 生成向量。
    response = client.embeddings.create(
        # 传入 embedding 模型名。
        model=config.model,
        # 传入当前批次文本。
        input=texts,
        # 显式指定维度，确保和 Qdrant collection vector size 一致。
        dimensions=config.dimension,
    )
    # 按 API 返回顺序取出 embedding。
    embeddings = [item.embedding for item in response.data]
    # 如果返回数量不一致，立即报错。
    if len(embeddings) != len(texts):
        # 抛出明确异常。
        raise RuntimeError(f"embedding 返回数量不一致：请求 {len(texts)} 条，返回 {len(embeddings)} 条。")
    # 校验每条向量维度。
    for embedding in embeddings:
        # 维度不一致时立即报错，避免写入错误 collection。
        if len(embedding) != config.dimension:
            # 抛出明确异常。
            raise RuntimeError(f"embedding 维度不一致：期望 {config.dimension}，实际 {len(embedding)}。")
    # 返回向量列表。
    return embeddings


def qdrant_distance(distance_name: str) -> models.Distance:
    # 统一距离名大小写。
    normalized = distance_name.strip().upper()
    # Cosine 距离。
    if normalized == "COSINE":
        # 返回 Qdrant 官方 Cosine 枚举。
        return models.Distance.COSINE
    # Dot 距离。
    if normalized == "DOT":
        # 返回 Qdrant 官方 Dot 枚举。
        return models.Distance.DOT
    # Euclid 距离。
    if normalized in {"EUCLID", "EUCLIDEAN"}:
        # 返回 Qdrant 官方 Euclid 枚举。
        return models.Distance.EUCLID
    # 未知距离直接报错。
    raise ValueError(f"不支持的 Qdrant distance：{distance_name}")


def ensure_qdrant_collection(client: QdrantClient, config: QdrantSyncConfig, embedding_config: EmbeddingConfig) -> None:
    # 判断 collection 是否存在。
    exists = client.collection_exists(config.collection_name)
    # 如果 dry-run，跳过实际建库动作。
    if config.dry_run:
        # 直接返回。
        return
    # 如果要求重建且 collection 已存在，先删除。
    if exists and config.recreate_collection:
        # 使用 Qdrant 官方 delete_collection API 删除旧 collection。
        client.delete_collection(collection_name=config.collection_name)
        # 更新存在状态。
        exists = False
    # 如果 collection 不存在，创建新 collection。
    if not exists:
        # 使用 Qdrant 官方 create_collection API 创建向量集合。
        client.create_collection(
            # 指定 collection 名称。
            collection_name=config.collection_name,
            # 指定向量维度和距离度量。
            vectors_config=models.VectorParams(
                # 指定向量维度。
                size=embedding_config.dimension,
                # 指定距离度量。
                distance=qdrant_distance(config.distance),
            ),
        )
        # 创建 payload 索引，方便其他机器按字段过滤。
        create_payload_indexes(client, config.collection_name)
        # 创建完成后返回。
        return
    # collection 已存在时读取 collection 信息。
    collection_info = client.get_collection(collection_name=config.collection_name)
    # 读取当前 collection 的向量配置。
    vectors_config = collection_info.config.params.vectors
    # 兼容单向量 collection 的 VectorParams 结构。
    if isinstance(vectors_config, models.VectorParams):
        # 读取当前向量维度。
        current_size = vectors_config.size
    # 兼容命名向量 collection 的字典结构。
    elif isinstance(vectors_config, dict):
        # 读取第一个命名向量维度。
        current_size = next(iter(vectors_config.values())).size
    # 其他结构直接报错。
    else:
        # 抛出明确异常。
        raise RuntimeError(f"无法识别 Qdrant collection 向量配置：{vectors_config}")
    # 如果维度不一致，必须让用户显式 --recreate。
    if current_size != embedding_config.dimension:
        # 抛出明确异常。
        raise RuntimeError(
            f"Qdrant collection 已存在但维度不一致：当前 {current_size}，期望 {embedding_config.dimension}。请加 --recreate 重建。"
        )
    # 已存在且维度正确时补齐 payload index。
    create_payload_indexes(client, config.collection_name)


def create_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    # 定义需要建索引的 payload 字段。
    indexes = {
        # chunk_id 用于回表。
        "chunk_id": models.PayloadSchemaType.KEYWORD,
        # document_id 用于按文档过滤。
        "document_id": models.PayloadSchemaType.KEYWORD,
        # scene 用于按业务场景过滤。
        "scene": models.PayloadSchemaType.KEYWORD,
        # cluster_id 用于按文档内聚类过滤。
        "cluster_id": models.PayloadSchemaType.KEYWORD,
        # global_cluster_id 用于按全局聚类过滤。
        "global_cluster_id": models.PayloadSchemaType.KEYWORD,
        # fusion_status 用于只取 canonical。
        "fusion_status": models.PayloadSchemaType.KEYWORD,
        # qa_pair_validated 用于过滤已校验问答。
        "qa_pair_validated": models.PayloadSchemaType.BOOL,
        # question_hash 用于同问消歧。
        "question_hash": models.PayloadSchemaType.KEYWORD,
        # answer_hash 用于同答融合。
        "answer_hash": models.PayloadSchemaType.KEYWORD,
        # payload schema 版本用于兼容排查。
        "payload_schema_version": models.PayloadSchemaType.KEYWORD,
        # RAG 消费契约版本用于下游筛选。
        "rag_contract_version": models.PayloadSchemaType.KEYWORD,
        # qdrant_ready 用于同步后自检。
        "qdrant_ready": models.PayloadSchemaType.BOOL,
    }
    # 遍历索引定义。
    for field_name, field_schema in indexes.items():
        # 创建 payload index。
        try:
            # 使用 Qdrant 官方 create_payload_index API。
            client.create_payload_index(
                # 指定 collection。
                collection_name=collection_name,
                # 指定字段名。
                field_name=field_name,
                # 指定字段类型。
                field_schema=field_schema,
            )
        # 索引已存在或版本差异时不阻断主流程。
        except Exception:
            # 继续下一个字段。
            continue


def validate_chunks_before_qdrant(chunks: list[CanonicalChunk]) -> dict[str, Any]:
    # 创建错误列表。
    errors: list[str] = []
    # 遍历 canonical chunks。
    for chunk in chunks:
        # 读取答案优先字段。
        answer = chunk.answer_text or chunk.answer
        # 构造 LLM 消费文本。
        llm_text = build_answer_first_text(chunk)
        # 构造检索文本。
        retrieval_text = build_embedding_text(chunk)
        # 读取完整来源摘录。
        source_excerpt_full = chunk.source_excerpt_full or chunk.source_excerpt or chunk.cleaned_text
        # 缺问题。
        if not chunk.question:
            errors.append(f"{chunk.chunk_id}: missing question")
        # 缺答案。
        if not answer:
            errors.append(f"{chunk.chunk_id}: missing answer_text")
        # payload 显式标记不可同步。
        if not chunk.qdrant_ready:
            errors.append(f"{chunk.chunk_id}: qdrant_ready is false")
        # LLM 消费文本漏答案。
        if answer and answer not in llm_text:
            errors.append(f"{chunk.chunk_id}: llm_text missing full answer")
        # 检索文本漏答案。
        if answer and answer not in retrieval_text:
            errors.append(f"{chunk.chunk_id}: retrieval_text missing full answer")
        # 完整摘录漏答案。
        if answer and answer not in source_excerpt_full:
            errors.append(f"{chunk.chunk_id}: source_excerpt_full missing full answer")
    # 有错误时阻断同步。
    if errors:
        preview = "\n".join(errors[:20])
        raise RuntimeError(f"Qdrant 同步前契约校验失败，共 {len(errors)} 个问题：\n{preview}")
    # 返回校验摘要。
    return {
        "checked_chunk_count": len(chunks),
        "contract_version": "qa-rag-contract-v1",
        "error_count": 0,
    }


def build_qdrant_points(chunks: list[CanonicalChunk], embeddings: list[list[float]], embedding_config: EmbeddingConfig) -> list[models.PointStruct]:
    # 创建 point 列表。
    points: list[models.PointStruct] = []
    # 同时遍历 chunk 和 embedding。
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        # 构造官方 PointStruct。
        points.append(
            models.PointStruct(
                # 设置稳定 UUID point id。
                id=build_qdrant_point_id(chunk.chunk_id),
                # 设置向量。
                vector=embedding,
                # 设置 payload。
                payload=build_qdrant_payload(chunk, embedding_config),
            )
        )
    # 返回 point 列表。
    return points


def upsert_points_to_qdrant(client: QdrantClient, config: QdrantSyncConfig, points: list[models.PointStruct]) -> None:
    # 如果 dry-run，跳过实际写入。
    if config.dry_run:
        # 直接返回。
        return
    # 按批次写入 Qdrant。
    for point_batch in chunk_list(points, config.upsert_batch_size):
        # 使用 Qdrant 官方 upsert API 写入 points。
        client.upsert(
            # 指定 collection。
            collection_name=config.collection_name,
            # 指定 point 批次。
            points=point_batch,
            # 等待写入完成，便于后续立即测试。
            wait=True,
        )


def build_document_chunk_counts(chunks: list[CanonicalChunk]) -> dict[str, int]:
    # 创建文档计数字典。
    counts: dict[str, int] = {}
    # 遍历所有 canonical chunk。
    for chunk in chunks:
        # 按 document_id 累计。
        counts[chunk.document_id] = counts.get(chunk.document_id, 0) + 1
    # 返回计数字典。
    return counts


def build_document_hashes(chunks: list[CanonicalChunk]) -> dict[str, str]:
    # 创建文档 hash 字典。
    hashes: dict[str, str] = {}
    # 遍历所有 canonical chunk。
    for chunk in chunks:
        # 首次出现该文档时记录内容 hash。
        hashes.setdefault(chunk.document_id, chunk.content_hash)
    # 返回 hash 字典。
    return hashes


def sync_state_id(document_id: str, collection_name: str) -> str:
    # 用 document_id 和 collection_name 生成稳定 hash。
    digest = hashlib.sha256(f"{document_id}|{collection_name}".encode("utf-8")).hexdigest()[:24]
    # 返回符合现有 NVARCHAR(80) 的同步 ID。
    return f"qdrantsync_{digest}"


def update_sqlserver_sync_state(
    sql_config: SqlServerConfig,
    qdrant_config: QdrantSyncConfig,
    embedding_config: EmbeddingConfig,
    chunks: list[CanonicalChunk],
    point_count: int,
) -> None:
    # dry-run 时不更新 SQL Server。
    if qdrant_config.dry_run:
        # 直接返回。
        return
    # 统计每个文档同步了多少 canonical chunk。
    chunk_counts = build_document_chunk_counts(chunks)
    # 读取每个文档的内容 hash。
    document_hashes = build_document_hashes(chunks)
    # 构造同步消息。
    sync_message = json.dumps(
        {
            # 写入 Qdrant URL。
            "qdrant_url": qdrant_config.url,
            # 写入 collection 名称。
            "collection": qdrant_config.collection_name,
            # 写入 embedding 模型。
            "embedding_model": embedding_config.model,
            # 写入 embedding 维度。
            "embedding_dimension": embedding_config.dimension,
            # 写入同步 point 数量。
            "point_count": point_count,
            # 写入同步时间。
            "synced_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )
    # 打开 SQL Server 连接。
    with pyodbc.connect(sqlserver_connection_string(sql_config), autocommit=True) as connection:
        # 创建 cursor。
        cursor = connection.cursor()
        # 遍历每个文档的同步状态。
        for document_id, chunk_count in chunk_counts.items():
            # 执行 MERGE 更新同步状态。
            cursor.execute(
                """
MERGE dbo.rag_rag_sync_state AS target
USING (
    SELECT
        ? AS sync_id,
        ? AS document_id,
        ? AS content_hash,
        ? AS sync_target,
        ? AS sync_status,
        ? AS chunk_count,
        ? AS needs_reindex,
        ? AS sync_message
) AS source
ON target.sync_id = source.sync_id
WHEN MATCHED THEN
    UPDATE SET
        content_hash = source.content_hash,
        sync_target = source.sync_target,
        sync_status = source.sync_status,
        chunk_count = source.chunk_count,
        needs_reindex = source.needs_reindex,
        sync_message = source.sync_message,
        updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (sync_id, document_id, content_hash, sync_target, sync_status, chunk_count, needs_reindex, sync_message)
    VALUES (source.sync_id, source.document_id, source.content_hash, source.sync_target, source.sync_status, source.chunk_count, source.needs_reindex, source.sync_message);
""",
                # 设置同步状态主键。
                sync_state_id(document_id, qdrant_config.collection_name),
                # 设置文档 ID。
                document_id,
                # 设置内容 hash。
                document_hashes.get(document_id, ""),
                # 设置同步目标。
                f"qdrant:{qdrant_config.collection_name}",
                # 设置同步状态。
                "synced",
                # 设置 chunk 数。
                chunk_count,
                # 设置 needs_reindex。
                0,
                # 设置同步消息。
                sync_message,
            )


def verify_qdrant_collection(client: QdrantClient, config: QdrantSyncConfig, first_vector: list[float]) -> dict[str, Any]:
    # dry-run 时返回空校验结果。
    if config.dry_run:
        # 返回 dry-run 结果。
        return {"dry_run": True}
    # 调用 Qdrant 官方 count API 统计 collection point 数。
    count_result = client.count(collection_name=config.collection_name, exact=True)
    # 调用 Qdrant 官方 query_points API 验证向量可检索。
    query_result = client.query_points(
        # 指定 collection。
        collection_name=config.collection_name,
        # 使用第一条向量做自检查询。
        query=first_vector,
        # 只取前三条。
        limit=3,
        # 返回 payload 给后续排查。
        with_payload=True,
        # 不返回向量，减少输出。
        with_vectors=False,
    )
    # 读取第一条命中 payload。
    first_payload = query_result.points[0].payload if query_result.points else {}
    # 读取答案和默认 text。
    first_answer = str(first_payload.get("answer_text") or first_payload.get("answer") or "") if first_payload else ""
    first_text = str(first_payload.get("text") or "") if first_payload else ""
    # 判断默认 text 是否包含完整答案。
    contract_ready = bool(first_payload and first_answer and first_answer in first_text and first_payload.get("qdrant_ready", True))
    # 返回校验摘要。
    return {
        # 返回 point 总数。
        "point_count": count_result.count,
        # 返回命中数量。
        "query_hit_count": len(query_result.points),
        # 返回第一条命中的 chunk_id。
        "first_hit_chunk_id": first_payload.get("chunk_id") if first_payload else "",
        # 返回第一条命中的问题。
        "first_hit_question": first_payload.get("question") if first_payload else "",
        # 返回第一条命中是否满足 RAG 消费契约。
        "first_hit_contract_ready": contract_ready,
        # 返回第一条命中的契约版本。
        "first_hit_contract_version": first_payload.get("rag_contract_version", "") if first_payload else "",
    }


def sync_sqlserver_to_qdrant(sql_config: SqlServerConfig, embedding_config: EmbeddingConfig, qdrant_config: QdrantSyncConfig) -> dict[str, Any]:
    # 从 SQL Server 读取 canonical chunks。
    chunks = load_canonical_chunks_from_sqlserver(sql_config)
    # 没有可同步数据时直接报错。
    if not chunks:
        # 抛出明确异常。
        raise RuntimeError("SQL Server 中没有可同步到 Qdrant 的 canonical QA chunk。")
    # 同步前执行 RAG 消费契约校验，阻断缺字段或漏答案的 point。
    contract_validation = validate_chunks_before_qdrant(chunks)
    # 创建 Qdrant 官方客户端。
    # 2026-06-06 11:30:19 修改原因：禁用系统代理环境，避免 Windows no_proxy 里的 IPv6 CIDR 破坏本地 Qdrant 同步。
    qdrant_client = QdrantClient(url=qdrant_config.url, trust_env=False)
    # 确保 Qdrant collection 存在且维度正确。
    ensure_qdrant_collection(qdrant_client, qdrant_config, embedding_config)
    # 创建 OpenAI-compatible embedding 客户端。
    embedding_client = create_embedding_client(embedding_config)
    # 创建全部 point 列表。
    all_points: list[models.PointStruct] = []
    # 遍历 chunk 批次。
    for chunk_batch in chunk_list(chunks, embedding_config.batch_size):
        # 构造当前批次的向量化文本。
        texts = [build_embedding_text(chunk) for chunk in chunk_batch]
        # 生成当前批次 embedding。
        embeddings = embed_texts(embedding_client, texts, embedding_config)
        # 构造当前批次 Qdrant points。
        point_batch = build_qdrant_points(chunk_batch, embeddings, embedding_config)
        # 追加到全部 point 列表。
        all_points.extend(point_batch)
        # 写入当前批次到 Qdrant。
        upsert_points_to_qdrant(qdrant_client, qdrant_config, point_batch)
    # 更新 SQL Server 同步状态。
    update_sqlserver_sync_state(sql_config, qdrant_config, embedding_config, chunks, len(all_points))
    # 执行 Qdrant 检索校验。
    verify_result = verify_qdrant_collection(qdrant_client, qdrant_config, all_points[0].vector)  # type: ignore[arg-type]
    # 返回同步摘要。
    return {
        # 返回 collection 名称。
        "collection": qdrant_config.collection_name,
        # 返回 Qdrant URL。
        "qdrant_url": qdrant_config.url,
        # 返回读取 chunk 数。
        "source_chunk_count": len(chunks),
        # 返回写入 point 数。
        "upserted_point_count": len(all_points),
        # 返回同步前契约校验摘要。
        "contract_validation": contract_validation,
        # 返回 embedding 模型。
        "embedding_model": embedding_config.model,
        # 返回 embedding 维度。
        "embedding_dimension": embedding_config.dimension,
        # 返回是否 dry-run。
        "dry_run": qdrant_config.dry_run,
        # 返回校验结果。
        "verify": verify_result,
    }


def main() -> None:
    # 加载项目 .env。
    load_project_env()
    # 解析命令行参数。
    args = parse_args()
    # 构造 SQL Server 配置。
    sql_config = build_sqlserver_config(args)
    # 构造 embedding 配置。
    embedding_config = build_embedding_config(args)
    # 构造 Qdrant 配置。
    qdrant_config = build_qdrant_config(args)
    # 执行 SQL Server 到 Qdrant 的同步。
    summary = sync_sqlserver_to_qdrant(sql_config, embedding_config, qdrant_config)
    # 输出同步摘要 JSON，便于命令行和 CI 读取。
    print(json.dumps(summary, ensure_ascii=False, indent=2))


# 作为脚本运行时进入 main。
if __name__ == "__main__":
    # 调用 main。
    main()
