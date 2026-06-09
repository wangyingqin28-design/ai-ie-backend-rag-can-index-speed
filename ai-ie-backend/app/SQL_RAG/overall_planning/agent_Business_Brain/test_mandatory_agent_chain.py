# -*- coding: utf-8 -*-
# 2026-06-05 10:03:12 新增原因：声明测试文件使用 UTF-8，保证中文业务问题和中文注释可读。
"""SQL_RAG 业务脑必经节点链路合同测试。"""
# 2026-06-05 10:03:12 新增原因：说明本文件只验证 app/SQL_RAG 内部运行时合同，不修改外层测试目录。

# 2026-06-05 10:03:12 新增原因：导入 sys，用于把 SQL_RAG 根目录加入本地模块搜索路径。
import sys
# 2026-06-05 10:03:12 新增原因：导入 unittest，用标准库测试锁定必经节点缺陷。
import unittest
# 2026-06-05 10:03:12 新增原因：导入 Path，用于定位 SQL_RAG 目录。
from pathlib import Path
# 2026-06-05 10:03:12 新增原因：导入 Any，给测试替身保持清晰类型。
from typing import Any


# 2026-06-05 10:52:18 新增原因：定义极简 MCP 文本块替身，用来复现 FastMCP call_tool 的真实返回形态。
class FakeMcpTextContent:
    # 2026-06-05 10:52:18 新增原因：只保存 text 字段，因为运行时代码只读取这个公开文本字段。
    def __init__(self, text: str) -> None:
        # 2026-06-05 10:52:18 新增原因：保留 MCP TextContent 的文本负载，供解码函数兜底解析。
        self.text = text


# 2026-06-05 10:03:12 新增原因：定位 SQL_RAG 根目录，避免依赖外层包安装。
SQL_RAG_DIR = Path(__file__).resolve().parents[2]
# 2026-06-05 10:03:12 新增原因：只在缺失时插入模块路径，避免重复污染 sys.path。
if str(SQL_RAG_DIR) not in sys.path:
    # 2026-06-05 10:03:12 新增原因：把 SQL_RAG 放到最前，保证测试读取当前源码。
    sys.path.insert(0, str(SQL_RAG_DIR))

# 2026-06-05 10:03:12 新增原因：导入业务脑运行时，直接测试必经工具链路选择。
from overall_planning.agent_Business_Brain.business_brain_runtime import BusinessBrainRuntime
# 2026-06-05 18:10:08 新增原因：导入本地业务工具仓库，直接验证只读业务上下文是否已经从场景硬编码改为泛化抽取。
from overall_planning.agent_Business_Brain.local_business_store import LocalBusinessActionStore
# 2026-06-05 10:03:12 新增原因：导入纠错飞轮运行时，测试缺图谱不能被 verifier 放行。
from overall_planning.Answer_correction import AnswerCorrectionRuntime, load_correction_config
# 2026-06-06 13:17:22 新增原因：导入通用极性校验函数，锁定 top1 首个事实方向不能被后文混合词抵消。
from overall_planning.semantic_evidence import extract_semantic_terms, semantic_answer_grounded_equivalence, semantic_answer_polarity_conflict


# 2026-06-05 10:03:12 新增原因：定义纠错替身，隔离 LangSmith/Phoenix 等外部观测依赖。
class FakeCorrectionRuntime:
    # 2026-06-05 10:03:12 新增原因：实现 normalize_mark，让业务脑能读取 mark 中的召回 chunk。
    def normalize_mark(self, raw_mark: dict[str, Any] | None) -> dict[str, Any]:
        # 2026-06-05 10:03:12 新增原因：返回浅拷贝，避免测试状态被原地污染。
        return dict(raw_mark or {})


# 2026-06-05 19:11:30 新增原因：定义 Qwen 最终回答替身，用来锁定 enable_thinking=false 是否透传到本地模型。
# 2026-06-06 14:54:36 新增原因：定义 verifier 修复替身配置，复现低置信后应回到模型重写而不是直接转人工。
class FakeVerifierRepairConfig:
    # 2026-06-06 14:54:36 新增原因：保持和生产阈值一致，方便 _verifier_node 判断是否需要修复。
    verifier_threshold = 0.72


# 2026-06-06 14:54:36 新增原因：定义 verifier 修复替身，第一次低分、第二次通过，锁定修复链路。
class FakeVerifierRepairCorrectionRuntime(FakeCorrectionRuntime):
    # 2026-06-06 14:54:36 新增原因：初始化配置和答案记录，确认修复后会重新校验模型答案。
    def __init__(self) -> None:
        # 2026-06-06 14:54:36 新增原因：提供 verifier 阈值给运行时。
        self.config = FakeVerifierRepairConfig()
        # 2026-06-06 14:54:36 新增原因：保存每次校验看到的答案。
        self.answers: list[str] = []

    # 2026-06-06 14:54:36 新增原因：复现确定性 verifier 先发现主题错配，修复后通过。
    def verify_answer_with_qwen(self, qwen_llm: Any, question: str, answer: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        # 2026-06-06 14:54:36 新增原因：记录当前被校验的答案文本。
        self.answers.append(answer)
        # 2026-06-06 14:54:36 新增原因：修复答案命中单据关系时返回通过，证明不是 renderer 兜底。
        if "单据关系" in answer and "重新冲账" in answer:
            # 2026-06-06 14:54:36 新增原因：返回通过结果，模拟 verifier 复验成功。
            return {"score": 0.8, "grounded": True, "complete": True, "needs_human": False, "failure_reason": "", "raw": {}}
        # 2026-06-06 14:54:36 新增原因：第一次返回语义错配，驱动运行时必须带失败原因重试模型。
        return {"score": 0.67, "grounded": True, "complete": False, "needs_human": True, "failure_reason": "answer_topic_mismatch", "raw": {"topic_coverage": {"missing_terms": ["单据关系", "重新冲账"]}}}

    # 2026-06-06 14:54:36 新增原因：提供失败分支定位，避免测试进入真实数据飞轮。
    def locate_failure_branch(self, mark: dict[str, Any]) -> str:
        # 2026-06-06 14:54:36 新增原因：返回稳定分支名，便于 renderer/trace 复用。
        return "answer_verifier"


class FakeFinalAnswerQwen:
    # 2026-06-05 19:11:30 新增原因：初始化调用记录，便于断言最终回答节点没有遗漏 OpenAI extra_body。
    def __init__(self) -> None:
        # 2026-06-05 19:11:30 新增原因：保存每次 chat 的参数，复现 Qwen3 reasoning_content 空答根因。
        self.calls: list[dict[str, Any]] = []

    # 2026-06-05 19:11:30 新增原因：实现最小 chat 接口，避免测试依赖真实 Qwen 服务。
    def chat(self, **kwargs: Any) -> list[dict[str, str]]:
        # 2026-06-05 19:11:30 新增原因：记录运行时传给 Qwen-Agent 封装层的完整参数。
        self.calls.append(kwargs)
        # 2026-06-05 19:11:30 新增原因：返回模型 content，证明正确关闭 thinking 后不应进入证据兜底。
        prompt_text = "\n".join(message.get("content", "") for message in kwargs.get("messages", []))
        if "退回状态" in prompt_text and "入账单" not in prompt_text:
            return [{"role": "assistant", "content": "是，应该先退回状态，确认前置处理完成后再继续后续业务动作。"}]
        return [{"role": "assistant", "content": "需要先反审入账单，再让付款状态退回。"}]


# 2026-06-06 11:46:12 新增原因：定义极性反写重试替身，复现第一次模型答反、第二次按证据修正的最终回答流程。
class FakePolarityRetryQwen:
    # 2026-06-06 11:46:12 新增原因：初始化调用记录，用于断言确实发生了无工具模型重试。
    def __init__(self) -> None:
        # 2026-06-06 11:46:12 新增原因：保存每次 chat 参数。
        self.calls: list[dict[str, Any]] = []

    # 2026-06-06 11:46:12 新增原因：实现最小 chat 接口，第一轮返回反向答案，第二轮返回正确答案。
    def chat(self, **kwargs: Any) -> list[dict[str, str]]:
        # 2026-06-06 11:46:12 新增原因：记录本轮调用参数。
        self.calls.append(kwargs)
        # 2026-06-06 11:46:12 新增原因：第一轮模拟本地模型把肯定证据答成否定。
        if len(self.calls) == 1:
            # 2026-06-06 11:46:12 新增原因：返回错误极性内容。
            return [{"role": "assistant", "content": "不是，不需要先退回状态，可以直接继续处理。"}]
        # 2026-06-06 11:46:12 新增原因：第二轮模拟模型按精简证据纠正为肯定答案。
        prompt_text = "\n".join(message.get("content", "") for message in kwargs.get("messages", []))
        if "完成前置状态" in prompt_text:
            return [{"role": "assistant", "content": "是，应该先完成前置状态，确认完成后再继续后续处理。"}]
        return [{"role": "assistant", "content": "是，应该先退回状态，确认前置处理完成后再继续后续业务动作。"}]


# 2026-06-06 13:41:09 新增原因：定义逃逸回答替身，复现模型拿到 Prompt Builder 后仍说证据不足的线上失败。
class FakeEvasiveFinalAnswerQwen:
    # 2026-06-06 13:41:09 新增原因：初始化调用记录，确认运行时触发模型重试而不是兜底硬编码。
    def __init__(self) -> None:
        # 2026-06-06 13:41:09 新增原因：保存每次 chat 参数，供测试断言最终回答链路真实调用模型。
        self.calls: list[dict[str, Any]] = []

    # 2026-06-06 13:41:09 新增原因：实现最小 chat 接口，第一轮逃逸，第二轮按证据组织业务答案。
    def chat(self, **kwargs: Any) -> list[dict[str, str]]:
        # 2026-06-06 13:41:09 新增原因：记录本轮模型调用参数。
        self.calls.append(kwargs)
        # 2026-06-06 13:41:09 新增原因：第一轮模拟本地模型忽略 top1 证据，输出“证据不足/人工确认”逃逸话术。
        if len(self.calls) == 1:
            # 2026-06-06 13:41:09 新增原因：返回逃逸答案，要求生产逻辑必须识别并重试。
            return [{"role": "assistant", "content": "当前问题需要更多业务证据或人工确认，我不能在证据不足时直接给出确定结论。"}]
        # 2026-06-06 13:41:09 新增原因：第二轮模拟模型消费极简 Prompt Builder 后按 top1 证据给出自然语言答案。
        return [{"role": "assistant", "content": "是，这笔账要先做前置审核，让状态返回回来，再继续后续处理。"}]


# 2026-06-05 10:03:12 新增原因：集中验证第一二张截图要求的必经节点合同。
# 2026-06-06 14:54:36 新增原因：定义内部词泄露替身，复现模型输出 RAG/Neo4j 等调试词时必须重试。
class FakeInternalLeakFinalAnswerQwen:
    # 2026-06-06 14:54:36 新增原因：初始化调用记录，确认泄露分支仍然调用模型而不是硬编码清洗。
    def __init__(self) -> None:
        # 2026-06-06 14:54:36 新增原因：保存模型调用参数。
        self.calls: list[dict[str, Any]] = []

    # 2026-06-06 14:54:36 新增原因：第一轮泄露内部词，第二轮输出纯用户答案。
    def chat(self, **kwargs: Any) -> list[dict[str, str]]:
        # 2026-06-06 14:54:36 新增原因：记录当前调用。
        self.calls.append(kwargs)
        # 2026-06-06 14:54:36 新增原因：第一轮模拟本地模型把内部链路词说给用户。
        if len(self.calls) == 1:
            # 2026-06-06 14:54:36 新增原因：返回含 RAG 的泄露答案，要求生产逻辑重试。
            return [{"role": "assistant", "content": "根据 RAG 证据，客户可以按分厂筛选订单。"}]
        # 2026-06-06 14:54:36 新增原因：第二轮返回不含内部词的模型答案。
        return [{"role": "assistant", "content": "可以，客户现在可以直接使用筛选功能，选择特定分厂查看订单。"}]


# 2026-06-06 14:54:36 新增原因：定义 verifier 修复用 Qwen 替身，验证低置信样本先回模型修复。

# 2026-06-09 09:12:31 Added: model may answer a troubleshooting question with a polluted yes lead while the body is grounded.
class FakeProcedureLeadFinalAnswerQwen:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> list[dict[str, str]]:
        self.calls.append(kwargs)
        return [{"role": "assistant", "content": "**\u662f**\n\n\u5982\u679c\u4e0d\u80fd\u7ed9\u8c03\u6574\u6743\u9650\uff0c\u5c31\u5728\u5458\u5de5\u8d44\u6599\u6388\u6743\u91cc\u52fe\u6389\uff1b\u518d\u770b\u73b0\u573a\u7ba1\u7406\u3002"}]

class FakeVerifierRepairQwen:
    # 2026-06-06 14:54:36 新增原因：初始化调用记录，确认 verifier 失败后确实重试模型。
    def __init__(self) -> None:
        # 2026-06-06 14:54:36 新增原因：保存模型调用参数。
        self.calls: list[dict[str, Any]] = []

    # 2026-06-06 14:54:36 新增原因：输出覆盖缺失主题词的修复答案。
    def chat(self, **kwargs: Any) -> list[dict[str, str]]:
        # 2026-06-06 14:54:36 新增原因：记录当前调用。
        self.calls.append(kwargs)
        # 2026-06-06 14:54:36 新增原因：返回模型组织的修复答案，覆盖单据关系和重新冲账。
        return [{"role": "assistant", "content": '需要先让财务反审入仓单，让预付款充账状态返回，再确认付款单单据关系并重新冲账，最后继续付款。'}]


class MandatoryAgentChainTest(unittest.TestCase):
    # 2026-06-05 10:03:12 新增原因：构造不初始化外部服务的业务脑实例。
    def make_runtime(self) -> BusinessBrainRuntime:
        # 2026-06-05 10:03:12 新增原因：绕开 __init__，只测试纯决策函数。
        runtime = BusinessBrainRuntime.__new__(BusinessBrainRuntime)
        # 2026-06-05 10:24:36 新增原因：显式标记真实运行态合同，让完整必经链在本测试中启用。
        runtime.config = object()
        # 2026-06-05 10:03:12 新增原因：注入纠错替身，满足运行时对 normalize_mark 的调用。
        runtime.correction_runtime = FakeCorrectionRuntime()
        # 2026-06-05 10:03:12 新增原因：返回轻量运行时，避免测试启动 Qwen/Qdrant/SQL Server。
        return runtime

    # 2026-06-05 10:03:12 新增原因：复现截图缺陷，业务问题 RAG 成功后仍必须补 Neo4j、记忆和业务审计。
    def test_business_question_runs_mandatory_evidence_chain_after_intent(self) -> None:
        # 2026-06-05 10:03:12 新增原因：创建轻量业务脑运行时。
        runtime = self.make_runtime()
        # 2026-06-05 10:03:12 新增原因：使用截图同款业务问题，不能依赖“图谱/关系”字眼才查图谱。
        question = "入账单你可以反你有反审的，对不对？"
        # 2026-06-05 10:03:12 新增原因：初始状态必须先补 RAG 召回节点。
        first_state = {"question": question, "tool_results": [], "mark": {}}
        # 2026-06-05 10:03:12 新增原因：读取第一项必经工具。
        first_tool = runtime._next_missing_required_tool(first_state)
        # 2026-06-05 10:03:12 新增原因：断言第一项是 RAG 召回。
        self.assertEqual(first_tool["name"], "sql_rag_retrieve")
        # 2026-06-05 10:03:12 新增原因：构造 RAG 已成功状态，模拟 LangGraph tool_executor 已写入 mark。
        rag_state = {
            # 2026-06-05 10:03:12 新增原因：保留原始问题，后续图谱和业务审计都要可追溯。
            "question": question,
            # 2026-06-05 10:03:12 新增原因：写入 RAG 工具成功结果。
            "tool_results": [{"tool_name": "sql_rag_retrieve", "result": {"status": "ok"}}],
            # 2026-06-05 10:03:12 新增原因：写入 RAG 召回 chunk，图谱工具必须从这些 chunk 做多跳。
            "mark": {"retrieved_chunk_ids": ["qachunk_0adc662813e7e7448ba26dcf"]},
        }
        # 2026-06-05 10:03:12 新增原因：读取 RAG 后下一项必经工具。
        graph_tool = runtime._next_missing_required_tool(rag_state)
        # 2026-06-05 10:03:12 新增原因：断言 RAG 后必须补 Neo4j 图谱扩展。
        self.assertEqual(graph_tool["name"], "sql_rag_graph_expand")
        # 2026-06-05 10:03:12 新增原因：断言图谱工具携带 RAG chunk，避免长 query 查空。
        self.assertEqual(graph_tool["args"]["source_chunk_ids"], ["qachunk_0adc662813e7e7448ba26dcf"])
        # 2026-06-05 10:03:12 新增原因：构造图谱已成功状态，下一步必须补记忆层。
        graph_state = {
            # 2026-06-05 10:03:12 新增原因：继续保留业务问题。
            "question": question,
            # 2026-06-05 10:03:12 新增原因：写入 RAG 和图谱两个已完成工具。
            "tool_results": [
                # 2026-06-05 10:03:12 新增原因：保留 RAG 成功记录。
                {"tool_name": "sql_rag_retrieve", "result": {"status": "ok"}},
                # 2026-06-05 10:03:12 新增原因：保留 Neo4j 图谱成功记录。
                {"tool_name": "sql_rag_graph_expand", "result": {"status": "succeeded", "triples": [{"subject": "反审", "predicate": "MENTIONED_IN_CHUNK", "object": "qachunk_0adc662813e7e7448ba26dcf"}]}},
            ],
            # 2026-06-05 10:03:12 新增原因：保留召回 chunk。
            "mark": {"retrieved_chunk_ids": ["qachunk_0adc662813e7e7448ba26dcf"]},
            # 2026-06-05 10:03:12 新增原因：提供用户 ID，记忆工具必须绑定真实用户。
            "user_id": "mandatory-chain-user",
        }
        # 2026-06-05 10:03:12 新增原因：读取图谱后下一项必经工具。
        memory_tool = runtime._next_missing_required_tool(graph_state)
        # 2026-06-05 10:03:12 新增原因：断言图谱后必须读取三层记忆。
        self.assertEqual(memory_tool["name"], "sql_rag_memory_read")
        # 2026-06-05 10:03:12 新增原因：构造记忆已成功状态，下一步必须经过业务工具审计。
        memory_state = {
            # 2026-06-05 10:03:12 新增原因：继续保留业务问题。
            "question": question,
            # 2026-06-05 10:03:12 新增原因：写入 RAG、图谱、记忆三个已完成工具。
            "tool_results": [
                # 2026-06-05 10:03:12 新增原因：保留 RAG 成功记录。
                {"tool_name": "sql_rag_retrieve", "result": {"status": "ok"}},
                # 2026-06-05 10:03:12 新增原因：保留图谱成功记录。
                {"tool_name": "sql_rag_graph_expand", "result": {"status": "succeeded", "triples": [{"subject": "反审", "predicate": "MENTIONED_IN_CHUNK", "object": "qachunk_0adc662813e7e7448ba26dcf"}]}},
                # 2026-06-05 10:03:12 新增原因：保留记忆读取成功记录。
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
            ],
            # 2026-06-05 10:03:12 新增原因：保留运行用户。
            "user_id": "mandatory-chain-user",
            # 2026-06-05 10:03:12 新增原因：保留召回 chunk。
            "mark": {"retrieved_chunk_ids": ["qachunk_0adc662813e7e7448ba26dcf"]},
        }
        # 2026-06-05 10:03:12 新增原因：读取记忆后下一项必经工具。
        business_tool = runtime._next_missing_required_tool(memory_state)
        # 2026-06-05 10:03:12 新增原因：断言业务工具必须经过 MCP/function calling 工具层。
        self.assertEqual(business_tool["name"], "sql_rag_business_action")
        # 2026-06-05 17:32:11 修改原因：断言默认业务节点是结构化业务上下文查询，不再只用 query_tickets 形式过场。
        self.assertEqual(business_tool["args"]["action_name"], "query_business_context")

    # 2026-06-05 10:03:12 新增原因：验证缺 Neo4j 图谱时 verifier 必须回流，不能再 score=0.8 通过。
    def test_verifier_rejects_business_answer_without_graph_evidence(self) -> None:
        # 2026-06-05 10:03:12 新增原因：创建真实纠错运行时，只测确定性校验逻辑。
        correction_runtime = AnswerCorrectionRuntime(load_correction_config())
        # 2026-06-05 10:03:12 新增原因：构造只有 RAG 没有图谱的证据，复现截图缺陷。
        evidence = [{"tool_name": "sql_rag_retrieve", "result": {"results": [{"chunk_id": "qachunk_0adc662813e7e7448ba26dcf"}], "best_answer": "可以反审。"}}]
        # 2026-06-05 10:03:12 新增原因：执行确定性校验，避免测试依赖本地 Qwen 输出。
        result = correction_runtime._deterministic_verify_answer("入账单你可以反你有反审的，对不对？", "可以反审。", evidence, "")
        # 2026-06-05 10:03:12 新增原因：断言业务问题必须要求图谱证据。
        self.assertTrue(result["requires_graph"])
        # 2026-06-05 10:03:12 新增原因：断言缺图谱时图谱要求不满足。
        self.assertFalse(result["graph_satisfied"])
        # 2026-06-05 10:03:12 新增原因：断言缺图谱时需要人工或回流纠错。
        self.assertTrue(result["needs_human"])

    # 2026-06-05 10:52:18 新增原因：复现 FastMCP 返回元组时工具结果被当成 non_dict_result 的缺陷。
    def test_mcp_tuple_result_decodes_structured_payload(self) -> None:
        # 2026-06-05 10:52:18 新增原因：创建轻量业务脑运行时，避免启动外部服务。
        runtime = self.make_runtime()
        # 2026-06-05 10:52:18 新增原因：构造 FastMCP 本地 call_tool 返回的 content_list 与 structured_result 元组。
        mcp_result = ([FakeMcpTextContent('{"status":"text_only"}')], {"status": "succeeded", "tool": "sql_rag_graph_expand", "triples": [{"subject": "反审", "predicate": "MENTIONED_IN_CHUNK", "object": "qachunk_0adc662813e7e7448ba26dcf"}]})
        # 2026-06-05 10:52:18 新增原因：执行 MCP 解码，要求优先使用结构化结果而不是文本兜底。
        decoded = runtime._decode_mcp_call_result(mcp_result)
        # 2026-06-05 10:52:18 新增原因：断言解码结果必须是 dict，才能进入 mark、Prompt Builder 和 verifier。
        self.assertIsInstance(decoded, dict)
        # 2026-06-05 10:52:18 新增原因：断言结构化状态保留下来，避免工具结果再次变成 non_dict_result。
        self.assertEqual(decoded["status"], "succeeded")
        # 2026-06-05 10:52:18 新增原因：断言 Neo4j 三元组证据不丢失，确保后续 Prompt Builder 能消费图谱。
        self.assertEqual(decoded["triples"][0]["predicate"], "MENTIONED_IN_CHUNK")

    # 2026-06-05 17:32:11 新增原因：复现截图中“订单筛选问题被入账单兜底污染”的核心缺陷。
    def test_fallback_answer_uses_current_rag_best_answer_without_hardcoded_finance_scene(self) -> None:
        # 2026-06-05 17:32:11 新增原因：创建轻量业务脑运行时，直接测试兜底答案生成函数。
        runtime = self.make_runtime()
        # 2026-06-05 17:32:11 新增原因：构造订单筛选问题，问题本身不包含入账单、反审或付款状态。
        question = "客户在查看订单列表时，不清楚如何区分和筛选出不同分厂（如越南、国内）以及产前样的订单。"
        # 2026-06-05 17:32:11 新增原因：构造与问题匹配的 RAG top1 标准答案证据。
        best_answer = "服务人员告知客户，之前已为其历史订单补填了分厂信息，现在可以直接使用筛选功能，选择特定的分厂来查看对应的订单。"
        # 2026-06-05 17:32:11 新增原因：构造已完成工具状态，让兜底函数只依赖当前问题证据。
        state = {
            # 2026-06-05 17:32:11 新增原因：保留原始问题，兜底答案必须按问题主题生成。
            "question": question,
            # 2026-06-05 17:32:11 新增原因：写入 RAG best_answer，验证兜底不再忽略正确证据。
            "mark": {"best_answer": best_answer},
            # 2026-06-05 17:32:11 新增原因：写入图谱结果，验证图谱只能补充证据，不能带偏业务主题。
            "tool_results": [
                # 2026-06-05 17:32:11 新增原因：构造与订单筛选相关的图谱三元组。
                {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "订单列表", "predicate": "RELATED_TO", "object": "分厂筛选"}]}}
            ],
        }
        # 2026-06-05 17:32:11 新增原因：调用兜底生成函数，复现模型空答后的程序分支。
        answer = runtime._compose_evidence_fallback_answer(state)
        # 2026-06-05 17:32:11 新增原因：断言答案必须覆盖当前 RAG 证据里的订单筛选核心词。
        self.assertIn("分厂", answer)
        # 2026-06-05 17:32:11 新增原因：断言答案必须覆盖当前 RAG 证据里的筛选动作。
        self.assertIn("筛选", answer)
        # 2026-06-05 17:32:11 新增原因：断言不能再把无关入账单兜底话术混进订单筛选问题。
        self.assertNotIn("入账单", answer)
        # 2026-06-05 17:32:11 新增原因：断言不能再把无关反审话术混进订单筛选问题。
        self.assertNotIn("反审", answer)

    # 2026-06-05 17:32:11 新增原因：复现工具全链完成后仍走 function-calling 空答分支的问题。
    def test_planner_uses_no_tool_final_answer_after_mandatory_tools_completed(self) -> None:
        # 2026-06-05 17:32:11 新增原因：创建轻量业务脑运行时，避免启动真实 Qwen。
        runtime = self.make_runtime()
        # 2026-06-05 17:32:11 新增原因：用列表记录无工具最终回答函数是否被调用。
        final_answer_calls: list[str] = []
        # 2026-06-05 17:32:11 新增原因：替换 planner function-calling 调用，模拟本地小模型空 content 且无 function_call。
        runtime._call_qwen = lambda state: {"content": "", "function_call": None, "prompt_builder_context": "planner-prompt"}
        # 2026-06-05 17:32:11 新增原因：替换无工具最终回答调用，用确定文本证明状态机进入正确分支。
        runtime._call_qwen_final_answer = lambda state: final_answer_calls.append("called") or {"content": "最终模型答案：请按分厂筛选订单。", "function_call": None, "prompt_builder_context": "final-prompt"}
        # 2026-06-05 17:32:11 新增原因：构造四类必经工具都已完成的状态。
        state = {
            # 2026-06-05 17:32:11 新增原因：使用订单场景触发完整 Agent 链路。
            "question": "客户要查看订单列表里不同分厂和产前样的订单，怎么筛选？",
            # 2026-06-05 17:32:11 新增原因：保留运行用户，满足记忆和业务工具上下文。
            "user_id": "mandatory-chain-user",
            # 2026-06-05 17:32:11 新增原因：写入完整工具结果，证明已不需要继续 function-calling 决策。
            "tool_results": [
                # 2026-06-05 17:32:11 新增原因：RAG 召回已成功并带 top1 答案。
                {"tool_name": "sql_rag_retrieve", "result": {"status": "ok", "results": [{"chunk_id": "qachunk_order"}], "best_answer": "使用分厂筛选查看订单。"}},
                # 2026-06-05 17:32:11 新增原因：Neo4j 图谱已成功并带三元组。
                {"tool_name": "sql_rag_graph_expand", "result": {"status": "succeeded", "triples": [{"subject": "订单", "predicate": "RELATED_TO", "object": "分厂"}]}},
                # 2026-06-05 17:32:11 新增原因：三层记忆读取已完成。
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
                # 2026-06-05 18:10:08 修改原因：只读业务上下文工具必须带动态主题证据，避免测试继续接受形式化 succeeded。
                {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "focus_terms": ["订单", "分厂", "筛选"], "business_context": ["业务主题词：订单、分厂、筛选。"]}},
            ],
            # 2026-06-05 17:32:11 新增原因：写入 RAG mark，供图谱和兜底逻辑读取。
            "mark": {"retrieved_chunk_ids": ["qachunk_order"], "best_answer": "使用分厂筛选查看订单。"},
        }
        # 2026-06-05 17:32:11 新增原因：执行 planner，验证工具完成后的最终回答状态机。
        next_state = runtime._planner_node(state)
        # 2026-06-05 17:32:11 新增原因：断言必须调用无工具最终回答函数，而不是停在空答兜底。
        self.assertEqual(final_answer_calls, ["called"])
        # 2026-06-05 17:32:11 新增原因：断言草稿来自无工具最终回答模型输出。
        self.assertEqual(next_state["draft_answer"], "最终模型答案：请按分厂筛选订单。")
        # 2026-06-05 17:32:11 新增原因：断言没有继续安排工具调用，避免循环或重复工具。
        self.assertEqual(next_state["pending_tool_call"], {})

    # 2026-06-05 19:11:30 新增原因：复现 Qwen3 最终回答只吐 reasoning_content 导致 content 空、程序进入兜底的问题。
    def test_final_answer_disables_qwen_thinking_to_return_model_content(self) -> None:
        # 2026-06-05 19:11:30 新增原因：创建轻量业务脑运行时，不连接真实 Qwen。
        runtime = self.make_runtime()
        # 2026-06-05 19:11:30 新增原因：注入 Qwen 替身，捕获最终回答调用参数。
        runtime.qwen_llm = FakeFinalAnswerQwen()
        # 2026-06-05 19:11:30 新增原因：构造证据链完成后的最终回答状态。
        state = {
            # 2026-06-05 19:11:30 新增原因：保留用户原问题，Prompt Builder 必须把它交给模型消费。
            "question": "入账单反审后付款状态为什么要退回？",
            # 2026-06-05 19:11:30 新增原因：写入 RAG 和业务锚点，最终回答不能依赖硬编码兜底。
            "mark": {"best_answer": "先反审入账单，再让付款状态退回。", "business_context": ["业务主题词：入账单、反审、付款状态。"]},
            # 2026-06-05 19:11:30 新增原因：写入工具结果，模拟 Prompt Builder 已拿到证据上下文。
            "tool_results": [
                # 2026-06-05 19:11:30 新增原因：RAG 证据已完成。
                {"tool_name": "sql_rag_retrieve", "result": {"best_answer": "先反审入账单，再让付款状态退回。"}},
                # 2026-06-05 19:11:30 新增原因：图谱证据已完成。
                {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "入账单", "predicate": "关联", "object": "付款状态"}]}},
                # 2026-06-05 19:11:30 新增原因：业务上下文已完成。
                {"tool_name": "sql_rag_business_action", "result": {"action_name": "query_business_context", "status": "succeeded", "focus_terms": ["入账单", "付款状态"], "business_context": ["业务主题词：入账单、付款状态。"]}},
            ],
        }
        # 2026-06-05 19:11:30 新增原因：调用最终回答节点，验证它直接使用模型 content。
        result = runtime._call_qwen_final_answer(state)
        # 2026-06-05 19:11:30 新增原因：断言答案来源是模型最终回答，不是 evidence_fallback。
        self.assertEqual(result["answer_source"], "qwen_final_answer")
        # 2026-06-05 19:11:30 新增原因：读取 Qwen 替身记录的第一次最终回答调用。
        first_call = runtime.qwen_llm.calls[0]
        # 2026-06-05 19:11:30 新增原因：断言通过 extra_body 关闭 Qwen3 thinking，防止 reasoning_content 吃完 token。
        self.assertEqual(first_call.get("extra_generate_cfg"), {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}})

    # 2026-06-06 10:59:53 新增原因：锁定最终模型消费 Prompt Builder 的通用约束，防止只走链路却空答或偏离 top1 chunk。
    def test_final_answer_prompt_requires_chunk_grounded_model_answer(self) -> None:
        # 2026-06-06 10:59:53 新增原因：创建轻量业务脑运行时，避免单测启动真实前后端服务。
        runtime = self.make_runtime()
        # 2026-06-06 10:59:53 新增原因：注入最终回答 Qwen 替身，用调用参数验证 Prompt Builder 是否交到模型。
        runtime.qwen_llm = FakeFinalAnswerQwen()
        # 2026-06-06 10:59:53 新增原因：构造是/否型业务问题，验证回答形态约束不是某个固定场景专用。
        state = {
            # 2026-06-06 10:59:53 新增原因：问题文本携带是/否判断形态，要求模型第一句正面回答。
            "question": "这条业务记录是否应该先退回状态再继续后续处理？",
            # 2026-06-06 10:59:53 新增原因：mark 写入任意业务 top1 标准答案，验证事实方向优先约束。
            "mark": {"best_answer": "应先退回状态，确认前置处理完成后再继续后续业务动作。"},
            # 2026-06-06 10:59:53 新增原因：工具结果覆盖 RAG、图谱、记忆、业务动作，模拟完整证据链已完成。
            "tool_results": [
                # 2026-06-06 10:59:53 新增原因：RAG 证据提供 top1 标准答案，最终回答必须贴住它。
                {"tool_name": "sql_rag_retrieve", "result": {"status": "ok", "best_answer": "应先退回状态，确认前置处理完成后再继续后续业务动作。", "results": [{"chunk_id": "qachunk_generic"}]}},
                # 2026-06-06 10:59:53 新增原因：图谱证据提供业务关系，但不允许模型泄露内部 chunk ID。
                {"tool_name": "sql_rag_graph_expand", "result": {"backend": "neo4j_triple_graph", "triples": [{"subject": "状态退回", "predicate": "前置于", "object": "后续处理"}]}},
                # 2026-06-06 10:59:53 新增原因：记忆节点存在，验证完整 Prompt Builder 分区。
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok", "memories": []}},
                # 2026-06-06 10:59:53 新增原因：业务工具提供只读上下文，验证不是 query_tickets 形式过场。
                {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "business_context": ["业务上下文：状态退回是后续处理的前置条件。"]}},
            ],
        }
        # 2026-06-06 10:59:53 新增原因：调用最终回答节点，捕获真实传给模型的 Prompt Builder。
        result = runtime._call_qwen_final_answer(state)
        # 2026-06-06 10:59:53 新增原因：读取模型调用消息，验证最终回答不是绕过模型直接拼兜底。
        sent_text = "\n".join(message["content"] for message in runtime.qwen_llm.calls[0]["messages"])
        # 2026-06-06 10:59:53 新增原因：Prompt Builder 必须要求以 top1 chunk 的事实方向为准。
        self.assertIn("必须以 RAG top1 标准答案证据的事实方向为准", sent_text)
        # 2026-06-06 10:59:53 新增原因：是/否问题必须第一句先正面回答，不能只解释一圈。
        self.assertIn("是/否问题第一句必须先回答“是”或“不是”", sent_text)
        # 2026-06-06 11:24:38 新增原因：是/否极性必须跟 top1 证据方向一致，防止肯定证据被模型答成“不是”。
        self.assertIn("肯定或否定方向必须跟 RAG top1 标准答案一致", sent_text)
        # 2026-06-06 11:38:19 新增原因：最终用户答案不能暴露 Prompt Builder、RAG top1、Neo4j 等内部链路名。
        self.assertIn("最终用户答案不要输出 Prompt Builder、RAG top1、Neo4j", sent_text)
        # 2026-06-06 12:02:07 新增原因：最终用户答案不能暴露重试痕迹或调试话术，保证语言自然通顺。
        self.assertIn("不要提上一版回答、错误答案、纠正说明、证据锚点或重试过程", sent_text)
        # 2026-06-06 10:59:53 新增原因：空答不能被兜底冒充模型回答，必须触发重试或转人工。
        self.assertIn("模型空答时不得把兜底证据草稿标记成模型回答", sent_text)
        # 2026-06-06 10:59:53 新增原因：返回来源必须仍是真模型最终回答通道。
        self.assertEqual(result["answer_source"], "qwen_final_answer")

    # 2026-06-06 11:46:12 新增原因：复现长 RAG/图谱证据把回答约束截断，导致模型看不到极性和空答规则的缺陷。
    def test_prompt_builder_truncation_preserves_answer_constraints(self) -> None:
        # 2026-06-06 11:46:12 新增原因：创建轻量业务脑运行时，直接测试 Prompt Builder 拼装。
        runtime = self.make_runtime()
        # 2026-06-06 11:46:12 新增原因：构造超长证据，模拟真实 Neo4j 多跳路径和 RAG 片段挤占上下文。
        long_evidence = "超长业务证据" * 900
        # 2026-06-06 11:46:12 新增原因：构造完整工具结果，确保回答约束位于证据之后。
        state = {
            # 2026-06-06 11:46:12 新增原因：保留任意业务问题，不绑定具体截图场景。
            "question": "这条业务记录是不是要先处理前置状态？",
            # 2026-06-06 11:46:12 新增原因：写入 top1 标准答案，供回答约束引用。
            "mark": {"best_answer": "可以，应该先处理前置状态再继续后续动作。"},
            # 2026-06-06 11:46:12 新增原因：写入超长 RAG/图谱/业务证据，复现截断风险。
            "tool_results": [
                # 2026-06-06 11:46:12 新增原因：RAG 证据超长，模拟真实 chunk 摘录过大。
                {"tool_name": "sql_rag_retrieve", "result": {"best_answer": "可以，应该先处理前置状态再继续后续动作。", "results": [{"chunk_id": "qachunk_generic", "source_excerpt_full": long_evidence}]}},
                # 2026-06-06 11:46:12 新增原因：图谱证据超长，模拟多跳路径过多。
                {"tool_name": "sql_rag_graph_expand", "result": {"backend": "neo4j_triple_graph", "triples": [{"subject": long_evidence, "predicate": "关联", "object": long_evidence}]}},
                # 2026-06-06 11:46:12 新增原因：记忆证据存在，覆盖完整分区。
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
                # 2026-06-06 11:46:12 新增原因：业务证据存在，覆盖完整分区。
                {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "business_context": [long_evidence]}},
            ],
        }
        # 2026-06-06 11:46:12 新增原因：构建 Prompt Builder，验证截断策略是否保留尾部回答合同。
        prompt = runtime._build_prompt_builder_context(state)
        # 2026-06-06 11:46:12 新增原因：回答约束分区必须保留，不能被长证据挤掉。
        self.assertIn("[回答约束]", prompt)
        # 2026-06-06 11:46:12 新增原因：极性约束必须保留，防止是/否题答反。
        self.assertIn("肯定或否定方向必须跟 RAG top1 标准答案一致", prompt)
        # 2026-06-06 11:46:12 新增原因：空答约束必须保留，防止兜底冒充模型。
        self.assertIn("模型空答时不得把兜底证据草稿标记成模型回答", prompt)
        # 2026-06-06 11:46:12 新增原因：内部名禁止输出约束必须保留，保证最终语言自然。
        self.assertIn("最终用户答案不要输出 Prompt Builder、RAG top1、Neo4j", prompt)
        # 2026-06-06 12:02:07 新增原因：重试痕迹禁止输出约束必须保留，避免用户看到内部纠错过程。
        self.assertIn("不要提上一版回答、错误答案、纠正说明、证据锚点或重试过程", prompt)

    # 2026-06-06 11:46:12 新增原因：复现模型第一次把 top1 肯定证据答成否定时，最终回答节点应无工具重试而不是直接交给 verifier。
    def test_final_answer_retries_when_model_reverses_yes_no_polarity(self) -> None:
        # 2026-06-06 11:46:12 新增原因：创建轻量业务脑运行时，直接测试最终回答节点。
        runtime = self.make_runtime()
        # 2026-06-06 11:46:12 新增原因：注入极性反写替身，第一轮错、第二轮对。
        runtime.qwen_llm = FakePolarityRetryQwen()
        # 2026-06-06 11:46:12 新增原因：构造肯定 top1 证据和完整工具链，验证重试不是硬编码兜底。
        state = {
            # 2026-06-06 11:46:12 新增原因：问题是/否型，最容易暴露极性反写。
            "question": "这条业务记录是不是要先退回状态再继续处理？",
            # 2026-06-06 11:46:12 新增原因：mark 写入肯定证据。
            "mark": {"best_answer": "可以，应该先退回状态，确认前置处理完成后再继续后续业务动作。"},
            # 2026-06-06 11:46:12 新增原因：tool_results 提供 verifier 和极性检测所需证据。
            "tool_results": [
                # 2026-06-06 11:46:12 新增原因：RAG top1 是肯定方向。
                {"tool_name": "sql_rag_retrieve", "result": {"best_answer": "可以，应该先退回状态，确认前置处理完成后再继续后续业务动作。", "results": [{"chunk_id": "qachunk_generic"}]}},
                # 2026-06-06 11:46:12 新增原因：图谱证据补充关系。
                {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "状态退回", "predicate": "前置于", "object": "继续处理"}]}},
                # 2026-06-06 11:46:12 新增原因：记忆节点存在。
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
                # 2026-06-06 11:46:12 新增原因：业务上下文节点存在。
                {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "business_context": ["业务上下文：状态退回是继续处理的前置条件。"]}},
            ],
        }
        # 2026-06-06 11:46:12 新增原因：执行最终回答节点。
        result = runtime._call_qwen_final_answer(state)
        # 2026-06-06 11:46:12 新增原因：断言发生了两次模型调用，第二次是无工具重试。
        self.assertEqual(len(runtime.qwen_llm.calls), 2)
        # 2026-06-06 11:46:12 新增原因：断言最终采用重试后的模型答案来源。
        self.assertEqual(result["answer_source"], "qwen_final_answer_retry")
        # 2026-06-06 11:46:12 新增原因：断言最终内容按 top1 肯定方向修正。
        self.assertTrue(result["content"].startswith("是"))

    # 2026-06-06 12:54:47 新增原因：复现压缩 evidence 缺少 top1 时最终回答极性漏判，保证任意业务 chunk 都从 mark/tool_results 汇总证据。
    def test_final_answer_retry_uses_mark_and_tool_results_when_compact_evidence_lacks_top1(self) -> None:
        # 2026-06-06 12:54:47 新增原因：创建轻量业务脑运行时，直接测试最终回答节点的全局证据汇总。
        runtime = self.make_runtime()
        # 2026-06-06 12:54:47 新增原因：注入极性反写替身，第一轮错、第二轮对，验证不是兜底硬编码。
        runtime.qwen_llm = FakePolarityRetryQwen()
        # 2026-06-06 12:54:47 新增原因：构造任意业务场景，mark 和 tool_results 有 top1，compact evidence 只有图谱摘要。
        state = {
            # 2026-06-06 12:54:47 新增原因：问题不绑定入账单，验证极性检查对任意业务对象泛化。
            "question": "这条业务记录是不是要先完成前置状态再继续后续处理？",
            # 2026-06-06 12:54:47 新增原因：mark 保存 RAG top1 事实方向，最终回答极性检查必须优先读取。
            "mark": {"best_answer": "可以，应该先完成前置状态，确认完成后再继续后续处理。"},
            # 2026-06-06 12:54:47 新增原因：压缩 evidence 模拟真实运行中 verifier 小摘要缺少 best_answer 的情况。
            "evidence": [{"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "前置状态", "predicate": "前置于", "object": "后续处理"}]}}],
            # 2026-06-06 12:54:47 新增原因：原始工具结果仍带 RAG top1，最终回答节点必须把它纳入极性检查。
            "tool_results": [
                # 2026-06-06 12:54:47 新增原因：RAG top1 是肯定方向，不能因 evidence 已非空而被跳过。
                {"tool_name": "sql_rag_retrieve", "result": {"best_answer": "可以，应该先完成前置状态，确认完成后再继续后续处理。", "results": [{"chunk_id": "qachunk_generic"}]}},
                # 2026-06-06 12:54:47 新增原因：图谱证据补充关系。
                {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "前置状态", "predicate": "前置于", "object": "后续处理"}]}},
                # 2026-06-06 12:54:47 新增原因：记忆节点存在。
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
                # 2026-06-06 12:54:47 新增原因：业务上下文节点存在。
                {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "business_context": ["业务上下文：前置状态完成后再继续后续处理。"]}},
            ],
        }
        # 2026-06-06 12:54:47 新增原因：执行最终回答节点。
        result = runtime._call_qwen_final_answer(state)
        # 2026-06-06 12:54:47 新增原因：断言压缩 evidence 缺 top1 时仍触发两次模型调用。
        self.assertEqual(len(runtime.qwen_llm.calls), 2)
        # 2026-06-06 12:54:47 新增原因：断言返回的是模型重试答案来源，而不是第一次答反内容。
        self.assertEqual(result["answer_source"], "qwen_final_answer_retry")

    # 2026-06-06 14:54:36 新增原因：复现口语化 top1 抽不出业务字段，导致 Prompt Builder 和 verifier 缺少证据关键词。
    def test_semantic_terms_extract_noisy_top1_business_fields(self) -> None:
        # 2026-06-06 14:54:36 新增原因：构造含口语、省略号和多动作的任意业务 top1。
        noisy_top1 = "如果是说这笔账要冲的话，那这张入仓单也进行财务反审，等于让预付款的充账状态返回回来，然后直接做付款单。"
        # 2026-06-06 14:54:36 新增原因：执行通用抽词，不允许只返回空或数字。
        terms = extract_semantic_terms(noisy_top1, limit=24)
        # 2026-06-06 14:54:36 新增原因：断言单据类对象必须被抽出，供后续答案贴合 chunk。
        self.assertIn("入仓单", terms)
        # 2026-06-06 14:54:36 新增原因：断言审核动作必须被抽出，避免财务反审链路丢失。
        self.assertIn("财务反审", terms)
        # 2026-06-06 14:54:36 新增原因：断言状态字段必须被抽出，覆盖任意状态回退类业务。
        self.assertIn("充账状态", terms)
        # 2026-06-06 14:54:36 新增原因：断言后续单据对象必须被抽出，避免只回答前半段。
        self.assertIn("付款单", terms)

    # 2026-06-06 13:17:22 新增原因：复现 top1 和答案都含混合词时词袋极性互相抵消，要求按首个事实方向泛化判冲突。
    def test_polarity_conflict_uses_primary_evidence_direction_before_mixed_terms(self) -> None:
        # 2026-06-06 13:17:22 新增原因：构造 top1 开头是肯定方向、后文带风险否定词的任意业务证据。
        evidence_texts = ["可以，应该先完成前置状态，再继续后续处理；否则后面可能无法处理。"]
        # 2026-06-06 13:17:22 新增原因：构造答案开头是否定方向、后文带可以词的反向模型草稿。
        answer = "不是，不需要先完成前置状态，可以直接继续后续处理。"
        # 2026-06-06 13:17:22 新增原因：执行通用极性校验，不依赖具体业务名。
        result = semantic_answer_polarity_conflict(answer, evidence_texts)
        # 2026-06-06 13:17:22 新增原因：断言 top1 首个事实方向为肯定时，答案开头否定必须被拦截。
        self.assertTrue(result["conflict"])
        # 2026-06-06 13:17:22 新增原因：断言失败原因可被 verifier 和数据飞轮复用。
        self.assertEqual(result["reason"], "answer_polarity_conflict")

    # 2026-06-06 13:41:09 新增原因：复现 top1 肯定证据后文带风险词时正确肯定答案被误杀的泛化 verifier 缺陷。
    def test_polarity_allows_primary_positive_answer_with_secondary_risk_terms(self) -> None:
        # 2026-06-06 13:41:09 新增原因：构造任意业务 top1，首要事实方向是要先完成动作。
        evidence_texts = ["如果这笔业务要继续处理，需要先完成前置动作，再执行后续步骤。", "否则可能无法继续，后续也不能直接处理。"]
        # 2026-06-06 13:41:09 新增原因：构造正确肯定答案，后续风险词不应把它判成冲突。
        answer = "是，要先完成前置动作，再执行后续步骤。"
        # 2026-06-06 13:41:09 新增原因：执行通用极性校验，不绑定入账单或订单场景。
        result = semantic_answer_polarity_conflict(answer, evidence_texts)
        # 2026-06-06 13:41:09 新增原因：断言正确肯定答案不能被次要风险否定词误杀。
        self.assertFalse(result["conflict"])

    # 2026-06-06 13:41:09 新增原因：复现答案先给肯定结论、后解释“不做会无法处理”时被单向证据规则误杀的问题。
    def test_polarity_allows_positive_answer_with_later_negative_reason(self) -> None:
        # 2026-06-06 13:41:09 新增原因：构造单向肯定 top1 证据，表示必须先做前置动作。
        evidence_texts = ["可以，应该先完成前置动作，再继续后续业务处理。"]
        # 2026-06-06 13:41:09 新增原因：构造正确答案，首句肯定，后面用“无法”解释不做的后果。
        answer = "是，应该先完成前置动作。原因是如果不先完成前置动作，后续状态可能无法继续处理。"
        # 2026-06-06 13:41:09 新增原因：执行通用极性校验，验证只按首个答案方向判断结论。
        result = semantic_answer_polarity_conflict(answer, evidence_texts)
        # 2026-06-06 13:41:09 新增原因：断言原因说明中的风险否定词不能推翻首句肯定结论。
        self.assertFalse(result["conflict"])

    # 2026-06-06 13:41:09 新增原因：复现口语 top1 使用“要做某动作”而不是“可以/应该”时，反向答案漏判的泛化缺陷。
    def test_polarity_conflict_recognizes_generic_required_action_terms(self) -> None:
        # 2026-06-06 13:41:09 新增原因：构造任意业务口语证据，只表达“要先做动作”，不依赖固定关键词。
        evidence_texts = ["如果这笔账要冲的话，那这张单据要先做前置审核，让状态返回回来。"]
        # 2026-06-06 13:41:09 新增原因：构造反向答案，模型把“要先做”答成“不需要”必须被拦截。
        answer = "不是，不需要先做前置审核，可以直接继续处理。"
        # 2026-06-06 13:41:09 新增原因：执行通用极性校验。
        result = semantic_answer_polarity_conflict(answer, evidence_texts)
        # 2026-06-06 13:41:09 新增原因：断言“要+动作”类证据也能驱动极性冲突识别。
        self.assertTrue(result["conflict"])

    # 2026-06-06 13:41:09 新增原因：复现 Prompt Builder 有证据时模型仍逃逸说证据不足，最终回答阶段必须重试模型。
    def test_final_answer_retries_evasive_model_answer_when_top1_evidence_exists(self) -> None:
        # 2026-06-06 13:41:09 新增原因：创建轻量业务脑运行时，直接测试最终回答节点，不启动真实服务。
        runtime = self.make_runtime()
        # 2026-06-06 13:41:09 新增原因：注入逃逸回答替身，第一轮逃逸、第二轮按证据回答。
        runtime.qwen_llm = FakeEvasiveFinalAnswerQwen()
        # 2026-06-06 13:41:09 新增原因：构造完整证据链，证明证据齐全时不能让“证据不足”直接进入 verifier。
        state = {
            # 2026-06-06 13:41:09 新增原因：保留是/否型用户问题，要求最终答案第一句正面结论。
            "question": "这笔业务是不是要先做前置审核，再把状态退回来继续处理？",
            # 2026-06-06 13:41:09 新增原因：写入口语化 top1 证据，覆盖任意 chunk 里的“要做某动作”表达。
            "mark": {"best_answer": "如果这笔账要冲的话，那这张单据要先做前置审核，让状态返回回来，再继续后续处理。"},
            # 2026-06-06 13:41:09 新增原因：写入四类工具结果，模拟 Prompt Builder 已经拿到完整证据。
            "tool_results": [
                # 2026-06-06 13:41:09 新增原因：RAG 证据提供 top1 标准答案。
                {"tool_name": "sql_rag_retrieve", "result": {"status": "ok", "best_answer": "如果这笔账要冲的话，那这张单据要先做前置审核，让状态返回回来，再继续后续处理。", "results": [{"chunk_id": "qachunk_generic"}]}},
                # 2026-06-06 13:41:09 新增原因：图谱证据提供关系。
                {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "前置审核", "predicate": "前置于", "object": "状态返回"}]}},
                # 2026-06-06 13:41:09 新增原因：记忆节点存在。
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
                # 2026-06-06 13:41:09 新增原因：业务工具提供只读业务上下文。
                {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "focus_terms": ["前置审核", "状态返回"], "business_context": ["业务上下文：前置审核完成后，状态返回才能继续后续处理。"]}},
            ],
        }
        # 2026-06-06 13:41:09 新增原因：执行最终回答节点，验证它会把逃逸答案送回模型重试。
        result = runtime._call_qwen_final_answer(state)
        # 2026-06-06 13:41:09 新增原因：断言发生两次模型调用，第二次仍是模型组织答案，不是程序硬编码兜底。
        self.assertEqual(len(runtime.qwen_llm.calls), 2)
        # 2026-06-06 13:41:09 新增原因：断言最终来源标记为模型重试答案。
        self.assertEqual(result["answer_source"], "qwen_final_answer_retry")
        # 2026-06-06 13:41:09 新增原因：断言最终答案正面回答用户的是/否问题。
        self.assertTrue(result["content"].startswith("是"))

    # 2026-06-06 14:54:36 新增原因：复现模型最终答案泄露内部链路词，要求用模型重试生成纯用户答案。
    def test_final_answer_retries_internal_token_leak(self) -> None:
        # 2026-06-06 14:54:36 新增原因：创建轻量业务脑运行时，直接测试最终回答节点。
        runtime = self.make_runtime()
        # 2026-06-06 14:54:36 新增原因：注入内部词泄露替身，第一轮泄露、第二轮修复。
        runtime.qwen_llm = FakeInternalLeakFinalAnswerQwen()
        # 2026-06-06 14:54:36 新增原因：构造完整证据链，证明泄露不是因为缺证据。
        state = {
            # 2026-06-06 14:54:36 新增原因：保留订单筛选问题，避免绑定入仓单场景。
            "question": "客户能不能按分厂筛选订单？",
            # 2026-06-06 14:54:36 新增原因：写入 top1 证据，模型必须基于证据回答。
            "mark": {"best_answer": "服务人员告知客户，现在可以直接使用筛选功能，选择特定分厂查看订单。"},
            # 2026-06-06 14:54:36 新增原因：写入四类工具结果，模拟 Prompt Builder 已完成。
            "tool_results": [
                # 2026-06-06 14:54:36 新增原因：RAG 证据提供标准答案。
                {"tool_name": "sql_rag_retrieve", "result": {"status": "ok", "best_answer": "服务人员告知客户，现在可以直接使用筛选功能，选择特定分厂查看订单。", "results": [{"chunk_id": "qachunk_order"}]}},
                # 2026-06-06 14:54:36 新增原因：图谱证据提供业务关系。
                {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "分厂", "predicate": "用于筛选", "object": "订单"}]}},
                # 2026-06-06 14:54:36 新增原因：记忆节点存在。
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
                # 2026-06-06 14:54:36 新增原因：业务工具提供只读上下文。
                {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "focus_terms": ["分厂", "订单"], "business_context": ["业务上下文：客户需要按分厂筛选订单。"]}},
            ],
        }
        # 2026-06-06 14:54:36 新增原因：执行最终回答节点，验证泄露答案会触发模型重试。
        result = runtime._call_qwen_final_answer(state)
        # 2026-06-06 14:54:36 新增原因：断言发生两次模型调用。
        self.assertEqual(len(runtime.qwen_llm.calls), 2)
        # 2026-06-06 14:54:36 新增原因：断言最终答案来源仍是模型重试，不是程序清洗兜底。
        self.assertEqual(result["answer_source"], "qwen_final_answer_retry")
        # 2026-06-06 14:54:36 新增原因：断言最终用户答案不含内部链路词。
        self.assertNotIn("RAG", result["content"])

    # 2026-06-08 18:08:41 test: retry prompt must not expose repair wording to the model.
    def test_final_answer_retry_prompt_hides_internal_repair_words(self) -> None:
        runtime = self.make_runtime()
        messages = runtime._final_answer_retry_messages("minimal evidence context", {"reason": "answer_quality_failed"})
        retry_prompt = "\n".join(message["content"] for message in messages)
        for token in ("上一版", "错误答案", "纠正说明", "证据锚点", "重试", "质量失败原因"):
            self.assertNotIn(token, retry_prompt)

    # 2026-06-06 14:54:36 新增原因：复现 verifier 发现语义错配后直接转人工，要求先回模型修复一次再复验。

    # 2026-06-09 09:12:31 Added: troubleshooting questions must not pass with a yes/need lead when top1 is negative.
    def test_procedure_question_rejects_positive_lead_but_accepts_step_answer(self) -> None:
        question = "\u6309\u94ae\u6743\u9650\u600e\u4e48\u6392\u67e5"
        evidence = ["\u5982\u679c\u4e0d\u80fd\u7ed9\u8c03\u6574\u6743\u9650\uff0c\u5c31\u5728\u5458\u5de5\u8d44\u6599\u6388\u6743\u91cc\u52fe\u6389\u3002\u7b2c\u4e8c\u6b65\u73b0\u573a\u7ba1\u7406\u3002"]
        bad = "**\u662f**\n\n\u9700\u8981\u5148\u770b\u8c03\u6574\u6743\u9650\uff0c\u518d\u6838\u5bf9\u5458\u5de5\u8d44\u6599\u6388\u6743\u548c\u73b0\u573a\u7ba1\u7406\u3002"
        bad_result = semantic_answer_grounded_equivalence(question, bad, evidence)
        self.assertFalse(bad_result["equivalent"])
        self.assertEqual(bad_result["procedural_polarity_check"]["reason"], "procedural_answer_reintroduces_yes_no_polarity")
        good = "\u6392\u67e5\u987a\u5e8f\uff1a\u5148\u770b\u8c03\u6574\u6743\u9650\uff0c\u5982\u679c\u4e0d\u80fd\u7ed9\u8c03\u6574\u6743\u9650\uff0c\u5c31\u5728\u5458\u5de5\u8d44\u6599\u6388\u6743\u91cc\u52fe\u6389\uff1b\u518d\u770b\u73b0\u573a\u7ba1\u7406\u3002"
        good_result = semantic_answer_grounded_equivalence(question, good, evidence)
        self.assertTrue(good_result["equivalent"])


    # 2026-06-09 09:38:12 Added: troubleshooting answers must also remove modal words inside the lead, not only a leading yes token.

    # 2026-06-09 09:47:18 Added: strict negative-evidence checks treat the yes character inside yes/no wording as a positive lead.

    # 2026-06-09 09:57:28 Added: if the model writes a yes conclusion before its own troubleshooting steps, keep the model steps and drop the polluted preface.

    # 2026-06-09 10:08:44 Added: when model writes numbered troubleshooting steps after a positive preface, keep the steps and drop meta sections.
    def test_final_answer_shape_normalization_keeps_numbered_steps_over_positive_preface(self) -> None:
        runtime = self.make_runtime()
        state = {"question": "\u6309\u94ae\u6743\u9650\u600e\u4e48\u6392\u67e5"}
        answer = "\u8d26\u53f7\u3001\u89d2\u8272\u4e4b\u95f4\u5e94\u9075\u5faa\u5148\u6388\u6743\u518d\u8c03\u6574\u3002\n1. \u57fa\u7840\u8d44\u6599\uff1a\u82e5\u7528\u6237\u770b\u4e0d\u5230\u6309\u94ae\uff0c\u82e5\u672a\u52fe\u9009\u6388\u6743\uff0c\u5c31\u52fe\u6389\u5458\u5de5\u8d44\u6599\u6388\u6743\u3002\n\n\u72b6\u6001\u4e0e\u6761\u4ef6\uff1a\u6743\u9650\u914d\u7f6e\u72b6\u6001\u3002"
        normalized = runtime._normalize_final_answer_shape(state, answer)
        self.assertTrue(normalized["normalized"])
        self.assertTrue(normalized["answer"].startswith("\u6392\u67e5\u987a\u5e8f"))
        self.assertNotIn("\u5e94\u9075\u5faa", normalized["answer"][:80])
        self.assertNotIn("\u72b6\u6001\u4e0e\u6761\u4ef6", normalized["answer"])

    def test_final_answer_shape_normalization_drops_preamble_before_procedure_steps(self) -> None:
        runtime = self.make_runtime()
        state = {"question": "\u6309\u94ae\u6743\u9650\u600e\u4e48\u6392\u67e5"}
        answer = "\u7ed3\u8bba\uff1a\u662f\u3002\n\u4e1a\u52a1\u5bf9\u8c61\u4e0e\u52a8\u4f5c\u5173\u7cfb\uff1a\u72b6\u6001\u3002\n\n\u6392\u67e5/\u5904\u7406\u987a\u5e8f\uff1a\n1. \u68c0\u67e5\u5458\u5de5\u8d44\u6599\u6388\u6743\u3002\n\n\u7ed3\u8bba\uff1a\n\u662f\u3002\u6839\u636e\u4e1a\u52a1\u8bc1\u636e\uff0c\u7ee7\u7eed\u6392\u67e5\u6388\u6743\u3002"
        normalized = runtime._normalize_final_answer_shape(state, answer)
        self.assertTrue(normalized["normalized"])
        self.assertTrue(normalized["answer"].startswith("\u6392\u67e5"))
        self.assertNotIn("\u7ed3\u8bba\uff1a\u662f", normalized["answer"][:20])
        self.assertNotIn("\u7ed3\u8bba", normalized["answer"])

    def test_final_answer_shape_normalization_rewrites_yes_no_word_in_procedure_lead(self) -> None:
        runtime = self.make_runtime()
        state = {"question": "\u6309\u94ae\u6743\u9650\u600e\u4e48\u6392\u67e5"}
        answer = "\u6392\u67e5\u987a\u5e8f\uff1a\u786e\u8ba4\u7528\u6237\u5f53\u524d\u662f\u5426\u62e5\u6709\u5de5\u5177\u680f\u6743\u9650\u6309\u94ae\u7684\u6388\u6743\u3002"
        normalized = runtime._normalize_final_answer_shape(state, answer)
        self.assertTrue(normalized["normalized"])
        self.assertNotIn("\u662f\u5426", normalized["answer"][:100])
        self.assertIn("\u6709\u65e0", normalized["answer"][:100])

    def test_final_answer_shape_normalization_removes_procedure_modal_words(self) -> None:
        runtime = self.make_runtime()
        state = {"question": "\u6309\u94ae\u6743\u9650\u600e\u4e48\u6392\u67e5"}
        answer = "\u6392\u67e5\u987a\u5e8f\uff1a\u9700\u8981\u5148\u770b\u8c03\u6574\u6743\u9650\uff0c\u5e94\u8be5\u518d\u6838\u5bf9\u5458\u5de5\u8d44\u6599\u6388\u6743\u3002"
        normalized = runtime._normalize_final_answer_shape(state, answer)
        self.assertTrue(normalized["normalized"])
        self.assertNotIn("\u9700\u8981", normalized["answer"][:100])
        self.assertNotIn("\u5e94\u8be5", normalized["answer"][:100])

    # 2026-06-09 09:12:31 Added: a grounded model body with a polluted yes lead should be normalized then rechecked, not hard-covered.
    def test_final_answer_normalizes_procedure_positive_lead_before_quality_gate(self) -> None:
        runtime = self.make_runtime()
        runtime.qwen_llm = FakeProcedureLeadFinalAnswerQwen()
        best_answer = "\u5982\u679c\u4e0d\u80fd\u7ed9\u8c03\u6574\u6743\u9650\uff0c\u5c31\u5728\u5458\u5de5\u8d44\u6599\u6388\u6743\u91cc\u52fe\u6389\u3002\u7b2c\u4e8c\u6b65\u73b0\u573a\u7ba1\u7406\u3002"
        state = {
            "question": "\u6309\u94ae\u6743\u9650\u600e\u4e48\u6392\u67e5",
            "mark": {"best_answer": best_answer},
            "tool_results": [
                {"tool_name": "sql_rag_retrieve", "result": {"status": "ok", "best_answer": best_answer, "results": [{"chunk_id": "qachunk_permission"}]}},
                {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "\u6388\u6743", "predicate": "\u5f71\u54cd", "object": "\u8c03\u6574\u6743\u9650"}]}},
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
                {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "focus_terms": ["\u8c03\u6574\u6743\u9650", "\u6388\u6743"], "business_context": ["\u4e1a\u52a1\u4e0a\u4e0b\u6587\uff1a\u8c03\u6574\u6743\u9650\u8981\u770b\u5458\u5de5\u8d44\u6599\u6388\u6743\u548c\u73b0\u573a\u7ba1\u7406\u3002"]}},
            ],
        }
        result = runtime._call_qwen_final_answer(state)
        self.assertEqual(result["answer_source"], "qwen_final_answer")
        self.assertFalse(result["content"].lstrip().startswith("**\u662f**"))
        self.assertFalse(result["content"].lstrip().startswith("\u662f"))
        self.assertTrue(result["answer_quality"]["passed"])
        self.assertTrue(result["answer_shape_normalized"])

    def test_verifier_retries_model_answer_before_transfer_human(self) -> None:
        # 2026-06-06 14:54:36 新增原因：创建轻量业务脑运行时。
        runtime = self.make_runtime()
        # 2026-06-06 14:54:36 新增原因：注入 verifier 修复替身，隔离真实数据库和 LangSmith。
        runtime.correction_runtime = FakeVerifierRepairCorrectionRuntime()
        # 2026-06-06 14:54:36 新增原因：注入模型修复替身，证明低置信后会回到模型而非 renderer 兜底。
        runtime.qwen_llm = FakeVerifierRepairQwen()
        # 2026-06-06 14:54:36 新增原因：构造初始跑偏答案和完整证据链。
        state = {
            # 2026-06-06 14:54:36 新增原因：保留需覆盖单据关系的泛化追问。
            "question": "状态退回来以后还要重新冲账，应该先确认哪些单据关系？",
            # 2026-06-06 14:54:36 新增原因：写入模型第一次不完整草稿。
            "draft_answer": "状态退回后可以继续付款。",
            # 2026-06-06 14:54:36 新增原因：标记草稿来自模型最终回答。
            "draft_answer_source": "qwen_final_answer",
            # 2026-06-06 14:54:36 新增原因：写入 mark 里的 top1 证据，修复 prompt 要保留证据事实。
            "mark": {"best_answer": "这张入仓单要财务反审，让预付款充账状态返回，然后确认付款单关系再重新冲账。", "public_trace_events": []},
            # 2026-06-06 14:54:36 新增原因：写入 verifier 需要的紧凑证据。
            "evidence": [
                # 2026-06-06 14:54:36 新增原因：RAG 证据提供标准答案。
                {"tool_name": "sql_rag_retrieve", "result": {"results": [{"chunk_id": "qachunk_generic"}], "best_answer": "这张入仓单要财务反审，让预付款充账状态返回，然后确认付款单关系再重新冲账。"}},
                # 2026-06-06 14:54:36 新增原因：图谱证据非空。
                {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "入仓单", "predicate": "前置", "object": "付款单"}]}},
                # 2026-06-06 14:54:36 新增原因：记忆节点已完成。
                {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
                # 2026-06-06 14:54:36 新增原因：业务上下文已完成。
                {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "focus_terms": ["单据关系", "重新冲账"], "business_context": ["业务上下文：先确认单据关系，再重新冲账。"]}},
            ],
            # 2026-06-06 14:54:36 新增原因：复用同一证据作为工具结果，供修复 prompt 读取。
            "tool_results": [],
        }
        # 2026-06-06 14:54:36 新增原因：让工具结果与证据一致，避免修复上下文缺工具摘要。
        state["tool_results"] = list(state["evidence"])
        # 2026-06-06 14:54:36 新增原因：执行 verifier 节点，要求低置信先触发模型修复。
        verified = runtime._verifier_node(state)
        # 2026-06-06 14:54:36 新增原因：断言修复模型被调用一次。
        self.assertEqual(len(runtime.qwen_llm.calls), 1)
        # 2026-06-06 14:54:36 新增原因：断言 verifier 复验看到了修复后的模型答案。
        self.assertIn("单据关系", runtime.correction_runtime.answers[-1])
        # 2026-06-06 14:54:36 新增原因：断言最终不再转人工。
        self.assertEqual(verified["mark"]["final_action"], "answer")
        # 2026-06-06 14:54:36 新增原因：断言草稿来源标记为模型重试。
        self.assertEqual(verified["draft_answer_source"], "qwen_final_answer_retry")

    # 2026-06-05 17:32:11 新增原因：复现 renderer 把兜底答案误标为 model_draft 的 trace 缺陷。
    def test_renderer_reports_evidence_fallback_source_separately(self) -> None:
        # 2026-06-05 17:32:11 新增原因：创建轻量业务脑运行时，直接测试最终渲染来源标记。
        runtime = self.make_runtime()
        # 2026-06-05 17:32:11 新增原因：构造通过 verifier 的兜底草稿状态。
        state = {
            # 2026-06-05 17:32:11 新增原因：保留问题文本，供渲染节点传回状态。
            "question": "客户怎么看不同分厂的订单？",
            # 2026-06-05 17:32:11 新增原因：写入兜底草稿，模拟模型空答后的证据兜底。
            "draft_answer": "可以按分厂筛选订单。",
            # 2026-06-05 17:32:11 新增原因：写入来源字段，要求 renderer 按真实来源展示。
            "draft_answer_source": "evidence_fallback",
            # 2026-06-05 17:32:11 新增原因：写入通过状态，避免进入人工转接分支。
            "verifier_result": {"needs_human": False, "score": 0.8},
            # 2026-06-05 17:32:11 新增原因：初始化 mark，方便 trace 追加事件。
            "mark": {"public_trace_events": []},
            # 2026-06-05 17:32:11 新增原因：没有副作用业务动作，最终动作应保持 answer。
            "tool_results": [],
        }
        # 2026-06-05 17:32:11 新增原因：执行 renderer，读取公开 trace。
        rendered = runtime._renderer_node(state)
        # 2026-06-05 17:32:11 新增原因：读取最后一条 trace 明细。
        detail = rendered["mark"]["public_trace_events"][-1]["detail"]
        # 2026-06-05 17:32:11 新增原因：断言兜底来源不能再冒充 model_draft。
        self.assertIn("answer_source=evidence_fallback", detail)

    # 2026-06-08 18:08:41 test: transfer-human output and trace should not keep stray ASCII question marks.
    def test_renderer_transfer_human_message_and_trace_have_clean_punctuation(self) -> None:
        runtime = self.make_runtime()
        runtime._ensure_transfer_handoff = lambda state, mark: {}
        runtime.correction_runtime.locate_failure_branch = lambda mark: "answer_verifier"
        state = {
            "question": "why was this answer rejected?",
            "draft_answer": "insufficient evidence",
            "draft_answer_source": "qwen_final_answer",
            "verifier_result": {"needs_human": True, "score": 0.2, "failure_reason": "answer_not_equivalent_to_top1"},
            "mark": {"public_trace_events": [], "final_action": "transfer_human"},
            "tool_results": [],
        }
        rendered = runtime._renderer_node(state)
        self.assertNotIn("?", rendered["final_answer"])
        self.assertNotIn("?", rendered["mark"]["public_trace_events"][-1]["detail"])

    # 2026-06-05 17:32:11 新增原因：复现 Verifier 只验链路不验语义，导致错误答案 0.8 通过的问题。
    def test_verifier_rejects_semantic_mismatch_even_when_all_tools_succeeded(self) -> None:
        # 2026-06-05 17:32:11 新增原因：创建真实纠错运行时，只测试确定性语义校验。
        correction_runtime = AnswerCorrectionRuntime(load_correction_config())
        # 2026-06-05 17:32:11 新增原因：构造订单筛选问题，核心意图是分厂、越南、国内、产前样和筛选步骤。
        question = "客户在查看订单列表时，不清楚如何区分和筛选出不同分厂（如越南、国内）以及产前样的订单。"
        # 2026-06-05 17:32:11 新增原因：构造错误答案，内容完全跑到入账单反审和付款状态。
        wrong_answer = "入账单反审要联系财务，让付款状态退回来，后续才能重新冲账或继续付款。"
        # 2026-06-05 17:32:11 新增原因：构造所有工具都成功的证据，验证语义不匹配也必须失败。
        evidence = [
            # 2026-06-05 17:32:11 新增原因：RAG 证据是正确的订单筛选答案。
            {"tool_name": "sql_rag_retrieve", "result": {"results": [{"chunk_id": "qachunk_order"}], "best_answer": "可以使用筛选功能，选择特定分厂来查看对应订单。"}},
            # 2026-06-05 17:32:11 新增原因：图谱证据非空，避免失败原因被图谱缺失掩盖。
            {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "订单", "predicate": "RELATED_TO", "object": "分厂"}]}},
            # 2026-06-05 17:32:11 新增原因：记忆工具已通过。
            {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
            # 2026-06-05 18:10:08 修改原因：业务工具证据必须带动态主题上下文，确保失败原因只来自答案语义跑偏。
            {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "focus_terms": ["订单", "分厂", "筛选"], "business_context": ["业务主题词：订单、分厂、筛选。"]}},
        ]
        # 2026-06-05 17:32:11 新增原因：执行确定性校验。
        result = correction_runtime._deterministic_verify_answer(question, wrong_answer, evidence, "")
        # 2026-06-05 17:32:11 新增原因：断言语义跑偏必须转人工或进入纠错回流。
        self.assertTrue(result["needs_human"])
        # 2026-06-05 17:32:11 新增原因：断言失败原因明确指向答案主题覆盖问题。
        self.assertEqual(result["failure_reason"], "answer_topic_mismatch")

    # 2026-06-06 11:24:38 新增原因：复现 top1 肯定证据被最终答案反写成否定但 verifier 仍给 0.8 的缺陷。
    def test_verifier_rejects_yes_no_polarity_conflict_against_top1_evidence(self) -> None:
        # 2026-06-06 11:24:38 新增原因：创建真实纠错运行时，直接测试确定性 verifier。
        correction_runtime = AnswerCorrectionRuntime(load_correction_config())
        # 2026-06-06 11:24:38 新增原因：构造是/否问题，用户需要模型正面判断。
        question = "这条业务记录是不是要先退回状态再继续处理？"
        # 2026-06-06 11:24:38 新增原因：构造 top1 肯定证据，表示应该先退回状态。
        best_answer = "可以，应该先退回状态，确认前置处理完成后再继续后续业务动作。"
        # 2026-06-06 11:24:38 新增原因：构造错误否定答案，复现模型把肯定证据答成不是。
        wrong_answer = "不是，不需要先退回状态，可以直接继续后续业务动作。"
        # 2026-06-06 11:24:38 新增原因：四类证据全部满足，确保失败只来自极性反写。
        evidence = [
            # 2026-06-06 11:24:38 新增原因：RAG top1 写入肯定证据。
            {"tool_name": "sql_rag_retrieve", "result": {"results": [{"chunk_id": "qachunk_generic"}], "best_answer": best_answer}},
            # 2026-06-06 11:24:38 新增原因：图谱证据非空，避免缺图谱掩盖极性问题。
            {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "状态退回", "predicate": "前置于", "object": "继续处理"}]}},
            # 2026-06-06 11:24:38 新增原因：记忆节点通过。
            {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
            # 2026-06-06 11:24:38 新增原因：业务上下文通过。
            {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "business_context": ["业务上下文：状态退回是继续处理的前置条件。"]}},
        ]
        # 2026-06-06 11:24:38 新增原因：执行确定性 verifier，要求拦截极性反写。
        result = correction_runtime._deterministic_verify_answer(question, wrong_answer, evidence, "")
        # 2026-06-06 11:24:38 新增原因：断言极性冲突不能通过。
        self.assertTrue(result["needs_human"])
        # 2026-06-06 11:24:38 新增原因：断言失败原因直接指向答案极性冲突。
        self.assertEqual(result["failure_reason"], "answer_polarity_conflict")

    # 2026-06-05 17:32:11 新增原因：复现图谱 raw triple 泄露到最终语言的问题。
    def test_graph_context_filters_internal_ids_and_prioritizes_question_terms(self) -> None:
        # 2026-06-05 17:32:11 新增原因：创建轻量业务脑运行时，直接测试图谱摘要格式化。
        runtime = self.make_runtime()
        # 2026-06-05 17:32:11 新增原因：构造带内部 chunk 边和真实业务边的图谱结果。
        graph_result = {
            # 2026-06-05 17:32:11 新增原因：保留后端信息，摘要仍需说明 Neo4j 来源。
            "backend": "neo4j_triple_graph",
            # 2026-06-05 17:32:11 新增原因：保留匹配策略，便于 trace 审计。
            "match_strategy": "neo4j_source_chunk_ids",
            # 2026-06-05 17:32:11 新增原因：内部关系排在前面，验证新逻辑不能按原始顺序泄露。
            "triples": [
                # 2026-06-05 17:32:11 新增原因：内部 chunk 关系不能进入用户答案。
                {"subject": "qachunk_xxx", "predicate": "CHUNK_IN_GLOBAL_CLUSTER", "object": "qaglobal_xxx"},
                # 2026-06-05 17:32:11 新增原因：无关工资关系应该被相关性排序压后。
                {"subject": "工资", "predicate": "MENTIONED_IN_CHUNK", "object": "qachunk_salary"},
                # 2026-06-05 17:32:11 新增原因：订单和分厂关系应该优先进入摘要。
                {"subject": "订单", "predicate": "业务关联", "object": "分厂筛选", "evidence_text": "订单列表可以按分厂筛选，包含越南、国内、产前样。"},
            ],
        }
        # 2026-06-05 17:32:11 新增原因：调用新图谱摘要接口，带上用户问题和 RAG top1 做相关性排序。
        lines = runtime._format_graph_context_for_prompt(
            graph_result,
            question="客户怎么看越南、国内和产前样的订单？",
            best_answer="使用分厂筛选功能查看不同分厂和产前样订单。",
        )
        # 2026-06-05 17:32:11 新增原因：合并摘要行，便于断言内部 ID 是否泄漏。
        joined = "\n".join(lines)
        # 2026-06-05 17:32:11 新增原因：断言业务相关关系被保留下来。
        self.assertIn("分厂筛选", joined)
        # 2026-06-05 17:32:11 新增原因：断言内部 chunk ID 不再进入模型最终语言上下文。
        self.assertNotIn("qachunk", joined)
        # 2026-06-05 17:32:11 新增原因：断言内部图谱关系名不再进入模型最终语言上下文。
        self.assertNotIn("MENTIONED_IN_CHUNK", joined)

    # 2026-06-05 17:32:11 新增原因：复现复杂业务问题只用 query_tickets 形式过场的问题。
    def test_complex_business_question_uses_business_context_query_not_ticket_query_only(self) -> None:
        # 2026-06-05 17:32:11 新增原因：创建轻量业务脑运行时，测试业务工具协议守卫。
        runtime = self.make_runtime()
        # 2026-06-05 17:32:11 新增原因：构造截图里的订单筛选类业务问题。
        state = {"question": "客户在订单列表里怎么筛选越南、国内和产前样订单？", "mark": {}, "tool_results": []}
        # 2026-06-05 17:32:11 新增原因：请求业务工具调用参数。
        tool_call = runtime._build_required_tool_call(state, "sql_rag_business_action")
        # 2026-06-05 17:32:11 新增原因：断言不再用客服工单查询冒充业务证据。
        self.assertEqual(tool_call["args"]["action_name"], "query_business_context")
        # 2026-06-05 17:32:11 新增原因：断言业务查询参数保留原问题，便于执行层按业务意图提取证据。
        self.assertIn("订单列表", tool_call["args"]["action_args"]["question"])

    # 2026-06-05 18:10:08 新增原因：验证完整 Agent 链路触发不能只靠订单/入账单等固定业务词，任意复杂业务知识问题都要进入证据链。
    def test_full_chain_detection_is_generic_for_unlisted_business_chunk(self) -> None:
        # 2026-06-05 18:10:08 新增原因：创建轻量业务脑运行时，直接测试意图触发函数。
        runtime = self.make_runtime()
        # 2026-06-05 18:10:08 新增原因：提供一个不含订单、入账单、财务等旧硬编码词的复杂业务问题。
        question = "质检报告导出时如何按供应商和检验批次筛选异常记录？"
        # 2026-06-05 18:10:08 新增原因：断言这类未知业务 chunk 问题也必须走完整 RAG、图谱、记忆、业务工具链。
        self.assertTrue(runtime._question_requires_full_agent_chain(question))

    # 2026-06-05 18:10:08 新增原因：验证业务上下文工具不能再按订单/财务两类写死，而要按当前问题和证据动态抽主题。
    def test_business_context_summary_is_dynamic_for_unlisted_chunk_terms(self) -> None:
        # 2026-06-05 18:10:08 新增原因：绕过构造函数，避免单测连接真实 SQL Server。
        store = LocalBusinessActionStore.__new__(LocalBusinessActionStore)
        # 2026-06-05 18:10:08 新增原因：构造包含“订单”但真实主题是质检导出的泛化业务问题，复现旧分类被订单词带偏。
        question = "售后订单质检报告导出时，如何按供应商和检验批次筛选异常记录？"
        # 2026-06-05 18:10:08 新增原因：提供 RAG top1 证据，要求业务工具从证据中抽取真实主题词。
        best_answer = "在质检报告导出页选择供应商、检验批次和异常类型后再导出异常记录。"
        # 2026-06-05 18:10:08 新增原因：动态抽取业务关注词，不允许只命中旧固定业务词。
        focus_terms = store._extract_business_focus_terms(question, best_answer)
        # 2026-06-05 18:10:08 新增原因：动态生成业务意图，不能落入 order_filter_rules 这种截图专用分类。
        intent = store._business_context_intent(focus_terms)
        # 2026-06-05 18:10:08 新增原因：生成业务摘要，验证摘要围绕当前证据而不是订单/财务模板。
        summary = "\n".join(store._business_context_summary(intent, focus_terms, best_answer))
        # 2026-06-05 18:10:08 新增原因：必须保留当前 chunk 的核心证据词。
        self.assertIn("供应商", summary)
        # 2026-06-05 18:10:08 新增原因：必须保留当前 chunk 的检验批次主题。
        self.assertIn("检验批次", summary)
        # 2026-06-05 18:10:08 新增原因：不能输出截图订单筛选模板里的分厂词。
        self.assertNotIn("分厂", summary)
        # 2026-06-05 18:10:08 新增原因：不能输出截图财务模板里的入账词。
        self.assertNotIn("入账单", summary)
        # 2026-06-05 18:10:08 新增原因：意图应该是通用语义业务上下文，不再是两类硬编码场景。
        self.assertEqual(intent, "semantic_business_context")

    # 2026-06-05 18:10:08 新增原因：验证业务工具调用要把 RAG top1 一起给执行层，执行层才能泛化生成业务上下文。
    def test_business_context_tool_receives_rag_best_answer_for_generic_summary(self) -> None:
        # 2026-06-05 18:10:08 新增原因：创建轻量业务脑运行时，直接测试协议守卫构造的工具参数。
        runtime = self.make_runtime()
        # 2026-06-05 18:10:08 新增原因：构造非订单财务类复杂业务问题和 RAG 证据。
        state = {
            # 2026-06-05 18:10:08 新增原因：问题主题为质检报告，验证泛化语义链。
            "question": "质检报告导出时如何按供应商筛选异常记录？",
            # 2026-06-05 18:10:08 新增原因：mark 携带 RAG top1，业务工具必须消费它。
            "mark": {"best_answer": "在质检报告导出页按供应商筛选异常记录。", "retrieved_chunk_ids": ["qachunk_quality"]},
            # 2026-06-05 18:10:08 新增原因：工具结果为空，直接构造业务工具调用。
            "tool_results": [],
        }
        # 2026-06-05 18:10:08 新增原因：构造必经业务上下文工具调用。
        tool_call = runtime._build_required_tool_call(state, "sql_rag_business_action")
        # 2026-06-05 18:10:08 新增原因：断言只读业务上下文动作不变。
        self.assertEqual(tool_call["args"]["action_name"], "query_business_context")
        # 2026-06-05 18:10:08 新增原因：断言 RAG top1 被传给业务工具，避免执行层只能看问题而泛化证据不足。
        self.assertIn("供应商", tool_call["args"]["action_args"]["best_answer"])

    # 2026-06-05 18:10:08 新增原因：验证 verifier 的语义覆盖校验也必须泛化，不能只识别订单/财务截图场景。
    def test_verifier_rejects_generic_topic_mismatch_even_when_chain_succeeded(self) -> None:
        # 2026-06-05 18:10:08 新增原因：创建真实纠错运行时，测试确定性语义闸门。
        correction_runtime = AnswerCorrectionRuntime(load_correction_config())
        # 2026-06-05 18:10:08 新增原因：构造不在旧业务词清单里的复杂业务问题。
        question = "质检报告导出时如何按供应商和检验批次筛选异常记录？"
        # 2026-06-05 18:10:08 新增原因：构造错误答案，内容跑到入账单反审场景。
        wrong_answer = "入账单反审要先联系财务，再把付款状态退回来。"
        # 2026-06-05 18:10:08 新增原因：构造所有工具都成功的证据，确保失败原因只来自主题不匹配。
        evidence = [
            # 2026-06-05 18:10:08 新增原因：RAG top1 明确是质检报告导出证据。
            {"tool_name": "sql_rag_retrieve", "result": {"results": [{"chunk_id": "qachunk_quality"}], "best_answer": "在质检报告导出页选择供应商、检验批次和异常类型后再导出异常记录。"}},
            # 2026-06-05 18:10:08 新增原因：图谱证据非空，避免缺图谱掩盖语义问题。
            {"tool_name": "sql_rag_graph_expand", "result": {"triples": [{"subject": "质检报告", "predicate": "按条件筛选", "object": "供应商"}]}},
            # 2026-06-05 18:10:08 新增原因：记忆节点成功。
            {"tool_name": "sql_rag_memory_read", "result": {"status": "ok"}},
            # 2026-06-05 18:10:08 新增原因：业务上下文工具成功并带动态主题词。
            {"tool_name": "sql_rag_business_action", "result": {"status": "succeeded", "action_name": "query_business_context", "focus_terms": ["质检报告", "供应商", "检验批次", "异常记录"]}},
        ]
        # 2026-06-05 18:10:08 新增原因：运行确定性 verifier。
        result = correction_runtime._deterministic_verify_answer(question, wrong_answer, evidence, "")
        # 2026-06-05 18:10:08 新增原因：答案主题错配必须被拦截。
        self.assertTrue(result["needs_human"])
        # 2026-06-05 18:10:08 新增原因：失败原因必须指向主题覆盖失败。
        self.assertEqual(result["failure_reason"], "answer_topic_mismatch")


# 2026-06-05 10:03:12 新增原因：允许直接运行本测试文件。
if __name__ == "__main__":
    # 2026-06-05 10:03:12 新增原因：执行 unittest 主入口。
    unittest.main()
