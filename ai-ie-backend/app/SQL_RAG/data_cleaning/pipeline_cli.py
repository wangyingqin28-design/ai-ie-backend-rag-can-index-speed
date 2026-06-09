# -*- coding: utf-8 -*-
"""命令行参数定义。"""

# 修改日期：2026-06-01 10:14:00。
# 修改理由：新增问答强相关绑定阈值和答案窗口参数，保证 Markdown 进入后端时先成对再清洗。
# 修改日期：2026-06-01 13:29:35。
# 修改理由：新增目录级多 Markdown 输入和跨文档融合阈值参数。

# 导入 argparse。
import argparse
# 导入路径类型。
from pathlib import Path


def build_arg_parser(default_env: dict[str, str], script_dir: Path) -> argparse.ArgumentParser:
    # 创建命令行解析器。
    parser = argparse.ArgumentParser(description="通用 Markdown 客户问答清洗、语义分块、向量化、SQL Server 2022 入库程序")
    # 输入路径支持单个 Markdown 文件或包含多个 Markdown 的目录。
    parser.add_argument("--input", default=r"C:\Users\DELL\Desktop\audio_merged_transcription.md", help="Markdown 问答文档路径或 Markdown 目录路径")
    # JSON 数组输出路径。
    parser.add_argument("--output-json", default=str(script_dir / "qa_cleaned_chunks.json"), help="结构化 JSON 输出路径")
    # JSONL 输出路径。
    parser.add_argument("--output-jsonl", default=str(script_dir / "qa_cleaned_chunks.jsonl"), help="结构化 JSONL 输出路径")
    # 数据库后端选择。
    parser.add_argument("--db-backend", choices=["none", "sqlcmd", "pyodbc", "sqlite"], default="sqlcmd", help="入库后端")
    # SQLite 兜底库路径。
    parser.add_argument("--sqlite-path", default=str(script_dir / "qa_cleaned_chunks.sqlite"), help="SQLite 兜底测试库路径")
    # Docker SQL Server 容器名。
    parser.add_argument("--sqlcmd-container", default="sql-rag-sqlserver-2022", help="SQL Server Docker 容器名")
    # SQL Server 地址。
    parser.add_argument("--sql-server", default="localhost", help="SQL Server 地址")
    # SQL Server 数据库名。
    parser.add_argument("--sql-db", default=default_env.get("APP_DB_NAME", "getai"), help="SQL Server 数据库名")
    # SQL Server 用户名。
    parser.add_argument("--sql-user", default=default_env.get("APP_DB_USER", "dev"), help="SQL Server 用户名")
    # SQL Server 密码。
    parser.add_argument("--sql-password", default=default_env.get("APP_DB_PASSWORD", "123456"), help="SQL Server 密码")
    # SQL Server ODBC 驱动名。
    parser.add_argument("--sql-driver", default="ODBC Driver 17 for SQL Server", help="pyodbc 使用的 SQL Server ODBC 驱动")
    # 调试 SQL 文件输出路径。
    parser.add_argument("--debug-sql", default="", help="可选：输出完整 SQL Server 入库脚本到指定路径")
    # 语义断点百分位。
    parser.add_argument("--breakpoint-percentile", type=float, default=90.0, help="语义距离断点百分位")
    # 本地向量维度。
    parser.add_argument("--vector-dim", type=int, default=256, help="本地向量维度")
    # 本地向量模型名。
    parser.add_argument("--vector-model", default="llamaindex-local-hash-embedding-v1", help="向量化模型名")
    # 问答成对最低相似度阈值。
    parser.add_argument("--qa-similarity-threshold", type=float, default=0.08, help="LlamaIndex SemanticSimilarityEvaluator 问答绑定最低分")
    # 每个问题最多绑定的后续答案句数量。
    parser.add_argument("--max-answer-sentences", type=int, default=6, help="每个问题最多向后绑定的答案句数量")
    # 跨文档 chunk 向量近似融合阈值。
    parser.add_argument("--fusion-similarity-threshold", type=float, default=0.92, help="跨文档 LlamaIndex embedding 近似融合阈值")
    # 2026-06-04 16:30:16 新增原因：允许从 .env 启用 Neo4j 三元组写入，满足图谱必须进入模型消费链路的要求。
    parser.add_argument("--neo4j-enabled", default=default_env.get("NEO4J_ENABLED", "0"), help="是否同步写入 Neo4j，1/true 启用")
    # 2026-06-04 16:30:16 新增原因：配置 Neo4j bolt 地址。
    parser.add_argument("--neo4j-uri", default=default_env.get("NEO4J_URI", "bolt://127.0.0.1:7687"), help="Neo4j bolt URI")
    # 2026-06-04 16:30:16 新增原因：配置 Neo4j 用户名。
    parser.add_argument("--neo4j-user", default=default_env.get("NEO4J_USER", "neo4j"), help="Neo4j 用户名")
    # 2026-06-04 16:30:16 新增原因：配置 Neo4j 密码。
    parser.add_argument("--neo4j-password", default=default_env.get("NEO4J_PASSWORD", ""), help="Neo4j 密码")
    # 2026-06-04 16:30:16 新增原因：配置 Neo4j database 名称。
    parser.add_argument("--neo4j-database", default=default_env.get("NEO4J_DATABASE", "neo4j"), help="Neo4j database")
    # 返回解析器。
    return parser
