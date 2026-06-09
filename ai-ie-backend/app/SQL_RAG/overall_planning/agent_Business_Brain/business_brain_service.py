# -*- coding: utf-8 -*-
"""SQL_RAG 商业级智能客服业务脑 FastAPI 服务。"""

# 修改日期：2026-06-03 10:38:00。
# 修改理由：按统一框架标准补齐可部署的业务脑服务入口，让 LangGraph 业务脑以 HTTP API 方式消费本地 Qwen3.5 OpenAI-compatible 模型服务。

# 导入 argparse，用于构建业务脑服务子命令。
import argparse
# 导入 JSON，用于命令行健康检查输出。
import json
# 导入 sys，用于 Windows 终端 UTF-8 输出。
import sys
# 导入 Lock，用于保护 BusinessBrainRuntime 单例初始化。
from threading import Lock
# 导入 dataclass，用于封装运行时资源。
from dataclasses import dataclass
# 导入 Path，用于定位 SQL_RAG 根目录。
from pathlib import Path
# 导入 Any 和 Sequence，用于接口和命令行参数标注。
from typing import Any, Sequence

# 导入 FastAPI 官方服务类。
from fastapi import FastAPI, HTTPException
# 2026-06-04 17:12:26 新增原因：导入 StreamingResponse，向前端实时输出 trace events。
from fastapi.responses import StreamingResponse
# 导入 Pydantic，用于定义商业级服务请求契约。
from pydantic import BaseModel, Field

# 导入 Neo4j 官方驱动，用于健康检查可选图谱后端。
from neo4j import GraphDatabase
# 导入 pyodbc 官方 SQL Server 驱动，用于健康检查业务动作落库通道。
import pyodbc
# 导入 Qdrant 官方客户端，用于健康检查 RAG collection。
from qdrant_client import QdrantClient

# 导入模型服务健康检查函数。
from module_config.model_service.model_service_runtime import check_openai_compatible_models
# 导入纠错飞轮运行时。
from overall_planning.Answer_correction import AnswerCorrectionRuntime, load_correction_config
# 导入三层记忆运行时。
from overall_planning.long_memory import ThreeLayerMemoryRuntime, load_memory_config
# 导入业务脑核心运行时。
from overall_planning.agent_Business_Brain.business_brain_runtime import (
    BusinessBrainRuntime,
    load_business_brain_config,
)

# 定位当前文件所在目录。
CURRENT_DIR = Path(__file__).resolve().parent
# 定位 overall_planning 目录。
OVERALL_PLANNING_DIR = CURRENT_DIR.parent
# 定位 SQL_RAG 根目录。
SQL_RAG_DIR = OVERALL_PLANNING_DIR.parent

# Windows 终端默认 GBK 时可能无法打印模型返回的中文，这里统一切到 UTF-8。
if hasattr(sys.stdout, "reconfigure"):
    # 只影响当前进程标准输出。
    sys.stdout.reconfigure(encoding="utf-8")


class BusinessBrainChatRequest(BaseModel):
    # 定义用户问题，真实业务调用必须传入。
    question: str = Field(min_length=1, description="用户输入的复杂业务问题。")
    # 定义用户 ID，用于画像记忆、工单和转人工队列隔离。
    user_id: str = Field(default="anonymous", min_length=1, description="业务用户 ID。")
    # 定义线程 ID，用于 LangGraph checkpoint 短期工作记忆。
    thread_id: str = Field(default="default", min_length=1, description="会话线程 ID。")
    # 定义可选元数据，预留给上层客服系统传订单、渠道或租户信息。
    metadata: dict[str, Any] = Field(default_factory=dict, description="上层业务系统透传元数据。")


class QdrantCheckRequest(BaseModel):
    # 定义检索检查问题。
    question: str = Field(min_length=1, description="用于检查 Qdrant 召回链路的问题。")


@dataclass
class BusinessBrainRuntimeBundle:
    # 保存三层记忆运行时。
    memory_runtime: ThreeLayerMemoryRuntime
    # 保存纠错飞轮运行时。
    correction_runtime: AnswerCorrectionRuntime
    # 保存业务脑运行时。
    business_runtime: BusinessBrainRuntime
    # 记录该 bundle 是否创建了 Qwen 模型连接。
    require_qwen: bool

    def close(self) -> None:
        # 关闭记忆层持有的 Neo4j 和 Postgres checkpoint 资源。
        self.memory_runtime.close()


class BusinessBrainServiceManager:
    # 保存 SQL_RAG 根目录。
    sql_rag_dir: Path
    # 保存完整业务脑运行时 bundle。
    _full_bundle: BusinessBrainRuntimeBundle | None
    # 保存只用于 Qdrant 检查的运行时 bundle。
    _qdrant_bundle: BusinessBrainRuntimeBundle | None
    # 保存单例初始化锁。
    _lock: Lock

    def __init__(self, sql_rag_dir: Path = SQL_RAG_DIR) -> None:
        # 保存 SQL_RAG 根目录。
        self.sql_rag_dir = sql_rag_dir
        # 初始化完整业务脑 bundle。
        self._full_bundle = None
        # 初始化 Qdrant 检查 bundle。
        self._qdrant_bundle = None
        # 初始化互斥锁。
        self._lock = Lock()

    def _build_bundle(self, require_qwen: bool) -> BusinessBrainRuntimeBundle:
        # 先读取业务脑配置，内部会固定加载 SQL_RAG/.env。
        business_config = load_business_brain_config(self.sql_rag_dir)
        # 读取三层记忆配置。
        memory_config = load_memory_config()
        # 读取纠错飞轮配置。
        correction_config = load_correction_config()
        # 创建三层记忆运行时。
        memory_runtime = ThreeLayerMemoryRuntime(memory_config)
        # 创建纠错飞轮运行时。
        correction_runtime = AnswerCorrectionRuntime(correction_config)
        # 创建 LangGraph + Qwen-Agent + LlamaIndex/Qdrant 业务脑运行时。
        business_runtime = BusinessBrainRuntime(
            config=business_config,
            memory_runtime=memory_runtime,
            correction_runtime=correction_runtime,
            require_qwen=require_qwen,
        )
        # 返回运行时 bundle。
        return BusinessBrainRuntimeBundle(
            memory_runtime=memory_runtime,
            correction_runtime=correction_runtime,
            business_runtime=business_runtime,
            require_qwen=require_qwen,
        )

    def get_bundle(self, require_qwen: bool) -> BusinessBrainRuntimeBundle:
        # 使用锁保护运行时单例初始化。
        with self._lock:
            # 完整业务脑请求优先复用 full bundle。
            if require_qwen:
                # full bundle 不存在时创建。
                if self._full_bundle is None:
                    # 创建完整业务脑运行时。
                    self._full_bundle = self._build_bundle(require_qwen=True)
                # 返回完整业务脑运行时。
                return self._full_bundle
            # 只做 Qdrant 检查时复用 qdrant bundle。
            if self._qdrant_bundle is None:
                # 创建不连接 Qwen 的轻量检查运行时。
                self._qdrant_bundle = self._build_bundle(require_qwen=False)
            # 返回 Qdrant 检查运行时。
            return self._qdrant_bundle

    def invoke_chat(self, request: BusinessBrainChatRequest) -> dict[str, Any]:
        # 获取完整业务脑运行时。
        bundle = self.get_bundle(require_qwen=True)
        # 调用 LangGraph Agent Runtime。
        result = bundle.business_runtime.invoke(
            question=request.question,
            user_id=request.user_id,
            thread_id=request.thread_id,
        )
        # 写入服务层元数据，便于上层接口审计。
        result["service_metadata"] = {
            "metadata": request.metadata,
            "runtime": "langgraph_qwen_agent_sql_rag_business_brain",
        }
        # 返回业务脑结果。
        return result

    def invoke_chat_stream(self, request: BusinessBrainChatRequest) -> Any:
        # 2026-06-04 17:12:26 新增原因：获取完整业务脑运行时。
        bundle = self.get_bundle(require_qwen=True)
        # 2026-06-04 17:12:26 新增原因：逐步转发 LangGraph trace 和最终结果。
        for event in bundle.business_runtime.invoke_stream(
            question=request.question,
            user_id=request.user_id,
            thread_id=request.thread_id,
        ):
            # 2026-06-04 17:12:26 新增原因：给最终结果补服务层元数据。
            if event.get("type") == "final" and isinstance(event.get("result"), dict):
                # 2026-06-04 17:12:26 新增原因：写入服务层元数据。
                event["result"]["service_metadata"] = {
                    "metadata": request.metadata,
                    "runtime": "langgraph_qwen_agent_sql_rag_business_brain_stream",
                }
            # 2026-06-04 17:12:26 新增原因：输出事件。
            yield event

    def qdrant_check(self, request: QdrantCheckRequest) -> dict[str, Any]:
        # 获取不连接 Qwen 的 Qdrant 检查运行时。
        bundle = self.get_bundle(require_qwen=False)
        # 调用 LlamaIndex + Qdrant 检索链路。
        return bundle.business_runtime.qdrant_check(question=request.question)

    def _sqlserver_connection_string(self) -> str:
        # 读取业务脑配置。
        config = load_business_brain_config(self.sql_rag_dir)
        # 拼接 SQL Server 连接串。
        return (
            f"DRIVER={{{config.sql_driver}}};"
            f"SERVER={config.sql_server};"
            f"DATABASE={config.sql_database};"
            f"UID={config.sql_user};"
            f"PWD={config.sql_password};"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )

    def _check_model_service(self) -> dict[str, Any]:
        # 读取业务脑配置。
        config = load_business_brain_config(self.sql_rag_dir)
        # 调用 OpenAI-compatible /v1/models 健康检查。
        check = check_openai_compatible_models(
            model_server=config.qwen_model_server,
            api_key=config.qwen_api_key,
            timeout=5.0,
        )
        # 写入期望模型名。
        check["expected_model"] = config.qwen_model
        # 写入模型服务地址。
        check["model_server"] = config.qwen_model_server
        # 返回检查结果。
        return check

    def _check_embedding_config(self) -> dict[str, Any]:
        # 读取业务脑配置。
        config = load_business_brain_config(self.sql_rag_dir)
        # 判断 embedding key 是否存在。
        has_key = bool(config.embedding_api_key)
        # 返回 embedding 配置状态。
        return {
            "ready": has_key and bool(config.embedding_api_base) and bool(config.embedding_model),
            "api_base": config.embedding_api_base,
            "model": config.embedding_model,
            "dimension": config.embedding_dimension,
            "has_api_key": has_key,
        }

    def _check_qdrant(self) -> dict[str, Any]:
        # 读取业务脑配置。
        config = load_business_brain_config(self.sql_rag_dir)
        # 尝试连接 Qdrant。
        try:
            # 创建 Qdrant 官方客户端。
            # 2026-06-06 11:30:19 修改原因：禁用本进程读取系统代理环境，避免 no_proxy IPv6 CIDR 影响本地 Qdrant 健康检查。
            client = QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key or None, timeout=5, trust_env=False)
            # 优先使用 collection_exists 检查 collection。
            if hasattr(client, "collection_exists"):
                # 读取 collection 是否存在。
                exists = bool(client.collection_exists(config.qdrant_collection))
            # 旧客户端没有 collection_exists 时用 get_collection 兜底。
            else:
                # 查询 collection 信息。
                client.get_collection(config.qdrant_collection)
                # 查询成功即存在。
                exists = True
            # 返回 Qdrant 可用状态。
            return {
                "ready": exists,
                "url": config.qdrant_url,
                "collection": config.qdrant_collection,
                "status": "ok" if exists else "missing_collection",
            }
        except Exception as exc:
            # 返回 Qdrant 异常状态。
            return {
                "ready": False,
                "url": config.qdrant_url,
                "collection": config.qdrant_collection,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _check_sqlserver(self) -> dict[str, Any]:
        # 尝试连接 SQL Server。
        try:
            # 打开 SQL Server 连接。
            with pyodbc.connect(self._sqlserver_connection_string(), timeout=5) as connection:
                # 执行轻量 SELECT 1。
                row = connection.cursor().execute("SELECT 1 AS ok").fetchone()
            # 返回 SQL Server 可用状态。
            return {"ready": bool(row and row.ok == 1), "status": "ok"}
        except Exception as exc:
            # 返回 SQL Server 异常状态。
            return {"ready": False, "status": "error", "error": f"{type(exc).__name__}: {exc}"}

    def _check_neo4j(self) -> dict[str, Any]:
        # 读取业务脑配置。
        config = load_business_brain_config(self.sql_rag_dir)
        # 未启用 Neo4j 图谱后端时标记为跳过。
        if config.graph_backend != "neo4j":
            # 返回跳过状态。
            return {"ready": True, "status": "skipped", "backend": config.graph_backend}
        # Neo4j 必填配置缺失时返回未配置。
        if not config.neo4j_uri or not config.neo4j_password:
            # 返回未配置状态。
            return {"ready": False, "status": "not_configured", "backend": "neo4j"}
        # 尝试验证 Neo4j 连接。
        try:
            # 创建 Neo4j driver。
            driver = GraphDatabase.driver(config.neo4j_uri, auth=(config.neo4j_user, config.neo4j_password))
            # 验证连通性。
            driver.verify_connectivity()
            # 关闭 driver。
            driver.close()
            # 返回可用状态。
            return {"ready": True, "status": "ok", "backend": "neo4j", "uri": config.neo4j_uri}
        except Exception as exc:
            # 返回 Neo4j 异常状态。
            return {"ready": False, "status": "error", "backend": "neo4j", "error": f"{type(exc).__name__}: {exc}"}

    def health(self) -> dict[str, Any]:
        # 检查模型服务。
        model_service = self._check_model_service()
        # 检查 embedding 配置。
        embedding = self._check_embedding_config()
        # 检查 Qdrant。
        qdrant = self._check_qdrant()
        # 检查 SQL Server。
        sqlserver = self._check_sqlserver()
        # 检查可选 Neo4j。
        neo4j = self._check_neo4j()
        # 汇总检查项。
        checks = {
            "qwen_openai_compatible_service": model_service,
            "embedding_config": embedding,
            "qdrant": qdrant,
            "sqlserver": sqlserver,
            "neo4j": neo4j,
        }
        # 必需检查项必须全部 ready。
        ready = all(
            bool(checks[name].get("ready"))
            for name in [
                "qwen_openai_compatible_service",
                "embedding_config",
                "qdrant",
                "sqlserver",
            ]
        )
        # 返回商业级健康检查摘要。
        return {
            "ready": ready,
            "service": "sql_rag_business_brain",
            "orchestrator": "LangGraph",
            "planner": "Qwen-Agent via OpenAI-compatible Qwen service",
            "checks": checks,
        }

    def tool_manifest(self) -> dict[str, Any]:
        # 返回业务脑统一工具契约。
        return {
            "orchestrator": "LangGraph Agent Runtime",
            "tools": [
                {
                    "name": "sql_rag_retrieve",
                    "role": "LlamaIndex + Qdrant 语义召回 SQL_RAG chunk。",
                },
                {
                    "name": "sql_rag_graph_expand",
                    # 2026-06-04 18:03:41 新增原因：公开工具清单必须说明当前主链是 Neo4j 多跳三元组图谱，避免继续误导成 SQL Server mention 表或 PropertyGraph。
                    "role": "Neo4j SQL_RAG 多跳三元组图谱扩展；未配置 Neo4j 时才退回 SQL Server mention 表兜底。",
                },
                {
                    "name": "sql_rag_memory_read",
                    "role": "读取 LangGraph checkpoint、画像记忆和 Graphiti 情景记忆。",
                },
                {
                    "name": "sql_rag_business_action",
                    "role": "执行工单、转人工、跟进、画像和备注等本地业务动作。",
                },
            ],
            "final_actions": ["answer", "clarify", "transfer_human", "execute"],
        }

    def close(self) -> None:
        # 使用锁保护关闭过程。
        with self._lock:
            # 关闭完整业务脑运行时。
            if self._full_bundle is not None:
                # 释放完整业务脑资源。
                self._full_bundle.close()
                # 清空引用。
                self._full_bundle = None
            # 关闭 Qdrant 检查运行时。
            if self._qdrant_bundle is not None:
                # 释放 Qdrant 检查资源。
                self._qdrant_bundle.close()
                # 清空引用。
                self._qdrant_bundle = None


def create_business_brain_app(sql_rag_dir: Path = SQL_RAG_DIR, eager_start: bool = False) -> FastAPI:
    # 创建服务管理器。
    manager = BusinessBrainServiceManager(sql_rag_dir=sql_rag_dir)
    # 创建 FastAPI 应用。
    app = FastAPI(
        title="SQL_RAG Business Brain Service",
        version="1.0.0",
        description="LangGraph + Qwen-Agent + LlamaIndex/Qdrant + SQL Server 的智能客服业务脑服务。",
    )
    # 把服务管理器挂到 app.state，方便生命周期关闭。
    app.state.business_brain_manager = manager

    @app.on_event("startup")
    def startup_business_brain() -> None:
        # 如果指定 eager_start，则启动时创建完整 BusinessBrainRuntime。
        if eager_start:
            # 预热完整业务脑运行时。
            manager.get_bundle(require_qwen=True)

    @app.on_event("shutdown")
    def shutdown_business_brain() -> None:
        # 关闭运行时持有的长连接资源。
        manager.close()

    @app.get("/agent/business-brain/health")
    def get_business_brain_health() -> dict[str, Any]:
        # 返回商业级健康检查结果。
        return manager.health()

    @app.get("/agent/business-brain/tools")
    def get_business_brain_tools() -> dict[str, Any]:
        # 返回工具契约，供前端或外部系统自检。
        return manager.tool_manifest()

    @app.post("/agent/business-brain/qdrant-check")
    def post_qdrant_check(request: QdrantCheckRequest) -> dict[str, Any]:
        # 捕获底层召回异常并转成 HTTP 错误。
        try:
            # 调用 Qdrant 检索检查。
            return manager.qdrant_check(request)
        except Exception as exc:
            # 返回标准 500 错误。
            raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc

    @app.post("/agent/business-brain/chat")
    def post_business_brain_chat(request: BusinessBrainChatRequest) -> dict[str, Any]:
        # 捕获底层 Agent 异常并转成 HTTP 错误。
        try:
            # 调用完整 LangGraph 业务脑。
            return manager.invoke_chat(request)
        except Exception as exc:
            # 返回标准 500 错误。
            raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc

    @app.post("/agent/business-brain/chat-stream")
    def post_business_brain_chat_stream(request: BusinessBrainChatRequest) -> StreamingResponse:
        # 2026-06-04 17:12:26 新增原因：定义 NDJSON 生成器，前端可按行读取 trace。
        def event_stream() -> Any:
            # 2026-06-04 17:12:26 新增原因：捕获底层 Agent 异常并用 error 事件返回。
            try:
                # 2026-06-04 17:12:26 新增原因：遍历业务脑流式事件。
                for event in manager.invoke_chat_stream(request):
                    # 2026-06-04 17:12:26 新增原因：每个事件单独 JSON 行输出。
                    yield json.dumps(event, ensure_ascii=False, default=str) + "\n"
            except Exception as exc:
                # 2026-06-04 17:12:26 新增原因：异常也以 NDJSON 输出，避免前端黑屏。
                yield json.dumps({"type": "error", "detail": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False) + "\n"

        # 2026-06-04 17:12:26 新增原因：返回流式响应。
        return StreamingResponse(event_stream(), media_type="application/x-ndjson; charset=utf-8")

    # 返回 FastAPI 应用。
    return app


def build_business_brain_service_arg_parser() -> argparse.ArgumentParser:
    # 创建业务脑服务命令行解析器。
    parser = argparse.ArgumentParser(description="启动 SQL_RAG 商业级智能客服业务脑 FastAPI 服务。")
    # 添加服务 host。
    parser.add_argument("--host", default="0.0.0.0", help="业务脑服务监听地址。")
    # 添加服务端口。
    parser.add_argument("--port", type=int, default=18180, help="业务脑服务监听端口。")
    # 添加是否启动时预热完整 Agent。
    parser.add_argument("--eager-start", action="store_true", help="启动时立即创建 BusinessBrainRuntime 并检查模型服务。")
    # 返回解析器。
    return parser


def run_business_brain_service_cli(argv: Sequence[str], sql_rag_dir: Path = SQL_RAG_DIR) -> int:
    # 延迟导入 uvicorn，避免仅做 CLI 健康检查时加载 ASGI server。
    import uvicorn
    # 构建解析器。
    parser = build_business_brain_service_arg_parser()
    # 解析参数。
    args = parser.parse_args(list(argv))
    # 创建 FastAPI 应用。
    app = create_business_brain_app(sql_rag_dir=sql_rag_dir, eager_start=args.eager_start)
    # 启动 uvicorn 服务。
    uvicorn.run(app, host=args.host, port=args.port)
    # uvicorn 正常退出时返回成功。
    return 0


def build_business_brain_health_arg_parser() -> argparse.ArgumentParser:
    # 创建业务脑健康检查解析器。
    parser = argparse.ArgumentParser(description="检查 SQL_RAG 商业级业务脑依赖是否就绪。")
    # 添加是否忽略失败退出码。
    parser.add_argument("--ignore-fail", action="store_true", help="健康检查失败时仍返回 0，便于本地查看 JSON。")
    # 返回解析器。
    return parser


def run_business_brain_health_cli(argv: Sequence[str], sql_rag_dir: Path = SQL_RAG_DIR) -> int:
    # 构建解析器。
    parser = build_business_brain_health_arg_parser()
    # 解析参数。
    args = parser.parse_args(list(argv))
    # 创建服务管理器。
    manager = BusinessBrainServiceManager(sql_rag_dir=sql_rag_dir)
    # 执行健康检查。
    result = manager.health()
    # 打印 JSON 健康检查。
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 返回健康状态退出码。
    return 0 if result.get("ready") or args.ignore_fail else 2
