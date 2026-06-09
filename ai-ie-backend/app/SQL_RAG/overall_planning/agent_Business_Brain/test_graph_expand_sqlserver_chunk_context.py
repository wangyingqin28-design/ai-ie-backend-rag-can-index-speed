# -*- coding: utf-8 -*-
"""SQL Server 图谱工具回跳 RAG chunk_id 的回归测试。"""

# 导入 sys，用于补充 SQL_RAG 模块路径。
import sys
# 导入 unittest 标准库，避免依赖外层测试框架。
import unittest
# 导入 Path，用于定位 SQL_RAG 根目录。
from pathlib import Path

# 定位 SQL_RAG 根目录。
SQL_RAG_DIR = Path(__file__).resolve().parents[2]
# 直接运行测试文件时补充 SQL_RAG 根目录。
if str(SQL_RAG_DIR) not in sys.path:
    # 插入模块搜索路径最前面。
    sys.path.insert(0, str(SQL_RAG_DIR))

# 导入纠错飞轮运行时。
from overall_planning.Answer_correction import AnswerCorrectionRuntime, load_correction_config
# 导入业务脑配置和运行时。
from overall_planning.agent_Business_Brain.business_brain_runtime import BusinessBrainRuntime, load_business_brain_config
# 导入三层记忆运行时。
from overall_planning.long_memory import ThreeLayerMemoryRuntime, load_memory_config


class SqlServerGraphExpandChunkContextTest(unittest.TestCase):
    # 测试用 RAG 召回 chunk，这些 chunk 在 dbo.rag_entity_mentions 中已有实体。
    retrieved_chunk_ids = [
        "qachunk_aa90c18fb862a51e6bf63301",
        "qachunk_3607a5a14f17cb7efbb0cc0c",
        "qachunk_45a4e8cc04fc82adf0c3db97",
        "qachunk_ed86a872455d6a43de674026",
        "qachunk_0adc662813e7e7448ba26dcf",
    ]

    def test_graph_expand_uses_retrieved_chunk_ids_when_long_query_has_no_like_hit(self) -> None:
        # 读取业务脑配置。
        business_config = load_business_brain_config(SQL_RAG_DIR)
        # 创建三层记忆运行时。
        memory_runtime = ThreeLayerMemoryRuntime(load_memory_config())
        # 保证测试结束释放资源。
        try:
            # 创建纠错飞轮运行时。
            correction_runtime = AnswerCorrectionRuntime(load_correction_config())
            # 创建不依赖 Qwen 的业务脑运行时。
            business_runtime = BusinessBrainRuntime(
                config=business_config,
                memory_runtime=memory_runtime,
                correction_runtime=correction_runtime,
                require_qwen=False,
            )
            # 调用 SQL Server 图谱工具，并传入 RAG 已召回的 chunk_id。
            output = business_runtime.tools["sql_rag_graph_expand"].call(
                query="客户反馈订单一直没有审核，请先查知识库判断可能原因，再读取历史记忆和相关实体关系。",
                entity_hint="客户反馈订单一直没有审核，请先查知识库判断可能原因，再读取历史记忆和相关实体关系。",
                source_chunk_ids=self.retrieved_chunk_ids,
            )
            # 读取结构化结果。
            result = output.raw_output
            # 断言图谱工具必须从 chunk_id 回跳出实体。
            self.assertGreater(len(result["entities"]), 0)
            # 断言图谱工具必须生成实体到 chunk 的关系边。
            self.assertGreater(len(result["edges"]), 0)
            # 断言返回结果可追溯使用了哪些 chunk_id。
            self.assertEqual(result["source_chunk_ids"], self.retrieved_chunk_ids)
        # 释放三层记忆运行时。
        finally:
            # 关闭记忆层资源。
            memory_runtime.close()


# 允许直接执行测试文件。
    def test_followup_request_is_not_satisfied_by_create_ticket_only(self) -> None:
        # 读取业务脑配置。
        business_config = load_business_brain_config(SQL_RAG_DIR)
        # 创建三层记忆运行时。
        memory_runtime = ThreeLayerMemoryRuntime(load_memory_config())
        # 保证测试结束释放资源。
        try:
            # 创建纠错飞轮运行时。
            correction_runtime = AnswerCorrectionRuntime(load_correction_config())
            # 创建不依赖 Qwen 的业务脑运行时。
            business_runtime = BusinessBrainRuntime(
                config=business_config,
                memory_runtime=memory_runtime,
                correction_runtime=correction_runtime,
                require_qwen=False,
            )
            # 构造已经建过普通工单但还没有跟进提醒的 LangGraph 状态。
            state = {
                "question": "请创建一个跟进提醒，提醒业务人员处理。",
                "user_id": "followup-required-user",
                "thread_id": "followup-required-thread",
                "tool_results": [
                    {
                        "tool_name": "sql_rag_business_action",
                        "tool_args": {"action_name": "create_ticket"},
                        "result": {"status": "succeeded", "action_name": "create_ticket"},
                    }
                ],
                "mark": {},
            }
            # 获取协议守卫要补齐的下一步工具。
            next_tool = business_runtime._next_missing_required_tool(state)
            # 先确认守卫返回了明确工具调用，而不是空字典。
            self.assertIn("name", next_tool)
            # 明确跟进/提醒诉求不能被普通 create_ticket 吞掉。
            self.assertEqual(next_tool["name"], "sql_rag_business_action")
            # 必须继续补齐 create_followup，才能真正生成提醒任务。
            self.assertEqual(next_tool["args"]["action_name"], "create_followup")
        # 释放三层记忆运行时。
        finally:
            # 关闭记忆层资源。
            memory_runtime.close()


if __name__ == "__main__":
    # 运行 unittest。
    unittest.main()
