# -*- coding: utf-8 -*-
"""状态 mark、LangSmith/Phoenix 观测和 SQL_RAG 纠错飞轮。"""

# 修改日期：2026-06-02 17:20:00。
# 修改理由：按照“状态不能黑盒，实时 mark，定位跑偏分支，回流纠错复跑”的截图要求，接入 LangSmith、Phoenix/OpenTelemetry 和 SQL_RAG 自身校验状态。

# 导入 JSON 标准库，用于解析和输出 verifier 结构化结果。
import json
# 导入 os，用于读取 LangSmith、Phoenix 和开放接口配置。
import os
# 导入 dataclass，用于定义观测纠错配置。
from dataclasses import dataclass
# 导入 datetime，用于记录纠错事件时间。
from datetime import datetime, timezone
# 导入任意字典类型。
from typing import Any

# 导入 LangSmith 官方 Client，用于失败样本沉淀和评测数据集写入。
from langsmith import Client, traceable

# 2026-06-06 11:24:38 修改原因：导入泛化语义和极性校验工具，Verifier 不再只看链路完成或主题词覆盖。
from overall_planning.semantic_evidence import collect_evidence_texts, question_requires_semantic_agent_chain, semantic_answer_coverage, semantic_answer_grounded_equivalence, semantic_answer_internal_token_leak, semantic_answer_polarity_conflict


# 定义截图中要求的完整 mark 字段清单。
REQUIRED_MARK_FIELDS = [
    "intent_node",
    "retrieval_query",
    "retrieved_chunk_ids",
    "global_cluster_ids",
    "kg_entities",
    "kg_edges",
    "tool_name",
    "tool_args",
    "tool_result_status",
    "memory_read_ids",
    "memory_write_event",
    "verifier_score",
    "answer_source_chunk_ids",
    "final_action",
    "failure_reason",
    "public_trace_events",
    "prompt_builder_context",
    "flywheel_event",
]


@dataclass(frozen=True)
class CorrectionConfig:
    # LangSmith 项目名，用于生产 trace 聚合。
    langsmith_project: str
    # 失败样本沉淀的数据集名。
    langsmith_dataset: str
    # Phoenix collector endpoint，为空时只启用 LangSmith。
    phoenix_endpoint: str
    # Phoenix 项目名。
    phoenix_project: str
    # SQL_RAG 开放接口地址，用于把纠错回流到现有数据库 API。
    sql_rag_open_api_base: str
    # verifier 低置信阈值，低于该值拒答或转人工。
    verifier_threshold: float


def load_correction_config() -> CorrectionConfig:
    # 从环境变量读取 LangSmith 项目名。
    langsmith_project = os.getenv("LANGSMITH_PROJECT", "sql-rag-agent-customer-service")
    # 从环境变量读取失败样本数据集名。
    langsmith_dataset = os.getenv("LANGSMITH_DATASET", "sql-rag-agent-failure-flywheel")
    # 从环境变量读取 Phoenix collector endpoint。
    phoenix_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "")
    # 从环境变量读取 Phoenix 项目名。
    phoenix_project = os.getenv("PHOENIX_PROJECT_NAME", "sql-rag-llamaindex-retrieval")
    # 从环境变量读取 SQL_RAG 开放接口地址。
    sql_rag_open_api_base = os.getenv("SQL_RAG_OPEN_API_BASE", "http://127.0.0.1:18080")
    # 从环境变量读取 verifier 阈值。
    verifier_threshold = float(os.getenv("AGENT_VERIFIER_THRESHOLD", "0.72"))
    # 返回纠错配置。
    return CorrectionConfig(
        langsmith_project=langsmith_project,
        langsmith_dataset=langsmith_dataset,
        phoenix_endpoint=phoenix_endpoint,
        phoenix_project=phoenix_project,
        sql_rag_open_api_base=sql_rag_open_api_base.rstrip("/"),
        verifier_threshold=verifier_threshold,
    )


class AnswerCorrectionRuntime:
    # 保存纠错配置。
    config: CorrectionConfig
    # 保存 LangSmith 官方客户端。
    langsmith_client: Client
    # 保存 Phoenix tracer provider。
    phoenix_tracer_provider: Any

    def __init__(self, config: CorrectionConfig) -> None:
        # 记录配置。
        self.config = config
        # 创建 LangSmith 官方客户端。
        self.langsmith_client = Client()
        # 注册 Phoenix/OpenTelemetry；未配置 endpoint 时保留 None，不伪造 span。
        self.phoenix_tracer_provider = self._register_phoenix_if_configured()

    def _register_phoenix_if_configured(self) -> Any:
        # 未配置 Phoenix endpoint 时跳过 Phoenix exporter。
        if not self.config.phoenix_endpoint:
            # 返回 None 表示只依赖 LangSmith trace。
            return None
        # 配置了 Phoenix 时才懒加载 Phoenix 官方 OpenTelemetry 注册入口，避免本地 stdin 测试触发 Phoenix schema 路径问题。
        from phoenix.otel import register as register_phoenix
        # 调用 Phoenix 官方 register API 注册 OpenTelemetry tracer provider。
        return register_phoenix(
            endpoint=self.config.phoenix_endpoint,
            project_name=self.config.phoenix_project,
            auto_instrument=True,
            verbose=False,
        )

    def build_empty_mark(self) -> dict[str, Any]:
        # 创建包含全部必需字段的空 mark，避免某个节点遗漏字段。
        return {
            "intent_node": "",
            "retrieval_query": "",
            "retrieved_chunk_ids": [],
            "global_cluster_ids": [],
            "kg_entities": [],
            "kg_edges": [],
            "tool_name": "",
            "tool_args": {},
            "tool_result_status": "",
            "memory_read_ids": [],
            "memory_write_event": {},
            "verifier_score": 0.0,
            "answer_source_chunk_ids": [],
            "final_action": "",
            "failure_reason": "",
            # 2026-06-04 16:36:27 新增原因：保存后端真实公开执行事件，前端逐字展示不再写死。
            "public_trace_events": [],
            # 2026-06-04 16:36:27 新增原因：保存 Prompt Builder 上下文摘要，便于纠错回放。
            "prompt_builder_context": "",
            # 2026-06-04 16:36:27 新增原因：记录数据飞轮事件状态，明确是否已沉淀样本。
            "flywheel_event": {},
        }

    def normalize_mark(self, raw_mark: dict[str, Any] | None) -> dict[str, Any]:
        # 先创建标准空 mark。
        mark = self.build_empty_mark()
        # 把上游节点写入的 mark 合并进标准结构。
        if raw_mark:
            # 更新已有字段。
            mark.update(raw_mark)
        # 补齐缺失字段，保证 trace 和回流表结构稳定。
        for field_name in REQUIRED_MARK_FIELDS:
            # 字段缺失时写入空值。
            mark.setdefault(field_name, self.build_empty_mark()[field_name])
        # 返回标准 mark。
        return mark

    def locate_failure_branch(self, mark: dict[str, Any]) -> str:
        # 读取标准化 mark。
        normalized = self.normalize_mark(mark)
        # 意图节点失败优先定位到 planner。
        if normalized.get("failure_reason") == "intent_error":
            # 返回 planner 分支。
            return "planner_intent_reasoner"
        # 召回为空或 chunk 不足定位到 RAG tool。
        if not normalized.get("retrieved_chunk_ids"):
            # 返回 RAG 分支。
            return "rag_tool_qdrant_llamaindex"
        # 2026-06-05 10:17:18 修改原因：缺图谱实体、缺图谱边或 verifier 明确缺图谱时都定位到图谱工具。
        if normalized.get("failure_reason") == "missing_graph_evidence" or not normalized.get("kg_edges"):
            # 返回 graph 分支。
            return "graph_tool_sqlserver_neo4j"
        # 2026-06-05 10:17:18 新增原因：缺记忆上下文时定位到记忆工具。
        if normalized.get("failure_reason") == "missing_memory_context":
            # 2026-06-05 10:17:18 新增原因：返回记忆分支。
            return "memory_tool_langgraph_checkpoint"
        # 2026-06-05 10:17:18 新增原因：缺业务工具审计时定位到 MCP 业务工具。
        if normalized.get("failure_reason") == "missing_business_tool_evidence":
            # 2026-06-05 10:17:18 新增原因：返回业务工具分支。
            return "mcp_business_tool"
        # 工具状态不是 ok 时定位到 MCP/业务工具。
        if normalized.get("tool_result_status") not in {"", "ok"}:
            # 返回工具分支。
            return "mcp_business_tool"
        # verifier 低分定位到答案校验。
        if float(normalized.get("verifier_score") or 0.0) < self.config.verifier_threshold:
            # 返回 verifier 分支。
            return "answer_verifier"
        # 默认定位到最终组织答案。
        return "final_answer_renderer"

    def _extract_json_object(self, content: str) -> dict[str, Any] | None:
        # 去掉模型输出两侧空白。
        text = (content or "").strip()
        # 空输出无法抽取 JSON。
        if not text:
            # 返回 None 表示没有可解析 JSON。
            return None
        # 优先尝试把完整文本作为 JSON 解析。
        try:
            # 返回完整 JSON 对象。
            parsed = json.loads(text)
            # 只接受字典对象，避免列表或字符串误判。
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            # 完整文本解析失败时继续尝试截取 JSON 对象。
            pass
        # 查找第一个左花括号。
        start = text.find("{")
        # 查找最后一个右花括号。
        end = text.rfind("}")
        # 没有完整花括号时无法解析。
        if start < 0 or end <= start:
            # 返回 None。
            return None
        # 截取可能的 JSON 对象。
        candidate = text[start : end + 1]
        # 尝试解析截取内容。
        try:
            # 解析 JSON 对象。
            parsed = json.loads(candidate)
            # 只接受字典对象。
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            # 截取内容仍失败时返回 None。
            return None

    # 2026-06-05 10:17:18 新增原因：识别复杂业务问题，决定 verifier 是否强制要求完整 Agent 节点证据。
    def _question_requires_full_agent_chain(self, question: str) -> bool:
        # 2026-06-05 18:10:08 修改原因：使用泛化问题形态和动态主题密度判断复杂业务问题，不再维护固定业务词表。
        return question_requires_semantic_agent_chain(question)

    def _deterministic_verify_answer(self, question: str, answer: str, evidence: list[dict[str, Any]], raw_content: str) -> dict[str, Any]:
        # 判断是否有非空答案。
        has_answer = bool((answer or "").strip())
        # 初始化召回数量。
        retrieved_count = 0
        # 初始化 RAG 直答证据。
        rag_best_answer = ""
        # 初始化业务动作成功标记。
        business_action_succeeded = False
        # 2026-06-05 10:17:18 新增原因：初始化图谱三元组数量，用于判断图谱是否真的可消费。
        graph_triple_count = 0
        # 2026-06-05 10:17:18 新增原因：初始化图谱路径数量，用于兼容紧凑图谱摘要。
        graph_path_count = 0
        # 初始化工具成功集合。
        succeeded_tools: set[str] = set()
        # 遍历证据列表。
        for evidence_item in evidence:
            # 读取工具名。
            tool_name = evidence_item.get("tool_name", "")
            # 读取工具结果。
            result = evidence_item.get("result", {})
            # 非 error 结果先记录为已调用成功。
            if not (isinstance(result, dict) and result.get("status") == "error"):
                # 添加成功工具名。
                succeeded_tools.add(tool_name)
            # RAG 召回工具统计 chunk 数。
            if tool_name == "sql_rag_retrieve" and isinstance(result, dict):
                # 累加召回结果数量。
                retrieved_count += len(result.get("results", []) or [])
                # 读取 RAG top1 直答证据。
                rag_best_answer = str(result.get("best_answer") or rag_best_answer)
            # 2026-06-05 10:17:18 新增原因：图谱工具必须有真实三元组或路径，不能只调用空结果。
            if tool_name == "sql_rag_graph_expand" and isinstance(result, dict):
                # 2026-06-05 10:17:18 新增原因：优先读取完整 triples 列表数量。
                graph_triple_count += len(result.get("triples", []) or [])
                # 2026-06-05 10:17:18 新增原因：兼容紧凑摘要里的 triple_count。
                graph_triple_count += int(result.get("triple_count", 0) or 0)
                # 2026-06-05 10:17:18 新增原因：读取完整 paths 列表数量。
                graph_path_count += len(result.get("paths", []) or [])
                # 2026-06-05 10:17:18 新增原因：兼容紧凑摘要里的 path_count。
                graph_path_count += int(result.get("path_count", 0) or 0)
            # 业务工具检查执行状态。
            if tool_name == "sql_rag_business_action" and isinstance(result, dict):
                # 2026-06-05 18:10:08 修改原因：读取业务动作名，区分只查工单和真正的语义业务上下文。
                action_name = str(result.get("action_name", ""))
                # 2026-06-05 18:10:08 修改原因：业务工具必须 succeeded 且不能只是 query_tickets/query_profile 形式过场。
                action_has_real_context = action_name not in {"query_tickets", "query_profile"} and bool(result.get("focus_terms") or result.get("business_context") or action_name not in {"query_business_context"})
                # 2026-06-05 18:10:08 修改原因：只有真实业务上下文或真实副作用动作成功，才算业务审计满足。
                business_action_succeeded = result.get("status") == "succeeded" and action_has_real_context
        # 2026-06-05 10:17:18 新增原因：复杂业务问题默认需要完整 Agent 节点链路。
        requires_full_chain = self._question_requires_full_agent_chain(question)
        # 根据用户问题判断是否要求执行业务动作。
        requires_business_action = requires_full_chain or any(keyword in question for keyword in ["创建", "工单", "跟进", "提醒", "转人工", "处理"])
        # 根据用户问题判断是否显式要求记忆工具。
        requires_memory = requires_full_chain or any(keyword in question for keyword in ["历史记忆", "记忆", "用户画像", "画像", "偏好"])
        # 根据用户问题判断是否显式要求图谱工具。
        requires_graph = requires_full_chain or any(keyword in question for keyword in ["实体关系", "相关实体", "相关关系", "图谱", "多跳", "关系"])
        # 有召回 chunk 即认为答案有基础证据。
        grounded = retrieved_count > 0
        # RAG 已给出 best_answer 时，视为存在可用答案证据。
        has_answer = has_answer or bool(rag_best_answer.strip())
        # 记忆要求满足情况。
        memory_satisfied = (not requires_memory) or ("sql_rag_memory_read" in succeeded_tools)
        # 2026-06-05 10:17:18 修改原因：图谱要求必须同时满足工具调用和非空多跳证据。
        graph_satisfied = (not requires_graph) or ("sql_rag_graph_expand" in succeeded_tools and (graph_triple_count > 0 or graph_path_count > 0))
        # 业务动作要求满足情况。
        business_satisfied = (not requires_business_action) or business_action_succeeded
        # 2026-06-05 18:10:08 新增原因：收集 RAG/图谱/业务工具文本，用于泛化语义覆盖校验。
        evidence_texts = collect_evidence_texts(evidence)
        # 2026-06-05 18:10:08 新增原因：校验答案是否覆盖当前问题主题，防止错误场景答案被链路完成掩盖。
        topic_coverage = semantic_answer_coverage(question, answer, evidence_texts)
        # 2026-06-06 11:24:38 新增原因：校验答案肯定/否定方向是否反写 top1 证据，防止“可以”被答成“不是”仍通过。
        polarity_check = semantic_answer_polarity_conflict(answer, evidence_texts)
        # 2026-06-08 15:44:31 新增原因：检查最终答案是否等价于 RAG top1/chunk 证据。
        equivalence_check = semantic_answer_grounded_equivalence(question, answer, evidence_texts)
        # 2026-06-08 15:44:31 新增原因：检查答案是否泄露内部链路词。
        internal_leak_check = semantic_answer_internal_token_leak(answer)
        # 2026-06-05 18:10:08 新增原因：读取语义覆盖是否满足。
        semantic_satisfied = bool(topic_coverage.get("satisfied")) and bool(equivalence_check.get("equivalent")) and not bool(polarity_check.get("conflict")) and not bool(internal_leak_check.get("leaked"))
        # 2026-06-05 18:10:08 修改原因：答案完整必须同时满足证据链和语义覆盖。
        complete = has_answer and grounded and memory_satisfied and graph_satisfied and business_satisfied and semantic_satisfied
        # 完整且有证据时给通过分。
        if complete:
            # 设置高于默认阈值的通过分。
            score = max(self.config.verifier_threshold + 0.08, 0.8)
        # 有证据但动作或答案不完整时给边界分。
        elif grounded:
            # 设置低于阈值的边界分。
            score = min(self.config.verifier_threshold - 0.05, 0.67)
        # 没有证据时给低分。
        else:
            # 设置明确低分。
            score = 0.0
        # 判断是否需要人工。
        needs_human = score < self.config.verifier_threshold
        # 2026-06-05 10:17:18 新增原因：缺图谱时给出明确失败原因，驱动纠错飞轮定位 graph 分支。
        failure_reason = "missing_graph_evidence" if requires_graph and not graph_satisfied else ""
        # 2026-06-05 10:17:18 新增原因：缺记忆时给出明确失败原因，驱动纠错飞轮定位 memory 分支。
        failure_reason = failure_reason or ("missing_memory_context" if requires_memory and not memory_satisfied else "")
        # 2026-06-05 10:17:18 新增原因：缺业务工具审计时给出明确失败原因，驱动纠错飞轮定位 MCP 业务工具分支。
        failure_reason = failure_reason or ("missing_business_tool_evidence" if requires_business_action and not business_satisfied else "")
        # 2026-06-08 15:44:31 新增原因：链路齐全但答案泄露内部词时直接失败。
        failure_reason = failure_reason or ("answer_internal_token_leak" if internal_leak_check.get("leaked") else "")
        # 2026-06-06 11:24:38 新增原因：链路齐全但答案把 top1 肯定/否定方向反写时，明确定位到最终回答极性冲突。
        failure_reason = failure_reason or ("answer_polarity_conflict" if polarity_check.get("conflict") else "")
        # 2026-06-08 18:08:41 修改原因：主题跑偏优先定位为 topic mismatch，避免被等价失败掩盖。
        failure_reason = failure_reason or ("answer_topic_mismatch" if not topic_coverage.get("satisfied") else "")
        # 2026-06-08 18:08:41 修改原因：主题命中但没切中 top1/chunk 核心事实时，再定位为等价失败。
        failure_reason = failure_reason or ("answer_not_equivalent_to_top1" if not equivalence_check.get("equivalent") else "")
        # 2026-06-05 10:17:18 新增原因：没有具体缺口但低分时保留原确定性低置信原因。
        failure_reason = failure_reason or ("" if not needs_human else "deterministic_verifier_low_confidence")
        # 返回确定性校验结果。
        return {
            "score": float(score),
            "grounded": grounded,
            "complete": complete,
            "needs_human": needs_human,
            "failure_reason": failure_reason,
            "raw_content": raw_content,
            "fallback": "deterministic_evidence_and_tool_consistency",
            "retrieved_count": retrieved_count,
            "business_action_succeeded": business_action_succeeded,
            # 2026-06-05 18:10:08 新增原因：返回语义覆盖状态，供 trace 和纠错飞轮复盘。
            "semantic_satisfied": semantic_satisfied,
            # 2026-06-05 18:10:08 新增原因：返回主题覆盖详情，定位答案缺了哪些当前问题主题词。
            "topic_coverage": topic_coverage,
            # 2026-06-06 11:24:38 新增原因：返回极性一致性详情，定位肯定证据被否定回答反写的问题。
            "polarity_check": polarity_check,
            # 2026-06-08 15:44:31 新增原因：返回等价校验详情，定位模型答案是否切中 chunk 证据。
            "answer_equivalence": equivalence_check,
            # 2026-06-08 15:44:31 新增原因：返回内部词泄露详情，避免 Prompt Builder 调试词进用户答案。
            "internal_leak_check": internal_leak_check,
            # 2026-06-05 10:17:18 新增原因：返回完整链路要求标记，便于前端和回流样本审计。
            "requires_full_chain": requires_full_chain,
            "requires_business_action": requires_business_action,
            "requires_memory": requires_memory,
            "memory_satisfied": memory_satisfied,
            "requires_graph": requires_graph,
            "graph_satisfied": graph_satisfied,
        }

    @traceable(name="sql_rag_answer_verifier")
    def verify_answer_with_qwen(self, qwen_llm: Any, question: str, answer: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        # 构造 verifier 系统提示，要求只基于证据评分。
        system_prompt = (
            "你是 SQL_RAG 智能客服答案校验器。只能依据 evidence 里的 chunk、图谱路径和工具结果评分，"
            "不要补充证据外事实。关闭思考模式，直接输出 JSON，不要输出解释。"
            "字段为 score、grounded、complete、needs_human、failure_reason。/no_think"
        )
        # 构造 verifier 用户输入。
        user_prompt = json.dumps(
            {
                "question": question,
                "answer": answer,
                "evidence": evidence,
                "score_rule": "0 到 1，低于阈值必须 needs_human=true 或 failure_reason 非空。",
            },
            ensure_ascii=False,
        )
        # 调用 Qwen-Agent 官方 chat 接口做校验。
        response = qwen_llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
        )
        # 读取最后一条模型消息。
        last_message = response[-1]
        # 兼容 Qwen-Agent Message 和 dict 两种返回。
        if isinstance(last_message, dict):
            # 字典返回时优先读取 content，再兼容 reasoning_content。
            content = last_message.get("content", "") or last_message.get("reasoning_content", "")
        else:
            # Message 对象返回时优先读取 content，再兼容 reasoning_content。
            content = getattr(last_message, "content", "") or getattr(last_message, "reasoning_content", "")
        # 尝试从模型输出里抽取 JSON 对象。
        parsed = self._extract_json_object(content)
        # 2026-06-05 18:10:08 新增原因：始终运行确定性校验，避免模型 verifier 忽略答案主题覆盖问题。
        deterministic_result = self._deterministic_verify_answer(question=question, answer=answer, evidence=evidence, raw_content=content)
        # 模型 JSON 不合格时启用确定性兜底校验，避免本地小模型 verifier 让状态变黑盒。
        if parsed is None:
            # 根据 evidence 和工具结果做确定性一致性校验。
            parsed = deterministic_result
        # 2026-06-05 18:10:08 新增原因：确定性校验发现语义或链路缺口时，覆盖模型 verifier 的宽松通过结果。
        elif deterministic_result.get("needs_human") or not deterministic_result.get("complete"):
            # 2026-06-05 18:10:08 新增原因：采用可复盘的确定性失败结果。
            parsed = deterministic_result
        # 返回标准校验结果。
        return {
            "score": float(parsed.get("score", 0.0) or 0.0),
            "grounded": bool(parsed.get("grounded", False)),
            "complete": bool(parsed.get("complete", False)),
            "needs_human": bool(parsed.get("needs_human", False)),
            "failure_reason": str(parsed.get("failure_reason", "")),
            "raw": parsed,
        }

    def record_failure_example(self, question: str, answer: str, mark: dict[str, Any], verifier_result: dict[str, Any]) -> dict[str, Any]:
        # 标准化 mark。
        normalized_mark = self.normalize_mark(mark)
        # 定位跑偏分支。
        failure_branch = self.locate_failure_branch(normalized_mark)
        # 构造失败样本输入。
        inputs = {
            "question": question,
            "mark": normalized_mark,
            "failure_branch": failure_branch,
        }
        # 构造失败样本输出。
        outputs = {
            "answer": answer,
            "verifier_result": verifier_result,
        }
        # 构造 LangSmith metadata。
        metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "failure_branch": failure_branch,
            "sql_rag_open_api_base": self.config.sql_rag_open_api_base,
        }
        # 写入 LangSmith 官方 dataset；未配置 LangSmith key 时让官方客户端抛出明确错误。
        example = self.langsmith_client.create_example(
            dataset_name=self.config.langsmith_dataset,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
        )
        # 返回沉淀结果。
        return {
            "dataset": self.config.langsmith_dataset,
            "example_id": str(example.id),
            "failure_branch": failure_branch,
        }
