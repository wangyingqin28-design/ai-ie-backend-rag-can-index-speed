# -*- coding: utf-8 -*-
"""三层记忆：LangGraph checkpoint、结构化画像、Zep/Graphiti 情景记忆。"""

# 修改日期：2026-06-02 17:28:00。
# 修改理由：按照截图第 2 点接入官方 LangGraph checkpointer/store、Neo4j 和 Graphiti API，避免自写伪记忆框架。

# 导入 asyncio，用于调用 Graphiti 官方异步记忆接口。
import asyncio
# 导入 JSON，用于持久化结构化画像值。
import json
# 导入 os，用于读取记忆层配置。
import os
# 导入 uuid，用于生成稳定记忆事件 ID。
import uuid
# 导入 dataclass，用于定义记忆配置。
from dataclasses import dataclass
# 导入 datetime，用于写入 updated_at、expiry 和事件时间。
from datetime import datetime, timezone
# 导入任意类型。
from typing import Any

# 导入 Graphiti 官方时序知识图谱。
from graphiti_core import Graphiti
# 导入 Graphiti 官方 episode 类型。
from graphiti_core.nodes import EpisodeType
# 导入 LangGraph 官方内存 checkpoint。
from langgraph.checkpoint.memory import InMemorySaver
# 导入 LangGraph 官方 Postgres checkpoint。
from langgraph.checkpoint.postgres import PostgresSaver
# 导入 LangGraph 官方 store，用于结构化画像记忆。
from langgraph.store.memory import InMemoryStore
# 导入 Neo4j 官方驱动，用于结构化画像落图库。
from neo4j import GraphDatabase


@dataclass(frozen=True)
class MemoryConfig:
    # LangGraph checkpoint 的 Postgres 连接串。
    postgres_checkpoint_dsn: str
    # 是否允许本地测试时使用官方 InMemorySaver。
    allow_in_memory_checkpoint: bool
    # Neo4j 地址，用于结构化画像和 Graphiti。
    neo4j_uri: str
    # Neo4j 用户名。
    neo4j_user: str
    # Neo4j 密码。
    neo4j_password: str
    # Neo4j database 名。
    neo4j_database: str
    # 是否启用 Graphiti 长期情景记忆。
    graphiti_enabled: bool
    # Graphiti group 前缀，用于多用户隔离。
    graphiti_group_prefix: str


def load_memory_config() -> MemoryConfig:
    # 读取 Postgres checkpoint 连接串。
    postgres_checkpoint_dsn = os.getenv("LANGGRAPH_POSTGRES_CHECKPOINT_DSN", "")
    # 读取是否允许官方内存 checkpoint 作为本地测试兜底。
    allow_in_memory_checkpoint = os.getenv("LANGGRAPH_ALLOW_IN_MEMORY_CHECKPOINT", "1") == "1"
    # 读取 Neo4j 地址。
    neo4j_uri = os.getenv("NEO4J_URI", "")
    # 读取 Neo4j 用户。
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    # 读取 Neo4j 密码。
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")
    # 读取 Neo4j database。
    neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")
    # 读取 Graphiti 启用开关。
    graphiti_enabled = os.getenv("GRAPHITI_ENABLED", "0") == "1"
    # 读取 Graphiti group 前缀。
    graphiti_group_prefix = os.getenv("GRAPHITI_GROUP_PREFIX", "sql_rag_user")
    # 返回记忆配置。
    return MemoryConfig(
        postgres_checkpoint_dsn=postgres_checkpoint_dsn,
        allow_in_memory_checkpoint=allow_in_memory_checkpoint,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        neo4j_database=neo4j_database,
        graphiti_enabled=graphiti_enabled,
        graphiti_group_prefix=graphiti_group_prefix,
    )


class ThreeLayerMemoryRuntime:
    # 保存配置。
    config: MemoryConfig
    # 保存 LangGraph 官方 checkpoint。
    checkpointer: Any
    # 保存 LangGraph 官方 store。
    store: InMemoryStore
    # 保存 Neo4j 官方 driver。
    neo4j_driver: Any
    # 保存 Graphiti 官方运行时。
    graphiti: Graphiti | None
    # 保存 PostgresSaver context manager，避免连接被提前释放。
    _checkpoint_context: Any

    def __init__(self, config: MemoryConfig) -> None:
        # 记录配置。
        self.config = config
        # 构建短期工作记忆 checkpoint。
        self.checkpointer, self._checkpoint_context = self._build_checkpointer()
        # 创建 LangGraph 官方 store 作为画像记忆的本地可测入口。
        self.store = InMemoryStore()
        # 创建 Neo4j 官方 driver。
        self.neo4j_driver = self._build_neo4j_driver()
        # 创建 Graphiti 官方情景记忆运行时。
        self.graphiti = self._build_graphiti()

    def _build_checkpointer(self) -> tuple[Any, Any]:
        # 配置了 Postgres 时优先使用 LangGraph 官方 PostgresSaver。
        if self.config.postgres_checkpoint_dsn:
            # 创建 PostgresSaver 官方 context manager。
            context = PostgresSaver.from_conn_string(self.config.postgres_checkpoint_dsn)
            # 进入 context，得到真正 saver。
            saver = context.__enter__()
            # 初始化官方 checkpoint 表结构。
            saver.setup()
            # 返回 saver 和 context。
            return saver, context
        # 本地测试允许官方 InMemorySaver。
        if self.config.allow_in_memory_checkpoint:
            # 返回 LangGraph 官方 InMemorySaver。
            return InMemorySaver(), None
        # 不允许兜底时抛出配置错误。
        raise RuntimeError("缺少 LANGGRAPH_POSTGRES_CHECKPOINT_DSN，且未允许 LANGGRAPH_ALLOW_IN_MEMORY_CHECKPOINT=1。")

    def _build_neo4j_driver(self) -> Any:
        # 未配置 Neo4j 时不启用画像图库。
        if not self.config.neo4j_uri or not self.config.neo4j_password:
            # 返回 None。
            return None
        # 使用 Neo4j 官方 GraphDatabase.driver。
        return GraphDatabase.driver(
            self.config.neo4j_uri,
            auth=(self.config.neo4j_user, self.config.neo4j_password),
        )

    def _build_graphiti(self) -> Graphiti | None:
        # 未开启 Graphiti 时不创建长期情景记忆。
        if not self.config.graphiti_enabled:
            # 返回 None。
            return None
        # Graphiti 需要 Neo4j 连接信息。
        if not self.config.neo4j_uri or not self.config.neo4j_password:
            # 抛出明确配置错误。
            raise RuntimeError("启用 GRAPHITI_ENABLED=1 时必须配置 NEO4J_URI 和 NEO4J_PASSWORD。")
        # 使用 Graphiti 官方构造器。
        return Graphiti(
            uri=self.config.neo4j_uri,
            user=self.config.neo4j_user,
            password=self.config.neo4j_password,
        )

    def close(self) -> None:
        # 关闭 Neo4j driver。
        if self.neo4j_driver is not None:
            # 调用 Neo4j 官方 close。
            self.neo4j_driver.close()
        # 退出 PostgresSaver context。
        if self._checkpoint_context is not None:
            # 调用 context manager 退出。
            self._checkpoint_context.__exit__(None, None, None)

    def graphiti_group_id(self, user_id: str) -> str:
        # 拼接 Graphiti group id，实现用户维度隔离。
        return f"{self.config.graphiti_group_prefix}:{user_id}"

    def write_profile_memory(
        self,
        user_id: str,
        key: str,
        value: dict[str, Any],
        source_id: str,
        confidence: float,
        expiry: str = "",
        consent_scope: str = "customer_service",
    ) -> dict[str, Any]:
        # 构造画像记忆值，强制带截图要求的治理字段。
        profile_value = {
            "value": value,
            "source_id": source_id,
            "confidence": confidence,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "expiry": expiry,
            "consent_scope": consent_scope,
        }
        # 使用 LangGraph 官方 store 写入画像记忆。
        self.store.put(("profile", user_id), key, profile_value)
        # 如果 Neo4j 可用，同步写入结构化画像图谱。
        if self.neo4j_driver is not None:
            # 调用 Neo4j 官方 session 执行 MERGE。
            with self.neo4j_driver.session(database=self.config.neo4j_database) as session:
                # 写入 UserProfile 节点。
                session.run(
                    """
                    MERGE (u:SQLRAGUser {user_id: $user_id})
                    MERGE (m:StructuredProfileMemory {memory_key: $key, user_id: $user_id})
                    SET m.value_json = $value_json,
                        m.source_id = $source_id,
                        m.confidence = $confidence,
                        m.updated_at = $updated_at,
                        m.expiry = $expiry,
                        m.consent_scope = $consent_scope
                    MERGE (u)-[:HAS_PROFILE_MEMORY]->(m)
                    """,
                    user_id=user_id,
                    key=key,
                    value_json=json.dumps(value, ensure_ascii=False),
                    source_id=source_id,
                    confidence=confidence,
                    updated_at=profile_value["updated_at"],
                    expiry=expiry,
                    consent_scope=consent_scope,
                )
        # 返回写入事件。
        return {"memory_layer": "structured_profile", "user_id": user_id, "key": key, "source_id": source_id}

    def search_profile_memory(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        # 使用 LangGraph 官方 store 搜索用户画像命名空间。
        items = self.store.search(("profile", user_id), limit=limit)
        # 转成可序列化结果。
        return [
            {
                "memory_id": item.key,
                "namespace": item.namespace,
                "value": item.value,
            }
            for item in items
        ]

    def write_episodic_memory(self, user_id: str, episode_name: str, episode_body: str, source_description: str) -> dict[str, Any]:
        # Graphiti 未启用时明确返回未启用状态，不伪造长期记忆。
        if self.graphiti is None:
            # 返回未启用。
            return {"memory_layer": "long_term_episode", "enabled": False, "reason": "graphiti_not_enabled"}
        # 生成稳定 episode uuid。
        episode_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{user_id}:{episode_name}:{episode_body}"))
        # 定义异步写入函数。
        async def _add_episode() -> Any:
            # 调用 Graphiti 官方 add_episode。
            return await self.graphiti.add_episode(
                name=episode_name,
                episode_body=episode_body,
                source_description=source_description,
                reference_time=datetime.now(timezone.utc),
                source=EpisodeType.message,
                group_id=self.graphiti_group_id(user_id),
                uuid=episode_uuid,
            )
        # 执行 Graphiti 异步写入。
        result = asyncio.run(_add_episode())
        # 返回写入事件。
        return {
            "memory_layer": "long_term_episode",
            "enabled": True,
            "episode_uuid": episode_uuid,
            "result": str(result),
        }

    def search_episodic_memory(self, user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        # Graphiti 未启用时返回空列表。
        if self.graphiti is None:
            # 返回空情景记忆。
            return []
        # 定义异步检索函数。
        async def _search() -> Any:
            # 调用 Graphiti 官方 search。
            return await self.graphiti.search(
                query=query,
                group_ids=[self.graphiti_group_id(user_id)],
                num_results=limit,
            )
        # 执行 Graphiti 异步搜索。
        results = asyncio.run(_search())
        # 转成可序列化结果。
        return [
            {
                "memory_id": getattr(edge, "uuid", ""),
                "fact": getattr(edge, "fact", str(edge)),
                "source": getattr(edge, "source_node_uuid", ""),
                "target": getattr(edge, "target_node_uuid", ""),
            }
            for edge in results
        ]

    def read_memory_context(self, user_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        # 读取结构化画像记忆。
        profile_memories = self.search_profile_memory(user_id=user_id, limit=limit)
        # 读取长期情景记忆。
        episodic_memories = self.search_episodic_memory(user_id=user_id, query=query, limit=limit)
        # 返回三层记忆上下文；短期工作记忆由 LangGraph checkpoint 自动承载。
        return {
            "short_term_working_memory": "langgraph_thread_state_checkpoint",
            "structured_profile_memory": profile_memories,
            "long_term_episodic_memory": episodic_memories,
        }

