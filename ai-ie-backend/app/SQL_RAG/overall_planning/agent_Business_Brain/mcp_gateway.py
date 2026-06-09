# -*- coding: utf-8 -*-
"""SQL_RAG MCP Gateway。"""

# 修改日期：2026-06-02 17:36:00。
# 修改理由：按照截图第 1 点，用 MCP 官方 FastMCP 把 RAG、图谱、记忆和业务系统能力包装成外部工具。

# 导入任意类型。
from typing import Any, Callable

# 导入 MCP 官方 FastMCP。
from mcp.server.fastmcp import FastMCP


def build_sql_rag_mcp_gateway(
    rag_retrieve: Callable[[str], dict[str, Any]],
    graph_expand: Callable[[str, str, list[str]], dict[str, Any]],
    memory_read: Callable[[str, str], dict[str, Any]],
    business_action: Callable[[str, dict[str, Any]], dict[str, Any]],
    host: str = "127.0.0.1",
    port: int = 18181,
    mount_path: str = "/mcp",
) -> FastMCP:
    # 创建 MCP 官方服务实例。
    mcp = FastMCP(
        name="sql-rag-agent-mcp-gateway",
        instructions="SQL_RAG 智能客服 MCP 工具网关，提供 RAG 召回、知识图谱多跳、记忆读取和业务动作入口。",
        host=host,
        port=port,
        mount_path=mount_path,
    )

    @mcp.tool(
        name="sql_rag_retrieve",
        description="使用 LlamaIndex + Qdrant 语义召回 SQL_RAG canonical QA chunk，返回 chunk_id、global_cluster_id 和证据文本。",
    )
    def sql_rag_retrieve(query: str) -> dict[str, Any]:
        # 调用 LlamaIndex + Qdrant 官方检索工具。
        return rag_retrieve(query)

    @mcp.tool(
        name="sql_rag_graph_expand",
        description="使用 SQL Server 关系表或 Neo4j PropertyGraph 做实体、别名、融合关系和校验问题的多跳扩展。",
    )
    def sql_rag_graph_expand(query: str, entity_hint: str = "", source_chunk_ids: list[str] | None = None) -> dict[str, Any]:
        # 调用 SQL Server/Neo4j 知识图谱多跳工具。
        return graph_expand(query, entity_hint, source_chunk_ids or [])

    @mcp.tool(
        name="sql_rag_memory_read",
        description="读取 LangGraph thread checkpoint、结构化用户画像记忆和 Graphiti/Zep 风格长期情景记忆。",
    )
    def sql_rag_memory_read(user_id: str, query: str) -> dict[str, Any]:
        # 调用三层记忆读取工具。
        return memory_read(user_id, query)

    @mcp.tool(
        name="sql_rag_business_action",
        description="执行或查询本地客服业务动作，包括工单、转人工、跟进任务、用户画像和备注等 SQL Server 落库动作。",
    )
    def sql_rag_business_action(action_name: str, action_args: dict[str, Any]) -> dict[str, Any]:
        # 调用后续 CRM、订单、合同、权限、支付等业务系统动作入口。
        return business_action(action_name, action_args)

    # 返回 MCP 官方服务。
    return mcp
