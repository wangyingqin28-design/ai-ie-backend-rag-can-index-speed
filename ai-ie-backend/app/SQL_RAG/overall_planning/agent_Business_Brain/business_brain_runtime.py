# -*- coding: utf-8 -*-
"""LangGraph + Qwen-Agent + LlamaIndex/Qdrant + SQL/Neo4j 的业务大脑运行时。"""

# 修改日期：2026-06-02 17:42:00。
# 修改理由：按照截图第 1 点实现模型自主决策、MCP/function calling、RAG 召回和知识图谱多跳，不写死业务自动化路径。

# 导入 argparse，用于 main.py 汇总 agent 子入口参数。
import argparse
# 2026-06-05 10:09:31 新增原因：导入 asyncio，用于在 LangGraph 工具节点中同步调用 FastMCP 官方异步工具接口。
import asyncio
# 导入 JSON，用于 Qwen function calling 参数和工具结果序列化。
import json
# 导入 os，用于读取 SQL_RAG/.env 里的配置。
import os
# 导入 re，用于修复本地小模型偶发的半截 JSON function arguments。
import re
# 导入 sys，用于保证从 overall_planning 直接导入 data_cleaning 兄弟包。
import sys
# 导入 dataclass，用于定义运行配置。
from dataclasses import dataclass
# 2026-06-04 16:38:45 新增原因：导入 UTC 时间，用于公开 trace events 打时间戳。
from datetime import datetime, timezone
# 导入 Path，用于定位 SQL_RAG 根目录。
from pathlib import Path
# 导入 TypedDict 和 Any，用于 LangGraph state。
from typing import Any, TypedDict

# 导入 python-dotenv 官方加载器。
from dotenv import load_dotenv
# 导入 LangChain Core 官方消息对象，用于把 Qwen function_call 桥接到 LangGraph 状态。
from langchain_core.messages import AIMessage
# 导入 LangGraph 官方图构建 API。
from langgraph.graph import END, START, StateGraph
# 导入 LlamaIndex 官方向量索引。
from llama_index.core import VectorStoreIndex
# 导入 LlamaIndex 官方 PropertyGraphIndex。
from llama_index.core.indices.property_graph import PropertyGraphIndex, VectorContextRetriever
# 导入 LlamaIndex 官方工具包装。
from llama_index.core.tools import FunctionTool, QueryEngineTool
# 导入 LlamaIndex 官方 OpenAI-compatible embedding。
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
# 导入 LlamaIndex 官方 OpenAI-compatible LLM。
from llama_index.llms.openai_like import OpenAILike
# 导入 LlamaIndex 官方 Neo4j graph store。
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
# 导入 LlamaIndex 官方 Qdrant vector store。
from llama_index.vector_stores.qdrant import QdrantVectorStore
# 导入 Neo4j 官方驱动。
from neo4j import GraphDatabase
# 导入 pyodbc 官方 SQL Server 访问库。
import pyodbc
# 导入 Qdrant 官方客户端。
from qdrant_client import QdrantClient
# 导入 Qwen-Agent 官方 chat model 工厂。
from qwen_agent.llm import get_chat_model

# 定位当前文件所在目录。
CURRENT_DIR = Path(__file__).resolve().parent
# 定位 overall_planning 目录。
OVERALL_PLANNING_DIR = CURRENT_DIR.parent
# 定位 SQL_RAG 根目录。
SQL_RAG_DIR = OVERALL_PLANNING_DIR.parent
# 定位 data_cleaning 目录，便于复用已有 SQL Server 工具配置。
DATA_CLEANING_DIR = SQL_RAG_DIR / "data_cleaning"
# 直接导入时补充 data_cleaning 模块路径。
if str(DATA_CLEANING_DIR) not in sys.path:
    # 插入模块搜索路径最前面。
    sys.path.insert(0, str(DATA_CLEANING_DIR))
# 兼容从外层 app.SQL_RAG 包路径导入时仍能解析 overall_planning 顶层包。
if str(SQL_RAG_DIR) not in sys.path:
    # 插入 SQL_RAG 根目录。
    sys.path.insert(0, str(SQL_RAG_DIR))

# 导入纠错飞轮运行时。
from overall_planning.Answer_correction import AnswerCorrectionRuntime
# 导入三层记忆运行时。
from overall_planning.long_memory import ThreeLayerMemoryRuntime
# 导入本地可执行客服业务仓库。
from overall_planning.agent_Business_Brain.local_business_store import LocalBusinessActionStore
# 2026-06-05 10:09:31 新增原因：导入 SQL_RAG FastMCP 网关构建器，让 /chat-stream 主链真实经过 MCP 工具网关。
from overall_planning.agent_Business_Brain.mcp_gateway import build_sql_rag_mcp_gateway
# 2026-06-06 11:46:12 修改原因：导入泛化语义、证据收集和极性校验工具，最终回答可在答反时无工具重试。
from overall_planning.semantic_evidence import collect_evidence_texts, extract_semantic_terms, question_requires_semantic_agent_chain, semantic_answer_coverage, semantic_answer_evasion, semantic_answer_grounded_equivalence, semantic_answer_internal_token_leak, semantic_answer_polarity_conflict


class AgentState(TypedDict, total=False):
    # 用户 ID。
    user_id: str
    # 当前线程 ID。
    thread_id: str
    # 用户问题。
    question: str
    # Qwen 输出的草稿答案。
    draft_answer: str
    # 最终答案。
    final_answer: str
    # 最终动作：answer、clarify、transfer_human、execute。
    final_action: str
    # 当前待执行工具调用。
    pending_tool_call: dict[str, Any]
    # 已执行工具调用结果。
    tool_results: list[dict[str, Any]]
    # 证据列表。
    evidence: list[dict[str, Any]]
    # 工具调用轮次。
    tool_iterations: int
    # verifier 结果。
    verifier_result: dict[str, Any]
    # 状态 mark。
    mark: dict[str, Any]


@dataclass(frozen=True)
class BusinessBrainConfig:
    # Qdrant HTTP 地址。
    qdrant_url: str
    # Qdrant collection 名称。
    qdrant_collection: str
    # Qdrant API key，为空时访问本地 Qdrant。
    qdrant_api_key: str
    # OpenAI-compatible embedding 服务地址。
    embedding_api_base: str
    # OpenAI-compatible embedding API key。
    embedding_api_key: str
    # embedding 模型名。
    embedding_model: str
    # embedding 维度。
    embedding_dimension: int
    # RAG 召回 top_k。
    rag_top_k: int
    # Qwen-Agent 模型名。
    qwen_model: str
    # Qwen-Agent model_type，DashScope 默认 qwen_dashscope。
    qwen_model_type: str
    # Qwen-Agent OpenAI-compatible model_server。
    qwen_model_server: str
    # Qwen/DashScope API key。
    qwen_api_key: str
    # Qwen-Agent 单轮最大输出 token，避免本机 CPU 验证时长思考拖死。
    qwen_max_tokens: int
    # 2026-06-05 17:32:11 新增原因：限制 Qwen-Agent 输入 token，修复本地 llama.cpp 8192 context 被 58000 配置误导导致空答。
    qwen_max_input_tokens: int
    # Qwen-Agent 温度，客服业务脑默认低温保证稳定工具调用。
    qwen_temperature: float
    # Qwen 最大工具循环次数。
    max_tool_iterations: int
    # SQL Server 主机。
    sql_server: str
    # SQL Server 数据库。
    sql_database: str
    # SQL Server 用户。
    sql_user: str
    # SQL Server 密码。
    sql_password: str
    # SQL Server ODBC 驱动。
    sql_driver: str
    # 2026-06-04 18:03:41 新增原因：图谱后端默认走 Neo4j 多跳三元组图谱，SQL Server mention 表仅保留为未配置时的兜底。
    graph_backend: str
    # Neo4j 地址。
    neo4j_uri: str
    # Neo4j 用户。
    neo4j_user: str
    # Neo4j 密码。
    neo4j_password: str
    # Neo4j database。
    neo4j_database: str
    # 图谱路径深度。
    graph_path_depth: int


def build_agent_arg_parser() -> argparse.ArgumentParser:
    # 创建 agent 子入口解析器。
    parser = argparse.ArgumentParser(description="运行 SQL_RAG RAG Agent 客服框架。")
    # 添加问题参数。
    parser.add_argument("--question", required=True, help="用户输入的复杂业务问题。")
    # 添加用户 ID。
    parser.add_argument("--user-id", default="anonymous", help="用户 ID，用于三层记忆隔离。")
    # 添加线程 ID。
    parser.add_argument("--thread-id", default="default", help="LangGraph thread_id，用于短期工作记忆 checkpoint。")
    # 添加只跑 Qdrant 检索检查参数。
    parser.add_argument("--qdrant-check-only", action="store_true", help="只检查 LlamaIndex + Qdrant 召回，不调用 Qwen。")
    # 返回解析器。
    return parser


def _env_value(name: str, default: str = "") -> str:
    # 从环境变量读取值。
    value = os.getenv(name)
    # 有值时返回值。
    if value not in (None, ""):
        # 返回环境变量值。
        return value
    # 否则返回默认值。
    return default


def _normalize_odbc_driver(driver_name: str) -> str:
    # 把 URL 风格加号还原成空格。
    normalized = driver_name.replace("+", " ").strip()
    # 去掉外部花括号。
    return normalized.removeprefix("{").removesuffix("}")


# 2026-06-06 11:42:06 新增原因：清洗当前进程代理绕过变量，避免 httpx/openai 把 Windows no_proxy 的 IPv6 CIDR 误解析成端口。
def _sanitize_local_proxy_bypass_env() -> None:
    # 2026-06-06 11:42:06 新增原因：同时处理大小写环境变量，兼容 Windows 和 Python HTTP 客户端读取习惯。
    for env_name in ("NO_PROXY", "no_proxy"):
        # 2026-06-06 11:42:06 新增原因：读取当前进程代理绕过列表。
        raw_value = os.environ.get(env_name, "")
        # 2026-06-06 11:42:06 新增原因：拆分代理绕过项并去掉空白。
        entries = [entry.strip() for entry in raw_value.split(",") if entry.strip()]
        # 2026-06-06 11:42:06 新增原因：只移除带冒号且带斜杠的 IPv6 CIDR 项，保留普通域名和 IPv4。
        cleaned_entries = [entry for entry in entries if not (":" in entry and "/" in entry)]
        # 2026-06-06 11:42:06 新增原因：本地 SQL_RAG 服务必须绕过代理，防止 Qdrant/Embedding/Qwen 本地请求走代理解析。
        for local_entry in ("127.0.0.1", "localhost"):
            # 2026-06-06 11:42:06 新增原因：缺失本地绕过项时补齐。
            if local_entry not in cleaned_entries:
                # 2026-06-06 11:42:06 新增原因：追加本地绕过项。
                cleaned_entries.append(local_entry)
        # 2026-06-06 11:42:06 新增原因：写回当前进程环境变量，不修改系统全局配置。
        os.environ[env_name] = ",".join(cleaned_entries)


def load_business_brain_config(sql_rag_dir: Path = SQL_RAG_DIR) -> BusinessBrainConfig:
    # 固定加载 SQL_RAG/.env。
    env_path = sql_rag_dir / ".env"
    # 文件存在时加载。
    if env_path.exists():
        # 2026-06-04 17:36:58 新增原因：项目内 SQL_RAG .env 必须覆盖机器全局环境，避免旧 NEO4J_URI 把图谱链路指到错误地址。
        load_dotenv(env_path, override=True)
    # 2026-06-06 11:42:06 新增原因：配置加载后清洗本进程代理绕过变量，避免 OpenAI embedding 和 Qdrant 客户端被坏 no_proxy 影响。
    _sanitize_local_proxy_bypass_env()
    # 返回业务大脑配置。
    return BusinessBrainConfig(
        qdrant_url=_env_value("QDRANT_URL", "http://127.0.0.1:6333"),
        qdrant_collection=_env_value("QDRANT_COLLECTION", "sql_rag_qa_chunks_v1"),
        qdrant_api_key=_env_value("QDRANT_API_KEY", ""),
        embedding_api_base=_env_value("EMBEDDING_SERVICE_URL", "https://api.siliconflow.cn/v1"),
        embedding_api_key=_env_value("EMBEDDING_SERVICE_API_KEY", ""),
        embedding_model=_env_value("MODEL_EMBED", "Qwen/Qwen3-Embedding-0.6B"),
        embedding_dimension=int(_env_value("EMBEDDING_DIMENSIONS", "1024")),
        rag_top_k=int(_env_value("AGENT_RAG_TOP_K", "5")),
        qwen_model=_env_value("QWEN_AGENT_MODEL", "Qwen/Qwen3.5-35B-A3B-FP8"),
        qwen_model_type=_env_value("QWEN_AGENT_MODEL_TYPE", "qwen_dashscope"),
        qwen_model_server=_env_value("QWEN_AGENT_MODEL_SERVER", "http://127.0.0.1:8000/v1"),
        qwen_api_key=_env_value("QWEN_AGENT_API_KEY", _env_value("DASHSCOPE_API_KEY", _env_value("QWEN_API_KEY", "EMPTY"))),
        qwen_max_tokens=int(_env_value("QWEN_AGENT_MAX_TOKENS", "512")),
        # 2026-06-05 17:32:11 新增原因：默认按本地 8192 context 预留工具 schema 和输出空间，避免复杂 Prompt Builder 进模型后空答。
        qwen_max_input_tokens=int(_env_value("QWEN_AGENT_MAX_INPUT_TOKENS", "6000")),
        qwen_temperature=float(_env_value("QWEN_AGENT_TEMPERATURE", "0.1")),
        max_tool_iterations=int(_env_value("AGENT_MAX_TOOL_ITERATIONS", "8")),
        sql_server=_env_value("DB_HOST", "127.0.0.1"),
        sql_database=_env_value("DB_NAME", "getai"),
        sql_user=_env_value("DB_USER", "dev"),
        sql_password=_env_value("DB_PASSWORD", "123456"),
        sql_driver=_normalize_odbc_driver(_env_value("DB_DRIVER", "ODBC Driver 17 for SQL Server")),
        graph_backend=_env_value("AGENT_GRAPH_BACKEND", "neo4j").lower(),
        neo4j_uri=_env_value("NEO4J_URI", ""),
        neo4j_user=_env_value("NEO4J_USER", "neo4j"),
        neo4j_password=_env_value("NEO4J_PASSWORD", ""),
        neo4j_database=_env_value("NEO4J_DATABASE", "neo4j"),
        graph_path_depth=int(_env_value("AGENT_GRAPH_PATH_DEPTH", "2")),
    )


class BusinessBrainRuntime:
    # 保存配置。
    config: BusinessBrainConfig
    # 保存三层记忆运行时。
    memory_runtime: ThreeLayerMemoryRuntime
    # 保存纠错飞轮运行时。
    correction_runtime: AnswerCorrectionRuntime
    # 保存本地业务动作仓库。
    business_store: LocalBusinessActionStore
    # 保存 Qwen-Agent 官方模型实例。
    qwen_llm: Any
    # 保存 LlamaIndex 官方 embedding。
    embed_model: OpenAILikeEmbedding
    # 保存 LlamaIndex 官方 OpenAI-compatible LLM。
    llamaindex_llm: OpenAILike | None
    # 保存 LlamaIndex 工具注册表。
    tools: dict[str, FunctionTool]
    # 2026-06-05 10:09:31 新增原因：保存 FastMCP 网关实例，保证工具执行主链不绕过 MCP 标准层。
    mcp_gateway: Any
    # 保存编译后的 LangGraph。
    graph: Any

    def __init__(
        self,
        config: BusinessBrainConfig,
        memory_runtime: ThreeLayerMemoryRuntime,
        correction_runtime: AnswerCorrectionRuntime,
        require_qwen: bool = True,
    ) -> None:
        # 保存配置。
        self.config = config
        # 保存记忆运行时。
        self.memory_runtime = memory_runtime
        # 保存纠错运行时。
        self.correction_runtime = correction_runtime
        # 创建本地可执行客服业务仓库，真实落库工单、转人工、画像和跟进任务。
        self.business_store = LocalBusinessActionStore(self._sqlserver_connection_string())
        # 创建 LlamaIndex 官方 embedding。
        self.embed_model = self._build_embedding_model()
        # 创建 LlamaIndex 官方 OpenAI-compatible LLM，供 QueryEngineTool 和 PropertyGraphIndex 使用。
        self.llamaindex_llm = self._build_llamaindex_llm()
        # 创建 Qwen-Agent 官方模型。
        self.qwen_llm = self._build_qwen_llm(require_qwen=require_qwen)
        # 创建工具注册表。
        self.tools = self._build_tools()
        # 2026-06-05 10:09:31 新增原因：基于同一批 FunctionTool 构建进程内 MCP 网关，避免 /chat-stream 主链只走本地函数。
        self.mcp_gateway = self._build_in_process_mcp_gateway()
        # 编译 LangGraph Agent Runtime。
        self.graph = self._build_langgraph()

    def _build_embedding_model(self) -> OpenAILikeEmbedding:
        # 缺少 embedding key 时直接报错，避免假召回。
        if not self.config.embedding_api_key:
            # 抛出明确错误。
            raise RuntimeError("缺少 EMBEDDING_SERVICE_API_KEY，无法用 LlamaIndex 官方 embedding 查询 Qdrant。")
        # 使用 LlamaIndex 官方 OpenAILikeEmbedding，支持 Qwen/SiliconFlow 等 OpenAI-compatible 模型名。
        return OpenAILikeEmbedding(
            model_name=self.config.embedding_model,
            api_key=self.config.embedding_api_key,
            api_base=self.config.embedding_api_base,
            dimensions=self.config.embedding_dimension,
        )

    def _build_qwen_llm(self, require_qwen: bool) -> Any:
        # 只做 Qdrant 检查时允许不创建 Qwen。
        if not require_qwen:
            # 返回 None。
            return None
        # 缺少 Qwen key 时直接报错。
        if not self.config.qwen_api_key:
            # 抛出明确错误。
            raise RuntimeError("缺少 QWEN_AGENT_API_KEY/DASHSCOPE_API_KEY/QWEN_API_KEY，无法调用 Qwen3.5 function calling。")
        # OpenAI-compatible 模式优先。
        if self.config.qwen_model_server:
            # 构造 Qwen-Agent OpenAI-compatible 配置。
            llm_cfg = {
                "model": self.config.qwen_model,
                "model_server": self.config.qwen_model_server,
                "api_key": self.config.qwen_api_key,
                "generate_cfg": {
                    "fncall_prompt_type": "nous",
                    # 2026-06-05 17:32:11 修改原因：使用配置化输入上限，不再硬写 58000 造成 8192 context 本地模型空答。
                    "max_input_tokens": self.config.qwen_max_input_tokens,
                    "max_tokens": self.config.qwen_max_tokens,
                    "temperature": self.config.qwen_temperature,
                },
            }
        # 否则使用 DashScope model_type。
        else:
            # 构造 Qwen-Agent DashScope 配置。
            llm_cfg = {
                "model": self.config.qwen_model,
                "model_type": self.config.qwen_model_type,
                "api_key": self.config.qwen_api_key,
                "generate_cfg": {
                    "fncall_prompt_type": "nous",
                    # 2026-06-05 17:32:11 修改原因：DashScope/OpenAI-compatible 两条路径保持同一输入上限语义。
                    "max_input_tokens": self.config.qwen_max_input_tokens,
                    "max_tokens": self.config.qwen_max_tokens,
                    "temperature": self.config.qwen_temperature,
                },
            }
        # 使用 Qwen-Agent 官方 get_chat_model。
        return get_chat_model(llm_cfg)

    def _build_llamaindex_llm(self) -> OpenAILike | None:
        # 没有 Qwen OpenAI-compatible 服务时不创建 LlamaIndex LLM。
        if not self.config.qwen_model_server or not self.config.qwen_api_key:
            # 返回 None。
            return None
        # 使用 LlamaIndex 官方 OpenAILike 适配 Qwen3.5。
        return OpenAILike(
            model=self.config.qwen_model,
            api_key=self.config.qwen_api_key,
            api_base=self.config.qwen_model_server,
            is_chat_model=True,
            temperature=0.1,
        )

    def _build_qdrant_index(self) -> VectorStoreIndex:
        # 创建 Qdrant 官方客户端。
        # 2026-06-06 11:30:19 修改原因：禁用本进程读取系统代理环境，避免 Windows no_proxy 里的 ::1/128 被 httpx 误解析成端口。
        qdrant_client = QdrantClient(url=self.config.qdrant_url, api_key=self.config.qdrant_api_key or None, trust_env=False)
        # 创建 LlamaIndex 官方 QdrantVectorStore。
        vector_store = QdrantVectorStore(
            collection_name=self.config.qdrant_collection,
            client=qdrant_client,
            text_key="text",
        )
        # 使用 LlamaIndex 官方 VectorStoreIndex.from_vector_store。
        return VectorStoreIndex.from_vector_store(vector_store=vector_store, embed_model=self.embed_model)

    def _build_rag_tool(self) -> FunctionTool:
        # 构建 Qdrant 向量索引。
        index = self._build_qdrant_index()
        # 构建 LlamaIndex 官方 query engine，保留 QueryEngineTool 入口。
        query_engine = index.as_query_engine(similarity_top_k=self.config.rag_top_k, llm=self.llamaindex_llm)
        # 创建 LlamaIndex 官方 QueryEngineTool，供外部扩展使用。
        QueryEngineTool.from_defaults(
            query_engine=query_engine,
            name="sql_rag_query_engine",
            description="使用 LlamaIndex + Qdrant 查询 SQL_RAG canonical QA chunk。",
        )
        # 构建 LlamaIndex 官方 retriever，用于拿到 chunk_id 等 mark 证据。
        retriever = index.as_retriever(similarity_top_k=self.config.rag_top_k)

        def sql_rag_retrieve(query: str) -> dict[str, Any]:
            # 使用 LlamaIndex 官方 retriever 从 Qdrant 召回。
            retrieved_nodes = retriever.retrieve(query)
            # 整理召回结果。
            results: list[dict[str, Any]] = []
            # 遍历召回节点。
            for node_with_score in retrieved_nodes:
                # 读取节点。
                node = node_with_score.node
                # 读取 metadata。
                metadata = dict(node.metadata or {})
                # 读取默认节点正文。
                node_text = node.get_content(metadata_mode="none")
                # 优先读取 SQL_RAG v3 契约里的直接答案字段。
                answer_text = str(metadata.get("answer_text") or metadata.get("answer") or "")
                # 优先读取 LLM 消费全文，兜底用 node text。
                evidence_text = str(metadata.get("llm_text") or node_text or "")
                # 如果消费全文没有完整答案，则在工具层补成答案优先，避免后续模型只看到摘要残片。
                if answer_text and answer_text not in evidence_text:
                    evidence_text = f"标准答案：{answer_text}\n用户问题：{metadata.get('question', '')}\n证据文本：{node_text}"
                # 添加可审计证据。
                results.append(
                    {
                        "score": float(node_with_score.score or 0.0),
                        "chunk_id": metadata.get("chunk_id", metadata.get("_node_content", "")),
                        "document_id": metadata.get("document_id", ""),
                        "global_cluster_id": metadata.get("global_cluster_id", ""),
                        "scene": metadata.get("scene", ""),
                        "question": metadata.get("question", ""),
                        "answer": metadata.get("answer", ""),
                        "answer_text": answer_text,
                        "canonical_question": metadata.get("canonical_question", metadata.get("question", "")),
                        "query_aliases": metadata.get("query_aliases", []),
                        "source_excerpt_full": metadata.get("source_excerpt_full", ""),
                        "llm_text": evidence_text,
                        "rag_contract_version": metadata.get("rag_contract_version", ""),
                        "qdrant_ready": metadata.get("qdrant_ready", True),
                        "entities_json": metadata.get("entities_json", ""),
                        "text": evidence_text,
                    }
                )
            # 读取 top1 作为直答证据。
            best_hit = results[0] if results else {}
            # 返回结构化检索结果。
            return {
                "tool": "sql_rag_retrieve",
                "query": query,
                "results": results,
                "best_hit": best_hit,
                "best_answer": best_hit.get("answer_text") or best_hit.get("answer") or "",
                "source_chunk_id": best_hit.get("chunk_id", ""),
            }

        # 用 LlamaIndex 官方 FunctionTool 包装 RAG 检索函数。
        return FunctionTool.from_defaults(
            fn=sql_rag_retrieve,
            name="sql_rag_retrieve",
            description="用 LlamaIndex + Qdrant 语义召回 SQL_RAG 问答 chunk，返回 chunk_id、global_cluster_id 和证据文本。",
        )

    def _sqlserver_connection_string(self) -> str:
        # 拼接 pyodbc SQL Server 连接串。
        return (
            f"DRIVER={{{self.config.sql_driver}}};"
            f"SERVER={self.config.sql_server};"
            f"DATABASE={self.config.sql_database};"
            f"UID={self.config.sql_user};"
            f"PWD={self.config.sql_password};"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )

    def _append_trace_event(
        self,
        mark: dict[str, Any],
        event_type: str,
        title: str,
        detail: str,
        tool_name: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # 2026-06-04 16:43:06 新增原因：复制已有 mark，避免调用方引用被不可预期修改。
        next_mark = dict(mark or {})
        # 2026-06-04 16:43:06 新增原因：读取已有公开 trace events。
        existing_events = next_mark.get("public_trace_events", [])
        # 2026-06-04 16:43:06 新增原因：非列表时重置为空列表，保证前端契约稳定。
        if not isinstance(existing_events, list):
            # 2026-06-04 16:43:06 新增原因：修复异常 mark 类型。
            existing_events = []
        # 2026-06-04 16:43:06 新增原因：构造可展示、可审计、无隐藏思维链的事件。
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event_type": event_type,
            "title": title,
            "detail": detail,
            "tool_name": tool_name,
            "payload": payload or {},
        }
        # 2026-06-04 16:43:06 新增原因：追加事件并限制长度，防止长会话撑爆前端。
        next_mark["public_trace_events"] = [*existing_events, event][-80:]
        # 2026-06-04 16:43:06 新增原因：返回带事件的新 mark。
        return next_mark

    # 2026-06-05 10:19:41 新增原因：把公开 trace 按 thread_id 落盘，便于复盘截图中的每一步节点。
    def _persist_thread_runtime_event(self, thread_id: str, event: dict[str, Any]) -> None:
        # 2026-06-05 10:19:41 新增原因：清理 thread_id，避免非法文件名写出 SQL_RAG 目录。
        safe_thread_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(thread_id or "default"))[:120]
        # 2026-06-05 10:19:41 新增原因：定位 SQL_RAG 内部 runtime_logs，不触碰外层目录。
        log_dir = SQL_RAG_DIR / "runtime_logs"
        # 2026-06-05 10:19:41 新增原因：确保日志目录存在。
        log_dir.mkdir(parents=True, exist_ok=True)
        # 2026-06-05 10:19:41 新增原因：构造线程级 NDJSON 日志文件路径。
        log_path = log_dir / f"thread_{safe_thread_id}.ndjson"
        # 2026-06-05 10:19:41 新增原因：追加写入一行 JSON，便于按行追踪。
        with log_path.open("a", encoding="utf-8") as handle:
            # 2026-06-05 10:19:41 新增原因：写入无隐藏思维链的公开事件。
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    def _neo4j_path_depth(self) -> int:
        # 2026-06-04 16:43:06 新增原因：把外部配置限制在 1 到 5 跳，避免 Cypher 路径爆炸。
        return max(1, min(int(self.config.graph_path_depth or 3), 5))

    def _neo4j_path_projection(self) -> str:
        # 2026-06-04 16:43:06 新增原因：复用 Cypher 投影，保证 chunk_id 和关键词两种查询返回同一结构。
        return """
        RETURN
          [node IN nodes(path) | {
            id: node.id,
            name: node.name,
            kind: node.kind
          }] AS nodes,
          [rel IN relationships(path) | {
            triple_id: rel.triple_id,
            predicate: rel.predicate,
            chunk_id: rel.chunk_id,
            document_id: rel.document_id,
            global_cluster_id: rel.global_cluster_id,
            evidence_text: rel.evidence_text,
            properties_json: rel.properties_json,
            subject: startNode(rel).id,
            object: endNode(rel).id,
            subject_type: startNode(rel).kind,
            object_type: endNode(rel).kind
          }] AS triples
        LIMIT 80
        """

    def _neo4j_records_to_graph_payload(self, records: list[Any]) -> dict[str, list[dict[str, Any]]]:
        # 2026-06-04 16:43:06 新增原因：创建 path 列表，供前端和 Prompt Builder 展示多跳链路。
        paths: list[dict[str, Any]] = []
        # 2026-06-04 16:43:06 新增原因：创建三元组去重表。
        triples_by_id: dict[str, dict[str, Any]] = {}
        # 2026-06-04 16:43:06 新增原因：创建节点去重表。
        nodes_by_id: dict[str, dict[str, Any]] = {}
        # 2026-06-04 16:43:06 新增原因：遍历 Neo4j 返回记录。
        for record in records:
            # 2026-06-04 16:43:06 新增原因：读取路径节点。
            nodes = [dict(node) for node in (record.get("nodes") or [])]
            # 2026-06-04 16:43:06 新增原因：读取路径关系三元组。
            triples = [dict(triple) for triple in (record.get("triples") or [])]
            # 2026-06-04 16:43:06 新增原因：登记节点。
            for node in nodes:
                # 2026-06-04 16:43:06 新增原因：按节点 ID 去重。
                nodes_by_id[str(node.get("id", ""))] = node
            # 2026-06-04 16:43:06 新增原因：登记关系。
            for triple in triples:
                # 2026-06-04 16:43:06 新增原因：关系 ID 兜底用 SPO，避免旧数据缺 triple_id。
                triple_id = str(triple.get("triple_id") or f"{triple.get('subject')}|{triple.get('predicate')}|{triple.get('object')}")
                # 2026-06-04 16:43:06 新增原因：保存去重三元组。
                triples_by_id[triple_id] = triple
            # 2026-06-04 16:43:06 新增原因：构造路径文本。
            path_text = " -> ".join(str(node.get("name") or node.get("id") or "") for node in nodes if node.get("id"))
            # 2026-06-04 16:43:06 新增原因：保存单条路径。
            paths.append({"nodes": nodes, "triples": triples, "text": path_text})
        # 2026-06-04 16:43:06 新增原因：把非 chunk 节点作为实体候选。
        entities = [node for node in nodes_by_id.values() if node.get("kind") != "chunk"]
        # 2026-06-04 16:43:06 新增原因：把三元组映射成兼容前端的边结构。
        edges = [
            {
                "source": triple.get("subject", ""),
                "relation": triple.get("predicate", ""),
                "target": triple.get("object", ""),
                "chunk_id": triple.get("chunk_id", ""),
                "global_cluster_id": triple.get("global_cluster_id", ""),
            }
            for triple in triples_by_id.values()
        ]
        # 2026-06-04 16:43:06 新增原因：返回统一图谱 payload。
        return {"paths": paths, "triples": list(triples_by_id.values()), "entities": entities, "edges": edges}

    def _query_neo4j_graph(self, query: str, entity_hint: str, source_chunk_ids: list[str]) -> dict[str, Any]:
        # 2026-06-04 16:43:06 新增原因：创建 Neo4j driver，真实读取三元组多跳图谱。
        driver = GraphDatabase.driver(self.config.neo4j_uri, auth=(self.config.neo4j_user, self.config.neo4j_password))
        # 2026-06-04 16:43:06 新增原因：计算安全路径深度。
        depth = self._neo4j_path_depth()
        # 2026-06-04 16:43:06 新增原因：提取关键词，支持无 chunk_id 的实体检索。
        search_terms = self._extract_graph_search_terms(entity_hint or query)
        # 2026-06-04 16:43:06 新增原因：确保 driver 最终关闭。
        try:
            # 2026-06-04 16:43:06 新增原因：验证连通性，失败时让上层 trace 明确 Neo4j 不可用。
            driver.verify_connectivity()
            # 2026-06-04 16:43:06 新增原因：打开 Neo4j session。
            with driver.session(database=self.config.neo4j_database) as session:
                # 2026-06-04 16:43:06 新增原因：优先按 RAG chunk_id 做多跳扩展。
                if source_chunk_ids:
                    # 2026-06-04 16:43:06 新增原因：从 chunk 节点出发查多跳路径。
                    records = list(
                        session.run(
                            f"""
                            MATCH (seed:SqlRagNode)
                            WHERE seed.id IN $source_chunk_ids
                            MATCH path=(seed)-[:SQL_RAG_RELATION*1..{depth}]-(target:SqlRagNode)
                            {self._neo4j_path_projection()}
                            """,
                            source_chunk_ids=source_chunk_ids,
                        )
                    )
                    # 2026-06-04 16:43:06 新增原因：记录查询策略。
                    match_strategy = "neo4j_source_chunk_ids"
                # 2026-06-04 16:43:06 新增原因：没有 chunk_id 时按实体关键词做多跳扩展。
                else:
                    # 2026-06-04 16:43:06 新增原因：从关键词命中的节点出发查多跳路径。
                    records = list(
                        session.run(
                            f"""
                            MATCH (seed:SqlRagNode)
                            WHERE any(term IN $search_terms WHERE toLower(seed.name) CONTAINS toLower(term) OR toLower(seed.id) CONTAINS toLower(term))
                            MATCH path=(seed)-[:SQL_RAG_RELATION*1..{depth}]-(target:SqlRagNode)
                            {self._neo4j_path_projection()}
                            """,
                            search_terms=search_terms or [query],
                        )
                    )
                    # 2026-06-04 16:43:06 新增原因：记录查询策略。
                    match_strategy = "neo4j_keyword_terms"
        # 2026-06-04 16:43:06 新增原因：释放 driver。
        finally:
            # 2026-06-04 16:43:06 新增原因：关闭 Neo4j driver。
            driver.close()
        # 2026-06-04 16:43:06 新增原因：转换 Neo4j path 记录。
        graph_payload = self._neo4j_records_to_graph_payload(records)
        # 2026-06-04 16:43:06 新增原因：返回多跳图谱结果。
        return {
            "tool": "sql_rag_graph_expand",
            "status": "succeeded",
            "backend": "neo4j_triple_graph",
            "query": query,
            "entity_hint": entity_hint,
            "source_chunk_ids": source_chunk_ids,
            "search_terms": search_terms,
            "match_strategy": match_strategy,
            "path_depth": depth,
            **graph_payload,
        }

    def _build_graph_tool(self) -> FunctionTool:
        # 显式指定 Neo4j 时使用 SQL_RAG 自建三元组图谱做多跳扩展。
        if self.config.graph_backend == "neo4j" and self.config.neo4j_uri and self.config.neo4j_password:
            def sql_rag_graph_expand(query: str, entity_hint: str = "", source_chunk_ids: list[str] | None = None) -> dict[str, Any]:
                # 2026-06-04 16:47:56 新增原因：整理 chunk_id，优先从 RAG 证据节点做多跳。
                cleaned_chunk_ids = [str(chunk_id).strip() for chunk_id in (source_chunk_ids or []) if str(chunk_id).strip()]
                # 2026-06-04 16:47:56 新增原因：调用 Neo4j 三元组图谱查询。
                return self._query_neo4j_graph(
                    query=query,
                    entity_hint=entity_hint,
                    source_chunk_ids=list(dict.fromkeys(cleaned_chunk_ids))[:50],
                )
        # 未配置 Neo4j 时使用 SQL_RAG 现有 SQL Server 关系表作为起步图谱层。
        else:
            # 创建 SQL Server 关系查询工具。
            def sql_rag_graph_expand(query: str, entity_hint: str = "", source_chunk_ids: list[str] | None = None) -> dict[str, Any]:
                # 整理 RAG 召回 chunk_id，优先用它回跳关系表。
                cleaned_chunk_ids = [str(chunk_id).strip() for chunk_id in (source_chunk_ids or []) if str(chunk_id).strip()]
                # 构造去重后的 chunk_id 列表。
                deduped_chunk_ids = list(dict.fromkeys(cleaned_chunk_ids))[:50]
                # 提取查询关键词，避免长 query 整串 LIKE 命中率过低。
                search_terms = self._extract_graph_search_terms(entity_hint or query)
                # 打开 SQL Server 连接。
                with pyodbc.connect(self._sqlserver_connection_string()) as connection:
                    # 创建 cursor。
                    cursor = connection.cursor()
                    # 初始化实体行。
                    entity_rows = []
                    # 初始化校验问题行。
                    issue_rows = []
                    # 如果有 RAG 召回 chunk_id，优先直接按 chunk_id 查实体。
                    if deduped_chunk_ids:
                        # 构造参数占位符。
                        placeholders = ", ".join("?" for _ in deduped_chunk_ids)
                        # 查询召回 chunk 关联实体。
                        entity_rows = cursor.execute(
                            f"""
                            SELECT TOP 80
                                mentions.entity_type,
                                mentions.entity_value,
                                mentions.canonical_entity,
                                mentions.chunk_id,
                                chunks.question,
                                chunks.answer,
                                chunks.global_cluster_id
                            FROM dbo.rag_entity_mentions AS mentions
                            INNER JOIN dbo.rag_qa_chunks AS chunks
                                ON chunks.chunk_id = mentions.chunk_id
                            WHERE mentions.chunk_id IN ({placeholders})
                            ORDER BY chunks.document_id, chunks.chunk_index, mentions.entity_type;
                            """,
                            *deduped_chunk_ids,
                        ).fetchall()
                        # 查询召回 chunk 关联校验问题。
                        issue_rows = cursor.execute(
                            f"""
                            SELECT TOP 40 issue_type, issue_level, issue_message, chunk_id
                            FROM dbo.rag_validation_issues
                            WHERE chunk_id IN ({placeholders})
                            ORDER BY created_at DESC;
                            """,
                            *deduped_chunk_ids,
                        ).fetchall()
                    # 没有 chunk_id 命中实体时，再用关键词兜底。
                    if not entity_rows and search_terms:
                        # 构造关键词 LIKE 条件。
                        term_conditions = " OR ".join(
                            "(mentions.entity_value LIKE ? OR mentions.canonical_entity LIKE ? OR chunks.question LIKE ? OR chunks.answer LIKE ?)"
                            for _ in search_terms
                        )
                        # 构造关键词参数。
                        term_parameters = [
                            parameter
                            for term in search_terms
                            for parameter in (f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%")
                        ]
                        # 查询实体提及及其关联 chunk。
                        entity_rows = cursor.execute(
                            f"""
                            SELECT TOP 80
                                mentions.entity_type,
                                mentions.entity_value,
                                mentions.canonical_entity,
                                mentions.chunk_id,
                                chunks.question,
                                chunks.answer,
                                chunks.global_cluster_id
                            FROM dbo.rag_entity_mentions AS mentions
                            INNER JOIN dbo.rag_qa_chunks AS chunks
                                ON chunks.chunk_id = mentions.chunk_id
                            WHERE {term_conditions}
                            ORDER BY chunks.document_id, chunks.chunk_index, mentions.entity_type;
                            """,
                            *term_parameters,
                        ).fetchall()
                        # 构造校验问题 LIKE 条件。
                        issue_conditions = " OR ".join("issue_message LIKE ?" for _ in search_terms)
                        # 查询相关校验问题。
                        issue_rows = cursor.execute(
                            f"""
                            SELECT TOP 40 issue_type, issue_level, issue_message, chunk_id
                            FROM dbo.rag_validation_issues
                            WHERE {issue_conditions}
                            ORDER BY created_at DESC;
                            """,
                            *(f"%{term}%" for term in search_terms),
                        ).fetchall()
                # 整理实体。
                entities = [
                    {
                        "entity_type": row.entity_type,
                        "entity_value": row.entity_value,
                        "canonical_entity": row.canonical_entity,
                        "chunk_id": row.chunk_id,
                        "question": row.question,
                        "answer": row.answer,
                        "global_cluster_id": row.global_cluster_id,
                    }
                    for row in entity_rows
                ]
                # 整理关系边。
                edges = [
                    {
                        "source": item["canonical_entity"],
                        "relation": "MENTIONED_IN_CHUNK",
                        "target": item["chunk_id"],
                        "global_cluster_id": item["global_cluster_id"],
                    }
                    for item in entities
                ]
                # 整理校验问题。
                issues = [
                    {
                        "issue_type": row.issue_type,
                        "issue_level": row.issue_level,
                        "issue_message": row.issue_message,
                        "chunk_id": row.chunk_id,
                    }
                    for row in issue_rows
                ]
                # 返回 SQL_RAG 起步图谱结果。
                return {
                    "tool": "sql_rag_graph_expand",
                    "backend": "sqlserver_relation_tables",
                    "query": query,
                    "entity_hint": entity_hint,
                    "source_chunk_ids": deduped_chunk_ids,
                    "search_terms": search_terms,
                    "match_strategy": "source_chunk_ids" if deduped_chunk_ids else "keyword_terms",
                    "entities": entities,
                    "edges": edges,
                    "validation_issues": issues,
                }

        # 用 LlamaIndex 官方 FunctionTool 包装图谱检索。
        return FunctionTool.from_defaults(
            fn=sql_rag_graph_expand,
            name="sql_rag_graph_expand",
            # 2026-06-04 18:03:41 新增原因：FunctionTool 描述必须与真实主链一致，避免前端/模型把图谱误判为 SQL Server mention 表。
            description="用 Neo4j SQL_RAG 多跳三元组图谱做关系扩展；未配置 Neo4j 时才回退 SQL Server mention 表。",
        )

    def _build_memory_tool(self) -> FunctionTool:
        # 定义三层记忆读取工具。
        def sql_rag_memory_read(user_id: str, query: str) -> dict[str, Any]:
            # 调用三层记忆运行时。
            memory_context = self.memory_runtime.read_memory_context(user_id=user_id, query=query, limit=10)
            # 补充 SQL Server 本地持久画像记忆，保证重启后画像仍可检索。
            try:
                local_profile_memory = self.business_store.read_profile_memory(user_id=user_id, limit=10)
                memory_context["structured_profile_memory"] = [
                    *memory_context.get("structured_profile_memory", []),
                    *local_profile_memory,
                ]
            except Exception as exc:
                memory_context["structured_profile_memory_error"] = f"{type(exc).__name__}: {exc}"
            return memory_context

        # 用 LlamaIndex 官方 FunctionTool 包装记忆读取。
        return FunctionTool.from_defaults(
            fn=sql_rag_memory_read,
            name="sql_rag_memory_read",
            description="读取短期工作记忆说明、结构化画像记忆和 Graphiti 长期情景记忆。",
        )

    def _build_business_tool(self) -> FunctionTool:
        # 定义业务动作入口。
        def sql_rag_business_action(action_name: str, action_args: dict[str, Any]) -> dict[str, Any]:
            # 读取工具执行节点注入的上下文，避免模型必须自己猜 user/thread。
            safe_args = dict(action_args or {})
            context = dict(safe_args.pop("_agent_context", {}) or {})
            # 调用本地 SQL Server 客服业务仓库，真实写入工单、转人工、画像或跟进任务。
            result = self.business_store.execute_action(action_name=action_name, action_args=safe_args, context=context)
            # 画像类动作同步写入 LangGraph store/Neo4j 画像记忆，保证记忆工具下一轮可读。
            memory_event = result.get("memory_write_event") if isinstance(result, dict) else None
            if isinstance(memory_event, dict) and memory_event.get("memory_id"):
                memory_result = self.memory_runtime.write_profile_memory(
                    user_id=str(memory_event.get("user_id") or context.get("user_id") or "anonymous"),
                    key=str(memory_event.get("key") or "customer_service_preference"),
                    value=safe_args.get("value", safe_args.get("profile", safe_args.get("preference", safe_args))),
                    source_id=str(memory_event.get("source_id") or result.get("action_id") or memory_event.get("memory_id")),
                    confidence=float(memory_event.get("confidence") or 0.8),
                    expiry=str(safe_args.get("expiry", "")),
                    consent_scope=str(memory_event.get("consent_scope") or safe_args.get("consent_scope", "customer_service")),
                )
                result["langgraph_memory_write"] = memory_result
            return result

        # 用 LlamaIndex 官方 FunctionTool 包装业务动作。
        return FunctionTool.from_defaults(
            fn=sql_rag_business_action,
            name="sql_rag_business_action",
            description=(
                "执行本地智能客服业务动作并写入 SQL Server。支持 action_name："
                "create_ticket/open_ticket/complaint/return_order/exchange_order/cancel_order/change_address、"
                "transfer_human/request_human、create_followup/set_reminder、record_customer_profile/record_preference、"
                "update_ticket_status/close_ticket、query_tickets、query_profile、log_note。"
                "action_args 可包含 subject、description、reason、order_no/order_id、contact、priority、due_at、value 等。"
            ),
        )

    def _build_tools(self) -> dict[str, FunctionTool]:
        # 构建全部工具。
        tools = [
            self._build_rag_tool(),
            self._build_graph_tool(),
            self._build_memory_tool(),
            self._build_business_tool(),
        ]
        # 按工具名注册。
        return {tool.metadata.name: tool for tool in tools}

    # 2026-06-05 10:09:31 新增原因：定义直接调用 FunctionTool 的内部桥，供 MCP 网关封装时复用。
    def _call_function_tool_direct(self, tool_name: str, **tool_args: Any) -> Any:
        # 2026-06-05 10:09:31 新增原因：从统一工具注册表读取 LlamaIndex FunctionTool。
        tool = self.tools[tool_name]
        # 2026-06-05 10:09:31 新增原因：调用 FunctionTool，保持原有工具实现不重复。
        tool_output = tool.call(**tool_args)
        # 2026-06-05 10:09:31 新增原因：优先返回结构化 raw_output，避免 MCP 层丢失 RAG/Neo4j payload。
        if getattr(tool_output, "raw_output", None) is not None:
            # 2026-06-05 10:09:31 新增原因：返回原始结构化工具结果。
            return tool_output.raw_output
        # 2026-06-05 10:09:31 新增原因：兼容没有 raw_output 的 ToolOutput。
        return getattr(tool_output, "content", tool_output)

    # 2026-06-05 10:09:31 新增原因：构建进程内 FastMCP 网关，让 Agent 主链真实经过 MCP 工具标准层。
    def _build_in_process_mcp_gateway(self) -> Any:
        # 2026-06-05 10:09:31 新增原因：定义 RAG MCP 回调，内部仍复用统一 FunctionTool。
        def rag_retrieve(query: str) -> dict[str, Any]:
            # 2026-06-05 10:09:31 新增原因：通过本地工具桥执行 RAG 召回。
            return self._call_function_tool_direct("sql_rag_retrieve", query=query)

        # 2026-06-05 10:09:31 新增原因：定义 Neo4j 图谱 MCP 回调，承接 RAG 召回 chunk 做多跳。
        def graph_expand(query: str, entity_hint: str = "", source_chunk_ids: list[str] | None = None) -> dict[str, Any]:
            # 2026-06-05 10:09:31 新增原因：通过本地工具桥执行图谱扩展。
            return self._call_function_tool_direct("sql_rag_graph_expand", query=query, entity_hint=entity_hint, source_chunk_ids=source_chunk_ids or [])

        # 2026-06-05 10:09:31 新增原因：定义记忆 MCP 回调，保证短期/画像/长期记忆节点经过 MCP 层。
        def memory_read(user_id: str, query: str) -> dict[str, Any]:
            # 2026-06-05 10:09:31 新增原因：通过本地工具桥执行三层记忆读取。
            return self._call_function_tool_direct("sql_rag_memory_read", user_id=user_id, query=query)

        # 2026-06-05 10:09:31 新增原因：定义业务动作 MCP 回调，保证业务工具节点经过 MCP 层。
        def business_action(action_name: str, action_args: dict[str, Any]) -> dict[str, Any]:
            # 2026-06-05 10:09:31 新增原因：通过本地工具桥执行业务动作或只读业务审计。
            return self._call_function_tool_direct("sql_rag_business_action", action_name=action_name, action_args=action_args)

        # 2026-06-05 10:09:31 新增原因：返回 FastMCP 网关实例，不在这里启动端口，避免和 WebUI 端口冲突。
        return build_sql_rag_mcp_gateway(
            # 2026-06-05 10:09:31 新增原因：注册 RAG MCP 工具入口。
            rag_retrieve=rag_retrieve,
            # 2026-06-05 10:09:31 新增原因：注册图谱 MCP 工具入口。
            graph_expand=graph_expand,
            # 2026-06-05 10:09:31 新增原因：注册记忆 MCP 工具入口。
            memory_read=memory_read,
            # 2026-06-05 10:09:31 新增原因：注册业务 MCP 工具入口。
            business_action=business_action,
        )

    # 2026-06-05 10:09:31 新增原因：把 FastMCP 返回的 TextContent 还原成业务工具结构化结果。
    def _decode_mcp_call_result(self, mcp_result: Any) -> Any:
        # 2026-06-05 10:55:04 新增原因：FastMCP 本地 call_tool 会返回 (content_list, structured_result) 元组。
        if isinstance(mcp_result, tuple) and len(mcp_result) >= 2:
            # 2026-06-05 10:55:04 新增原因：读取第二项结构化结果，避免工具证据被误判为 non_dict_result。
            structured_result = mcp_result[1]
            # 2026-06-05 10:55:04 新增原因：结构化结果是 dict/list 时直接交给 LangGraph mark 与 Prompt Builder 消费。
            if isinstance(structured_result, (dict, list)):
                # 2026-06-05 10:55:04 新增原因：返回真实工具输出，保留 RAG、Neo4j、记忆、业务工具证据。
                return structured_result
            # 2026-06-05 10:55:04 新增原因：结构化结果非空但不是容器时也保留，避免丢失 FastMCP 输出。
            if structured_result not in (None, ""):
                # 2026-06-05 10:55:04 新增原因：兼容未来 FastMCP 返回字符串或标量结构化结果。
                return structured_result
            # 2026-06-05 10:55:04 新增原因：没有结构化结果时回退到第一项 content_list 文本解析。
            mcp_result = mcp_result[0]
        # 2026-06-05 10:09:31 新增原因：FastMCP 本地 call_tool 通常返回 content 列表。
        if isinstance(mcp_result, list) and mcp_result:
            # 2026-06-05 10:09:31 新增原因：读取第一段文本内容。
            text = getattr(mcp_result[0], "text", "")
            # 2026-06-05 10:09:31 新增原因：有文本时尝试按 JSON 结构还原。
            if text:
                # 2026-06-05 10:09:31 新增原因：解析 MCP 工具输出 JSON。
                try:
                    # 2026-06-05 10:09:31 新增原因：返回结构化结果给 LangGraph state。
                    return json.loads(text)
                # 2026-06-05 10:09:31 新增原因：非 JSON 时保留文本，避免工具输出丢失。
                except json.JSONDecodeError:
                    # 2026-06-05 10:09:31 新增原因：返回原始文本。
                    return text
        # 2026-06-05 10:09:31 新增原因：兼容未来 MCP 返回结构化对象。
        return mcp_result

    # 2026-06-05 10:09:31 新增原因：同步调用 MCP 工具，供当前同步 FastAPI/LangGraph 节点使用。
    def _call_tool_through_mcp_gateway(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        # 2026-06-05 10:09:31 新增原因：兼容测试或降级场景没有初始化 mcp_gateway 的运行时。
        if not getattr(self, "mcp_gateway", None):
            # 2026-06-05 10:09:31 新增原因：缺少 MCP 网关时回退到直接 FunctionTool，避免测试替身崩溃。
            return self._call_function_tool_direct(tool_name, **tool_args)
        # 2026-06-05 10:09:31 新增原因：构造 FastMCP 异步工具调用协程。
        coroutine = self.mcp_gateway.call_tool(tool_name, tool_args)
        # 2026-06-05 10:09:31 新增原因：在同步服务线程中执行 MCP 异步调用。
        mcp_result = asyncio.run(coroutine)
        # 2026-06-05 10:09:31 新增原因：把 MCP TextContent 解码回结构化工具结果。
        return self._decode_mcp_call_result(mcp_result)

    def _qwen_functions(self) -> list[dict[str, Any]]:
        # 创建 Qwen-Agent function schema 列表。
        functions: list[dict[str, Any]] = []
        # 遍历 LlamaIndex 官方工具。
        for tool in self.tools.values():
            # 读取工具 schema。
            schema = tool.metadata.fn_schema.model_json_schema() if tool.metadata.fn_schema else {"type": "object", "properties": {}}
            # 写入 Qwen-Agent functions。
            functions.append(
                {
                    "name": tool.metadata.name,
                    "description": tool.metadata.description,
                    "parameters": schema,
                }
            )
        # 返回 function schema。
        return functions

    def _question_has_any_keyword(self, question: str, keywords: tuple[str, ...]) -> bool:
        # 判断用户问题是否包含任一业务约束关键词。
        return any(keyword in question for keyword in keywords)

    # 2026-06-05 10:11:02 新增原因：识别 SQL_RAG 复杂业务问题，命中后第一二张截图的基础节点都必须经过。
    def _question_requires_full_agent_chain(self, question: str) -> bool:
        # 2026-06-05 10:24:36 新增原因：只有真实初始化的运行时启用完整链，避免旧轻量单元替身误触外部节点合同。
        if not getattr(self, "config", None):
            # 2026-06-05 10:24:36 新增原因：没有配置对象说明不是服务运行态，保持纯单元测试兼容。
            return False
        # 2026-06-06 11:02:18 修改原因：使用泛化问题形态和动态主题密度判断复杂业务问题，不再维护固定业务词表。
        return question_requires_semantic_agent_chain(question)

    # 2026-06-05 10:11:02 新增原因：判断是否需要 RAG 证据，复杂业务问题默认必须召回。
    def _question_requires_rag(self, question: str) -> bool:
        # 2026-06-05 10:11:02 新增原因：显式查知识库或复杂业务问题都需要 RAG。
        return self._question_requires_full_agent_chain(question) or self._question_has_any_keyword(question, ("知识库", "召回", "证据", "资料", "原因", "判断"))

    def _extract_graph_search_terms(self, text: str) -> list[str]:
        # 2026-06-05 18:10:08 修改原因：复用泛化语义抽词，不再用固定业务词表限制图谱检索范围。
        return extract_semantic_terms(text, limit=12)

    def _required_tools_for_question(self, question: str) -> list[str]:
        # 初始化按业务证据顺序排列的必需工具。
        required_tools: list[str] = []
        # 2026-06-05 10:11:02 修改原因：复杂业务问题默认必须先做 RAG，而不是只靠模型直接回答。
        if self._question_requires_rag(question):
            # 追加 RAG 工具。
            required_tools.append("sql_rag_retrieve")
        # 2026-06-05 10:11:02 修改原因：复杂业务问题 RAG 后必须补 Neo4j 多跳图谱，不能只靠“图谱/关系”字眼触发。
        if self._question_requires_full_agent_chain(question) or self._question_has_any_keyword(question, ("实体关系", "相关实体", "相关关系", "图谱", "多跳", "关系")):
            # 追加图谱工具。
            required_tools.append("sql_rag_graph_expand")
        # 2026-06-05 10:11:02 修改原因：复杂业务问题必须读取短期 checkpoint、画像记忆和长期记忆节点。
        if self._question_requires_full_agent_chain(question) or self._question_has_any_keyword(question, ("历史记忆", "记忆", "用户画像", "画像", "偏好")):
            # 追加记忆工具。
            required_tools.append("sql_rag_memory_read")
        # 用户明确要求工单、提醒、跟进、转人工或处理时，必须执行业务动作。
        if self._question_requires_full_agent_chain(question) or self._question_has_any_keyword(question, ("工单", "提醒", "跟进", "转人工", "业务处理", "处理", "创建")):
            # 追加业务动作工具。
            required_tools.append("sql_rag_business_action")
        # 返回去重后的工具顺序。
        return list(dict.fromkeys(required_tools))

    def _required_business_action_name(self, question: str) -> str:
        # 跟进和提醒是有明确副作用的待办任务，不能只用普通工单替代。
        if self._question_has_any_keyword(question, ("提醒", "跟进")):
            # 返回标准跟进动作名。
            return "create_followup"
        # 转人工诉求必须进入人工接管队列。
        if self._question_has_any_keyword(question, ("转人工", "人工接管", "人工处理")):
            # 返回标准转人工动作名。
            return "transfer_human"
        # 2026-06-05 10:12:44 新增原因：明确创建工单诉求时才创建工单，避免普通问答被审计节点误建工单。
        if self._question_has_any_keyword(question, ("创建工单", "开工单", "新建工单")):
            # 2026-06-05 10:12:44 新增原因：返回标准工单创建动作名。
            return "create_ticket"
        # 2026-06-05 10:12:44 新增原因：复杂业务问答默认用只读业务审计节点，不制造无关副作用。
        if self._question_requires_full_agent_chain(question):
            # 2026-06-05 17:32:11 修改原因：返回结构化业务上下文查询，修复 query_tickets 只查客服工单导致业务证据形式过场。
            return "query_business_context"
        # 其他业务处理不限定具体动作，由模型或协议守卫选择。
        return ""

    def _business_action_succeeded(self, state: AgentState, required_action_name: str = "") -> bool:
        # 遍历本轮已经执行过的业务工具结果。
        for tool_result in state.get("tool_results", []):
            # 跳过非业务工具。
            if tool_result.get("tool_name") != "sql_rag_business_action":
                # 继续检查下一个工具结果。
                continue
            # 读取工具结果。
            result = tool_result.get("result", {})
            # 非字典结果不算业务成功。
            if not isinstance(result, dict):
                # 继续检查下一个工具结果。
                continue
            # 只有真实 succeeded 才能证明业务侧写入成功。
            if result.get("status") != "succeeded":
                # 继续检查下一个工具结果。
                continue
            # 未限定具体动作时，任意成功业务动作都算满足。
            if not required_action_name:
                # 返回成功。
                return True
            # 读取业务仓库归一化后的动作名。
            actual_action_name = str(result.get("action_name", ""))
            # 读取原始动作名，兼容 set_reminder 等别名。
            original_action_name = str(result.get("original_action_name", ""))
            # 2026-06-05 18:10:08 修改原因：query_business_context 必须带动态业务上下文，防止任何业务问题只用 succeeded 形式过场。
            has_business_context = bool(result.get("focus_terms") or result.get("business_context") or result.get("best_answer"))
            # 2026-06-05 18:10:08 修改原因：当要求只读业务上下文时，空上下文不能算业务证据已满足。
            if required_action_name == "query_business_context" and actual_action_name == "query_business_context" and not has_business_context:
                # 2026-06-05 18:10:08 修改原因：继续寻找带真实上下文的业务工具结果，避免误判完整链已完成。
                continue
            # 具体动作命中时才算满足。
            if required_action_name in {actual_action_name, original_action_name}:
                # 返回成功。
                return True
        # 没有找到满足要求的业务动作。
        return False

    def _business_action_satisfied_for_question(self, state: AgentState) -> bool:
        # 根据用户问题判断本轮业务动作是否已经满足协议要求。
        return self._business_action_succeeded(
            state=state,
            required_action_name=self._required_business_action_name(state.get("question", "")),
        )

    def _tool_call_succeeded(self, state: AgentState, tool_name: str) -> bool:
        # 遍历已经执行的工具结果。
        for tool_result in state.get("tool_results", []):
            # 跳过其他工具。
            if tool_result.get("tool_name") != tool_name:
                # 继续检查下一个工具结果。
                continue
            # 读取工具结果。
            result = tool_result.get("result", {})
            # 明确 error 状态不算成功。
            if isinstance(result, dict) and result.get("status") == "error":
                # 继续查找是否有后续成功调用。
                continue
            # 业务动作必须真正 succeeded。
            if tool_name == "sql_rag_business_action":
                # 按用户问题要求的具体业务动作判断是否满足。
                return self._business_action_satisfied_for_question(state)
            # 非业务工具只要没有 error 就算完成，空图谱也是可审计结果。
            return True
        # 没有找到成功工具调用。
        return False

    def _build_required_tool_call(self, state: AgentState, tool_name: str) -> dict[str, Any]:
        # 读取用户问题。
        question = state.get("question", "")
        # RAG 工具使用原始问题作为查询，保证不丢上下文。
        if tool_name == "sql_rag_retrieve":
            # 返回 RAG 工具调用。
            return {"name": tool_name, "args": {"query": question}}
        # 记忆工具用运行时 user_id，避免模型伪造用户 ID。
        if tool_name == "sql_rag_memory_read":
            # 返回记忆工具调用。
            return {"name": tool_name, "args": {"user_id": state.get("user_id", "anonymous"), "query": question}}
        # 图谱工具用原始问题作为 query 和 entity_hint。
        if tool_name == "sql_rag_graph_expand":
            # 返回图谱工具调用。
            return {
                "name": tool_name,
                "args": {
                    "query": question,
                    "entity_hint": question,
                    "source_chunk_ids": self.correction_runtime.normalize_mark(state.get("mark")).get("retrieved_chunk_ids", []),
                },
            }
        # 用户明确要求跟进、提醒或工单时，协议守卫可构造标准跟进动作。
        if tool_name == "sql_rag_business_action":
            # 返回业务动作工具调用。
            # 2026-06-05 10:12:44 新增原因：先读取当前问题需要的具体业务动作。
            required_action_name = self._required_business_action_name(question)
            # 2026-06-05 17:32:11 新增原因：普通复杂业务问答默认查询结构化业务上下文，不再只查客服工单。
            if required_action_name == "query_business_context":
                # 2026-06-05 17:32:11 新增原因：返回 query_business_context，不制造副作用但给 Prompt Builder 真实业务字段。
                return {
                    # 2026-06-05 17:32:11 新增原因：声明工具名。
                    "name": tool_name,
                    # 2026-06-05 17:32:11 新增原因：声明只读业务上下文查询参数。
                    "args": {
                        # 2026-06-05 17:32:11 新增原因：选择业务上下文查询动作，避免 query_tickets 成功被误当业务佐证。
                        "action_name": "query_business_context",
                        # 2026-06-06 11:02:18 修改原因：传递原问题，执行层据此抽取当前问题和 RAG 证据里的动态业务字段。
                        "action_args": {
                            # 2026-06-05 17:32:11 新增原因：保留问题原文，便于业务工具做只读语义归档。
                            "question": question,
                            # 2026-06-05 18:10:08 新增原因：传入 RAG top1，业务工具按当前证据动态抽主题，不再靠固定业务词分类。
                            "best_answer": self.correction_runtime.normalize_mark(state.get("mark")).get("best_answer", ""),
                            # 2026-06-05 17:32:11 新增原因：写入 RAG chunk，业务上下文可以回指证据来源。
                            "retrieved_chunk_ids": self.correction_runtime.normalize_mark(state.get("mark")).get("retrieved_chunk_ids", []),
                            # 2026-06-05 17:32:11 新增原因：标记只读模式，防止查询型业务节点产生副作用。
                            "audit_only": True,
                        },
                    },
                }
            # 2026-06-05 10:12:44 新增原因：转人工诉求必须执行标准 transfer_human。
            if required_action_name == "transfer_human":
                # 2026-06-05 10:12:44 新增原因：返回转人工业务动作参数。
                return {
                    # 2026-06-05 10:12:44 新增原因：声明工具名。
                    "name": tool_name,
                    # 2026-06-05 10:12:44 新增原因：声明转人工参数。
                    "args": {
                        # 2026-06-05 10:12:44 新增原因：选择转人工动作。
                        "action_name": "transfer_human",
                        # 2026-06-05 10:12:44 新增原因：传递转人工原因和优先级。
                        "action_args": {"subject": "客户请求人工处理", "reason": question, "priority": "high"},
                    },
                }
            # 2026-06-05 10:12:44 新增原因：创建工单诉求必须执行标准 create_ticket。
            if required_action_name == "create_ticket":
                # 2026-06-05 10:12:44 新增原因：返回创建工单业务动作参数。
                return {
                    # 2026-06-05 10:12:44 新增原因：声明工具名。
                    "name": tool_name,
                    # 2026-06-05 10:12:44 新增原因：声明创建工单参数。
                    "args": {
                        # 2026-06-05 10:12:44 新增原因：选择创建工单动作。
                        "action_name": "create_ticket",
                        # 2026-06-05 10:12:44 新增原因：传递工单主题和描述。
                        "action_args": {"subject": "客户业务请求", "description": question, "priority": "normal"},
                    },
                }
            # 2026-06-05 10:12:44 新增原因：跟进/提醒沿用标准 create_followup 逻辑。
            return {
                "name": tool_name,
                "args": {
                    "action_name": "create_followup",
                    "action_args": {
                        "subject": "客户业务问题跟进",
                        "description": question,
                        "reason": question,
                        "contact": "业务人员",
                        "priority": "high",
                        "channel": "agent_task",
                        "message": "请业务人员根据 SQL_RAG 召回证据和图谱/记忆检查结果跟进处理。",
                    },
                },
            }
        # 其他工具不由协议守卫自动构造。
        return {}

    def _next_missing_required_evidence_tool(self, state: AgentState) -> dict[str, Any]:
        # 读取用户显式要求的工具。
        required_tools = self._required_tools_for_question(state.get("question", ""))
        # 2026-06-05 10:21:06 修改原因：证据工具顺序必须符合截图主链：RAG 先召回，Neo4j 再多跳，Memory 再补上下文。
        for tool_name in ("sql_rag_retrieve", "sql_rag_graph_expand", "sql_rag_memory_read"):
            # 未被用户要求的工具跳过。
            if tool_name not in required_tools:
                # 继续检查下一个工具。
                continue
            # 已成功调用则跳过。
            if self._tool_call_succeeded(state, tool_name):
                # 继续检查下一个工具。
                continue
            # 返回缺失工具调用。
            return self._build_required_tool_call(state, tool_name)
        # 没有缺失证据工具。
        return {}

    def _next_missing_required_tool(self, state: AgentState) -> dict[str, Any]:
        # 优先补齐证据类工具。
        evidence_tool_call = self._next_missing_required_evidence_tool(state)
        # 有证据工具缺失时直接返回。
        if evidence_tool_call:
            # 返回证据工具调用。
            return evidence_tool_call
        # 读取用户显式要求的工具。
        required_tools = self._required_tools_for_question(state.get("question", ""))
        # 用户要求业务处理且尚未成功执行时，补标准业务动作。
        if "sql_rag_business_action" in required_tools and not self._tool_call_succeeded(state, "sql_rag_business_action"):
            # 返回业务动作工具调用。
            return self._build_required_tool_call(state, "sql_rag_business_action")
        # 没有缺失工具。
        return {}

    def _truncate_for_prompt(self, value: Any, max_chars: int = 600) -> str:
        # 2026-06-04 18:21:37 新增原因：统一限制喂给本地 Qwen 的证据长度，避免 8192 context 被单个工具 payload 撑爆。
        text = str(value or "").strip()
        # 2026-06-04 18:21:37 新增原因：短文本直接返回，保留原始证据表达。
        if len(text) <= max_chars:
            # 2026-06-04 18:21:37 新增原因：返回未截断文本。
            return text
        # 2026-06-04 18:21:37 新增原因：长文本保留前段并显式标注已截断，避免模型误以为证据完整。
        return f"{text[:max_chars]}...（已截断）"

    def _format_rag_context_for_prompt(self, result: dict[str, Any]) -> list[str]:
        # 2026-06-04 16:52:28 新增原因：初始化 RAG 上下文行。
        lines: list[str] = []
        # 2026-06-04 16:52:28 新增原因：读取 RAG top1 直答证据。
        best_answer = str(result.get("best_answer") or "")
        # 2026-06-04 16:52:28 新增原因：top1 答案存在时写入 Prompt Builder。
        if best_answer:
            # 2026-06-04 16:52:28 新增原因：明确这是证据，不是最终直出。
            lines.append(f"- RAG top1 标准答案证据：{self._truncate_for_prompt(best_answer, 500)}")
        # 2026-06-04 16:52:28 新增原因：遍历召回结果，给模型完整证据片段。
        for item in (result.get("results", []) or [])[:3]:
            # 2026-06-04 16:52:28 新增原因：跳过非字典召回项。
            if not isinstance(item, dict):
                # 2026-06-04 16:52:28 新增原因：继续下一个召回项。
                continue
            # 2026-06-04 16:52:28 新增原因：读取 chunk ID。
            chunk_id = str(item.get("chunk_id", ""))
            # 2026-06-04 16:52:28 新增原因：读取证据文本。
            evidence_text = str(item.get("llm_text") or item.get("text") or item.get("answer_text") or item.get("answer") or "")
            # 2026-06-04 16:52:28 新增原因：截断长文本，避免本地模型上下文被单条证据撑满。
            evidence_text = self._truncate_for_prompt(evidence_text, 500)
            # 2026-06-04 16:52:28 新增原因：写入 RAG chunk 摘要。
            lines.append(f"- chunk={chunk_id} evidence={evidence_text}")
        # 2026-06-04 16:52:28 新增原因：返回 RAG 上下文行。
        return lines

    # 2026-06-05 17:32:11 新增原因：过滤图谱内部节点 ID，避免 qachunk/qaglobal 泄漏到模型最终回答。
    def _sanitize_graph_prompt_text(self, value: Any) -> str:
        # 2026-06-05 17:32:11 新增原因：把任意值转成字符串，兼容 Neo4j 属性和 SQL fallback 字段。
        text = str(value or "").strip()
        # 2026-06-05 17:32:11 新增原因：隐藏内部 chunk/global ID，只保留“证据节点”语义。
        text = re.sub(r"qa(?:chunk|global)_[A-Za-z0-9_\\-]+", "内部证据节点", text)
        # 2026-06-05 17:32:11 新增原因：隐藏内部关系名，避免最终答案出现 MENTIONED_IN_CHUNK 等调试词。
        text = text.replace("MENTIONED_IN_CHUNK", "证据提及")
        # 2026-06-05 17:32:11 新增原因：隐藏聚类关系名，避免用户看到 CHUNK_IN_GLOBAL_CLUSTER。
        text = text.replace("CHUNK_IN_GLOBAL_CLUSTER", "证据聚类")
        # 2026-06-05 17:32:11 新增原因：隐藏融合关系名，避免用户看到 FUSED_INTO。
        text = text.replace("FUSED_INTO", "证据融合")
        # 2026-06-05 17:32:11 新增原因：返回可给模型消费的干净文本。
        return text

    # 2026-06-05 17:32:11 新增原因：识别 Neo4j 内部结构关系，最终答案不应直接暴露这些 raw triple。
    def _is_internal_graph_relation(self, subject: str, predicate: str, obj: str) -> bool:
        # 2026-06-05 17:32:11 新增原因：内部谓词用于定位证据，不属于业务语义关系。
        if predicate in {"MENTIONED_IN_CHUNK", "CHUNK_IN_GLOBAL_CLUSTER", "FUSED_INTO"}:
            # 2026-06-05 17:32:11 新增原因：返回内部关系标记。
            return True
        # 2026-06-05 17:32:11 新增原因：内部节点 ID 不应进入最终模型语言。
        return any(value.startswith(("qachunk_", "qaglobal_")) for value in (subject, obj))

    # 2026-06-05 17:32:11 新增原因：按用户问题和 RAG top1 对图谱证据排序，修复只取前几条导致相关关系被截断。
    def _graph_relevance_score(self, item: dict[str, Any], ranking_terms: list[str]) -> int:
        # 2026-06-05 17:32:11 新增原因：拼接三元组和证据文本，作为相关性匹配语料。
        text = " ".join(str(item.get(key, "")) for key in ("subject", "predicate", "object", "evidence_text", "text"))
        # 2026-06-05 17:32:11 新增原因：每命中一个问题/RAG 关键词增加权重。
        score = sum(8 for term in ranking_terms if term and term in text)
        # 2026-06-05 17:32:11 新增原因：带业务证据文本的图谱关系优先喂给模型。
        score += 3 if str(item.get("evidence_text") or item.get("text") or "").strip() else 0
        # 2026-06-05 17:32:11 新增原因：内部定位关系降权，避免挤掉业务语义关系。
        score -= 6 if self._is_internal_graph_relation(str(item.get("subject", "")), str(item.get("predicate", "")), str(item.get("object", ""))) else 0
        # 2026-06-05 17:32:11 新增原因：返回排序分数。
        return score

    # 2026-06-05 17:32:11 新增原因：把单条图谱记录转成业务语义行，内部关系只在有证据文本时作为摘要使用。
    def _semantic_graph_line(self, item: dict[str, Any], internal_relation_names: set[str]) -> str:
        # 2026-06-05 17:32:11 新增原因：读取原始主语。
        raw_subject = str(item.get("subject", item.get("source", "")))
        # 2026-06-05 17:32:11 新增原因：读取原始谓词或边关系。
        raw_predicate = str(item.get("predicate", item.get("relation", "")))
        # 2026-06-05 17:32:11 新增原因：读取原始宾语。
        raw_object = str(item.get("object", item.get("target", "")))
        # 2026-06-05 17:32:11 新增原因：读取证据文本，内部关系优先转摘要。
        evidence_text = self._sanitize_graph_prompt_text(item.get("evidence_text") or item.get("text") or "")
        # 2026-06-05 17:32:11 新增原因：内部关系没有业务证据文本时不进入模型上下文。
        if self._is_internal_graph_relation(raw_subject, raw_predicate, raw_object) and not evidence_text:
            # 2026-06-05 17:32:11 新增原因：返回空行表示跳过 raw triple。
            return ""
        # 2026-06-05 17:32:11 新增原因：内部关系有证据文本时仅输出证据摘要，不输出 qachunk 或内部谓词。
        if self._is_internal_graph_relation(raw_subject, raw_predicate, raw_object):
            # 2026-06-05 17:32:11 新增原因：输出干净证据摘要。
            return f"- 图谱证据摘要：{self._truncate_for_prompt(evidence_text, 220)}"
        # 2026-06-05 17:32:11 新增原因：清洗主语，防止内部 ID 混入。
        subject = self._sanitize_graph_prompt_text(raw_subject)
        # 2026-06-05 17:32:11 新增原因：清洗谓词，防止内部关系名混入。
        predicate = self._sanitize_graph_prompt_text(raw_predicate)
        # 2026-06-05 17:32:11 新增原因：清洗宾语，防止内部 ID 混入。
        obj = self._sanitize_graph_prompt_text(raw_object)
        # 2026-06-05 17:32:11 新增原因：没有完整业务三元组时跳过。
        if not subject or not predicate or not obj:
            # 2026-06-05 17:32:11 新增原因：返回空行表示不可消费。
            return ""
        # 2026-06-05 17:32:11 新增原因：记录内部关系名，避免未来误把内部谓词直接放出。
        internal_relation_names.update({"MENTIONED_IN_CHUNK", "CHUNK_IN_GLOBAL_CLUSTER", "FUSED_INTO"})
        # 2026-06-05 18:10:08 修改原因：保留可读业务三元组合同格式，同时仍过滤内部 qachunk 和内部边名。
        line = f"- 业务关系：{subject} -[{predicate}]-> {obj}"
        # 2026-06-05 17:32:11 新增原因：有证据文本时补充摘要，增强模型依据。
        if evidence_text:
            # 2026-06-05 17:32:11 新增原因：追加截断后的证据说明。
            line = f"{line}；证据：{self._truncate_for_prompt(evidence_text, 180)}"
        # 2026-06-05 17:32:11 新增原因：返回模型可消费图谱行。
        return line

    def _format_graph_context_for_prompt(self, result: dict[str, Any], question: str = "", best_answer: str = "") -> list[str]:
        # 2026-06-04 16:52:28 新增原因：初始化图谱上下文行。
        lines: list[str] = []
        # 2026-06-04 16:52:28 新增原因：写入图谱后端和匹配策略。
        lines.append(f"- 图谱后端：{result.get('backend', 'unknown')}，策略：{result.get('match_strategy', 'unknown')}")
        # 2026-06-05 17:32:11 新增原因：用用户问题和 RAG top1 共同生成排序词，修复图谱前几条不相关问题。
        ranking_terms = self._extract_graph_search_terms(f"{question} {best_answer}")
        # 2026-06-05 17:32:11 新增原因：读取 Neo4j triples 并过滤非字典项。
        triples = [item for item in (result.get("triples", []) or []) if isinstance(item, dict)]
        # 2026-06-05 17:32:11 新增原因：读取 SQL fallback edges 并规范成统一结构。
        edge_items = [
            # 2026-06-05 17:32:11 新增原因：把 edge 字段映射为三元组字段，复用同一格式化逻辑。
            {"subject": edge.get("source", ""), "predicate": edge.get("relation", ""), "object": edge.get("target", ""), "evidence_text": edge.get("evidence_text", "")}
            # 2026-06-05 17:32:11 新增原因：遍历旧边列表。
            for edge in (result.get("edges", []) or [])
            # 2026-06-05 17:32:11 新增原因：只接受字典边。
            if isinstance(edge, dict)
        ]
        # 2026-06-05 17:32:11 新增原因：合并 Neo4j 和 SQL fallback 关系候选。
        candidates = triples + edge_items
        # 2026-06-05 17:32:11 新增原因：按相关性降序排序，避免截掉真正相关的业务关系。
        ranked_candidates = sorted(candidates, key=lambda item: self._graph_relevance_score(item, ranking_terms), reverse=True)
        # 2026-06-05 17:32:11 新增原因：初始化去重集合，防止同一关系重复喂给模型。
        seen_lines: set[str] = set()
        # 2026-06-05 17:32:11 新增原因：记录内部关系名集合，确保不会直接泄漏。
        internal_relation_names: set[str] = set()
        # 2026-06-05 17:32:11 新增原因：遍历排序后的前 12 条候选，再取最多 6 条业务摘要。
        for item in ranked_candidates[:12]:
            # 2026-06-05 17:32:11 新增原因：转成语义摘要行。
            line = self._semantic_graph_line(item, internal_relation_names)
            # 2026-06-05 17:32:11 新增原因：空行或重复行跳过。
            if not line or line in seen_lines:
                # 2026-06-05 17:32:11 新增原因：继续下一个候选关系。
                continue
            # 2026-06-05 17:32:11 新增原因：写入图谱语义摘要。
            lines.append(line)
            # 2026-06-05 17:32:11 新增原因：记录已输出行。
            seen_lines.add(line)
            # 2026-06-05 17:32:11 新增原因：最多输出 6 条，控制本地模型上下文长度。
            if len(seen_lines) >= 6:
                # 2026-06-05 17:32:11 新增原因：达到上限后停止。
                break
        # 2026-06-05 17:32:11 新增原因：遍历路径摘要，但先清洗内部 ID 和内部关系。
        for path in (result.get("paths", []) or [])[:3]:
            # 2026-06-04 16:52:28 新增原因：跳过非字典路径。
            if not isinstance(path, dict):
                # 2026-06-04 16:52:28 新增原因：继续下一个路径。
                continue
            # 2026-06-04 16:52:28 新增原因：读取路径文本。
            path_text = self._sanitize_graph_prompt_text(path.get("text", ""))
            # 2026-06-04 16:52:28 新增原因：路径文本存在时写入上下文。
            if path_text:
                # 2026-06-04 16:52:28 新增原因：写入多跳路径。
                lines.append(f"- 多跳路径摘要：{self._truncate_for_prompt(path_text, 300)}")
        # 2026-06-05 17:32:11 新增原因：没有业务语义行时说明图谱仅用于定位，不把 raw triple 混进最终答案。
        if len(lines) == 1:
            # 2026-06-05 17:32:11 新增原因：写入安全提示，避免模型编造不存在的图谱关系。
            lines.append("- 图谱只返回内部定位链路，已用于证据对齐；当前无可直接表述的业务关系。")
        # 2026-06-04 16:52:28 新增原因：返回图谱上下文行。
        return lines

    def _format_memory_context_for_prompt(self, result: dict[str, Any]) -> list[str]:
        # 2026-06-04 16:52:28 新增原因：初始化记忆上下文行。
        lines: list[str] = []
        # 2026-06-04 16:52:28 新增原因：读取结构化画像记忆。
        profile_memory = result.get("structured_profile_memory", []) or []
        # 2026-06-04 16:52:28 新增原因：写入画像记忆数量。
        lines.append(f"- 画像记忆：{len(profile_memory)} 条")
        # 2026-06-04 16:52:28 新增原因：读取情景记忆。
        episodic_memory = result.get("long_term_episodic_memory", []) or []
        # 2026-06-04 16:52:28 新增原因：写入情景记忆数量。
        lines.append(f"- 长期情景记忆：{len(episodic_memory)} 条")
        # 2026-06-04 16:52:28 新增原因：返回记忆上下文行。
        return lines

    def _format_business_context_for_prompt(self, result: dict[str, Any]) -> list[str]:
        # 2026-06-04 16:52:28 新增原因：初始化业务动作上下文行。
        lines: list[str] = []
        # 2026-06-04 16:52:28 新增原因：写入动作名和状态。
        lines.append(f"- 业务动作：{result.get('action_name', '')}，状态：{result.get('status', '')}")
        # 2026-06-05 17:32:11 新增原因：业务上下文查询必须写入意图，避免 query_tickets succeeded 被误当真实业务证据。
        if result.get("business_intent"):
            # 2026-06-05 17:32:11 新增原因：写入业务意图供模型判断回答形态。
            lines.append(f"- 业务意图：{result.get('business_intent')}")
        # 2026-06-05 17:32:11 新增原因：业务关注字段必须进入 Prompt Builder，Verifier 才能检查答案覆盖。
        if result.get("focus_terms"):
            # 2026-06-05 17:32:11 新增原因：写入去重后的字段列表。
            lines.append(f"- 关注字段：{'、'.join(str(term) for term in result.get('focus_terms', []) if term)}")
        # 2026-06-05 18:10:08 新增原因：业务上下文必须展示 RAG 证据锚点，避免模型只看到工具成功而看不到当前 chunk 语义。
        if result.get("best_answer"):
            # 2026-06-05 18:10:08 新增原因：限制锚点长度，避免 Prompt Builder 超过本地模型上下文。
            lines.append(f"- RAG证据锚点：{self._truncate_for_prompt(result.get('best_answer'), 220)}")
        # 2026-06-05 17:32:11 新增原因：写入结构化业务摘要，不再只展示动作成功。
        for item in (result.get("business_context", []) or [])[:5]:
            # 2026-06-05 17:32:11 新增原因：跳过空摘要项。
            if not item:
                # 2026-06-05 17:32:11 新增原因：继续下一个业务摘要。
                continue
            # 2026-06-05 17:32:11 新增原因：写入业务字段证据。
            lines.append(f"- 业务证据：{self._truncate_for_prompt(item, 220)}")
        # 2026-06-04 16:52:28 新增原因：有工单 ID 时写入。
        if result.get("ticket_id"):
            # 2026-06-04 16:52:28 新增原因：写入工单 ID。
            lines.append(f"- 工单 ID：{result.get('ticket_id')}")
        # 2026-06-04 16:52:28 新增原因：有转人工 ID 时写入。
        if result.get("handoff_id"):
            # 2026-06-04 16:52:28 新增原因：写入转人工 ID。
            lines.append(f"- 转人工 ID：{result.get('handoff_id')}")
        # 2026-06-04 16:52:28 新增原因：有跟进 ID 时写入。
        if result.get("followup_id"):
            # 2026-06-04 16:52:28 新增原因：写入跟进 ID。
            lines.append(f"- 跟进 ID：{result.get('followup_id')}")
        # 2026-06-04 16:52:28 新增原因：返回业务上下文行。
        return lines

    def _build_prompt_builder_context(self, state: AgentState) -> str:
        # 2026-06-04 16:52:28 新增原因：初始化 Prompt Builder 分区。
        sections: list[str] = ["Prompt Builder 证据上下文（给模型组织语言使用，不允许直接硬覆盖最终答案）："]
        # 2026-06-04 16:52:28 新增原因：遍历工具结果，按工具类型整理成可消费上下文。
        for tool_result in state.get("tool_results", []):
            # 2026-06-04 16:52:28 新增原因：读取工具名。
            tool_name = str(tool_result.get("tool_name", ""))
            # 2026-06-04 16:52:28 新增原因：读取工具结果。
            result = tool_result.get("result", {})
            # 2026-06-04 16:52:28 新增原因：非字典工具结果转成文本行。
            if not isinstance(result, dict):
                # 2026-06-04 16:52:28 新增原因：写入原始工具结果摘要。
                sections.append(f"\n[{tool_name}]\n- {str(result)[:1000]}")
                # 2026-06-04 16:52:28 新增原因：继续下一个工具。
                continue
            # 2026-06-04 16:52:28 新增原因：RAG 工具按证据片段整理。
            if tool_name == "sql_rag_retrieve":
                # 2026-06-04 16:52:28 新增原因：写入 RAG 分区。
                sections.append("\n[RAG / Qdrant / LlamaIndex]\n" + "\n".join(self._format_rag_context_for_prompt(result)))
            # 2026-06-04 16:52:28 新增原因：图谱工具按三元组和路径整理。
            elif tool_name == "sql_rag_graph_expand":
                # 2026-06-04 16:52:28 新增原因：写入图谱分区。
                sections.append("\n[Neo4j 多跳三元组图谱]\n" + "\n".join(self._format_graph_context_for_prompt(result, question=state.get("question", ""), best_answer=self.correction_runtime.normalize_mark(state.get("mark")).get("best_answer", ""))))
            # 2026-06-04 16:52:28 新增原因：记忆工具按记忆计数整理。
            elif tool_name == "sql_rag_memory_read":
                # 2026-06-04 16:52:28 新增原因：写入记忆分区。
                sections.append("\n[三层记忆]\n" + "\n".join(self._format_memory_context_for_prompt(result)))
            # 2026-06-04 16:52:28 新增原因：业务工具按动作结果整理。
            elif tool_name == "sql_rag_business_action":
                # 2026-06-04 16:52:28 新增原因：写入业务动作分区。
                sections.append("\n[业务动作]\n" + "\n".join(self._format_business_context_for_prompt(result)))
            # 2026-06-04 16:52:28 新增原因：其他工具保留 JSON 摘要。
            else:
                # 2026-06-04 16:52:28 新增原因：写入未知工具分区。
                sections.append(f"\n[{tool_name}]\n- {json.dumps(result, ensure_ascii=False, default=str)[:1200]}")
        # 2026-06-04 16:52:28 新增原因：没有工具结果时明确告知模型证据为空。
        if len(sections) == 1:
            # 2026-06-04 16:52:28 新增原因：写入空证据说明。
            sections.append("\n[当前证据]\n- 尚未调用工具，请根据 functions 自主决定下一步，证据不足不要直接下结论。")
        # 2026-06-06 10:59:53 修改原因：最终回答约束改为通用证据消费合同，任意业务 chunk 都必须按 top1 事实方向组织答案。
        answer_constraints = [
            # 2026-06-06 10:59:53 新增原因：要求模型用证据组织自然语言，避免 renderer 硬覆盖和隐藏推理链泄露。
            "- 用以上证据组织自然语言结论；不要暴露隐藏思维链；证据不足时澄清或转人工；不要把 best_answer 原样当作 renderer 硬覆盖。",
            # 2026-06-06 10:59:53 新增原因：锁定 RAG top1 标准答案的事实方向，防止模型把已完成/可操作改写成相反状态。
            "- 必须以 RAG top1 标准答案证据的事实方向为准，不得改写成相反结论或无依据的新业务状态。",
            # 2026-06-06 10:59:53 新增原因：要求模型覆盖用户问题里的对象、动作、条件和状态，避免只泛泛复述工具经过。
            "- 最终答案必须覆盖用户问题里的核心业务对象、动作、条件和状态，并说明这些点与证据之间的关系。",
            # 2026-06-06 10:59:53 新增原因：是/否型、步骤型、原因型问题分别约束回答形态，适配任意业务场景而非固定模板。
            "- 是/否问题第一句必须先回答“是”或“不是”；操作步骤问题必须列步骤；原因关系问题必须先给结论再解释依据。",
            # 2026-06-06 11:24:38 新增原因：把是/否问题的极性绑定到 top1 证据，防止肯定证据被答成否定或反过来。
            "- 肯定或否定方向必须跟 RAG top1 标准答案一致；top1 表达“可以/应该/需要”时第一句用肯定结论，top1 表达“不需要/不能/无法”时第一句用否定结论。",
            # 2026-06-06 11:38:19 新增原因：最终用户答案只说业务依据，不暴露内部链路名，保证语言自然可读。
            "- 最终用户答案不要输出 Prompt Builder、RAG top1、Neo4j、Qdrant、LlamaIndex 这类内部链路名；需要引用依据时说“知识库证据”或“业务证据”。",
            # 2026-06-06 12:02:07 新增原因：重试纠错信息只供模型内部使用，最终用户答案必须像一次正常回答。
            "- 最终用户答案不要提上一版回答、错误答案、纠正说明、证据锚点或重试过程；直接回答当前业务问题。",
            # 2026-06-06 10:59:53 新增原因：禁止把内部图谱调试节点写入最终答案，防止 qachunk 和内部关系名污染用户语言。
            "- 最终答案不要输出 qachunk、qaglobal、MENTIONED_IN_CHUNK、CHUNK_IN_GLOBAL_CLUSTER、FUSED_INTO 这类内部调试标记。",
            # 2026-06-06 10:59:53 新增原因：明确空答处理边界，兜底证据草稿不能冒充模型最终回答。
            "- 模型空答时不得把兜底证据草稿标记成模型回答，必须重试最终回答或交给 verifier 转人工。",
        ]
        # 2026-06-06 11:46:12 修改原因：回答约束是最终回答合同，必须从长证据截断预算中独立出来，不能被 RAG/图谱挤掉。
        constraints_context = "\n[回答约束]\n" + "\n".join(answer_constraints)
        # 2026-06-06 11:46:12 新增原因：先拼接证据正文，后续只截断证据正文，不截断回答约束。
        evidence_context = "\n".join(sections)
        # 2026-06-06 11:46:12 新增原因：给回答约束预留固定空间，确保本地 Qwen 8192 context 内仍能看到最终回答规则。
        evidence_budget = max(1200, 3600 - len(constraints_context) - 2)
        # 2026-06-06 11:46:12 修改原因：证据正文按预算截断，回答约束原样追加，防止模型看不到极性、空答和内部名禁止规则。
        return self._truncate_for_prompt(evidence_context, evidence_budget) + "\n" + constraints_context

    def _compact_tool_result_for_model(self, tool_name: str, result: Any) -> dict[str, Any]:
        # 2026-06-04 18:21:37 新增原因：function role 只给模型工具摘要，不再原样塞入完整 RAG/图谱 payload。
        if not isinstance(result, dict):
            # 2026-06-04 18:21:37 新增原因：非字典结果转成短摘要，避免大对象直接进入上下文。
            return {"status": "non_dict_result", "summary": self._truncate_for_prompt(result, 300)}
        # 2026-06-04 18:21:37 新增原因：RAG 结果只保留 top1、召回数量和少量 chunk ID。
        if tool_name == "sql_rag_retrieve":
            # 2026-06-04 18:21:37 新增原因：读取召回列表。
            items = result.get("results", []) or []
            # 2026-06-04 18:21:37 新增原因：返回 RAG 紧凑摘要。
            return {
                "status": result.get("status", "ok"),
                "retrieved_count": len(items) if isinstance(items, list) else 0,
                "source_chunk_id": result.get("source_chunk_id", ""),
                "best_answer": self._truncate_for_prompt(result.get("best_answer", ""), 500),
                "chunk_ids": [str(item.get("chunk_id", "")) for item in items[:5] if isinstance(item, dict)],
            }
        # 2026-06-04 18:21:37 新增原因：图谱结果只保留后端、路径数量和少量三元组。
        if tool_name == "sql_rag_graph_expand":
            # 2026-06-04 18:21:37 新增原因：读取三元组列表。
            triples = result.get("triples", []) or []
            # 2026-06-04 18:21:37 新增原因：返回图谱紧凑摘要。
            return {
                "status": result.get("status", "ok"),
                "backend": result.get("backend", ""),
                "match_strategy": result.get("match_strategy", ""),
                "path_count": len(result.get("paths", []) or []),
                "triple_count": len(triples) if isinstance(triples, list) else 0,
                "triples": [
                    {
                        "subject": self._truncate_for_prompt(triple.get("subject", ""), 80),
                        "predicate": self._truncate_for_prompt(triple.get("predicate", ""), 80),
                        "object": self._truncate_for_prompt(triple.get("object", ""), 80),
                    }
                    for triple in triples[:8]
                    if isinstance(triple, dict)
                ],
            }
        # 2026-06-04 18:21:37 新增原因：记忆结果只保留计数，避免画像长文本泄入上下文。
        if tool_name == "sql_rag_memory_read":
            # 2026-06-04 18:21:37 新增原因：返回记忆紧凑摘要。
            return {
                "status": result.get("status", "ok"),
                "profile_memory_count": len(result.get("structured_profile_memory", []) or []),
                "episodic_memory_count": len(result.get("long_term_episodic_memory", []) or []),
            }
        # 2026-06-04 18:21:37 新增原因：业务动作结果只保留状态和业务 ID，不带完整入参。
        if tool_name == "sql_rag_business_action":
            # 2026-06-04 18:21:37 新增原因：返回业务动作紧凑摘要。
            return {
                "status": result.get("status", ""),
                "action_name": result.get("action_name", ""),
                # 2026-06-05 17:32:11 新增原因：保留业务意图，Verifier 不能只看到 succeeded。
                "business_intent": result.get("business_intent", ""),
                # 2026-06-05 17:32:11 新增原因：保留业务关注字段，支持语义覆盖校验。
                "focus_terms": result.get("focus_terms", []),
                # 2026-06-05 17:32:11 新增原因：保留短业务上下文，避免业务工具形式过场。
                "business_context": result.get("business_context", []),
                # 2026-06-05 18:10:08 新增原因：保留 RAG 证据锚点，让 function-role 摘要也能支持泛化语义覆盖。
                "best_answer": self._truncate_for_prompt(result.get("best_answer", ""), 300),
                "ticket_id": result.get("ticket_id", ""),
                "handoff_id": result.get("handoff_id", ""),
                "followup_id": result.get("followup_id", ""),
            }
        # 2026-06-04 18:21:37 新增原因：未知工具只保留顶层键，避免原始大字段进入模型。
        return {"status": result.get("status", "ok"), "keys": list(result.keys())[:12]}

    def _public_tool_results(self, tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 2026-06-04 19:15:51 新增原因：最终接口只返回工具摘要，避免前端最后一包 NDJSON 带出完整 RAG/图谱大 payload。
        public_results: list[dict[str, Any]] = []
        # 2026-06-04 19:15:51 新增原因：遍历运行时工具结果。
        for tool_result in tool_results:
            # 2026-06-04 19:15:51 新增原因：读取工具名。
            tool_name = str(tool_result.get("tool_name", ""))
            # 2026-06-04 19:15:51 新增原因：追加紧凑结果。
            public_results.append(
                {
                    "tool_name": tool_name,
                    "tool_args": tool_result.get("tool_args", {}),
                    "result": self._compact_tool_result_for_model(tool_name, tool_result.get("result", {})),
                }
            )
        # 2026-06-04 19:15:51 新增原因：返回前端可安全展示的工具摘要。
        return public_results

    def _public_verifier_result(self, verifier_result: dict[str, Any]) -> dict[str, Any]:
        # 2026-06-04 19:42:12 新增原因：对外响应不能暴露 verifier 模型的 raw 思维文本，只保留结构化校验结论。
        public_result = {
            "score": verifier_result.get("score", 0.0),
            "grounded": verifier_result.get("grounded", False),
            "complete": verifier_result.get("complete", False),
            "needs_human": verifier_result.get("needs_human", False),
            "failure_reason": verifier_result.get("failure_reason", ""),
        }
        # 2026-06-04 19:42:12 新增原因：raw 中只保留确定性校验摘要字段，删除 raw_content/Thinking Process。
        raw = verifier_result.get("raw", {})
        # 2026-06-04 19:42:12 新增原因：只处理字典 raw。
        if isinstance(raw, dict):
            # 2026-06-04 19:42:12 新增原因：保留可审计但不含思维链的字段。
            public_result["raw"] = {
                key: raw.get(key)
                for key in (
                    "fallback",
                    "retrieved_count",
                    "business_action_succeeded",
                    # 2026-06-05 10:18:39 新增原因：把完整链路要求公开给前端审计，不暴露隐藏思维链。
                    "requires_full_chain",
                    "requires_business_action",
                    "requires_memory",
                    "memory_satisfied",
                    "requires_graph",
                    "graph_satisfied",
                    # 2026-06-08 17:35:42 修改原因：对外保留答案等价和内部词门禁摘要，便于 WebUI 复查而不暴露思维链。
                    "answer_equivalence",
                    # 2026-06-08 17:35:42 修改原因：对外保留答案等价和内部词门禁摘要，便于 WebUI 复查而不暴露思维链。
                    "internal_leak_check",
                    # 2026-06-08 17:35:42 修改原因：对外保留答案等价和内部词门禁摘要，便于 WebUI 复查而不暴露思维链。
                    "topic_coverage",
                    # 2026-06-08 17:35:42 修改原因：对外保留答案等价和内部词门禁摘要，便于 WebUI 复查而不暴露思维链。
                    "polarity_check",
                )
                if key in raw
            }
        # 2026-06-04 19:42:12 新增原因：返回净化后的 verifier 结果。
        return public_result

    def _compact_evidence_for_verifier(self, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 2026-06-04 19:27:18 新增原因：Verifier 只需要小证据摘要，不能把完整 RAG/Neo4j payload 再塞爆 Qwen context。
        compact_evidence: list[dict[str, Any]] = []
        # 2026-06-04 19:27:18 新增原因：遍历原始证据。
        for evidence_item in evidence:
            # 2026-06-04 19:27:18 新增原因：读取工具名。
            tool_name = str(evidence_item.get("tool_name", ""))
            # 2026-06-04 19:27:18 新增原因：读取工具结果。
            result = evidence_item.get("result", {})
            # 2026-06-04 19:27:18 新增原因：先复用模型工具摘要。
            compact_result = self._compact_tool_result_for_model(tool_name, result)
            # 2026-06-04 19:27:18 新增原因：Verifier 的确定性逻辑需要 results 数量，因此给 RAG 摘要补轻量 chunk 列表。
            if tool_name == "sql_rag_retrieve" and isinstance(compact_result, dict):
                # 2026-06-04 19:27:18 新增原因：读取紧凑 chunk_id 列表。
                chunk_ids = compact_result.get("chunk_ids", []) or []
                # 2026-06-04 19:27:18 新增原因：写入轻量 results，避免携带每条 chunk 全量文本。
                compact_result["results"] = [{"chunk_id": chunk_id} for chunk_id in chunk_ids]
            # 2026-06-04 19:27:18 新增原因：追加紧凑证据项。
            compact_evidence.append({"tool_name": tool_name, "result": compact_result})
        # 2026-06-04 19:27:18 新增原因：返回 verifier 可消费的小证据。
        return compact_evidence

    # 2026-06-06 11:02:18 修改原因：判断证据文本是否覆盖当前问题主题，避免其他 chunk 的兜底答案污染当前问题。
    def _answer_matches_question_topic(self, question: str, answer: str) -> bool:
        # 2026-06-05 17:32:11 新增原因：空答案不能算主题匹配。
        if not str(answer or "").strip():
            # 2026-06-05 17:32:11 新增原因：返回不匹配。
            return False
        # 2026-06-05 18:10:08 修改原因：使用泛化语义覆盖率判断问题和答案是否同题，不再依赖固定停用词和固定业务词。
        coverage = semantic_answer_coverage(question, answer)
        # 2026-06-05 18:10:08 修改原因：返回覆盖率判定结果，阻止其他业务 chunk 的 best_answer 污染当前问题。
        return bool(coverage.get("satisfied"))

    # 2026-06-05 17:32:11 新增原因：为是/否类问题生成第一句正面结论，修复模型/兜底不回答“是或不是”的缺陷。
    def _direct_conclusion_for_question(self, question: str, evidence_answer: str) -> str:
        # 2026-06-05 17:32:11 新增原因：判断是否是二选一/是非类追问。
        is_binary_question = self._question_has_any_keyword(question, ("是不是", "是否", "对不对", "要不要", "能不能", "可不可以", "是不是要"))
        # 2026-06-05 17:32:11 新增原因：非二选一问题不强行输出“是/不是”。
        if not is_binary_question:
            # 2026-06-05 17:32:11 新增原因：返回通用结论前缀。
            return "结论："
        # 2026-06-05 17:32:11 新增原因：证据含否定词时输出“不是/不建议”。
        if any(term in evidence_answer for term in ("不需要", "不用", "不要", "不能", "不可以", "不建议")):
            # 2026-06-05 17:32:11 新增原因：返回否定结论。
            return "结论：不是。"
        # 2026-06-05 17:32:11 新增原因：证据含肯定处理词时输出“是”。
        if any(term in evidence_answer for term in ("需要", "应该", "可以", "要先", "先做", "必须", "建议")):
            # 2026-06-05 17:32:11 新增原因：返回肯定结论。
            return "结论：是。"
        # 2026-06-05 17:32:11 新增原因：证据不够明确时输出条件式结论，避免强编。
        return "结论：需要结合证据确认。"

    def _compose_evidence_fallback_answer(self, state: AgentState) -> str:
        # 2026-06-04 19:15:51 新增原因：如果小模型无工具最终回答仍为空，用已验证证据生成非空兜底草稿，交给 verifier 判定。
        mark = self.correction_runtime.normalize_mark(state.get("mark"))
        # 2026-06-05 17:32:11 新增原因：读取当前用户问题，兜底必须围绕当前问题动态生成。
        question = str(state.get("question", ""))
        # 2026-06-04 19:15:51 新增原因：优先读取 RAG top1 证据。
        best_answer = str(mark.get("best_answer") or "")
        # 2026-06-05 17:32:11 新增原因：RAG top1 不覆盖当前问题主题时返回空，让 verifier 转人工或回流。
        if not self._answer_matches_question_topic(question, best_answer):
            # 2026-06-05 17:32:11 新增原因：拒绝用其他业务场景兜底污染当前问题。
            return ""
        # 2026-06-04 19:15:51 新增原因：初始化图谱关系摘要。
        graph_lines: list[str] = []
        # 2026-06-05 17:32:11 新增原因：初始化业务上下文摘要。
        business_lines: list[str] = []
        # 2026-06-04 19:15:51 新增原因：遍历工具结果查找图谱结果。
        for tool_result in state.get("tool_results", []):
            # 2026-06-04 19:15:51 新增原因：只处理图谱工具。
            if tool_result.get("tool_name") == "sql_rag_graph_expand":
                # 2026-06-04 19:15:51 新增原因：读取图谱结果。
                result = tool_result.get("result", {})
                # 2026-06-04 19:15:51 新增原因：只接受字典结果。
                if isinstance(result, dict):
                    # 2026-06-05 17:32:11 修改原因：复用清洗后的 Prompt Builder 图谱摘要，并带入问题和 RAG top1 做相关性排序。
                    graph_lines = self._format_graph_context_for_prompt(result, question=question, best_answer=best_answer)[1:4]
                # 2026-06-05 17:32:11 新增原因：继续扫描业务工具，不能在图谱后提前退出。
                continue
            # 2026-06-05 17:32:11 新增原因：处理业务上下文工具。
            if tool_result.get("tool_name") == "sql_rag_business_action":
                # 2026-06-05 17:32:11 新增原因：读取业务工具结果。
                result = tool_result.get("result", {})
                # 2026-06-05 17:32:11 新增原因：只接受字典业务结果。
                if isinstance(result, dict):
                    # 2026-06-05 17:32:11 新增原因：复用业务上下文格式化结果，补充业务字段证据。
                    business_lines = self._format_business_context_for_prompt(result)[1:5]
        # 2026-06-05 17:32:11 新增原因：按问题形态给出第一句结论。
        conclusion_prefix = self._direct_conclusion_for_question(question, best_answer)
        # 2026-06-05 17:32:11 新增原因：初始化答案行，兜底只能基于当前 best_answer。
        answer_lines = [f"{conclusion_prefix}{best_answer}"]
        # 2026-06-05 17:32:11 新增原因：有图谱摘要时作为证据补充，不暴露 raw triple。
        if graph_lines:
            # 2026-06-05 17:32:11 新增原因：写入图谱补充说明。
            answer_lines.append("图谱补充：" + "；".join(graph_lines))
        # 2026-06-05 17:32:11 新增原因：有业务上下文时作为字段佐证，不只显示工具 succeeded。
        if business_lines:
            # 2026-06-05 17:32:11 新增原因：写入业务工具补充说明。
            answer_lines.append("业务工具补充：" + "；".join(business_lines))
        # 2026-06-05 17:32:11 新增原因：返回动态兜底草稿，来源会单独标记为 evidence_fallback。
        return "\n".join(answer_lines)

    # 2026-06-06 12:54:47 新增原因：汇总最终回答校验证据，避免压缩 evidence 已非空时漏掉 RAG top1 事实方向。
    def _collect_final_answer_evidence_texts(self, state: AgentState) -> list[str]:
        # 2026-06-06 12:54:47 新增原因：标准化 mark，优先读取运行时已确认的 top1 标准答案。
        mark = self.correction_runtime.normalize_mark(state.get("mark"))
        # 2026-06-06 12:54:47 新增原因：初始化有序证据列表，让 RAG top1 永远排在压缩图谱摘要之前。
        ordered_texts: list[str] = []
        # 2026-06-06 12:54:47 新增原因：mark.best_answer 是当前问题最强答案锚点，必须参与极性和主题校验。
        if mark.get("best_answer"):
            # 2026-06-06 12:54:47 新增原因：追加 RAG top1 原文，任意业务 chunk 都按这个事实方向校准。
            ordered_texts.append(str(mark.get("best_answer") or ""))
        # 2026-06-06 12:54:47 新增原因：业务工具可能回填同一 RAG 锚点，作为跨节点一致性补充。
        if mark.get("business_best_answer"):
            # 2026-06-06 12:54:47 新增原因：追加业务工具消费过的 RAG 锚点，防止 tool_results 被裁剪时丢证据。
            ordered_texts.append(str(mark.get("business_best_answer") or ""))
        # 2026-06-06 12:54:47 新增原因：业务上下文是执行层只读佐证，参与校验但不覆盖 top1 排序。
        for item in (mark.get("business_context", []) or []):
            # 2026-06-06 12:54:47 新增原因：跳过空业务上下文，避免无意义文本影响极性判断。
            if item:
                # 2026-06-06 12:54:47 新增原因：追加业务上下文文本，用于判断答案是否切中当前业务对象。
                ordered_texts.append(str(item))
        # 2026-06-06 12:54:47 新增原因：原始工具结果包含完整 RAG best_answer，不能被 compact evidence 的存在短路。
        ordered_texts.extend(collect_evidence_texts(state.get("tool_results", [])))
        # 2026-06-06 12:54:47 新增原因：压缩 evidence 仍保留 verifier 小摘要，作为辅助证据而非唯一证据。
        ordered_texts.extend(collect_evidence_texts(state.get("evidence", [])))
        # 2026-06-06 12:54:47 新增原因：初始化去重集合，避免同一 top1 重复过多放大某个词。
        seen: set[str] = set()
        # 2026-06-06 12:54:47 新增原因：初始化最终证据列表，保持原始优先级顺序。
        final_texts: list[str] = []
        # 2026-06-06 12:54:47 新增原因：逐条清洗和去重汇总证据。
        for text in ordered_texts:
            # 2026-06-06 12:54:47 新增原因：统一转字符串并去除空白，兼容列表、字典和普通文本。
            normalized_text = str(text or "").strip()
            # 2026-06-06 12:54:47 新增原因：空文本或重复文本不进入最终校验证据。
            if not normalized_text or normalized_text in seen:
                # 2026-06-06 12:54:47 新增原因：继续处理下一条证据。
                continue
            # 2026-06-06 12:54:47 新增原因：记录已见文本，保证全局泛化去重。
            seen.add(normalized_text)
            # 2026-06-06 12:54:47 新增原因：保留有效证据文本，供最终回答极性和空答重试使用。
            final_texts.append(normalized_text)
        # 2026-06-06 12:54:47 新增原因：返回有序去重证据，调用方不再依赖 state.evidence or tool_results 的短路逻辑。
        return final_texts

    # 2026-06-05 17:32:11 新增原因：构造极简最终回答重试上下文，避免完整 tools schema 后本地 2B 空答。
    def _build_minimal_final_retry_context(self, state: AgentState) -> str:
        # 2026-06-05 17:32:11 新增原因：读取标准 mark。
        mark = self.correction_runtime.normalize_mark(state.get("mark"))
        # 2026-06-05 17:32:11 新增原因：初始化极简上下文行。
        lines = ["最终回答极简证据："]
        # 2026-06-05 17:32:11 新增原因：写入用户原问题，保证重试不丢意图。
        lines.append(f"- 用户问题：{state.get('question', '')}")
        # 2026-06-05 17:32:11 新增原因：写入 RAG top1，作为最强答案证据。
        if mark.get("best_answer"):
            # 2026-06-05 17:32:11 新增原因：限制 RAG 证据长度，避免重试上下文超限。
            lines.append(f"- RAG top1：{self._truncate_for_prompt(mark.get('best_answer'), 500)}")
        # 2026-06-05 17:32:11 新增原因：写入业务上下文摘要，辅助模型避免答偏场景。
        for item in (mark.get("business_context", []) or [])[:3]:
            # 2026-06-05 17:32:11 新增原因：跳过空业务摘要。
            if not item:
                # 2026-06-05 17:32:11 新增原因：继续下一个摘要。
                continue
            # 2026-06-05 17:32:11 新增原因：追加业务摘要。
            lines.append(f"- 业务上下文：{self._truncate_for_prompt(item, 220)}")
        # 2026-06-05 17:32:11 新增原因：写入回答形态约束，保证是/否和步骤问题正面回答。
        lines.append("- 回答要求：第一句先给结论；是/否问题必须回答是或不是；操作问题必须给步骤；证据不足就说明需要人工确认。")
        # 2026-06-06 11:46:12 新增原因：极简重试也必须跟 top1 肯定/否定方向一致，避免第一次答反后重试仍答反。
        lines.append("- 极性要求：肯定或否定方向必须跟 RAG top1 标准答案一致；可以/应该/需要对应肯定结论，不需要/不能/无法对应否定结论。")
        # 2026-06-06 11:46:12 新增原因：极简重试最终面向用户，也不能输出内部链路名。
        lines.append("- 用户语言要求：不要输出 Prompt Builder、RAG top1、Neo4j、Qdrant、LlamaIndex、qachunk 等内部名。")
        # 2026-06-06 12:02:07 新增原因：极简重试不能把内部纠错过程写给用户。
        lines.append("- 重试痕迹要求：不要提上一版回答、错误答案、纠正说明、证据锚点或重试过程。")
        # 2026-06-05 17:32:11 新增原因：返回极简重试上下文。
        return self._truncate_for_prompt("\n".join(lines), 1800)

    # 2026-06-05 19:11:30 新增原因：集中生成最终回答阶段的 Qwen 配置，避免 Qwen3 只返回 reasoning_content 导致模型空答。
    def _final_answer_extra_generate_cfg(self) -> dict[str, Any]:
        # 2026-06-05 19:11:30 新增原因：通过 OpenAI extra_body 透传 llama.cpp/Qwen3 的关闭 thinking 参数。
        return {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}

    # 2026-06-06 11:12:44 新增原因：集中兼容 Qwen-Agent 正式客户端和旧单测替身的 chat 参数差异。
    def _chat_qwen_final_answer(self, messages: list[dict[str, str]]) -> list[Any]:
        # 2026-06-06 11:12:44 新增原因：先按生产路径携带 extra_generate_cfg，保证本地 Qwen3 不再只吐 reasoning_content。
        chat_kwargs = {"messages": messages, "functions": [], "stream": False, "extra_generate_cfg": self._final_answer_extra_generate_cfg()}
        # 2026-06-06 11:12:44 新增原因：执行正式 Qwen 调用。
        try:
            # 2026-06-06 11:12:44 新增原因：返回生产客户端响应。
            return self.qwen_llm.chat(**chat_kwargs)
        # 2026-06-06 11:12:44 新增原因：兼容历史测试替身不接受 extra_generate_cfg 的签名。
        except TypeError as exc:
            # 2026-06-06 11:12:44 新增原因：只有明确是 extra_generate_cfg 参数不兼容时才降级，其他类型错误继续暴露。
            if "extra_generate_cfg" not in str(exc):
                # 2026-06-06 11:12:44 新增原因：重新抛出非兼容问题，避免吞掉真实生产错误。
                raise
            # 2026-06-06 11:12:44 新增原因：移除旧替身不支持的参数，保持外层合同测试可复用。
            chat_kwargs.pop("extra_generate_cfg", None)
            # 2026-06-06 11:12:44 新增原因：按旧签名重试一次。
            return self.qwen_llm.chat(**chat_kwargs)


    # 2026-06-08 15:44:31 新增原因：集中校验模型最终答案，覆盖答对、乱答、逃逸和内部词泄露。
    def _final_answer_quality_check(self, state: AgentState, answer_text: str, evidence_texts: list[str]) -> dict[str, Any]:
        # 2026-06-08 15:44:31 新增原因：执行答案与 top1/chunk 证据的等价校验。
        equivalence_check = semantic_answer_grounded_equivalence(str(state.get("question", "")), answer_text, evidence_texts)
        # 2026-06-08 15:44:31 新增原因：执行极性校验，防止肯定证据被答成否定。
        polarity_check = semantic_answer_polarity_conflict(answer_text, evidence_texts)
        # 2026-06-08 15:44:31 新增原因：执行逃逸校验，防止证据齐全时模型说证据不足。
        evasion_check = semantic_answer_evasion(answer_text, evidence_texts)
        # 2026-06-08 15:44:31 新增原因：执行内部词泄露校验，防止调试词进用户答案。
        internal_leak_check = semantic_answer_internal_token_leak(answer_text)
        # 2026-06-08 15:44:31 新增原因：四类门禁全部通过才允许进入 verifier/renderer。
        passed = bool(equivalence_check.get("equivalent")) and not polarity_check.get("conflict") and not evasion_check.get("evasive") and not internal_leak_check.get("leaked")
        # 2026-06-08 15:44:31 新增原因：生成结构化失败原因，支持纠错回流。
        reason = "" if passed else (equivalence_check.get("reason") or polarity_check.get("reason") or evasion_check.get("reason") or internal_leak_check.get("reason") or "answer_quality_failed")
        # 2026-06-08 15:44:31 新增原因：返回门禁详情，不再只看模型是否吐字。
        return {"passed": passed, "reason": reason, "equivalence_check": equivalence_check, "polarity_check": polarity_check, "evasion_check": evasion_check, "internal_leak_check": internal_leak_check}

    # 2026-06-09 09:12:31 Added: detect troubleshooting shapes that are not yes/no questions.
    def _question_is_procedure_answer_shape(self, question: str) -> bool:
        question_text = str(question or "")
        if re.search("\u662f\u5426|\u662f\u4e0d\u662f|\u5bf9\u4e0d\u5bf9|\u80fd\u4e0d\u80fd|\u8981\u4e0d\u8981|\u53ef\u4e0d\u53ef\u4ee5", question_text):
            return False
        return bool(re.search("\u6392\u67e5|\u6b65\u9aa4|\u600e\u4e48|\u5982\u4f55|\u786e\u8ba4|\u68c0\u67e5", question_text))

    # 2026-06-09 09:12:31 Added: remove only a polluted yes/should/need lead from model text, then quality gates re-check the remaining model answer.
    def _normalize_final_answer_shape(self, state: AgentState, answer_text: str) -> dict[str, Any]:
        original_answer = str(answer_text or "").strip()
        if not original_answer:
            return {"answer": "", "normalized": False, "reason": ""}
        if not self._question_is_procedure_answer_shape(str(state.get("question", ""))):
            return {"answer": original_answer, "normalized": False, "reason": ""}
        cleaned_answer = re.sub(r"^\s*(?:#+\s*)?(?:\*\*)?\s*(?:\u662f(?:\u7684)?|\u53ef\u4ee5|\u5e94\u8be5|\u9700\u8981)(?:\*\*)?\s*[,\uff0c.\u3002;\uff1b:\uff1a\s]*", "", original_answer, count=1).lstrip()
        cleaned_answer = re.sub(r"^[,\uff0c.\u3002;\uff1b:\uff1a\s]+", "", cleaned_answer).lstrip()
        step_match = re.search(r"(?:\u6392\u67e5/\u5904\u7406\u987a\u5e8f|\u6392\u67e5\u987a\u5e8f|\u5904\u7406\u987a\u5e8f)\s*[:\uff1a]", cleaned_answer[:400])
        if step_match and step_match.start() > 0:
            cleaned_answer = cleaned_answer[step_match.start():].lstrip()
        numbered_step_match = re.search(r"(?:^|\n)\s*1\s*[.\uff0e\u3001\)\uff09]", cleaned_answer[:500])
        if numbered_step_match and numbered_step_match.start() > 0 and not step_match:
            cleaned_answer = "\u6392\u67e5\u987a\u5e8f\uff1a " + cleaned_answer[numbered_step_match.start():].strip()
        cleaned_answer = re.sub(r"\n+\s*(?:\u72b6\u6001\u4e0e\u6761\u4ef6|\u4e1a\u52a1\u5bf9\u8c61\u4e0e\u52a8\u4f5c\u5173\u7cfb)\s*[:\uff1a][\s\S]*", "", cleaned_answer).strip()
        cleaned_answer = re.sub(r"\s*\u7ed3\u8bba\s*[:\uff1a]\s*\n?\s*\u662f(?:\u7684)?[,.\uff0c\u3002;\uff1b\s]*", " ", cleaned_answer).strip()
        lead_text = cleaned_answer[:100]
        tail_text = cleaned_answer[100:]
        lead_text = lead_text.replace("\u662f\u5426", "\u6709\u65e0")
        normalized_lead = re.sub(r"(?<!\u4e0d)(?:\u53ef\u4ee5|\u5e94\u8be5|\u9700\u8981)", "", lead_text)
        normalized_lead = re.sub(r"\s+", " ", normalized_lead).strip()
        cleaned_answer = (normalized_lead + tail_text).strip()
        if cleaned_answer and cleaned_answer != original_answer:
            return {"answer": cleaned_answer, "normalized": True, "reason": "procedure_positive_lead_removed"}
        return {"answer": original_answer, "normalized": False, "reason": ""}

    # 2026-06-08 19:47:06 Reason: build a tool-free retry prompt from dynamic business terms without leaking internal gates.
    def _final_answer_retry_messages(self, retry_context: str, quality_check: dict[str, Any]) -> list[dict[str, str]]:
        # 2026-06-08 19:47:06 Reason: convert quality failure feedback into business terms the model must cover.
        equivalence_check = quality_check.get("equivalence_check", {}) if isinstance(quality_check.get("equivalence_check", {}), dict) else {}
        # 2026-06-08 19:47:06 Reason: use chunk-derived terms so the model writes the answer instead of renderer hard-covering it.
        required_terms = [str(term).strip() for term in equivalence_check.get("required_terms", []) if str(term).strip()]
        # 2026-06-08 19:47:06 Reason: cap the list so the local small model stays focused.
        core_terms = "\u3001".join(required_terms[:8])
        # 2026-06-08 19:47:06 Reason: keep a generic prompt when there are no dynamic terms.
        core_requirement = f"\n\u5fc5\u987b\u8986\u76d6\u8fd9\u4e9b\u4e1a\u52a1\u8981\u70b9\uff1a{core_terms}\u3002" if core_terms else ""
        # 2026-06-08 19:47:06 Reason: retry consumes evidence only and must not call tools.
        system_content = "\u4f60\u662f SQL_RAG \u667a\u80fd\u5ba2\u670d\u4e1a\u52a1\u5927\u8111\u3002\u4e0d\u8981\u8c03\u7528\u5de5\u5177\uff0c\u53ea\u57fa\u4e8e\u8bc1\u636e\u8f93\u51fa\u6700\u7ec8\u7528\u6237\u7b54\u6848\uff1b\u4e0d\u8981\u63d0\u5185\u90e8\u94fe\u8def\u3001\u8c03\u8bd5\u6807\u8bb0\u3002"
        # 2026-06-08 19:47:06 Reason: avoid exposing quality gates, previous answers, or repair process to the model.
        user_content = f"{retry_context}\n\n\u8bf7\u53ea\u6839\u636e\u4e0a\u9762\u7684\u4e1a\u52a1\u8bc1\u636e\u7ec4\u7ec7\u6700\u7ec8\u7528\u6237\u56de\u7b54\u3002{core_requirement}\u7b2c\u4e00\u53e5\u5148\u7ed9\u7ed3\u8bba\uff1b\u968f\u540e\u8bf4\u660e\u4e1a\u52a1\u5bf9\u8c61\u3001\u6267\u884c\u52a8\u4f5c\u3001\u72b6\u6001\u6216\u6761\u4ef6\u4e4b\u95f4\u7684\u5173\u7cfb\u3002\u53ea\u6709\u7528\u6237\u660e\u786e\u95ee\u662f\u5426/\u5bf9\u4e0d\u5bf9/\u80fd\u4e0d\u80fd/\u8981\u4e0d\u8981\u65f6\u624d\u7528\u201c\u662f/\u4e0d\u662f\u201d\u5f00\u5934\uff1b\u6392\u67e5\u3001\u6b65\u9aa4\u3001\u600e\u4e48\u7c7b\u95ee\u9898\u7528\u201c\u6392\u67e5\u987a\u5e8f\uff1a\u201d\u6216\u201c\u5904\u7406\u987a\u5e8f\uff1a\u201d\u5f00\u5934\uff0c\u524d 100 \u5b57\u4e0d\u8981\u51fa\u73b0\u201c\u662f/\u53ef\u4ee5/\u5e94\u8be5/\u9700\u8981\u201d\u3002\u64cd\u4f5c\u7c7b\u95ee\u9898\u7ed9\u6b65\u9aa4\uff0c\u539f\u56e0\u7c7b\u95ee\u9898\u5148\u7ed3\u8bba\u518d\u89e3\u91ca\u3002\u4e0d\u8981\u8f93\u51fa RAG\u3001Neo4j\u3001Qdrant\u3001qachunk\u3001Prompt Builder \u7b49\u5185\u90e8\u8bcd\u3002"
        # 2026-06-08 19:47:06 Reason: return tool-free messages for final answer retry.
        return [{"role": "system", "content": system_content}, {"role": "user", "content": user_content}]

    def _renderer_model_draft_is_verified(self, state: AgentState, mark: dict[str, Any], verifier_result: dict[str, Any]) -> bool:
        # 2026-06-08 15:44:31 新增原因：优先读取 verifier raw 里的等价校验。
        raw_equivalence = (verifier_result.get("raw", {}) or {}).get("answer_equivalence", {}) if isinstance(verifier_result.get("raw", {}), dict) else {}
        # 2026-06-08 15:44:31 新增原因：读取 planner 写入 mark 的等价校验。
        mark_equivalence = mark.get("final_answer_equivalence", {}) if isinstance(mark.get("final_answer_equivalence", {}), dict) else {}
        # 2026-06-08 15:44:31 新增原因：任一上游硬门明确通过即可信任模型答案。
        if raw_equivalence.get("equivalent") or mark_equivalence.get("equivalent"):
            # 2026-06-08 15:44:31 新增原因：返回可信状态。
            return True
        # 2026-06-08 15:44:31 新增原因：上游缺标记时出口再做一次动态等价校验。
        dynamic_equivalence = semantic_answer_grounded_equivalence(str(state.get("question", "")), str(state.get("draft_answer", "")), self._collect_final_answer_evidence_texts(state))
        # 2026-06-08 15:44:31 新增原因：保存 renderer 出口校验结果。
        mark["renderer_answer_equivalence"] = dynamic_equivalence
        # 2026-06-08 15:44:31 新增原因：返回动态等价结果。
        return bool(dynamic_equivalence.get("equivalent"))

    # 2026-06-08 15:44:31 新增原因：判断 verifier 低分后是否应回到模型修复。
    def _should_repair_after_verifier(self, state: AgentState, draft_answer: str, verifier_result: dict[str, Any]) -> bool:
        # 2026-06-08 15:44:31 新增原因：空草稿无法修复，交给低置信回流。
        if not str(draft_answer or "").strip():
            # 2026-06-08 15:44:31 新增原因：返回不修复。
            return False
        # 2026-06-08 15:44:31 新增原因：只修复模型来源草稿，避免改写业务工具结果。
        source = str(state.get("draft_answer_source") or self.correction_runtime.normalize_mark(state.get("mark")).get("draft_answer_source") or "")
        # 2026-06-08 15:44:31 新增原因：限定模型来源才进入修复链。
        return source in {"qwen_final_answer", "qwen_final_answer_retry", "qwen_planner_content"}

    # 2026-06-08 15:44:31 新增原因：verifier 失败后只重试一次模型最终答案并复验。
    def _repair_answer_after_verifier(self, state: AgentState, draft_answer: str, verifier_result: dict[str, Any], mark: dict[str, Any]) -> dict[str, Any]:
        # 2026-06-08 15:44:31 新增原因：不满足修复条件时返回空结果。
        if not self._should_repair_after_verifier(state, draft_answer, verifier_result):
            # 2026-06-08 15:44:31 新增原因：返回空字典表示不修复。
            return {}
        # 2026-06-08 15:44:31 新增原因：写入 verifier 失败原因供重试追踪。
        mark["verifier_repair_reason"] = verifier_result.get("failure_reason", "")
        # 2026-06-08 15:44:31 新增原因：重新调用无工具最终回答。
        repair_decision = self._call_qwen_final_answer({**state, "mark": mark})
        # 2026-06-08 15:44:31 新增原因：读取模型修复答案。
        repair_answer = str(repair_decision.get("content", "") or "").strip()
        # 2026-06-08 15:44:31 新增原因：修复仍空时保留原低分路径。
        if not repair_answer:
            # 2026-06-08 15:44:31 新增原因：记录修复失败原因。
            mark["verifier_repair_failed_reason"] = repair_decision.get("quality_failure_reason", "model_repair_empty")
            # 2026-06-08 15:44:31 新增原因：返回空结果。
            return {}
        # 2026-06-08 15:44:31 新增原因：修复答案必须再过 verifier，不能只凭第二次吐字放行。
        repaired_verifier_result = self.correction_runtime.verify_answer_with_qwen(qwen_llm=self.qwen_llm, question=state["question"], answer=repair_answer, evidence=self._compact_evidence_for_verifier(state.get("evidence", [])))
        # 2026-06-08 15:44:31 新增原因：复验仍低分时不放行。
        if float(repaired_verifier_result.get("score", 0.0) or 0.0) < self.correction_runtime.config.verifier_threshold:
            # 2026-06-08 15:44:31 新增原因：保存复验失败原因。
            mark["verifier_repair_failed_reason"] = repaired_verifier_result.get("failure_reason", "verifier_repair_low_score")
            # 2026-06-08 15:44:31 新增原因：返回空结果。
            return {}
        # 2026-06-08 15:44:31 新增原因：保存修复答案等价结果。
        mark["final_answer_equivalence"] = repair_decision.get("answer_equivalence", {})
        # 2026-06-09 09:12:31 Added: expose model answer shape normalization for WebUI audit.
        mark["answer_shape_normalization"] = repair_decision.get("answer_shape_normalization", {})
        # 2026-06-08 15:44:31 新增原因：标记 verifier 修复链路成功执行。
        mark["verifier_repair_attempted"] = True
        # 2026-06-08 15:44:31 新增原因：返回修复后状态片段。
        return {"draft_answer": repair_answer, "draft_answer_source": "qwen_final_answer_retry", "verifier_result": repaired_verifier_result, "mark": mark}

    def _call_qwen_final_answer(self, state: AgentState) -> dict[str, Any]:
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        prompt_builder_context = self._build_prompt_builder_context(state)
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        system_prompt = '你是 SQL_RAG 智能客服业务大脑。当前证据工具已经完成，不允许再调用任何工具。请只基于 Prompt Builder 证据上下文组织简洁业务答案；不要暴露隐藏思维链；证据不足时说明需要人工确认。必须以 RAG top1 标准答案证据的事实方向为准；是/否问题第一句必须先回答“是”或“不是”。最终用户答案不要输出 Prompt Builder、RAG top1、Neo4j、Qdrant、LlamaIndex、qachunk 这类内部链路名。必须覆盖用户问题和证据中的核心业务对象、动作、状态或条件；如果证据不足，直接说明需要人工确认，不要猜。'
        system_prompt += "\u53ea\u6709\u7528\u6237\u660e\u786e\u95ee\u662f\u5426/\u5bf9\u4e0d\u5bf9/\u80fd\u4e0d\u80fd/\u8981\u4e0d\u8981\u65f6\u624d\u7528\u201c\u662f/\u4e0d\u662f\u201d\u5f00\u5934\uff1b\u6392\u67e5\u3001\u6b65\u9aa4\u3001\u600e\u4e48\u7c7b\u95ee\u9898\u7b2c\u4e00\u53e5\u7528\u201c\u6392\u67e5\u987a\u5e8f\uff1a\u201d\u6216\u201c\u5904\u7406\u987a\u5e8f\uff1a\u201d\u5f00\u5934\uff0c\u524d 100 \u5b57\u4e0d\u8981\u51fa\u73b0\u201c\u662f/\u53ef\u4ee5/\u5e94\u8be5/\u9700\u8981\u201d\u3002"
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        messages = [
            # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
            {"role": "system", "content": system_prompt},
            # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
            {"role": "user", "content": f"用户问题：{state['question']}\n\n{prompt_builder_context}\n\n请直接输出最终答案。"},
        ]
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        response = self._chat_qwen_final_answer(messages)
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        last_message = response[-1]
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        content = getattr(last_message, "content", None) or last_message.get("content", "")
        # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
        evidence_texts = self._collect_final_answer_evidence_texts(state)
        # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
        answer_text = str(content or "").strip()
        # 2026-06-09 09:12:31 Added: normalize a polluted procedure lead before the same quality gates run.
        answer_shape = self._normalize_final_answer_shape(state, answer_text)
        answer_text = str(answer_shape.get("answer", "") or "").strip()
        # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
        if answer_text:
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            quality_check = self._final_answer_quality_check(state, answer_text, evidence_texts)
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            if quality_check.get("passed"):
                # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
                return {"content": answer_text, "function_call": None, "prompt_builder_context": prompt_builder_context, "answer_source": "qwen_final_answer", "answer_quality": quality_check, "answer_equivalence": quality_check.get("equivalence_check", {}), "answer_shape_normalized": bool(answer_shape.get("normalized")), "answer_shape_normalization": answer_shape if answer_shape.get("normalized") else {}}
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            retry_context = self._build_minimal_final_retry_context(state)
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            retry_messages = self._final_answer_retry_messages(retry_context, quality_check)
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            retry_response = self._chat_qwen_final_answer(retry_messages)
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            retry_last_message = retry_response[-1]
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            retry_content = getattr(retry_last_message, "content", None) or retry_last_message.get("content", "")
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            retry_answer_text = str(retry_content or "").strip()
            # 2026-06-09 09:12:31 Added: normalize retry candidate shape before quality gates.
            retry_shape = self._normalize_final_answer_shape(state, retry_answer_text)
            retry_answer_text = str(retry_shape.get("answer", "") or "").strip()
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            retry_quality_check = self._final_answer_quality_check(state, retry_answer_text, evidence_texts)
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            if retry_answer_text and retry_quality_check.get("passed"):
                # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
                return {"content": retry_answer_text, "function_call": None, "prompt_builder_context": prompt_builder_context, "answer_source": "qwen_final_answer_retry", "answer_quality": retry_quality_check, "answer_equivalence": retry_quality_check.get("equivalence_check", {}), "answer_shape_normalized": bool(retry_shape.get("normalized")), "answer_shape_normalization": retry_shape if retry_shape.get("normalized") else {}}
            # 2026-06-08 16:42:36 修改原因：重试失败只返回结构化失败原因，不再把证据摘要硬编成最终答案。
            return {"content": "", "function_call": None, "prompt_builder_context": prompt_builder_context, "answer_source": "model_quality_failed", "model_quality_failed": True, "quality_failure_reason": retry_quality_check.get("reason") or quality_check.get("reason"), "answer_quality": retry_quality_check, "answer_equivalence": retry_quality_check.get("equivalence_check", {}), "answer_shape_normalized": bool(answer_shape.get("normalized") or retry_shape.get("normalized")), "answer_shape_normalization": retry_shape if retry_shape.get("normalized") else (answer_shape if answer_shape.get("normalized") else {})}
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        retry_context = self._build_minimal_final_retry_context(state)
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        retry_messages = self._final_answer_retry_messages(retry_context, {"reason": "model_empty_final_answer"})
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        retry_response = self._chat_qwen_final_answer(retry_messages)
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        retry_last_message = retry_response[-1]
        # 2026-06-08 16:42:36 修改原因：全局最终答案治理，阻止空答、乱答和硬编码兜底进入用户答案。
        retry_content = getattr(retry_last_message, "content", None) or retry_last_message.get("content", "")
        # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
        retry_answer_text = str(retry_content or "").strip()
        # 2026-06-09 09:12:31 Added: normalize retry candidate shape before quality gates.
        retry_shape = self._normalize_final_answer_shape(state, retry_answer_text)
        retry_answer_text = str(retry_shape.get("answer", "") or "").strip()
        # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
        retry_quality_check = self._final_answer_quality_check(state, retry_answer_text, evidence_texts)
        # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
        if retry_answer_text and retry_quality_check.get("passed"):
            # 2026-06-08 16:42:36 修改原因：模型答案必须切中 RAG top1/chunk 证据，且不泄露内部链路词。
            return {"content": retry_answer_text, "function_call": None, "prompt_builder_context": prompt_builder_context, "answer_source": "qwen_final_answer_retry", "answer_quality": retry_quality_check, "answer_equivalence": retry_quality_check.get("equivalence_check", {}), "answer_shape_normalized": bool(retry_shape.get("normalized")), "answer_shape_normalization": retry_shape if retry_shape.get("normalized") else {}}
        # 2026-06-08 16:42:36 修改原因：重试失败只返回结构化失败原因，不再把证据摘要硬编成最终答案。
        return {"content": "", "function_call": None, "prompt_builder_context": prompt_builder_context, "answer_source": "model_empty_final_answer", "model_empty_final_answer": True, "quality_failure_reason": retry_quality_check.get("reason") or "model_empty_final_answer", "answer_quality": retry_quality_check, "answer_equivalence": retry_quality_check.get("equivalence_check", {}), "answer_shape_normalized": bool(retry_shape.get("normalized")), "answer_shape_normalization": retry_shape if retry_shape.get("normalized") else {}}

    def _call_qwen(self, state: AgentState) -> dict[str, Any]:
        # 构造系统提示，强调证据边界和动态工具选择。
        system_prompt = (
            "你是 SQL_RAG 智能客服业务大脑。你只能做决策和推理，不能伪造工具结果。"
            "复杂业务问题必须优先根据需要动态调用工具：sql_rag_retrieve、sql_rag_graph_expand、"
            "sql_rag_memory_read、sql_rag_business_action。不要遵循固定业务流程；根据上下文自主选择下一步。"
            "最终回答必须引用已召回证据；证据不足要澄清、拒答或转人工。"
            "如果 sql_rag_retrieve 返回 best_answer，必须优先依据 best_answer 作答，不能改写成“没有直接提到”。"
            "需要实际处理客户请求时，调用 sql_rag_business_action 创建本地工单、转人工、跟进任务或画像记忆。"
            "如果用户明确要求查知识库，必须调用 sql_rag_retrieve；明确要求历史记忆或用户画像，必须调用 sql_rag_memory_read；"
            "明确要求实体关系、图谱、多跳或相关关系，必须调用 sql_rag_graph_expand；明确要求工单、提醒、转人工或业务处理，必须调用 sql_rag_business_action。"
            "工具结果已经由 Prompt Builder 组织成证据上下文后再交给你；最终答案由你基于证据组织语言输出。"
        )
        # 如果本轮已经成功执行业务动作，明确要求模型不要重复写工单等有副作用动作。
        if self._business_action_satisfied_for_question(state):
            # 追加防重提示，避免本地小模型在工具循环里重复创建工单。
            system_prompt += "当前轮次已经有业务动作执行成功，不要再次调用 sql_rag_business_action，请直接基于证据和工具结果组织最终回答。"
        # 创建消息列表。
        prompt_builder_context = self._build_prompt_builder_context(state)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"用户问题：{state['question']}\n\n{prompt_builder_context}"},
        ]
        # 2026-06-04 18:58:09 修改原因：工具结果已经进入 Prompt Builder 摘要，不再追加 function-role 历史，避免 Qwen-Agent 内部展开完整工具上下文导致 8192 context 爆掉。
        # 调用 Qwen-Agent 官方 chat，并传入 functions。
        response = self.qwen_llm.chat(messages=messages, functions=self._qwen_functions(), stream=False)
        # 取最后一条消息。
        last_message = response[-1]
        # 兼容 Qwen-Agent Message 和 dict。
        content = getattr(last_message, "content", None) or last_message.get("content", "")
        # 读取 function_call。
        function_call = getattr(last_message, "function_call", None) or last_message.get("function_call")
        # 2026-06-05 17:32:11 新增原因：记录模型是否既无内容也无工具调用，便于空答分支纠错。
        model_empty_decision = not str(content or "").strip() and not function_call
        # 2026-06-05 18:06:43 新增原因：模型直接吐内容时标记 planner 来源，避免 renderer 把来源重新猜成 model_draft。
        answer_source = "qwen_planner_content" if str(content or "").strip() else "model_empty"
        # 2026-06-05 18:06:43 修改原因：返回模型决策时带上 answer_source，方便 trace 和数据飞轮区分模型内容与空答。
        return {"content": content, "function_call": function_call, "prompt_builder_context": prompt_builder_context, "model_empty_decision": model_empty_decision, "answer_source": answer_source}

    def _parse_tool_arguments(self, raw_arguments: Any) -> dict[str, Any]:
        # 字典参数直接复制，避免模型参数被后续节点原地修改。
        if isinstance(raw_arguments, dict):
            # 返回参数字典。
            return dict(raw_arguments)
        # 非字符串参数无法 JSON 解析时返回空参数。
        if not isinstance(raw_arguments, str):
            # 返回空字典。
            return {}
        # 去掉字符串两侧空白。
        raw_text = raw_arguments.strip()
        # 空字符串返回空参数。
        if not raw_text:
            # 返回空字典。
            return {}
        # 优先严格按 JSON 解析。
        try:
            # 解析模型返回的 function arguments。
            parsed = json.loads(raw_text)
            # 只接受对象参数。
            return dict(parsed) if isinstance(parsed, dict) else {"raw_arguments": raw_text}
        except json.JSONDecodeError:
            # 严格解析失败时继续做结构化修复。
            pass
        # 统计左花括号数量。
        left_braces = raw_text.count("{")
        # 统计右花括号数量。
        right_braces = raw_text.count("}")
        # 本地小模型常见问题是末尾少一个右花括号，这里只补缺失右括号。
        if left_braces > right_braces:
            # 构造补齐右花括号后的候选 JSON。
            balanced_text = raw_text + ("}" * (left_braces - right_braces))
            # 尝试解析补齐后的 JSON。
            try:
                # 解析补齐候选。
                parsed = json.loads(balanced_text)
                # 只接受对象参数。
                return dict(parsed) if isinstance(parsed, dict) else {"raw_arguments": raw_text}
            except json.JSONDecodeError:
                # 补齐后仍失败时继续提取键值对。
                pass
        # 用正则提取简单字符串键值对，兜住 {"query": "... 这类半截参数。
        repaired_args = {
            # 保存键名和值。
            match.group("key"): match.group("value")
            # 遍历所有 "key": "value" 对。
            for match in re.finditer(r'"(?P<key>[^"]+)"\s*:\s*"(?P<value>[^"]*)"', raw_text)
        }
        # 有可恢复键值时返回恢复参数。
        if repaired_args:
            # 返回恢复后的参数。
            return repaired_args
        # 最后仍无法恢复时保留原始参数，方便 mark 定位模型格式问题。
        return {"raw_arguments": raw_text}

    # 2026-06-05 17:32:11 新增原因：判断截图要求的必经工具节点是否已经全部完成。
    def _required_agent_chain_completed(self, state: AgentState) -> bool:
        # 2026-06-05 17:32:11 新增原因：读取当前问题需要的工具列表。
        required_tools = self._required_tools_for_question(state.get("question", ""))
        # 2026-06-05 17:32:11 新增原因：没有必需工具时不能套用完整链收敛逻辑。
        if not required_tools:
            # 2026-06-05 17:32:11 新增原因：返回未完成。
            return False
        # 2026-06-05 17:32:11 新增原因：没有任何工具结果时说明还没进入证据链。
        if not state.get("tool_results"):
            # 2026-06-05 17:32:11 新增原因：返回未完成。
            return False
        # 2026-06-05 17:32:11 新增原因：没有缺失工具时才算完整链路完成。
        return not bool(self._next_missing_required_tool(state))

    def _planner_node(self, state: AgentState) -> AgentState:
        # 标准化 mark。
        mark = self.correction_runtime.normalize_mark(state.get("mark"))
        # 标记当前节点。
        mark["intent_node"] = "planner_intent_reasoner"
        # 2026-06-05 17:32:11 新增原因：必经工具完成后直接进入无工具最终回答，避免再次落入 function-calling 空答分支。
        if self._required_agent_chain_completed(state):
            # 2026-06-05 17:32:11 新增原因：调用无工具最终回答，让模型只消费 Prompt Builder。
            final_decision = self._call_qwen_final_answer(state)
            # 2026-06-05 17:32:11 新增原因：读取最终回答来源。
            draft_answer_source = str(final_decision.get("answer_source", "qwen_final_answer"))
            # 2026-06-05 17:32:11 新增原因：把 Prompt Builder 上下文写入 mark，便于前端和日志复盘。
            mark["prompt_builder_context"] = final_decision.get("prompt_builder_context", "")
            # 2026-06-08 17:35:42 修改原因：把最终模型答案质量结果写入 mark，防止 renderer 不知道答案是否等价。
            mark["final_answer_quality"] = final_decision.get("answer_quality", {})
            # 2026-06-08 17:35:42 修改原因：把最终模型答案质量结果写入 mark，防止 renderer 不知道答案是否等价。
            mark["final_answer_equivalence"] = final_decision.get("answer_equivalence", {})
            # 2026-06-09 09:12:31 Added: expose model answer shape normalization for WebUI audit.
            mark["answer_shape_normalization"] = final_decision.get("answer_shape_normalization", {})
            # 2026-06-05 17:32:11 新增原因：记录草稿来源，renderer 不能再把兜底冒充 model_draft。
            mark["draft_answer_source"] = draft_answer_source
            # 2026-06-05 17:32:11 新增原因：模型空答时写入明确标记，驱动数据飞轮定位最终回答节点。
            if final_decision.get("model_empty_final_answer"):
                # 2026-06-05 17:32:11 新增原因：保存空答标记。
                mark["model_empty_final_answer"] = True
            # 2026-06-05 17:32:11 新增原因：追加公开 trace，说明已从工具链收敛到最终回答。
            mark = self._append_trace_event(
                # 2026-06-05 17:32:11 新增原因：传入当前 mark。
                mark,
                # 2026-06-05 17:32:11 新增原因：事件类型仍属于 planner。
                event_type="planner",
                # 2026-06-05 17:32:11 新增原因：事件标题说明完整链路收敛。
                title="必经工具完成后最终回答",
                # 2026-06-05 17:32:11 新增原因：事件明细展示真实答案来源。
                detail=f"RAG、Neo4j、记忆和业务工具已完成，进入无工具最终回答，answer_source={draft_answer_source}。",
                # 2026-06-05 17:32:11 新增原因：标记工具名为 planner。
                tool_name="qwen_planner",
                # 2026-06-05 17:32:11 新增原因：把来源写入 payload 方便前端消费。
                payload={"answer_source": draft_answer_source},
            )
            # 2026-06-05 17:32:11 新增原因：返回最终草稿，不再安排工具。
            return {
                # 2026-06-05 17:32:11 新增原因：保留原状态字段。
                **state,
                # 2026-06-05 17:32:11 新增原因：写入最终草稿。
                "draft_answer": final_decision.get("content", ""),
                # 2026-06-05 17:32:11 新增原因：写入草稿来源。
                "draft_answer_source": draft_answer_source,
                # 2026-06-05 17:32:11 新增原因：清空待执行工具。
                "pending_tool_call": {},
                # 2026-06-05 17:32:11 新增原因：写回 mark。
                "mark": mark,
            }
        # 2026-06-09 10:58:24 Added: skip repeated Qwen planner when the required tool order is deterministic.
        required_tool_call_before_qwen = self._next_missing_required_tool(state)
        if state.get("tool_results") and required_tool_call_before_qwen:
            # Only schedules the next tool; retrieval, graph, memory, business, final answer, and verifier logic stay unchanged.
            mark["protocol_required_tool"] = required_tool_call_before_qwen["name"]
            mark["tool_name"] = required_tool_call_before_qwen["name"]
            mark["tool_args"] = required_tool_call_before_qwen["args"]
            return {
                **state,
                "pending_tool_call": required_tool_call_before_qwen,
                "mark": mark,
            }
        # 调用 Qwen-Agent 官方 function calling。
        decision = self._call_qwen(state)
        # 2026-06-04 16:57:14 新增原因：把 Prompt Builder 上下文写入 mark，便于前端 trace 和纠错 replay。
        mark["prompt_builder_context"] = decision.get("prompt_builder_context", "")
        # 2026-06-04 16:57:14 新增原因：记录 planner 已把上下文交给模型。
        mark = self._append_trace_event(
            mark,
            event_type="planner",
            title="Qwen-Agent 规划",
            detail="已调用 Prompt Builder，把工具证据上下文交给模型判断下一步。",
            tool_name="qwen_planner",
            payload={"has_tool_results": bool(state.get("tool_results"))},
        )
        # 读取 function_call。
        function_call = decision.get("function_call")
        # 如果模型决定调用工具。
        if function_call:
            # 读取工具名。
            tool_name = function_call.get("name", "")
            # 读取原始参数。
            raw_arguments = function_call.get("arguments", {}) or {}
            # 解析并修复工具参数，避免本地小模型半截 JSON 导致工具空转。
            tool_args = self._parse_tool_arguments(raw_arguments)
            # 查找用户显式要求但尚未完成的下一项工具。
            required_tool_call = self._next_missing_required_tool(state)
            # 如果模型选择顺序跑偏或重复已满足工具，就由协议守卫补下一项必需工具。
            if required_tool_call and required_tool_call["name"] != tool_name:
                # 写入协议守卫标记。
                mark["protocol_required_tool"] = required_tool_call["name"]
                # 覆盖工具名。
                tool_name = required_tool_call["name"]
                # 覆盖工具参数。
                tool_args = required_tool_call["args"]
            # 2026-06-04 19:15:51 新增原因：证据工具已成功且没有缺失工具时，模型重复调工具会导致循环，必须收敛到最终回答。
            elif (
                not required_tool_call
                and (
                    # 2026-06-05 10:14:08 修改原因：证据工具重复调用时必须收敛到最终回答，避免循环。
                    (tool_name in {"sql_rag_retrieve", "sql_rag_graph_expand", "sql_rag_memory_read"} and self._tool_call_succeeded(state, tool_name))
                    # 2026-06-05 10:14:08 修改原因：业务审计或业务动作已满足时也不能重复调用，避免二次副作用。
                    or (tool_name == "sql_rag_business_action" and self._business_action_satisfied_for_question(state))
                )
            ):
                # 2026-06-04 19:15:51 新增原因：记录重复工具名，便于前端 trace 和纠错回放定位。
                mark["protocol_duplicate_tool"] = tool_name
                # 2026-06-04 19:15:51 新增原因：调用无工具最终回答提示，让模型基于 Prompt Builder 组织语言。
                final_decision = self._call_qwen_final_answer(state)
                # 2026-06-04 19:15:51 新增原因：刷新 Prompt Builder 上下文。
                mark["prompt_builder_context"] = final_decision.get("prompt_builder_context", mark.get("prompt_builder_context", ""))
                # 2026-06-08 17:35:42 修改原因：把最终模型答案质量结果写入 mark，防止 renderer 不知道答案是否等价。
                mark["final_answer_quality"] = final_decision.get("answer_quality", {})
                # 2026-06-08 17:35:42 修改原因：把最终模型答案质量结果写入 mark，防止 renderer 不知道答案是否等价。
                mark["final_answer_equivalence"] = final_decision.get("answer_equivalence", {})
                # 2026-06-09 09:12:31 Added: expose model answer shape normalization for WebUI audit.
                mark["answer_shape_normalization"] = final_decision.get("answer_shape_normalization", {})
                # 2026-06-05 17:32:11 新增原因：记录重复工具收敛后的真实答案来源。
                mark["draft_answer_source"] = final_decision.get("answer_source", "qwen_final_answer")
                # 2026-06-04 19:15:51 新增原因：追加公开 trace，说明为什么没有继续执行重复工具。
                mark = self._append_trace_event(
                    mark,
                    event_type="planner",
                    title="重复证据工具收敛",
                    detail=f"{tool_name} 已有成功结果，本轮改为直接组织最终答案。",
                    tool_name="qwen_planner",
                    payload={"duplicate_tool": tool_name},
                )
                # 2026-06-04 19:15:51 新增原因：返回草稿答案，不再进入工具执行。
                return {
                    **state,
                    "draft_answer": final_decision.get("content", ""),
                    "draft_answer_source": final_decision.get("answer_source", "qwen_final_answer"),
                    "pending_tool_call": {},
                    "mark": mark,
                }
            # 更新 mark 工具字段。
            mark["tool_name"] = tool_name
            # 更新 mark 工具参数。
            mark["tool_args"] = tool_args
            # 创建 LangChain Core 官方 AIMessage，作为 LangGraph 消息态的可审计桥接。
            AIMessage(content=decision.get("content", ""), tool_calls=[{"name": tool_name, "args": tool_args, "id": f"call_{state.get('tool_iterations', 0)}"}])
            # 返回待执行工具调用。
            return {
                **state,
                "pending_tool_call": {"name": tool_name, "args": tool_args},
                "mark": mark,
            }
        # 没有工具调用时，保存草稿答案。
        required_tool_call = self._next_missing_required_tool(state)
        # 如果模型准备直接回答，但用户显式要求的证据工具还没跑完，就补齐证据工具。
        if required_tool_call:
            # 写入协议守卫标记。
            mark["protocol_required_tool"] = required_tool_call["name"]
            # 写入工具名。
            mark["tool_name"] = required_tool_call["name"]
            # 写入工具参数。
            mark["tool_args"] = required_tool_call["args"]
            # 返回待执行工具调用。
            return {
                **state,
                "pending_tool_call": required_tool_call,
                "mark": mark,
            }
        # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
        model_content = str(decision.get("content", "") or "").strip()
        # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
        if model_content:
            # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
            draft_answer = model_content
            # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
            draft_answer_source = "qwen_planner_content"
        else:
            # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
            mark["model_empty_decision"] = bool(decision.get("model_empty_decision", True))
            # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
            final_decision = self._call_qwen_final_answer(state)
            # 2026-06-08 17:35:42 修改原因：把最终模型答案质量结果写入 mark，防止 renderer 不知道答案是否等价。
            mark["prompt_builder_context"] = final_decision.get("prompt_builder_context", mark.get("prompt_builder_context", ""))
            # 2026-06-08 17:35:42 修改原因：把最终模型答案质量结果写入 mark，防止 renderer 不知道答案是否等价。
            mark["final_answer_quality"] = final_decision.get("answer_quality", {})
            # 2026-06-08 17:35:42 修改原因：把最终模型答案质量结果写入 mark，防止 renderer 不知道答案是否等价。
            mark["final_answer_equivalence"] = final_decision.get("answer_equivalence", {})
            # 2026-06-09 09:12:31 Added: expose model answer shape normalization for WebUI audit.
            mark["answer_shape_normalization"] = final_decision.get("answer_shape_normalization", {})
            # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
            draft_answer = final_decision.get("content", "")
            # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
            draft_answer_source = final_decision.get("answer_source", "model_empty_final_answer")
            # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
            if final_decision.get("model_empty_final_answer"):
                # 2026-06-08 17:35:42 修改原因：planner 空答不再调用证据兜底，而是进入无工具最终回答并由质量门禁决定是否放行。
                mark["model_empty_final_answer"] = True
        mark["draft_answer_source"] = draft_answer_source
        return {
            **state,
            "draft_answer": draft_answer,
            "draft_answer_source": draft_answer_source,
            "pending_tool_call": {},
            "mark": mark,
        }

    def _tool_executor_node(self, state: AgentState) -> AgentState:
        # 标准化 mark。
        mark = self.correction_runtime.normalize_mark(state.get("mark"))
        # 读取工具调用。
        pending_tool_call = state.get("pending_tool_call", {})
        # 读取工具名。
        tool_name = pending_tool_call.get("name", "")
        # 读取工具参数。
        tool_args = pending_tool_call.get("args", {})
        # 工具不存在时写入失败。
        if tool_name not in self.tools:
            # 更新 mark。
            mark["tool_result_status"] = "unknown_tool"
            # 返回失败状态。
            return {
                **state,
                "pending_tool_call": {},
                "tool_iterations": state.get("tool_iterations", 0) + 1,
                "mark": mark,
            }
        # 为业务工具注入当前 LangGraph 上下文，保证动作真实归属到用户和线程。
        tool_args = self._prepare_tool_args_for_state(tool_name, tool_args, state)
        # 如果本轮已经有成功业务动作，拒绝重复执行有副作用的业务工具。
        if tool_name == "sql_rag_business_action" and self._business_action_succeeded(state, str(tool_args.get("action_name", ""))):
            # 标记工具状态仍为 ok，因为这是业务侧幂等防重，不是执行失败。
            mark["tool_result_status"] = "ok"
            # 记录防重事件，方便 mark 和 trace 定位。
            mark["duplicate_business_action_skipped"] = True
            # 清空待执行工具，并增加轮次，让 LangGraph 回到 planner 组织最终答案。
            return {
                **state,
                "pending_tool_call": {},
                "tool_iterations": state.get("tool_iterations", 0) + 1,
                "mark": mark,
            }
        # 调用 LlamaIndex 官方 Tool.call，并把异常也写入 mark，避免状态黑盒。
        try:
            # 2026-06-05 10:15:21 修改原因：工具执行必须先经过 FastMCP 网关，再由网关调用 LlamaIndex FunctionTool。
            result = self._call_tool_through_mcp_gateway(tool_name, tool_args)
        except Exception as exc:
            result = {
                "tool": tool_name,
                "status": "error",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        # 追加工具结果。
        tool_results = [*state.get("tool_results", []), {"tool_name": tool_name, "tool_args": tool_args, "result": result}]
        # 追加证据。
        evidence = [
            *state.get("evidence", []),
            *self._compact_evidence_for_verifier([{"tool_name": tool_name, "result": result}]),
        ]
        # 更新 mark。
        mark = self._merge_tool_result_into_mark(mark, tool_name, tool_args, result)
        # 返回更新状态。
        return {
            **state,
            "pending_tool_call": {},
            "tool_results": tool_results,
            "evidence": evidence,
            "tool_iterations": state.get("tool_iterations", 0) + 1,
            "mark": mark,
        }

    def _prepare_tool_args_for_state(self, tool_name: str, tool_args: dict[str, Any], state: AgentState) -> dict[str, Any]:
        # 图谱工具需要带上 RAG 召回 chunk_id，避免长 query LIKE 不命中实体关系表。
        if tool_name == "sql_rag_graph_expand":
            # 复制参数，避免原地修改模型输出。
            prepared_args = dict(tool_args or {})
            # 如果模型没传 source_chunk_ids，就用 mark 中的 RAG 召回结果。
            if not prepared_args.get("source_chunk_ids"):
                # 写入召回 chunk_id。
                prepared_args["source_chunk_ids"] = self.correction_runtime.normalize_mark(state.get("mark")).get("retrieved_chunk_ids", [])
            # 返回图谱工具参数。
            return prepared_args
        # 非业务工具不需要额外注入上下文。
        if tool_name != "sql_rag_business_action":
            return tool_args
        # 兼容模型把参数整体塞进 raw_arguments 的情况。
        prepared_args = dict(tool_args or {})
        action_args = prepared_args.get("action_args")
        if not isinstance(action_args, dict):
            action_args = {}
        # 注入不可由模型伪造的运行时上下文。
        action_args["_agent_context"] = {
            "user_id": state.get("user_id", "anonymous"),
            "thread_id": state.get("thread_id", "default"),
            "source_question": state.get("question", ""),
            "retrieved_chunk_ids": self.correction_runtime.normalize_mark(state.get("mark")).get("retrieved_chunk_ids", []),
            # 2026-06-05 18:10:08 新增原因：把 RAG top1 注入业务工具上下文，支持任意业务 chunk 的泛化摘要生成。
            "best_answer": self.correction_runtime.normalize_mark(state.get("mark")).get("best_answer", ""),
            "evidence_count": len(state.get("evidence", [])),
        }
        prepared_args["action_args"] = action_args
        # 如果模型没有给 action_name，就降级记录备注，仍然真实落库而不是空转。
        prepared_args.setdefault("action_name", "log_note")
        return prepared_args

    def _merge_tool_result_into_mark(self, mark: dict[str, Any], tool_name: str, tool_args: dict[str, Any], result: Any) -> dict[str, Any]:
        # 2026-06-05 10:15:21 新增原因：标记工具执行经过 MCP 网关桥，便于前端和纠错回放审计。
        mark["mcp_gateway_route"] = "fastmcp_in_process_gateway"
        # 标记工具执行状态。
        if isinstance(result, dict) and result.get("status"):
            raw_status = str(result.get("status"))
            mark["tool_result_status"] = "ok" if raw_status == "succeeded" else raw_status
        else:
            mark["tool_result_status"] = "ok"
        # RAG 工具写入召回 mark。
        if tool_name == "sql_rag_retrieve" and isinstance(result, dict):
            # 读取召回 query。
            mark["retrieval_query"] = str(result.get("query", tool_args.get("query", "")))
            # 读取结果列表。
            results = result.get("results", [])
            # 写入 chunk ids。
            mark["retrieved_chunk_ids"] = [item.get("chunk_id", "") for item in results if item.get("chunk_id")]
            # 写入全局聚类 ids。
            mark["global_cluster_ids"] = [item.get("global_cluster_id", "") for item in results if item.get("global_cluster_id")]
            # 写入 top1 直答证据。
            best_hit = result.get("best_hit") if isinstance(result.get("best_hit"), dict) else (results[0] if results else {})
            mark["best_answer"] = str(result.get("best_answer") or best_hit.get("answer_text") or best_hit.get("answer") or "")
            mark["best_answer_source_chunk_id"] = str(result.get("source_chunk_id") or best_hit.get("chunk_id") or "")
            # 写入最终答案证据 chunk ids。
            mark["answer_source_chunk_ids"] = [mark["best_answer_source_chunk_id"]] if mark["best_answer_source_chunk_id"] else mark["retrieved_chunk_ids"]
        # 图谱工具写入实体和边。
        if tool_name == "sql_rag_graph_expand" and isinstance(result, dict):
            # 写入实体。
            mark["kg_entities"] = result.get("entities", result.get("paths", []))
            # 写入边。
            mark["kg_edges"] = result.get("edges", [])
            # 2026-06-04 16:58:46 新增原因：写入图谱后端，前端明确看到 Neo4j 或 fallback。
            mark["kg_backend"] = result.get("backend", "")
            # 2026-06-04 16:58:46 新增原因：写入 Neo4j 三元组数量，供 trace 摘要展示。
            mark["kg_triple_count"] = len(result.get("triples", []) or [])
        # 记忆工具写入记忆读取 ids。
        if tool_name == "sql_rag_memory_read" and isinstance(result, dict):
            # 读取画像记忆。
            profile = result.get("structured_profile_memory", [])
            # 读取情景记忆。
            episodic = result.get("long_term_episodic_memory", [])
            # 合并记忆 ID。
            mark["memory_read_ids"] = [
                *(item.get("memory_id", "") for item in profile),
                *(item.get("memory_id", "") for item in episodic),
            ]
        # 业务工具写入执行结果和记忆事件。
        if tool_name == "sql_rag_business_action" and isinstance(result, dict):
            # 记录业务动作和关键业务 ID，便于后续纠错定位。
            mark["business_action_id"] = result.get("action_id", "")
            # 2026-06-05 18:10:08 修改原因：记录泛化业务意图，便于 trace 复盘业务工具是否返回语义上下文。
            mark["business_intent"] = result.get("business_intent", "")
            # 2026-06-05 17:32:11 新增原因：记录业务关注字段，Verifier 和数据飞轮可复盘答案覆盖缺口。
            mark["business_focus_terms"] = result.get("focus_terms", [])
            # 2026-06-05 17:32:11 新增原因：记录业务上下文摘要，前端不再只显示 query_tickets/succeeded。
            mark["business_context"] = result.get("business_context", [])
            # 2026-06-05 18:10:08 新增原因：记录业务工具消费的 RAG 锚点，支持跨 chunk 的泛化复盘。
            mark["business_best_answer"] = result.get("best_answer", "")
            mark["business_ticket_id"] = result.get("ticket_id", result.get("ticket", {}).get("ticket_id", "") if isinstance(result.get("ticket"), dict) else "")
            mark["business_handoff_id"] = result.get("handoff_id", "")
            mark["business_followup_id"] = result.get("followup_id", "")
            # 画像记忆写事件进入截图要求的 memory_write_event。
            if result.get("memory_write_event"):
                mark["memory_write_event"] = result.get("memory_write_event", {})
            # 业务执行失败时把失败原因写进 mark。
            if mark.get("tool_result_status") not in {"", "ok"}:
                mark["failure_reason"] = str(result.get("message") or result.get("error_message") or mark.get("tool_result_status"))
        # 2026-06-04 16:58:46 新增原因：根据工具类型构造公开 trace 事件标题。
        trace_title_map = {
            "sql_rag_retrieve": "RAG 召回完成",
            "sql_rag_graph_expand": "Neo4j 图谱扩展完成",
            "sql_rag_memory_read": "三层记忆读取完成",
            "sql_rag_business_action": "业务工具执行完成",
        }
        # 2026-06-04 16:58:46 新增原因：读取工具状态。
        trace_status = mark.get("tool_result_status", "ok")
        # 2026-06-04 16:58:46 新增原因：构造工具事件明细。
        if tool_name == "sql_rag_retrieve" and isinstance(result, dict):
            # 2026-06-04 16:58:46 新增原因：RAG 明细包含召回数量和 top1 chunk。
            trace_detail = f"召回 {len(result.get('results', []) or [])} 条 chunk，top1={mark.get('best_answer_source_chunk_id', '')}。"
        elif tool_name == "sql_rag_graph_expand" and isinstance(result, dict):
            # 2026-06-04 16:58:46 新增原因：图谱明细包含后端、路径数和三元组数。
            trace_detail = f"backend={result.get('backend', '')}，paths={len(result.get('paths', []) or [])}，triples={len(result.get('triples', []) or [])}。"
        elif tool_name == "sql_rag_memory_read" and isinstance(result, dict):
            # 2026-06-04 16:58:46 新增原因：记忆明细包含读取记忆数。
            trace_detail = f"读取 {len(mark.get('memory_read_ids', []) or [])} 条记忆引用。"
        elif tool_name == "sql_rag_business_action" and isinstance(result, dict):
            # 2026-06-04 16:58:46 新增原因：业务明细包含动作状态和关键 ID。
            trace_detail = f"action={result.get('action_name', '')}，status={result.get('status', '')}，intent={result.get('business_intent', '')}，ticket={mark.get('business_ticket_id', '')}。"
        else:
            # 2026-06-04 16:58:46 新增原因：未知工具保留状态摘要。
            trace_detail = f"工具状态：{trace_status}。"
        # 2026-06-04 16:58:46 新增原因：追加公开 trace 事件，供前端动态逐字展示。
        mark = self._append_trace_event(
            mark,
            event_type="tool_result",
            title=trace_title_map.get(tool_name, "工具执行完成"),
            detail=trace_detail,
            tool_name=tool_name,
            payload={"status": trace_status},
        )
        # 返回 mark。
        return mark

    def _verifier_node(self, state: AgentState) -> AgentState:
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        mark = self.correction_runtime.normalize_mark(state.get("mark"))
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        draft_answer = state.get("draft_answer", "")
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        if not draft_answer:
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            verifier_result = {"score": 0.0, "needs_human": True, "failure_reason": "empty_draft_answer"}
        else:
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            verifier_evidence = self._compact_evidence_for_verifier(state.get("evidence", []))
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            verifier_result = self.correction_runtime.verify_answer_with_qwen(qwen_llm=self.qwen_llm, question=state["question"], answer=draft_answer, evidence=verifier_evidence)
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        threshold = self.correction_runtime.config.verifier_threshold
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        low_confidence = float(verifier_result.get("score", 0.0) or 0.0) < threshold
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        if low_confidence:
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            mark["verifier_score"] = verifier_result.get("score", 0.0)
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            mark["failure_reason"] = verifier_result.get("failure_reason", "")
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            mark["correction_sample"] = self._record_low_confidence_sample(state, draft_answer, mark, verifier_result)
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            mark["flywheel_event"] = {"status": "recorded_low_confidence_sample", "branch": self.correction_runtime.locate_failure_branch(mark)}
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            repaired_state = self._repair_answer_after_verifier(state, draft_answer, verifier_result, mark)
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            if repaired_state:
                # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
                draft_answer = repaired_state.get("draft_answer", draft_answer)
                # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
                verifier_result = repaired_state.get("verifier_result", verifier_result)
                # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
                mark = repaired_state.get("mark", mark)
                # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
                state = {**state, "draft_answer": draft_answer, "draft_answer_source": repaired_state.get("draft_answer_source", state.get("draft_answer_source", "qwen_final_answer_retry")), "mark": mark}
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        mark["verifier_score"] = verifier_result.get("score", 0.0)
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        mark["failure_reason"] = verifier_result.get("failure_reason", "")
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        final_low_confidence = float(verifier_result.get("score", 0.0) or 0.0) < threshold
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        if final_low_confidence:
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            mark["final_action"] = "transfer_human"
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            mark["flywheel_event"] = mark.get("flywheel_event") or {"status": "recorded_low_confidence_sample", "branch": self.correction_runtime.locate_failure_branch(mark)}
        else:
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            mark["final_action"] = "answer"
            # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
            mark["flywheel_event"] = {"status": "verifier_repaired" if mark.get("verifier_repair_attempted") else "verifier_passed", "score": verifier_result.get("score", 0.0)}
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        mark = self._append_trace_event(
            mark,
            event_type="verifier",
            title='答案校验完成',
            detail=f"score={verifier_result.get('score', 0.0)}, needs_human={verifier_result.get('needs_human', False)}, reason={verifier_result.get('failure_reason', '')}",
            tool_name="answer_verifier",
            payload={"flywheel_event": mark.get("flywheel_event", {})},
        )
        # 2026-06-08 17:35:42 修改原因：verifier 低分后先记录数据飞轮样本，再回到模型修复并复验，不直接用人工模板覆盖。
        return {**state, "draft_answer": draft_answer, "verifier_result": verifier_result, "mark": mark}

    def _renderer_node(self, state: AgentState) -> AgentState:
        # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
        mark = self.correction_runtime.normalize_mark(state.get("mark"))
        # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
        verifier_result = state.get("verifier_result", {})
        # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
        answer_source = state.get("draft_answer_source") or mark.get("draft_answer_source") or ("qwen_planner_content" if state.get("draft_answer") else "rag_best_answer")
        # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
        if answer_source in {"qwen_final_answer", "qwen_final_answer_retry", "qwen_planner_content"} and not verifier_result.get("needs_human"):
            # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
            if not self._renderer_model_draft_is_verified(state, mark, verifier_result):
                # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
                verifier_result = {**verifier_result, "needs_human": True, "failure_reason": "unverified_model_draft"}
                # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
                mark["failure_reason"] = "unverified_model_draft"
                # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
                mark["final_action"] = "transfer_human"
        # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
        if mark.get("final_action") == "transfer_human" or verifier_result.get("needs_human"):
            # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
            handoff_result = self._ensure_transfer_handoff(state, mark)
            # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
            if handoff_result:
                # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
                mark["business_handoff_id"] = handoff_result.get("handoff_id", mark.get("business_handoff_id", ""))
            # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
            final_answer = '当前问题需要更多业务证据或人工确认，我不能在证据不足时直接给出确定结论。' + f"已定位可能跑偏分支：{self.correction_runtime.locate_failure_branch(mark)}。"
            # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
            final_action = "transfer_human"
        else:
            # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
            final_answer = state.get("draft_answer", "")
            # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
            final_action = "execute" if self._has_succeeded_business_action(state) else "answer"
        # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
        mark["final_action"] = final_action
        # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
        mark = self._append_trace_event(
            mark,
            event_type="renderer",
            title='最终答案生成',
            detail=f"final_action={final_action}, answer_source={answer_source}。",
            tool_name="final_answer_renderer",
            payload={"answer_source_chunk_ids": mark.get("answer_source_chunk_ids", []), "answer_source": answer_source},
        )
        # 2026-06-08 17:35:42 修改原因：renderer 出口复核模型草稿等价性，防止模型答对后被后处理改错或错答被放行。
        return {**state, "verifier_result": verifier_result, "final_answer": final_answer, "final_action": final_action, "mark": mark}

    def _has_succeeded_business_action(self, state: AgentState) -> bool:
        # 2026-06-05 10:16:03 修改原因：只有有副作用的业务动作成功时最终动作才是 execute。
        for tool_result in state.get("tool_results", []):
            if tool_result.get("tool_name") != "sql_rag_business_action":
                continue
            result = tool_result.get("result", {})
            # 2026-06-05 10:16:03 新增原因：只读查询只是必经业务审计，不代表替用户执行了业务处理。
            readonly_actions = {"query_tickets", "query_profile", "query_business_context"}
            # 2026-06-05 10:16:03 修改原因：排除只读审计动作后再判断 execute。
            if isinstance(result, dict) and result.get("status") == "succeeded" and result.get("action_name") not in readonly_actions:
                return True
        return False

    def _has_transfer_handoff(self, state: AgentState) -> bool:
        # 避免重复插入人工队列。
        for tool_result in state.get("tool_results", []):
            result = tool_result.get("result", {})
            if isinstance(result, dict) and result.get("handoff_id"):
                return True
        return False

    def _ensure_transfer_handoff(self, state: AgentState, mark: dict[str, Any]) -> dict[str, Any]:
        # 如果模型已经调用过转人工动作，就不重复创建。
        if self._has_transfer_handoff(state):
            return {}
        try:
            result = self.business_store.execute_action(
                action_name="transfer_human",
                action_args={
                    "subject": "低置信智能客服转人工",
                    "reason": mark.get("failure_reason") or "verifier_low_score",
                    "priority": "high",
                    "retrieved_chunk_ids": mark.get("retrieved_chunk_ids", []),
                },
                context={
                    "user_id": state.get("user_id", "anonymous"),
                    "thread_id": state.get("thread_id", "default"),
                    "source_question": state.get("question", ""),
                    "evidence_count": len(state.get("evidence", [])),
                },
            )
            mark["tool_result_status"] = "ok" if result.get("status") == "succeeded" else str(result.get("status", "error"))
            return result
        except Exception as exc:
            mark["tool_result_status"] = "transfer_handoff_error"
            mark["failure_reason"] = f"transfer_handoff_error: {type(exc).__name__}: {exc}"
            return {}

    def _record_low_confidence_sample(
        self,
        state: AgentState,
        answer: str,
        mark: dict[str, Any],
        verifier_result: dict[str, Any],
    ) -> dict[str, Any]:
        # 本地 SQL_RAG 纠错样本必须优先可用。
        failure_branch = self.correction_runtime.locate_failure_branch(mark)
        result: dict[str, Any] = {"failure_branch": failure_branch}
        try:
            result["local"] = self.business_store.record_failure_sample(
                user_id=state.get("user_id", "anonymous"),
                thread_id=state.get("thread_id", "default"),
                question=state.get("question", ""),
                answer=answer,
                failure_branch=failure_branch,
                verifier_score=float(verifier_result.get("score", 0.0) or 0.0),
                mark=mark,
                verifier_result=verifier_result,
            )
        except Exception as exc:
            result["local_error"] = f"{type(exc).__name__}: {exc}"
        # 配置了 LangSmith key 时同步到 LangSmith，否则本地表就是主飞轮入口。
        if os.getenv("LANGSMITH_API_KEY"):
            try:
                result["langsmith"] = self.correction_runtime.record_failure_example(
                    question=state.get("question", ""),
                    answer=answer,
                    mark=mark,
                    verifier_result=verifier_result,
                )
            except Exception as exc:
                result["langsmith_error"] = f"{type(exc).__name__}: {exc}"
        return result

    def _route_after_planner(self, state: AgentState) -> str:
        # 超过最大工具轮次时直接验证。
        if state.get("tool_iterations", 0) >= self.config.max_tool_iterations:
            # 返回 verifier。
            return "verifier"
        # 有待执行工具时进入工具节点。
        if state.get("pending_tool_call"):
            # 返回工具执行。
            return "tool_executor"
        # 否则进入 verifier。
        return "verifier"

    def _build_langgraph(self) -> Any:
        # 创建 LangGraph 官方 StateGraph。
        workflow = StateGraph(AgentState)
        # 添加 planner 节点。
        workflow.add_node("planner_intent_reasoner", self._planner_node)
        # 添加工具执行节点。
        workflow.add_node("tool_executor", self._tool_executor_node)
        # 添加 verifier 节点。
        workflow.add_node("answer_verifier", self._verifier_node)
        # 添加答案渲染节点。
        workflow.add_node("final_answer_renderer", self._renderer_node)
        # 从开始进入 planner。
        workflow.add_edge(START, "planner_intent_reasoner")
        # planner 后由模型决策是否调工具。
        workflow.add_conditional_edges(
            "planner_intent_reasoner",
            self._route_after_planner,
            {
                "tool_executor": "tool_executor",
                "verifier": "answer_verifier",
            },
        )
        # 工具结果回到 planner，让模型继续动态决策。
        workflow.add_edge("tool_executor", "planner_intent_reasoner")
        # verifier 后进入最终渲染。
        workflow.add_edge("answer_verifier", "final_answer_renderer")
        # 渲染后结束。
        workflow.add_edge("final_answer_renderer", END)
        # 编译 LangGraph，并接入三层记忆短期 checkpoint。
        return workflow.compile(checkpointer=self.memory_runtime.checkpointer, store=self.memory_runtime.store)

    def qdrant_check(self, question: str) -> dict[str, Any]:
        # 调用 LlamaIndex 官方 RAG 工具，检查 Qdrant 是否可消费。
        output = self.tools["sql_rag_retrieve"].call(query=question)
        # 返回 raw_output。
        return output.raw_output if output.raw_output is not None else {"content": output.content}

    def invoke(self, question: str, user_id: str, thread_id: str) -> dict[str, Any]:
        # 构造初始状态。
        initial_state: AgentState = {
            "user_id": user_id,
            "thread_id": thread_id,
            "question": question,
            "tool_results": [],
            "evidence": [],
            "tool_iterations": 0,
            "mark": self.correction_runtime.build_empty_mark(),
        }
        # 使用 LangGraph 官方 invoke，并传入 thread_id 让 checkpoint 生效。
        result = self.graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )
        # 2026-06-05 10:19:41 新增原因：标准化最终 mark，供响应和线程 trace 落盘共用。
        final_mark = self.correction_runtime.normalize_mark(result.get("mark"))
        # 2026-06-05 10:19:41 新增原因：非流式调用也按 thread_id 记录最终公开 trace。
        self._persist_thread_runtime_event(thread_id, {"type": "final_trace_snapshot", "trace_events": final_mark.get("public_trace_events", [])})
        # 返回最终结果。
        return {
            "question": question,
            "answer": result.get("final_answer", ""),
            "final_action": result.get("final_action", ""),
            "mark": final_mark,
            "verifier_result": self._public_verifier_result(result.get("verifier_result", {})),
            "tool_results": self._public_tool_results(result.get("tool_results", [])),
            # 2026-06-04 17:03:06 新增原因：顶层返回公开 trace events，前端实时解析过程不再写死。
            "trace_events": final_mark.get("public_trace_events", []),
        }

    def invoke_stream(self, question: str, user_id: str, thread_id: str) -> Any:
        # 2026-06-04 17:10:39 新增原因：构造初始状态，供 LangGraph stream 逐节点返回。
        initial_state: AgentState = {
            "user_id": user_id,
            "thread_id": thread_id,
            "question": question,
            "tool_results": [],
            "evidence": [],
            "tool_iterations": 0,
            "mark": self.correction_runtime.build_empty_mark(),
        }
        # 2026-06-04 17:10:39 新增原因：记录已发送 trace event 数量，避免重复推送。
        emitted_event_count = 0
        # 2026-06-04 17:10:39 新增原因：保存最终状态。
        final_state: AgentState = initial_state
        # 2026-06-04 17:10:39 新增原因：使用 LangGraph 官方 stream 逐步观察节点输出。
        for state_snapshot in self.graph.stream(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="values",
        ):
            # 2026-06-04 17:10:39 新增原因：保存最新状态。
            final_state = state_snapshot
            # 2026-06-04 17:10:39 新增原因：标准化 mark。
            mark = self.correction_runtime.normalize_mark(state_snapshot.get("mark"))
            # 2026-06-04 17:10:39 新增原因：读取公开 trace events。
            trace_events = mark.get("public_trace_events", [])
            # 2026-06-04 17:10:39 新增原因：只处理列表事件。
            if not isinstance(trace_events, list):
                # 2026-06-04 17:10:39 新增原因：异常类型跳过。
                continue
            # 2026-06-04 17:10:39 新增原因：逐条发送新增事件。
            for event in trace_events[emitted_event_count:]:
                # 2026-06-05 10:19:41 新增原因：把前端即将看到的 trace 同步落盘到 thread 级 NDJSON。
                self._persist_thread_runtime_event(thread_id, {"type": "trace", "event": event})
                # 2026-06-04 17:10:39 新增原因：输出 trace 事件。
                yield {"type": "trace", "event": event}
            # 2026-06-04 17:10:39 新增原因：更新已发送数量。
            emitted_event_count = len(trace_events)
        # 2026-06-04 17:10:39 新增原因：标准化最终 mark。
        final_mark = self.correction_runtime.normalize_mark(final_state.get("mark"))
        # 2026-06-04 17:10:39 新增原因：构造最终完整响应。
        result = {
            "question": question,
            "answer": final_state.get("final_answer", ""),
            "final_action": final_state.get("final_action", ""),
            "mark": final_mark,
            "verifier_result": self._public_verifier_result(final_state.get("verifier_result", {})),
            "tool_results": self._public_tool_results(final_state.get("tool_results", [])),
            "trace_events": final_mark.get("public_trace_events", []),
        }
        # 2026-06-05 10:19:41 新增原因：把最终响应摘要也落盘，便于按 thread_id 复盘最终动作和工具摘要。
        self._persist_thread_runtime_event(thread_id, {"type": "final", "result": result})
        # 2026-06-04 17:10:39 新增原因：发送最终结果。
        yield {"type": "final", "result": result}
