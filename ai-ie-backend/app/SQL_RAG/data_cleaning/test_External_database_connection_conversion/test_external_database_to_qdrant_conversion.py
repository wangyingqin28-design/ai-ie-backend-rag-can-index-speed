# -*- coding: utf-8 -*-
"""外部关系型数据库转 Qdrant 复现链路的顺序合同测试。"""

# 导入 sys，用来把当前测试目录加入模块搜索路径。
import sys
# 从 dataclasses 导入 dataclass，用来创建轻量假 chunk。
from dataclasses import dataclass
# 从 pathlib 导入 Path，用来定位当前测试目录。
from pathlib import Path
# 导入 unittest，沿用仓库现有测试风格。
import unittest

# 定位当前测试目录。
CURRENT_DIR = Path(__file__).resolve().parent
# 如果当前测试目录还不在 sys.path，就加入最前面。
if str(CURRENT_DIR) not in sys.path:
    # 把测试目录放到最前，确保导入当前目录里的复现脚本。
    sys.path.insert(0, str(CURRENT_DIR))

# 导入待实现的外部数据库转 Qdrant 复现脚本。
import external_database_to_qdrant_conversion as conversion


@dataclass(frozen=True)
class FakeChunk:
    # 定义最小 chunk_id，足够让复现脚本分批和统计。
    chunk_id: str


@dataclass(frozen=True)
class FakePoint:
    # 定义最小 point 向量，足够让 Qdrant 自检节点取第一条向量。
    vector: list[float]


class FakeSyncModule:
    # 初始化假同步模块。
    def __init__(self) -> None:
        # 记录复现脚本实际调用过的 API 名称和关键参数。
        self.calls: list[tuple] = []
        # 准备三条假 canonical chunk，用来验证分两批处理。
        self.chunks = [FakeChunk("chunk-1"), FakeChunk("chunk-2"), FakeChunk("chunk-3")]

    # 复刻现有 qdrant_sqlserver_sync.load_canonical_chunks_from_sqlserver API。
    def load_canonical_chunks_from_sqlserver(self, sql_config):
        # 记录读取 SQL Server 节点调用。
        self.calls.append(("load_canonical_chunks_from_sqlserver", sql_config.database))
        # 返回假 chunk 列表。
        return self.chunks

    # 复刻现有 qdrant_sqlserver_sync.validate_chunks_before_qdrant API。
    def validate_chunks_before_qdrant(self, chunks):
        # 记录同步前契约校验节点调用。
        self.calls.append(("validate_chunks_before_qdrant", len(chunks)))
        # 返回假校验摘要。
        return {"checked_chunk_count": len(chunks), "error_count": 0}

    # 复刻现有 qdrant_sqlserver_sync.ensure_qdrant_collection API。
    def ensure_qdrant_collection(self, client, qdrant_config, embedding_config):
        # 记录 Qdrant collection 准备节点调用。
        self.calls.append(("ensure_qdrant_collection", qdrant_config.collection_name, embedding_config.dimension))

    # 复刻现有 qdrant_sqlserver_sync.create_embedding_client API。
    def create_embedding_client(self, embedding_config):
        # 记录 embedding 客户端创建节点调用。
        self.calls.append(("create_embedding_client", embedding_config.model))
        # 返回假 embedding 客户端。
        return "fake-embedding-client"

    # 复刻现有 qdrant_sqlserver_sync.chunk_list API。
    def chunk_list(self, items, batch_size):
        # 记录分批节点调用。
        self.calls.append(("chunk_list", len(items), batch_size))
        # 按测试需要固定切成两批。
        return [items[:2], items[2:]]

    # 复刻现有 qdrant_sqlserver_sync.build_embedding_text API。
    def build_embedding_text(self, chunk):
        # 记录向量化文本构造节点调用。
        self.calls.append(("build_embedding_text", chunk.chunk_id))
        # 返回假检索文本。
        return f"text:{chunk.chunk_id}"

    # 复刻现有 qdrant_sqlserver_sync.embed_texts API。
    def embed_texts(self, client, texts, embedding_config):
        # 记录 embedding 批量生成节点调用。
        self.calls.append(("embed_texts", tuple(texts), embedding_config.dimension))
        # 返回和文本数量一致的假向量。
        return [[float(index)] for index, _ in enumerate(texts, start=1)]

    # 复刻现有 qdrant_sqlserver_sync.build_qdrant_points API。
    def build_qdrant_points(self, chunks, embeddings, embedding_config):
        # 记录 Qdrant point 构造节点调用。
        self.calls.append(("build_qdrant_points", tuple(chunk.chunk_id for chunk in chunks), len(embeddings)))
        # 返回和 chunk 数量一致的假 point。
        return [FakePoint(vector=embedding) for embedding in embeddings]

    # 复刻现有 qdrant_sqlserver_sync.upsert_points_to_qdrant API。
    def upsert_points_to_qdrant(self, client, qdrant_config, points):
        # 记录 Qdrant upsert 节点调用。
        self.calls.append(("upsert_points_to_qdrant", qdrant_config.collection_name, len(points)))

    # 复刻现有 qdrant_sqlserver_sync.update_sqlserver_sync_state API。
    def update_sqlserver_sync_state(self, sql_config, qdrant_config, embedding_config, chunks, point_count):
        # 记录 SQL Server 同步状态回写节点调用。
        self.calls.append(("update_sqlserver_sync_state", sql_config.database, qdrant_config.collection_name, len(chunks), point_count))

    # 复刻现有 qdrant_sqlserver_sync.verify_qdrant_collection API。
    def verify_qdrant_collection(self, client, qdrant_config, first_vector):
        # 记录 Qdrant 自检节点调用。
        self.calls.append(("verify_qdrant_collection", qdrant_config.collection_name, tuple(first_vector)))
        # 返回假自检摘要。
        return {"point_count": 3, "query_hit_count": 1}


class ExternalDatabaseToQdrantConversionTest(unittest.TestCase):
    # 测试复现脚本必须按现有 SQL Server 到 Qdrant API 顺序执行。
    def test_replays_existing_qdrant_sync_api_chain_in_node_order(self) -> None:
        # 创建假同步模块。
        fake_sync = FakeSyncModule()
        # 构造外部 SQL Server 配置。
        sql_config = conversion.qdrant_sync.SqlServerConfig(
            server="external-sql-host",
            database="external_getai",
            user="external_user",
            password="external_password",
            driver="ODBC Driver 17 for SQL Server",
        )
        # 构造 embedding 配置。
        embedding_config = conversion.qdrant_sync.EmbeddingConfig(
            api_base="http://embedding-service/v1",
            api_key="fake-key",
            model="fake-embedding-model",
            dimension=2,
            batch_size=2,
        )
        # 构造目标 Qdrant 配置。
        qdrant_config = conversion.qdrant_sync.QdrantSyncConfig(
            url="http://qdrant-host:6333",
            collection_name="external_getai_payload_v1",
            distance="Cosine",
            recreate_collection=True,
            upsert_batch_size=64,
            dry_run=False,
        )

        # 定义假 QdrantClient 工厂。
        def fake_qdrant_client_factory(url: str):
            # 记录 Qdrant 客户端创建节点调用。
            fake_sync.calls.append(("QdrantClient", url))
            # 返回假 Qdrant 客户端。
            return "fake-qdrant-client"

        # 执行复现链路。
        summary = conversion.run_external_database_to_qdrant_conversion(
            sql_config=sql_config,
            embedding_config=embedding_config,
            qdrant_config=qdrant_config,
            sync_module=fake_sync,
            qdrant_client_factory=fake_qdrant_client_factory,
        )

        # 断言调用顺序完全贴合现有 qdrant_sqlserver_sync.sync_sqlserver_to_qdrant 链路。
        self.assertEqual(
            fake_sync.calls,
            [
                ("load_canonical_chunks_from_sqlserver", "external_getai"),
                ("validate_chunks_before_qdrant", 3),
                ("QdrantClient", "http://qdrant-host:6333"),
                ("ensure_qdrant_collection", "external_getai_payload_v1", 2),
                ("create_embedding_client", "fake-embedding-model"),
                ("chunk_list", 3, 2),
                ("build_embedding_text", "chunk-1"),
                ("build_embedding_text", "chunk-2"),
                ("embed_texts", ("text:chunk-1", "text:chunk-2"), 2),
                ("build_qdrant_points", ("chunk-1", "chunk-2"), 2),
                ("upsert_points_to_qdrant", "external_getai_payload_v1", 2),
                ("build_embedding_text", "chunk-3"),
                ("embed_texts", ("text:chunk-3",), 2),
                ("build_qdrant_points", ("chunk-3",), 1),
                ("upsert_points_to_qdrant", "external_getai_payload_v1", 1),
                ("update_sqlserver_sync_state", "external_getai", "external_getai_payload_v1", 3, 3),
                ("verify_qdrant_collection", "external_getai_payload_v1", (1.0,)),
            ],
        )
        # 断言摘要保留外部库名，便于确认别人接入的是哪套关系型库。
        self.assertEqual(summary["source_database"], "external_getai")
        # 断言摘要保留新 Qdrant collection 名称，便于别人后续连接消费 payload。
        self.assertEqual(summary["collection"], "external_getai_payload_v1")
        # 断言复现链路写入 point 数正确。
        self.assertEqual(summary["upserted_point_count"], 3)
        # 断言摘要暴露节点 API 调用链。
        self.assertEqual(summary["api_call_chain"][0]["api"], "load_canonical_chunks_from_sqlserver")


# 允许直接运行当前测试文件。
if __name__ == "__main__":
    # 调用 unittest 主入口。
    unittest.main()
