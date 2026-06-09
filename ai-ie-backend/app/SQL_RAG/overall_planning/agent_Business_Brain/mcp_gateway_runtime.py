# -*- coding: utf-8 -*-
"""SQL_RAG MCP Gateway 运行时入口。"""

# 修改日期：2026-06-03 15:45:00。
# 修改理由：补齐截图第 1 点要求的 MCP 工具标准化运行入口，让外部 Agent 或业务系统能真实调用 SQL_RAG 四类工具。

# 导入 argparse，用于构建 MCP 网关命令行入口。
import argparse
# 导入 asyncio，用于调用 FastMCP 官方异步工具列表和工具调用接口。
import asyncio
# 导入 JSON，用于打印网关自检和烟测结果。
import json
# 导入 sys，用于保证直接执行时包路径稳定。
import sys
# 导入 dataclass，用于封装 MCP 网关运行时资源。
from dataclasses import dataclass
# 导入 Path，用于定位 SQL_RAG 根目录。
from pathlib import Path
# 导入 Any 和 Sequence，用于接口参数标注。
from typing import Any, Sequence

# 导入 MCP 官方 FastMCP 类型。
from mcp.server.fastmcp import FastMCP

# 定位当前文件所在目录。
CURRENT_DIR = Path(__file__).resolve().parent
# 定位 overall_planning 目录。
OVERALL_PLANNING_DIR = CURRENT_DIR.parent
# 定位 SQL_RAG 根目录。
SQL_RAG_DIR = OVERALL_PLANNING_DIR.parent
# 直接从当前文件导入时补充 SQL_RAG 根目录。
if str(SQL_RAG_DIR) not in sys.path:
    # 插入到模块搜索路径最前面。
    sys.path.insert(0, str(SQL_RAG_DIR))

# 导入纠错飞轮运行时。
from overall_planning.Answer_correction import AnswerCorrectionRuntime, load_correction_config
# 导入三层记忆运行时。
from overall_planning.long_memory import ThreeLayerMemoryRuntime, load_memory_config
# 导入业务脑核心运行时和配置。
from overall_planning.agent_Business_Brain.business_brain_runtime import BusinessBrainRuntime, load_business_brain_config
# 导入 MCP 网关构建器。
from overall_planning.agent_Business_Brain.mcp_gateway import build_sql_rag_mcp_gateway


@dataclass
class McpGatewayRuntimeBundle:
    # 保存三层记忆运行时。
    memory_runtime: ThreeLayerMemoryRuntime
    # 保存纠错飞轮运行时。
    correction_runtime: AnswerCorrectionRuntime
    # 保存业务脑运行时。
    business_runtime: BusinessBrainRuntime
    # 保存 FastMCP 网关实例。
    mcp_gateway: FastMCP

    def close(self) -> None:
        # 关闭记忆层持有的 Neo4j 和 Postgres checkpoint 资源。
        self.memory_runtime.close()


def _raw_tool_output(tool_output: Any) -> Any:
    # LlamaIndex ToolOutput 有 raw_output 时优先返回结构化结果。
    if hasattr(tool_output, "raw_output") and tool_output.raw_output is not None:
        # 返回原始结构化输出。
        return tool_output.raw_output
    # ToolOutput 没有 raw_output 时兼容 content 文本。
    if hasattr(tool_output, "content"):
        # 返回 content 字段。
        return tool_output.content
    # 其他对象原样返回。
    return tool_output


def _call_runtime_tool(business_runtime: BusinessBrainRuntime, tool_name: str, **tool_args: Any) -> dict[str, Any]:
    # 从 BusinessBrainRuntime 的统一工具注册表读取工具。
    tool = business_runtime.tools[tool_name]
    # 调用 LlamaIndex 官方 FunctionTool。
    tool_output = tool.call(**tool_args)
    # 返回标准化后的工具结果。
    return _raw_tool_output(tool_output)


def build_mcp_gateway_runtime(
    sql_rag_dir: Path = SQL_RAG_DIR,
    host: str = "127.0.0.1",
    port: int = 18181,
    mount_path: str = "/mcp",
) -> McpGatewayRuntimeBundle:
    # 先读取业务脑配置，内部会固定加载 SQL_RAG/.env。
    business_config = load_business_brain_config(sql_rag_dir)
    # 再读取记忆配置，确保 .env 里的记忆参数已经进入环境变量。
    memory_config = load_memory_config()
    # 读取纠错飞轮配置。
    correction_config = load_correction_config()
    # 创建三层记忆运行时。
    memory_runtime = ThreeLayerMemoryRuntime(memory_config)
    # 创建纠错飞轮运行时。
    correction_runtime = AnswerCorrectionRuntime(correction_config)
    # 创建业务脑运行时；MCP 网关只暴露工具，不需要 Qwen 自己参与规划。
    business_runtime = BusinessBrainRuntime(
        config=business_config,
        memory_runtime=memory_runtime,
        correction_runtime=correction_runtime,
        require_qwen=False,
    )
    # 用同一个业务脑工具注册表包装 MCP RAG 召回工具。
    def rag_retrieve(query: str) -> dict[str, Any]:
        # 调用业务脑统一 RAG 工具。
        return _call_runtime_tool(business_runtime, "sql_rag_retrieve", query=query)

    # 用同一个业务脑工具注册表包装 MCP 图谱扩展工具。
    def graph_expand(query: str, entity_hint: str = "", source_chunk_ids: list[str] | None = None) -> dict[str, Any]:
        # 调用业务脑统一图谱工具。
        return _call_runtime_tool(
            business_runtime,
            "sql_rag_graph_expand",
            query=query,
            entity_hint=entity_hint,
            source_chunk_ids=source_chunk_ids or [],
        )

    # 用同一个业务脑工具注册表包装 MCP 记忆读取工具。
    def memory_read(user_id: str, query: str) -> dict[str, Any]:
        # 调用业务脑统一三层记忆工具。
        return _call_runtime_tool(business_runtime, "sql_rag_memory_read", user_id=user_id, query=query)

    # 用同一个业务脑工具注册表包装 MCP 业务动作工具。
    def business_action(action_name: str, action_args: dict[str, Any]) -> dict[str, Any]:
        # 调用业务脑统一业务动作工具。
        return _call_runtime_tool(business_runtime, "sql_rag_business_action", action_name=action_name, action_args=action_args)

    # 构建 FastMCP 网关实例。
    mcp_gateway = build_sql_rag_mcp_gateway(
        rag_retrieve=rag_retrieve,
        graph_expand=graph_expand,
        memory_read=memory_read,
        business_action=business_action,
        host=host,
        port=port,
        mount_path=mount_path,
    )
    # 返回完整运行时 bundle。
    return McpGatewayRuntimeBundle(
        memory_runtime=memory_runtime,
        correction_runtime=correction_runtime,
        business_runtime=business_runtime,
        mcp_gateway=mcp_gateway,
    )


def _serialize_mcp_tool(tool: Any) -> dict[str, Any]:
    # Pydantic v2 工具对象优先用 model_dump。
    if hasattr(tool, "model_dump"):
        # 导出工具结构。
        raw_tool = tool.model_dump()
    # Pydantic v1 工具对象兼容 dict。
    elif hasattr(tool, "dict"):
        # 导出工具结构。
        raw_tool = tool.dict()
    # 普通对象降级读取常见属性。
    else:
        # 构造最小工具结构。
        raw_tool = {
            "name": getattr(tool, "name", ""),
            "description": getattr(tool, "description", ""),
            "inputSchema": getattr(tool, "inputSchema", {}),
        }
    # 返回统一字段。
    return {
        "name": raw_tool.get("name", ""),
        "description": raw_tool.get("description", ""),
        "input_schema": raw_tool.get("inputSchema", raw_tool.get("input_schema", {})),
    }


def _serialize_mcp_call_result(result: Any) -> Any:
    # FastMCP 工具调用通常返回内容块列表和结构化结果的元组。
    if isinstance(result, tuple):
        # 二元组第二项是结构化字典时直接返回结构化结果。
        if len(result) == 2 and isinstance(result[1], dict):
            # 返回结构化工具结果。
            return result[1]
        # 其他元组逐项序列化。
        return [_serialize_mcp_call_result(item) for item in result]
    # dict 结果已经可 JSON 序列化。
    if isinstance(result, dict):
        # 返回字典。
        return result
    # list 结果逐项序列化。
    if isinstance(result, list):
        # 遍历列表内容。
        return [_serialize_mcp_call_result(item) for item in result]
    # Pydantic v2 内容块优先用 model_dump。
    if hasattr(result, "model_dump"):
        # 返回 Pydantic 字典。
        return result.model_dump()
    # Pydantic v1 内容块兼容 dict。
    if hasattr(result, "dict"):
        # 返回 Pydantic 字典。
        return result.dict()
    # 普通对象转字符串。
    return str(result)


async def _list_mcp_tools(mcp_gateway: FastMCP) -> list[dict[str, Any]]:
    # 调用 FastMCP 官方异步工具列表接口。
    tools = await mcp_gateway.list_tools()
    # 序列化工具清单。
    return [_serialize_mcp_tool(tool) for tool in tools]


async def _call_mcp_tool(mcp_gateway: FastMCP, name: str, arguments: dict[str, Any]) -> Any:
    # 调用 FastMCP 官方异步工具调用接口。
    result = await mcp_gateway.call_tool(name, arguments)
    # 返回可打印结构。
    return _serialize_mcp_call_result(result)


async def _smoke_mcp_tools(
    mcp_gateway: FastMCP,
    query: str,
    user_id: str,
    thread_id: str,
) -> dict[str, Any]:
    # 烟测 RAG 召回工具。
    rag_result = await _call_mcp_tool(mcp_gateway, "sql_rag_retrieve", {"query": query})
    # 烟测图谱扩展工具。
    graph_result = await _call_mcp_tool(mcp_gateway, "sql_rag_graph_expand", {"query": query, "entity_hint": query})
    # 烟测三层记忆读取工具。
    memory_result = await _call_mcp_tool(mcp_gateway, "sql_rag_memory_read", {"user_id": user_id, "query": query})
    # 烟测业务工具查询能力，避免创建测试工单污染数据。
    business_result = await _call_mcp_tool(
        mcp_gateway,
        "sql_rag_business_action",
        {
            "action_name": "query_tickets",
            "action_args": {
                "_agent_context": {
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "source_question": query,
                }
            },
        },
    )
    # 汇总四类工具烟测结果。
    return {
        "sql_rag_retrieve": rag_result,
        "sql_rag_graph_expand": graph_result,
        "sql_rag_memory_read": memory_result,
        "sql_rag_business_action": business_result,
    }


def inspect_mcp_gateway(
    bundle: McpGatewayRuntimeBundle,
    smoke_tools: bool,
    query: str,
    user_id: str,
    thread_id: str,
) -> dict[str, Any]:
    # 读取 MCP 工具清单。
    tools = asyncio.run(_list_mcp_tools(bundle.mcp_gateway))
    # 构造检查结果。
    result: dict[str, Any] = {
        "ready": len(tools) == 4,
        "gateway": "sql-rag-agent-mcp-gateway",
        "transport_options": ["stdio", "sse", "streamable-http"],
        "tools": tools,
    }
    # 需要烟测时调用四类工具。
    if smoke_tools:
        # 执行非破坏性工具烟测。
        result["smoke"] = asyncio.run(_smoke_mcp_tools(bundle.mcp_gateway, query=query, user_id=user_id, thread_id=thread_id))
    # 返回检查结果。
    return result


def build_mcp_gateway_arg_parser() -> argparse.ArgumentParser:
    # 创建 MCP 网关命令行解析器。
    parser = argparse.ArgumentParser(description="运行或检查 SQL_RAG MCP 工具网关。")
    # 创建子命令解析器。
    subparsers = parser.add_subparsers(dest="command")
    # 创建 inspect 子命令。
    inspect_parser = subparsers.add_parser("inspect", help="检查 MCP 工具是否真实注册。")
    # 添加是否执行工具烟测。
    inspect_parser.add_argument("--smoke-tools", action="store_true", help="同时调用四个 MCP 工具做非破坏性烟测。")
    # 添加烟测查询文本。
    inspect_parser.add_argument("--query", default="订单审核", help="MCP 工具烟测使用的问题。")
    # 添加烟测用户 ID。
    inspect_parser.add_argument("--user-id", default="mcp-smoke-user", help="MCP 记忆和业务工具烟测用户 ID。")
    # 添加烟测线程 ID。
    inspect_parser.add_argument("--thread-id", default="mcp-smoke-thread", help="MCP 业务工具烟测线程 ID。")
    # 创建 run 子命令。
    run_parser = subparsers.add_parser("run", help="启动 FastMCP 网关。")
    # 添加 transport 参数。
    run_parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio", help="FastMCP 传输模式。")
    # 添加 host 参数。
    run_parser.add_argument("--host", default="127.0.0.1", help="SSE/streamable-http 监听地址。")
    # 添加 port 参数。
    run_parser.add_argument("--port", type=int, default=18181, help="SSE/streamable-http 监听端口。")
    # 添加 mount path 参数。
    run_parser.add_argument("--mount-path", default="/mcp", help="FastMCP 挂载路径。")
    # 返回解析器。
    return parser


def run_mcp_gateway_cli(argv: Sequence[str], sql_rag_dir: Path = SQL_RAG_DIR) -> int:
    # 构建解析器。
    parser = build_mcp_gateway_arg_parser()
    # 解析参数。
    args = parser.parse_args(list(argv))
    # 没有子命令时默认执行 inspect，方便 main.py 自检。
    command = args.command or "inspect"
    # inspect 使用默认网关监听参数，因为不会真正占用端口。
    if command == "inspect":
        # 构建 MCP 网关运行时 bundle。
        bundle = build_mcp_gateway_runtime(sql_rag_dir=sql_rag_dir)
        # 确保检查后释放记忆层长连接。
        try:
            # 执行 MCP 工具注册检查。
            result = inspect_mcp_gateway(
                bundle=bundle,
                smoke_tools=bool(getattr(args, "smoke_tools", False)),
                query=str(getattr(args, "query", "订单审核")),
                user_id=str(getattr(args, "user_id", "mcp-smoke-user")),
                thread_id=str(getattr(args, "thread_id", "mcp-smoke-thread")),
            )
            # 打印 JSON 检查结果。
            print(json.dumps(result, ensure_ascii=False, indent=2))
            # 返回检查状态。
            return 0 if result.get("ready") else 2
        # 无论是否成功都释放资源。
        finally:
            # 关闭 MCP 运行时 bundle。
            bundle.close()
    # run 子命令根据参数构建真实网关。
    if command == "run":
        # 构建 MCP 网关运行时 bundle。
        bundle = build_mcp_gateway_runtime(
            sql_rag_dir=sql_rag_dir,
            host=str(args.host),
            port=int(args.port),
            mount_path=str(args.mount_path),
        )
        # 确保服务退出时释放资源。
        try:
            # 启动 FastMCP 官方服务。
            bundle.mcp_gateway.run(transport=args.transport, mount_path=args.mount_path)
            # 正常退出返回成功。
            return 0
        # 无论是否成功都释放资源。
        finally:
            # 关闭 MCP 运行时 bundle。
            bundle.close()
    # 理论上不会走到这里，保留明确错误。
    parser.error(f"不支持的 MCP 网关命令：{command}")
    # 返回错误退出码。
    return 2
