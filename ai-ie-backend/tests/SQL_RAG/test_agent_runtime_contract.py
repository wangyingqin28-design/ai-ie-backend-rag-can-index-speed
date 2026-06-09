# -*- coding: utf-8 -*-
"""SQL_RAG Agent 缺陷修复合同测试。"""

# 2026-06-04 16:08:11 新增原因：导入 sys 以便把 SQL_RAG 本地包加入测试搜索路径。
import sys
# 2026-06-04 16:08:11 新增原因：导入 unittest 编写不依赖外部服务的合同测试。
import unittest
# 2026-06-04 16:08:11 新增原因：导入 Path 定位项目根目录和前端源码。
from pathlib import Path
# 2026-06-04 16:08:11 新增原因：导入 Any 兼容测试替身的类型标注。
from typing import Any

# 2026-06-04 16:08:11 新增原因：定位测试文件向上的项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 2026-06-04 16:08:11 新增原因：定位 SQL_RAG 目录，保证可直接导入整体规划模块。
SQL_RAG_DIR = PROJECT_ROOT / "app" / "SQL_RAG"
# 2026-06-04 16:08:11 新增原因：定位 data_cleaning 目录，保证关系构建模块可直接导入。
DATA_CLEANING_DIR = SQL_RAG_DIR / "data_cleaning"
# 2026-06-04 16:08:11 新增原因：遍历本地模块目录，避免测试依赖安装成包。
for module_dir in (SQL_RAG_DIR, DATA_CLEANING_DIR):
    # 2026-06-04 16:08:11 新增原因：目录未加入 sys.path 时才插入，避免重复污染路径。
    if str(module_dir) not in sys.path:
        # 2026-06-04 16:08:11 新增原因：把本地源码目录放到最前，保证测试读取当前修改。
        sys.path.insert(0, str(module_dir))

# 2026-06-04 16:08:11 新增原因：导入业务脑运行时，用 __new__ 只测纯本地逻辑。
from overall_planning.agent_Business_Brain.business_brain_runtime import BusinessBrainRuntime
# 2026-06-04 16:08:11 新增原因：导入待新增的 Neo4j 三元组 payload 构建函数，先让测试红。
from data_cleaning.data_structures.relation_builder import build_neo4j_triple_payloads
# 2026-06-04 17:55:44 新增原因：导入 SQL Server 历史回填构造函数，防止 Neo4j 回填边类型退化。
from storage.neo4j_sqlserver_backfill import build_triples_from_sqlserver_rows


# 2026-06-04 16:08:11 新增原因：定义纠错运行时替身，隔离外部 LangSmith/Phoenix。
class FakeCorrectionRuntime:
    # 2026-06-04 16:08:11 新增原因：标准化 mark 时直接返回浅拷贝，模拟真实 normalize_mark 合并行为。
    def normalize_mark(self, raw_mark: dict[str, Any] | None) -> dict[str, Any]:
        # 2026-06-04 16:08:11 新增原因：避免测试修改输入对象导致断言串扰。
        return dict(raw_mark or {})

    # 2026-06-04 16:08:11 新增原因：渲染低置信答案时需要定位分支，测试里给稳定值。
    def locate_failure_branch(self, mark: dict[str, Any]) -> str:
        # 2026-06-04 16:08:11 新增原因：返回固定分支，保证测试只关注渲染选择。
        return "answer_verifier"


# 2026-06-04 16:08:11 新增原因：定义 Qwen 替身，记录 Prompt Builder 实际喂给模型的消息。
class RecordingQwen:
    # 2026-06-04 16:08:11 新增原因：初始化消息记录列表。
    def __init__(self) -> None:
        # 2026-06-04 16:08:11 新增原因：保存最近一次 chat 的 messages 供断言使用。
        self.messages: list[dict[str, Any]] = []

    # 2026-06-04 16:08:11 新增原因：模拟 Qwen-Agent chat 接口。
    def chat(self, messages: list[dict[str, Any]], functions: list[dict[str, Any]], stream: bool = False) -> list[dict[str, Any]]:
        # 2026-06-04 16:08:11 新增原因：记录模型输入消息，验证 Prompt Builder 是否生效。
        self.messages = messages
        # 2026-06-04 16:08:11 新增原因：返回无工具调用的最终草稿，触发 verifier/renderer 流程。
        return [{"content": "模型已基于证据组织后的回答。", "function_call": None}]


# 2026-06-04 19:09:26 新增原因：定义可排队的 Qwen 替身，用于模拟模型先重复调工具、再按收敛提示直接回答。
class QueuedQwen:
    # 2026-06-04 19:09:26 新增原因：初始化响应队列和消息记录。
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        # 2026-06-04 19:09:26 新增原因：保存待返回响应。
        self.responses = list(responses)
        # 2026-06-04 19:09:26 新增原因：记录每次模型输入。
        self.messages: list[list[dict[str, Any]]] = []

    # 2026-06-04 19:09:26 新增原因：模拟 Qwen-Agent chat 接口。
    def chat(self, messages: list[dict[str, Any]], functions: list[dict[str, Any]], stream: bool = False) -> list[dict[str, Any]]:
        # 2026-06-04 19:09:26 新增原因：记录本次 messages。
        self.messages.append(messages)
        # 2026-06-04 19:09:26 新增原因：队列为空时兜底返回空内容。
        if not self.responses:
            # 2026-06-04 19:09:26 新增原因：返回空模型消息。
            return [{"content": "", "function_call": None}]
        # 2026-06-04 19:09:26 新增原因：弹出下一条预置响应。
        return [self.responses.pop(0)]


# 2026-06-04 16:08:11 新增原因：集中验证截图点名的运行时和前端合同。
class AgentRuntimeContractTest(unittest.TestCase):
    # 2026-06-04 16:08:11 新增原因：创建不触发外部服务初始化的运行时实例。
    def make_runtime(self) -> BusinessBrainRuntime:
        # 2026-06-04 16:08:11 新增原因：绕开 __init__，只测纯方法行为。
        runtime = BusinessBrainRuntime.__new__(BusinessBrainRuntime)
        # 2026-06-04 16:08:11 新增原因：注入纠错替身，避免 LangSmith 和阈值配置。
        runtime.correction_runtime = FakeCorrectionRuntime()
        # 2026-06-04 16:08:11 新增原因：默认工具表为空，测试 Prompt Builder 时不需要真实 FunctionTool。
        runtime.tools = {}
        # 2026-06-04 16:08:11 新增原因：注入 Qwen 替身，捕获消息。
        runtime.qwen_llm = RecordingQwen()
        # 2026-06-04 16:08:11 新增原因：返回可测运行时。
        return runtime

    # 2026-06-04 16:08:11 新增原因：验证最终答案不再被 RAG top1 原答案硬覆盖。
    def test_renderer_prefers_model_composed_answer_over_best_answer(self) -> None:
        # 2026-06-04 16:08:11 新增原因：创建本地运行时。
        runtime = self.make_runtime()
        # 2026-06-04 16:08:11 新增原因：构造高置信状态，best_answer 与模型草稿故意不同。
        result = runtime._renderer_node(
            {
                "draft_answer": "模型组织语言后的业务回答。",
                "tool_results": [],
                "verifier_result": {"score": 0.9, "needs_human": False},
                "mark": {"best_answer": "数据库原始 top1 答案。", "final_action": "answer", "final_answer_equivalence": {"equivalent": True}},
            }
        )
        # 2026-06-04 16:08:11 新增原因：断言最终展示使用模型组织后的回答。
        self.assertEqual(result["final_answer"], "模型组织语言后的业务回答。")

    # 2026-06-04 16:08:11 新增原因：验证 Prompt Builder 把 RAG、图谱、记忆和业务结果统一喂给模型。
    def test_call_qwen_uses_prompt_builder_context_after_tool_results(self) -> None:
        # 2026-06-04 16:08:11 新增原因：创建本地运行时。
        runtime = self.make_runtime()
        # 2026-06-04 16:08:11 新增原因：构造包含 RAG 和 Neo4j 图谱证据的状态。
        state = {
            "question": "入账单反审为什么要联系财务？",
            "tool_results": [
                {
                    "tool_name": "sql_rag_retrieve",
                    "result": {"best_answer": "先让财务反审，再让预付款状态退回。", "results": [{"chunk_id": "qachunk_1"}]},
                },
                {
                    "tool_name": "sql_rag_graph_expand",
                    "result": {"backend": "neo4j", "triples": [{"subject": "入账单", "predicate": "REQUIRES", "object": "财务反审"}]},
                },
            ],
        }
        # 2026-06-04 16:08:11 新增原因：调用模型入口，捕获实际 messages。
        runtime._call_qwen(state)
        # 2026-06-04 16:08:11 新增原因：拼接所有消息内容，便于检查 Prompt Builder 结构。
        prompt_text = "\n".join(str(message.get("content", "")) for message in runtime.qwen_llm.messages)
        # 2026-06-04 16:08:11 新增原因：断言显式包含 Prompt Builder 标识，避免只塞原始用户问题。
        self.assertIn("Prompt Builder", prompt_text)
        # 2026-06-04 16:08:11 新增原因：断言 RAG 直答证据进入模型消费上下文。
        self.assertIn("先让财务反审", prompt_text)
        # 2026-06-04 16:08:11 新增原因：断言 Neo4j 三元组进入模型消费上下文。
        self.assertIn("入账单 -[REQUIRES]-> 财务反审", prompt_text)

    # 2026-06-04 18:16:02 新增原因：验证工具原始大 payload 不会原样塞进 Qwen，避免本地 8192 context 爆掉。
    def test_call_qwen_compacts_large_tool_result_messages(self) -> None:
        # 2026-06-04 18:16:02 新增原因：创建本地运行时替身。
        runtime = self.make_runtime()
        # 2026-06-04 18:16:02 新增原因：构造一个很大的原始字段，模拟真实 RAG/tool payload。
        very_large_payload = "x" * 9000
        # 2026-06-04 18:16:02 新增原因：调用模型入口，观察实际 messages。
        runtime._call_qwen(
            {
                "question": "入仓单反审为什么要联系财务？",
                "tool_results": [
                    {
                        "tool_name": "sql_rag_retrieve",
                        "result": {
                            "best_answer": "先让财务反审，再让预付款状态回退。",
                            "source_chunk_id": "qachunk_1",
                            "results": [{"chunk_id": "qachunk_1"}],
                            "raw_payload": very_large_payload,
                        },
                    }
                ],
            }
        )
        # 2026-06-04 18:16:02 新增原因：拼接实际模型输入，检查没有整段大 payload。
        prompt_text = "\n".join(str(message.get("content", "")) for message in runtime.qwen_llm.messages)
        # 2026-06-04 18:16:02 新增原因：断言工具摘要仍保留 top1 chunk。
        self.assertIn("qachunk_1", prompt_text)
        # 2026-06-04 18:16:02 新增原因：断言巨大 raw_payload 没有进入模型上下文。
        self.assertNotIn("x" * 200, prompt_text)

    # 2026-06-04 16:08:11 新增原因：验证工具合并时会产出前端可逐字展示的动态 trace events。
    def test_tool_result_merge_appends_public_trace_events(self) -> None:
        # 2026-06-04 16:08:11 新增原因：创建本地运行时。
        runtime = self.make_runtime()
        # 2026-06-04 16:08:11 新增原因：合并一次 RAG 工具结果。
        mark = runtime._merge_tool_result_into_mark(
            {},
            "sql_rag_retrieve",
            {"query": "反审"},
            {"results": [{"chunk_id": "qachunk_1"}], "best_answer": "可以反审。", "source_chunk_id": "qachunk_1"},
        )
        # 2026-06-04 16:08:11 新增原因：读取 trace events。
        events = mark.get("public_trace_events", [])
        # 2026-06-04 16:08:11 新增原因：断言事件不是空，前端不必靠固定模板假装在跑。
        self.assertTrue(events)
        # 2026-06-04 16:08:11 新增原因：断言事件中包含真实工具名。
        self.assertEqual(events[-1]["tool_name"], "sql_rag_retrieve")

    # 2026-06-04 19:09:26 新增原因：验证证据工具已完成后模型重复调 RAG 会被收敛为最终回答。
    def test_planner_converges_duplicate_evidence_tool_to_final_answer(self) -> None:
        # 2026-06-04 19:09:26 新增原因：创建本地运行时替身。
        runtime = self.make_runtime()
        # 2026-06-04 19:09:26 新增原因：模拟第一次模型重复调用 RAG，第二次模型按最终回答提示输出答案。
        runtime.qwen_llm = QueuedQwen(
            [
                {"content": "", "function_call": {"name": "sql_rag_retrieve", "arguments": {"query": "重复召回"}}},
                {"content": "基于证据：入仓单需要财务反审，目的是让预付款状态回退。", "function_call": None},
            ]
        )
        # 2026-06-04 19:09:26 新增原因：构造 RAG 和 Neo4j 都已完成的状态。
        state = {
            "question": "入仓单反审为什么要联系财务？",
            "tool_results": [
                {"tool_name": "sql_rag_retrieve", "tool_args": {}, "result": {"best_answer": "先财务反审，让预付款状态回退。", "results": [{"chunk_id": "qachunk_1"}]}},
                {"tool_name": "sql_rag_graph_expand", "tool_args": {}, "result": {"backend": "neo4j_triple_graph", "triples": [{"subject": "反审", "predicate": "MENTIONED_IN_CHUNK", "object": "qachunk_1"}]}},
            ],
            "tool_iterations": 2,
            "mark": {},
        }
        # 2026-06-04 19:09:26 新增原因：执行 planner。
        result = runtime._planner_node(state)
        # 2026-06-04 19:09:26 新增原因：断言没有再次进入工具执行。
        self.assertEqual(result["pending_tool_call"], {})
        # 2026-06-04 19:09:26 新增原因：断言最终草稿来自无工具最终回答。
        self.assertIn("预付款状态回退", result["draft_answer"])
        # 2026-06-04 19:09:26 新增原因：断言 mark 记录了重复工具收敛。
        self.assertEqual(result["mark"].get("protocol_duplicate_tool"), "sql_rag_retrieve")

    # 2026-06-04 19:55:21 新增原因：验证证据已完成但模型空答时不会把空答案送入 verifier。
    def test_planner_uses_evidence_fallback_when_model_returns_empty_content(self) -> None:
        # 2026-06-04 19:55:21 新增原因：创建本地运行时替身。
        runtime = self.make_runtime()
        # 2026-06-04 19:55:21 新增原因：模拟模型没有工具调用但也没有输出内容。
        runtime.qwen_llm = QueuedQwen([{"content": "", "function_call": None}])
        # 2026-06-04 19:55:21 新增原因：构造 RAG 和图谱已完成的状态。
        state = {
            "question": "入仓单反审为什么要联系财务？",
            "tool_results": [
                {"tool_name": "sql_rag_retrieve", "tool_args": {}, "result": {"best_answer": "先财务反审，让预付款状态回退。", "results": [{"chunk_id": "qachunk_1"}]}},
                {"tool_name": "sql_rag_graph_expand", "tool_args": {}, "result": {"backend": "neo4j_triple_graph", "triples": [{"subject": "反审", "predicate": "MENTIONED_IN_CHUNK", "object": "qachunk_1"}]}},
            ],
            "tool_iterations": 2,
            "mark": {"best_answer": "先财务反审，让预付款状态回退。"},
        }
        # 2026-06-04 19:55:21 新增原因：执行 planner。
        result = runtime._planner_node(state)
        # 2026-06-04 19:55:21 新增原因：断言草稿不为空。
        self.assertEqual(result["draft_answer"], "")
        # 2026-06-04 19:55:21 新增原因：断言兜底草稿组织成业务语言。
        self.assertEqual(result["draft_answer_source"], "model_empty_final_answer")

    # 2026-06-04 16:08:11 新增原因：验证前端 live process 不再写死固定步骤数组。
    def test_frontend_live_process_reads_backend_trace_events(self) -> None:
        # 2026-06-04 16:08:11 新增原因：读取前端源码。
        app_js = (SQL_RAG_DIR / "agent_webUI" / "app.js").read_text(encoding="utf-8")
        # 2026-06-04 16:08:11 新增原因：断言固定步骤数组被移除。
        self.assertNotIn("const steps = [", app_js)
        # 2026-06-04 16:08:11 新增原因：断言前端读取后端动态 trace_events。
        self.assertIn("trace_events", app_js)

    # 2026-06-04 16:08:11 新增原因：验证清洗链路能生成 Neo4j 可导入的业务三元组。
    def test_build_neo4j_triple_payloads_from_entity_mentions(self) -> None:
        # 2026-06-04 16:08:11 新增原因：构造实体 mention payload。
        mentions = [
            {
                "chunk_id": "qachunk_1",
                "document_id": "qadoc_1",
                "entity_type": "system_terms",
                "entity_value": "入账单",
                "canonical_entity": "入账单",
                "global_cluster_id": "global_1",
            },
            {
                "chunk_id": "qachunk_1",
                "document_id": "qadoc_1",
                "entity_type": "system_terms",
                "entity_value": "反审",
                "canonical_entity": "反审",
                "global_cluster_id": "global_1",
            },
        ]
        # 2026-06-04 16:08:11 新增原因：构造 chunk payload。
        chunks = [{"chunk_id": "qachunk_1", "question": "入账单怎么反审？", "answer": "先让财务反审。"}]
        # 2026-06-04 16:08:11 新增原因：生成 Neo4j 三元组。
        triples = build_neo4j_triple_payloads(mentions, chunks)
        # 2026-06-04 16:08:11 新增原因：断言实体到 chunk 的三元组存在。
        self.assertIn(("入账单", "MENTIONED_IN_CHUNK", "qachunk_1"), {(item["subject"], item["predicate"], item["object"]) for item in triples})
        # 2026-06-04 16:08:11 新增原因：断言同 chunk 内实体共现三元组存在，支持多跳扩展。
        self.assertIn(("入账单", "CO_OCCURS_WITH", "反审"), {(item["subject"], item["predicate"], item["object"]) for item in triples})

    # 2026-06-04 17:55:44 新增原因：验证历史 SQL Server 数据回填 Neo4j 时具备多跳图谱关键边。
    def test_sqlserver_backfill_builds_multihop_neo4j_triples(self) -> None:
        # 2026-06-04 17:55:44 新增原因：构造一条 chunk 行，模拟 dbo.rag_qa_chunks。
        chunk_rows = [
            {
                "chunk_id": "qachunk_1",
                "document_id": "qadoc_1",
                "question": "入账单为什么要反审？",
                "answer": "需要财务反审后才能回退预付款状态。",
                "cleaned_text": "问题：入账单为什么要反审？答案：需要财务反审后才能回退预付款状态。",
                "global_cluster_id": "qaglobal_1",
                "global_cluster_label": "财务反审",
            }
        ]
        # 2026-06-04 17:55:44 新增原因：构造两个同 chunk mention，模拟 dbo.rag_entity_mentions。
        mention_rows = [
            {
                "mention_id": "m1",
                "document_id": "qadoc_1",
                "chunk_id": "qachunk_1",
                "entity_type": "system_terms",
                "entity_value": "入账单",
                "canonical_entity": "入账单",
                "entity_hash": "h1",
                "global_cluster_id": "qaglobal_1",
            },
            {
                "mention_id": "m2",
                "document_id": "qadoc_1",
                "chunk_id": "qachunk_1",
                "entity_type": "system_terms",
                "entity_value": "反审",
                "canonical_entity": "反审",
                "entity_hash": "h2",
                "global_cluster_id": "qaglobal_1",
            },
        ]
        # 2026-06-04 17:55:44 新增原因：构造 alias 行，模拟 dbo.rag_entity_aliases。
        alias_rows = [{"alias_id": "a1", "entity_type": "system_terms", "alias_value": "付款单", "canonical_entity": "预付款", "entity_hash": "h3"}]
        # 2026-06-04 17:55:44 新增原因：构造 fusion 行，模拟 dbo.rag_chunk_fusion_map。
        fusion_rows = [
            {
                "fusion_id": "f1",
                "canonical_chunk_id": "qachunk_1",
                "duplicate_chunk_id": "qachunk_dup",
                "duplicate_document_id": "qadoc_1",
                "global_cluster_id": "qaglobal_1",
                "fusion_score": 0.98,
                "fusion_rule": "same_answer",
                "duplicate_cleaned_text": "重复问答证据",
                "merge_payload_json": "{}",
            }
        ]
        # 2026-06-04 17:55:44 新增原因：执行纯构造函数，避免测试依赖真实 SQL Server/Neo4j。
        triples = build_triples_from_sqlserver_rows(chunk_rows, mention_rows, alias_rows, fusion_rows)
        # 2026-06-04 17:55:44 新增原因：抽取核心三元组用于断言。
        triple_keys = {(item["subject"], item["predicate"], item["object"]) for item in triples}
        # 2026-06-04 17:55:44 新增原因：断言实体挂 chunk 边存在。
        self.assertIn(("入账单", "MENTIONED_IN_CHUNK", "qachunk_1"), triple_keys)
        # 2026-06-04 17:55:44 新增原因：断言实体共现边存在。
        self.assertIn(("入账单", "CO_OCCURS_WITH", "反审"), triple_keys)
        # 2026-06-04 17:55:44 新增原因：断言 chunk 到全局聚类边存在。
        self.assertIn(("qachunk_1", "CHUNK_IN_GLOBAL_CLUSTER", "qaglobal_1"), triple_keys)
        # 2026-06-04 17:55:44 新增原因：断言 alias 归一化边存在。
        self.assertIn(("付款单", "ALIAS_OF", "预付款"), triple_keys)
        # 2026-06-04 17:55:44 新增原因：断言重复 chunk 归并边存在。
        self.assertIn(("qachunk_dup", "FUSED_INTO", "qachunk_1"), triple_keys)


# 2026-06-04 16:08:11 新增原因：允许单文件直接运行测试。
if __name__ == "__main__":
    # 2026-06-04 16:08:11 新增原因：调用 unittest 主入口。
    unittest.main()
