# -*- coding: utf-8 -*-
"""本地智能客服业务动作仓库。"""

# 修改日期：2026-06-03 00:00:00。
# 修改理由：补齐截图里的 Business Tool 真实执行层，避免 Agent 只保留空接口。

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

import pyodbc

# 2026-06-06 11:02:18 修改原因：导入泛化语义抽词工具，替代固定业务场景词硬编码。
from overall_planning.semantic_evidence import extract_semantic_terms


SUPPORTED_BUSINESS_ACTIONS = [
    "create_ticket",
    "transfer_human",
    "create_followup",
    "record_customer_profile",
    "update_ticket_status",
    "query_tickets",
    # 2026-06-05 17:32:11 新增原因：新增结构化业务上下文查询，避免复杂业务问题只用 query_tickets 形式过场。
    "query_business_context",
    "query_profile",
    "log_note",
]


ACTION_ALIASES = {
    "open_ticket": "create_ticket",
    "complaint": "create_ticket",
    "return_order": "create_ticket",
    "exchange_order": "create_ticket",
    "cancel_order": "create_ticket",
    "change_address": "create_ticket",
    "order_lookup": "create_ticket",
    "shipping_followup": "create_followup",
    "order_followup": "create_followup",
    "set_reminder": "create_followup",
    "handoff": "transfer_human",
    "human_handoff": "transfer_human",
    "request_human": "transfer_human",
    "transfer_to_human": "transfer_human",
    "record_preference": "record_customer_profile",
    "update_customer_profile": "record_customer_profile",
    "close_ticket": "update_ticket_status",
    "get_tickets": "query_tickets",
    "get_profile": "query_profile",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def stable_business_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}_{uuid.uuid5(uuid.NAMESPACE_URL, raw).hex[:24]}"


def new_business_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def normalize_business_action_name(action_name: str) -> str:
    normalized = (action_name or "").strip().lower().replace("-", "_").replace(" ", "_")
    return ACTION_ALIASES.get(normalized, normalized)


def ensure_local_business_sqlserver_schema_script() -> str:
    return """
SET NOCOUNT ON;

IF OBJECT_ID(N'dbo.rag_agent_action_events', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_agent_action_events (
        action_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        user_id NVARCHAR(160) NOT NULL,
        thread_id NVARCHAR(160) NOT NULL,
        action_name NVARCHAR(120) NOT NULL,
        action_status NVARCHAR(60) NOT NULL,
        subject NVARCHAR(260) NULL,
        order_no NVARCHAR(120) NULL,
        contact NVARCHAR(260) NULL,
        priority NVARCHAR(40) NOT NULL,
        payload_json NVARCHAR(MAX) NULL,
        result_json NVARCHAR(MAX) NULL,
        source_question NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_agent_action_events_created_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_customer_service_tickets', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_customer_service_tickets (
        ticket_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        user_id NVARCHAR(160) NOT NULL,
        thread_id NVARCHAR(160) NOT NULL,
        ticket_type NVARCHAR(120) NOT NULL,
        status NVARCHAR(60) NOT NULL,
        priority NVARCHAR(40) NOT NULL,
        subject NVARCHAR(260) NOT NULL,
        description NVARCHAR(MAX) NULL,
        order_no NVARCHAR(120) NULL,
        contact NVARCHAR(260) NULL,
        payload_json NVARCHAR(MAX) NULL,
        source_question NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_customer_service_tickets_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_customer_service_tickets_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_customer_handoff_queue', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_customer_handoff_queue (
        handoff_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        ticket_id NVARCHAR(80) NULL,
        user_id NVARCHAR(160) NOT NULL,
        thread_id NVARCHAR(160) NOT NULL,
        reason NVARCHAR(MAX) NULL,
        priority NVARCHAR(40) NOT NULL,
        status NVARCHAR(60) NOT NULL,
        payload_json NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_customer_handoff_queue_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_customer_handoff_queue_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_customer_profile_memory', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_customer_profile_memory (
        memory_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        user_id NVARCHAR(160) NOT NULL,
        memory_key NVARCHAR(160) NOT NULL,
        value_json NVARCHAR(MAX) NOT NULL,
        source_id NVARCHAR(120) NOT NULL,
        confidence FLOAT NOT NULL,
        updated_at DATETIME2(0) NOT NULL,
        expiry NVARCHAR(80) NULL,
        consent_scope NVARCHAR(120) NOT NULL
    );
END;

IF OBJECT_ID(N'dbo.rag_agent_followups', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_agent_followups (
        followup_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        ticket_id NVARCHAR(80) NULL,
        user_id NVARCHAR(160) NOT NULL,
        thread_id NVARCHAR(160) NOT NULL,
        due_at NVARCHAR(80) NULL,
        channel NVARCHAR(80) NOT NULL,
        status NVARCHAR(60) NOT NULL,
        message NVARCHAR(MAX) NULL,
        payload_json NVARCHAR(MAX) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_agent_followups_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_agent_followups_updated_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID(N'dbo.rag_agent_correction_samples', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rag_agent_correction_samples (
        sample_id NVARCHAR(80) NOT NULL PRIMARY KEY,
        user_id NVARCHAR(160) NOT NULL,
        thread_id NVARCHAR(160) NOT NULL,
        question NVARCHAR(MAX) NOT NULL,
        answer NVARCHAR(MAX) NULL,
        failure_branch NVARCHAR(160) NOT NULL,
        verifier_score FLOAT NOT NULL,
        mark_json NVARCHAR(MAX) NOT NULL,
        verifier_json NVARCHAR(MAX) NOT NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_rag_agent_correction_samples_created_at DEFAULT SYSUTCDATETIME()
    );
END;

IF COL_LENGTH(N'dbo.rag_agent_action_events', N'result_json') IS NULL
BEGIN
    ALTER TABLE dbo.rag_agent_action_events ADD result_json NVARCHAR(MAX) NULL;
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_agent_action_events_user_thread' AND object_id = OBJECT_ID(N'dbo.rag_agent_action_events'))
BEGIN
    CREATE INDEX IX_rag_agent_action_events_user_thread ON dbo.rag_agent_action_events(user_id, thread_id, created_at);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_customer_service_tickets_user_status' AND object_id = OBJECT_ID(N'dbo.rag_customer_service_tickets'))
BEGIN
    CREATE INDEX IX_rag_customer_service_tickets_user_status ON dbo.rag_customer_service_tickets(user_id, status, updated_at);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rag_customer_profile_memory_user_key' AND object_id = OBJECT_ID(N'dbo.rag_customer_profile_memory'))
BEGIN
    CREATE UNIQUE INDEX IX_rag_customer_profile_memory_user_key ON dbo.rag_customer_profile_memory(user_id, memory_key);
END;
"""


def ensure_local_business_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_agent_action_events (
            action_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            action_name TEXT NOT NULL,
            action_status TEXT NOT NULL,
            subject TEXT,
            order_no TEXT,
            contact TEXT,
            priority TEXT NOT NULL,
            payload_json TEXT,
            result_json TEXT,
            source_question TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_customer_service_tickets (
            ticket_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            ticket_type TEXT NOT NULL,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT,
            order_no TEXT,
            contact TEXT,
            payload_json TEXT,
            source_question TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_customer_handoff_queue (
            handoff_id TEXT PRIMARY KEY,
            ticket_id TEXT,
            user_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            reason TEXT,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_customer_profile_memory (
            memory_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            memory_key TEXT NOT NULL,
            value_json TEXT NOT NULL,
            source_id TEXT NOT NULL,
            confidence REAL NOT NULL,
            updated_at TEXT NOT NULL,
            expiry TEXT,
            consent_scope TEXT NOT NULL,
            UNIQUE(user_id, memory_key)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_agent_followups (
            followup_id TEXT PRIMARY KEY,
            ticket_id TEXT,
            user_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            due_at TEXT,
            channel TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_agent_correction_samples (
            sample_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT,
            failure_branch TEXT NOT NULL,
            verifier_score REAL NOT NULL,
            mark_json TEXT NOT NULL,
            verifier_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


class LocalBusinessActionStore:
    """SQL Server backed local business system for the customer agent."""

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string

    def ensure_schema(self) -> None:
        with pyodbc.connect(self.connection_string) as connection:
            connection.execute(ensure_local_business_sqlserver_schema_script())
            connection.commit()

    def execute_action(self, action_name: str, action_args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        normalized_action = normalize_business_action_name(action_name)
        safe_args = dict(action_args or {})
        safe_context = dict(context or {})
        self.ensure_schema()
        if normalized_action == "create_ticket":
            return self._create_ticket(normalized_action, action_name, safe_args, safe_context)
        if normalized_action == "transfer_human":
            return self._transfer_human(normalized_action, action_name, safe_args, safe_context)
        if normalized_action == "create_followup":
            return self._create_followup(normalized_action, action_name, safe_args, safe_context)
        if normalized_action == "record_customer_profile":
            return self._record_customer_profile(normalized_action, action_name, safe_args, safe_context)
        if normalized_action == "update_ticket_status":
            return self._update_ticket_status(normalized_action, action_name, safe_args, safe_context)
        if normalized_action == "query_tickets":
            return self._query_tickets(normalized_action, action_name, safe_args, safe_context)
        if normalized_action == "query_business_context":
            # 2026-06-05 17:32:11 新增原因：复杂业务问答必须拿结构化业务上下文，不能只查客服工单列表。
            return self._query_business_context(normalized_action, action_name, safe_args, safe_context)
        if normalized_action == "query_profile":
            return self._query_profile(normalized_action, action_name, safe_args, safe_context)
        if normalized_action == "log_note":
            return self._log_note(normalized_action, action_name, safe_args, safe_context)
        return self._unsupported_action(normalized_action, action_name, safe_args, safe_context)

    def record_failure_sample(
        self,
        user_id: str,
        thread_id: str,
        question: str,
        answer: str,
        failure_branch: str,
        verifier_score: float,
        mark: dict[str, Any],
        verifier_result: dict[str, Any],
    ) -> dict[str, Any]:
        self.ensure_schema()
        sample_id = stable_business_id("failsample", user_id, thread_id, question, failure_branch, verifier_score)
        now = utc_now()
        with pyodbc.connect(self.connection_string) as connection:
            connection.execute(
                """
                MERGE dbo.rag_agent_correction_samples AS target
                USING (
                    SELECT ? AS sample_id, ? AS user_id, ? AS thread_id, ? AS question,
                           ? AS answer, ? AS failure_branch, ? AS verifier_score,
                           ? AS mark_json, ? AS verifier_json, ? AS created_at
                ) AS source
                ON target.sample_id = source.sample_id
                WHEN MATCHED THEN
                    UPDATE SET answer = source.answer,
                               failure_branch = source.failure_branch,
                               verifier_score = source.verifier_score,
                               mark_json = source.mark_json,
                               verifier_json = source.verifier_json
                WHEN NOT MATCHED THEN
                    INSERT (sample_id, user_id, thread_id, question, answer, failure_branch, verifier_score, mark_json, verifier_json, created_at)
                    VALUES (source.sample_id, source.user_id, source.thread_id, source.question, source.answer, source.failure_branch,
                            source.verifier_score, source.mark_json, source.verifier_json, source.created_at);
                """,
                sample_id,
                user_id,
                thread_id,
                question,
                answer,
                failure_branch,
                verifier_score,
                json_dumps(mark),
                json_dumps(verifier_result),
                now,
            )
            connection.commit()
        return {"sample_id": sample_id, "failure_branch": failure_branch, "storage": "sqlserver"}

    def read_profile_memory(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        self.ensure_schema()
        rows: list[dict[str, Any]] = []
        with pyodbc.connect(self.connection_string) as connection:
            cursor = connection.execute(
                """
                SELECT TOP (?) memory_id, user_id, memory_key, value_json,
                       source_id, confidence, updated_at, expiry, consent_scope
                FROM dbo.rag_customer_profile_memory
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                int(limit),
                user_id,
            )
            for row in cursor.fetchall():
                rows.append(
                    {
                        "memory_id": row.memory_id,
                        "namespace": ["sqlserver_profile", row.user_id],
                        "key": row.memory_key,
                        "value": json.loads(row.value_json) if row.value_json else {},
                        "source_id": row.source_id,
                        "confidence": float(row.confidence or 0.0),
                        "updated_at": str(row.updated_at),
                        "expiry": row.expiry,
                        "consent_scope": row.consent_scope,
                    }
                )
        return rows

    def _context_value(self, context: dict[str, Any], key: str, default: str = "") -> str:
        value = context.get(key, default)
        return str(value) if value not in (None, "") else default

    def _arg_value(self, args: dict[str, Any], keys: tuple[str, ...], default: str = "") -> str:
        for key in keys:
            value = args.get(key)
            if value not in (None, ""):
                return str(value)
        return default

    def _priority(self, args: dict[str, Any], default: str = "normal") -> str:
        value = self._arg_value(args, ("priority", "risk_level", "urgency"), default)
        return value[:40]

    def _ticket_type(self, original_action: str, args: dict[str, Any]) -> str:
        return self._arg_value(args, ("ticket_type", "case_type", "business_type"), normalize_business_action_name(original_action))[:120]

    def _subject(self, args: dict[str, Any], context: dict[str, Any], default: str) -> str:
        subject = self._arg_value(args, ("subject", "title", "summary", "reason"), "")
        if not subject:
            subject = self._context_value(context, "source_question", default)
        return subject[:260]

    # 2026-06-06 11:02:18 修改原因：集中抽取业务关注词时同时消费问题和 RAG top1，不再维护固定场景词表。
    def _extract_business_focus_terms(self, question: str, best_answer: str = "") -> list[str]:
        # 2026-06-05 18:10:08 修改原因：使用共享泛化语义抽词，任何新 chunk 的字段词都能进入业务上下文。
        return extract_semantic_terms(question, best_answer, limit=16)

    # 2026-06-06 11:02:18 修改原因：业务上下文意图改为通用语义审计，避免固定模板污染其他业务问题。
    def _business_context_intent(self, focus_terms: list[str]) -> str:
        # 2026-06-05 18:10:08 修改原因：不按固定业务词分类，统一返回可泛化的语义业务上下文。
        return "semantic_business_context"

    # 2026-06-06 11:02:18 修改原因：业务摘要从动态主题词和 RAG 证据生成，不再输出固定场景模板。
    def _business_context_summary(self, intent: str, focus_terms: list[str], best_answer: str = "") -> list[str]:
        # 2026-06-05 18:10:08 修改原因：动态拼接当前业务主题词。
        focus_text = "、".join(focus_terms) if focus_terms else "未抽取到明确主题词"
        # 2026-06-05 18:10:08 修改原因：初始化泛化业务上下文摘要。
        summary = [
            # 2026-06-05 18:10:08 修改原因：展示当前问题和证据抽出的真实主题词。
            f"业务主题词：{focus_text}。",
            # 2026-06-05 18:10:08 修改原因：声明该工具是只读语义审计，不替用户制造副作用。
            "业务动作：只读业务上下文查询；最终答案必须覆盖当前问题的核心对象、动作、状态或条件，不得改写成其他业务场景。",
        ]
        # 2026-06-05 18:10:08 修改原因：RAG top1 存在时作为业务语义锚点进入 Prompt Builder。
        if best_answer:
            # 2026-06-05 18:10:08 修改原因：追加证据锚点，控制长度避免 Prompt Builder 过长。
            summary.append(f"RAG证据锚点：{best_answer[:260]}。")
        # 2026-06-05 18:10:08 修改原因：返回泛化摘要。
        return summary

    def _insert_action_event(
        self,
        connection: pyodbc.Connection,
        action_id: str,
        action_name: str,
        action_status: str,
        args: dict[str, Any],
        context: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO dbo.rag_agent_action_events (
                action_id, user_id, thread_id, action_name, action_status, subject,
                order_no, contact, priority, payload_json, result_json, source_question, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            action_id,
            self._context_value(context, "user_id", "anonymous"),
            self._context_value(context, "thread_id", "default"),
            action_name,
            action_status,
            self._arg_value(args, ("subject", "title", "summary", "reason"), "")[:260],
            self._arg_value(args, ("order_no", "order_id", "order_number"), "")[:120],
            self._arg_value(args, ("contact", "phone", "mobile", "email"), "")[:260],
            self._priority(args),
            json_dumps(args),
            json_dumps(result),
            self._context_value(context, "source_question", ""),
            utc_now(),
        )

    def _insert_ticket(
        self,
        connection: pyodbc.Connection,
        original_action: str,
        args: dict[str, Any],
        context: dict[str, Any],
        status: str = "open",
    ) -> dict[str, Any]:
        ticket_id = self._arg_value(args, ("ticket_id", "case_id"), "") or new_business_id("ticket")
        ticket_type = self._ticket_type(original_action, args)
        priority = self._priority(args, "high" if ticket_type in {"complaint", "return_order"} else "normal")
        subject = self._subject(args, context, "客户业务请求")
        description = self._arg_value(args, ("description", "detail", "message", "reason"), self._context_value(context, "source_question", ""))
        order_no = self._arg_value(args, ("order_no", "order_id", "order_number"), "")[:120]
        contact = self._arg_value(args, ("contact", "phone", "mobile", "email"), "")[:260]
        now = utc_now()
        connection.execute(
            """
            MERGE dbo.rag_customer_service_tickets AS target
            USING (
                SELECT ? AS ticket_id, ? AS user_id, ? AS thread_id, ? AS ticket_type,
                       ? AS status, ? AS priority, ? AS subject, ? AS description,
                       ? AS order_no, ? AS contact, ? AS payload_json, ? AS source_question,
                       ? AS created_at, ? AS updated_at
            ) AS source
            ON target.ticket_id = source.ticket_id
            WHEN MATCHED THEN
                UPDATE SET status = source.status,
                           priority = source.priority,
                           subject = source.subject,
                           description = source.description,
                           order_no = source.order_no,
                           contact = source.contact,
                           payload_json = source.payload_json,
                           updated_at = source.updated_at
            WHEN NOT MATCHED THEN
                INSERT (ticket_id, user_id, thread_id, ticket_type, status, priority, subject, description, order_no, contact,
                        payload_json, source_question, created_at, updated_at)
                VALUES (source.ticket_id, source.user_id, source.thread_id, source.ticket_type, source.status, source.priority,
                        source.subject, source.description, source.order_no, source.contact, source.payload_json,
                        source.source_question, source.created_at, source.updated_at);
            """,
            ticket_id,
            self._context_value(context, "user_id", "anonymous"),
            self._context_value(context, "thread_id", "default"),
            ticket_type,
            status,
            priority,
            subject,
            description,
            order_no,
            contact,
            json_dumps(args),
            self._context_value(context, "source_question", ""),
            now,
            now,
        )
        return {
            "ticket_id": ticket_id,
            "ticket_type": ticket_type,
            "status": status,
            "priority": priority,
            "subject": subject,
            "order_no": order_no,
            "contact": contact,
        }

    def _create_ticket(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action_id = new_business_id("action")
        with pyodbc.connect(self.connection_string) as connection:
            ticket = self._insert_ticket(connection, original_action, args, context)
            result = {
                "tool": "sql_rag_business_action",
                "status": "succeeded",
                "action_name": normalized_action,
                "original_action_name": original_action,
                "action_id": action_id,
                "ticket": ticket,
                "message": f"已创建本地客服工单 {ticket['ticket_id']}，状态为 {ticket['status']}。",
            }
            self._insert_action_event(connection, action_id, normalized_action, "succeeded", args, context, result)
            connection.commit()
        return result

    def _transfer_human(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action_id = new_business_id("action")
        with pyodbc.connect(self.connection_string) as connection:
            ticket_id = self._arg_value(args, ("ticket_id", "case_id"), "")
            ticket = None
            if not ticket_id:
                ticket = self._insert_ticket(connection, "human_handoff", args, context, status="awaiting_human")
                ticket_id = ticket["ticket_id"]
            handoff_id = new_business_id("handoff")
            priority = self._priority(args, "high")
            reason = self._arg_value(args, ("reason", "description", "message"), self._context_value(context, "source_question", ""))
            now = utc_now()
            connection.execute(
                """
                INSERT INTO dbo.rag_customer_handoff_queue (
                    handoff_id, ticket_id, user_id, thread_id, reason, priority,
                    status, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                handoff_id,
                ticket_id,
                self._context_value(context, "user_id", "anonymous"),
                self._context_value(context, "thread_id", "default"),
                reason,
                priority,
                "queued",
                json_dumps(args),
                now,
                now,
            )
            result = {
                "tool": "sql_rag_business_action",
                "status": "succeeded",
                "action_name": normalized_action,
                "original_action_name": original_action,
                "action_id": action_id,
                "ticket": ticket,
                "ticket_id": ticket_id,
                "handoff_id": handoff_id,
                "handoff_status": "queued",
                "message": f"已进入本地人工接管队列 {handoff_id}。",
            }
            self._insert_action_event(connection, action_id, normalized_action, "succeeded", args, context, result)
            connection.commit()
        return result

    def _create_followup(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action_id = new_business_id("action")
        with pyodbc.connect(self.connection_string) as connection:
            ticket_id = self._arg_value(args, ("ticket_id", "case_id"), "")
            ticket = None
            if not ticket_id:
                ticket = self._insert_ticket(connection, original_action, args, context, status="open")
                ticket_id = ticket["ticket_id"]
            followup_id = new_business_id("followup")
            due_at = self._arg_value(args, ("due_at", "remind_at", "deadline"), "")
            channel = self._arg_value(args, ("channel", "notify_channel"), "agent_task")[:80]
            message = self._arg_value(args, ("message", "description", "reason"), self._context_value(context, "source_question", ""))
            now = utc_now()
            connection.execute(
                """
                INSERT INTO dbo.rag_agent_followups (
                    followup_id, ticket_id, user_id, thread_id, due_at, channel,
                    status, message, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                followup_id,
                ticket_id,
                self._context_value(context, "user_id", "anonymous"),
                self._context_value(context, "thread_id", "default"),
                due_at,
                channel,
                "pending",
                message,
                json_dumps(args),
                now,
                now,
            )
            result = {
                "tool": "sql_rag_business_action",
                "status": "succeeded",
                "action_name": normalized_action,
                "original_action_name": original_action,
                "action_id": action_id,
                "ticket": ticket,
                "ticket_id": ticket_id,
                "followup_id": followup_id,
                "followup_status": "pending",
                "message": f"已创建本地跟进任务 {followup_id}。",
            }
            self._insert_action_event(connection, action_id, normalized_action, "succeeded", args, context, result)
            connection.commit()
        return result

    def _record_customer_profile(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action_id = new_business_id("action")
        user_id = self._context_value(context, "user_id", "anonymous")
        memory_key = self._arg_value(args, ("memory_key", "key", "profile_key"), "customer_service_preference")[:160]
        value = args.get("value", args.get("profile", args.get("preference", args)))
        confidence = float(args.get("confidence", 0.8) or 0.8)
        expiry = self._arg_value(args, ("expiry", "expires_at"), "")
        consent_scope = self._arg_value(args, ("consent_scope", "scope"), "customer_service")[:120]
        memory_id = stable_business_id("profile", user_id, memory_key)
        now = utc_now()
        with pyodbc.connect(self.connection_string) as connection:
            connection.execute(
                """
                MERGE dbo.rag_customer_profile_memory AS target
                USING (
                    SELECT ? AS memory_id, ? AS user_id, ? AS memory_key, ? AS value_json,
                           ? AS source_id, ? AS confidence, ? AS updated_at,
                           ? AS expiry, ? AS consent_scope
                ) AS source
                ON target.user_id = source.user_id AND target.memory_key = source.memory_key
                WHEN MATCHED THEN
                    UPDATE SET value_json = source.value_json,
                               source_id = source.source_id,
                               confidence = source.confidence,
                               updated_at = source.updated_at,
                               expiry = source.expiry,
                               consent_scope = source.consent_scope
                WHEN NOT MATCHED THEN
                    INSERT (memory_id, user_id, memory_key, value_json, source_id, confidence, updated_at, expiry, consent_scope)
                    VALUES (source.memory_id, source.user_id, source.memory_key, source.value_json, source.source_id,
                            source.confidence, source.updated_at, source.expiry, source.consent_scope);
                """,
                memory_id,
                user_id,
                memory_key,
                json_dumps(value),
                action_id,
                confidence,
                now,
                expiry,
                consent_scope,
            )
            result = {
                "tool": "sql_rag_business_action",
                "status": "succeeded",
                "action_name": normalized_action,
                "original_action_name": original_action,
                "action_id": action_id,
                "memory_write_event": {
                    "memory_layer": "structured_profile",
                    "memory_id": memory_id,
                    "user_id": user_id,
                    "key": memory_key,
                    "source_id": action_id,
                    "confidence": confidence,
                    "consent_scope": consent_scope,
                },
                "message": f"已写入本地客户画像记忆 {memory_id}。",
            }
            self._insert_action_event(connection, action_id, normalized_action, "succeeded", args, context, result)
            connection.commit()
        return result

    def _update_ticket_status(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action_id = new_business_id("action")
        ticket_id = self._arg_value(args, ("ticket_id", "case_id"), "")
        if not ticket_id:
            result = {
                "tool": "sql_rag_business_action",
                "status": "missing_required_field",
                "action_name": normalized_action,
                "action_id": action_id,
                "required_fields": ["ticket_id"],
                "message": "更新工单状态需要 ticket_id。",
            }
            with pyodbc.connect(self.connection_string) as connection:
                self._insert_action_event(connection, action_id, normalized_action, "missing_required_field", args, context, result)
                connection.commit()
            return result
        raw_original_action = (original_action or "").strip().lower().replace("-", "_").replace(" ", "_")
        status = self._arg_value(args, ("status",), "closed" if raw_original_action == "close_ticket" else "open")[:60]
        with pyodbc.connect(self.connection_string) as connection:
            cursor = connection.execute(
                """
                UPDATE dbo.rag_customer_service_tickets
                SET status = ?, updated_at = ?
                WHERE ticket_id = ?
                """,
                status,
                utc_now(),
                ticket_id,
            )
            updated = cursor.rowcount
            result = {
                "tool": "sql_rag_business_action",
                "status": "succeeded" if updated else "not_found",
                "action_name": normalized_action,
                "original_action_name": original_action,
                "action_id": action_id,
                "ticket_id": ticket_id,
                "ticket_status": status,
                "updated_rows": int(updated),
                "message": f"已更新工单 {ticket_id} 状态为 {status}。" if updated else f"未找到工单 {ticket_id}。",
            }
            self._insert_action_event(connection, action_id, normalized_action, result["status"], args, context, result)
            connection.commit()
        return result

    # 2026-06-05 17:32:11 新增原因：提供只读业务上下文查询，修复 query_tickets 成功但没有业务字段佐证的问题。
    def _query_business_context(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        # 2026-06-05 17:32:11 新增原因：生成动作 ID，保证 action_events 可审计。
        action_id = new_business_id("action")
        # 2026-06-05 17:32:11 新增原因：优先读取工具参数里的原始问题。
        question = self._arg_value(args, ("question", "reason", "description", "subject"), "")
        # 2026-06-05 17:32:11 新增原因：参数缺失时回退运行时上下文里的用户问题。
        question = question or self._context_value(context, "source_question", "")
        # 2026-06-05 18:10:08 新增原因：读取 RAG top1 证据，作为泛化业务上下文的语义锚点。
        best_answer = self._arg_value(args, ("best_answer", "rag_best_answer", "answer"), "")
        # 2026-06-05 18:10:08 新增原因：参数缺失时回退运行时上下文里的 RAG top1。
        best_answer = best_answer or self._context_value(context, "best_answer", "")
        # 2026-06-05 18:10:08 修改原因：从问题和 RAG top1 动态抽取业务关注字段，作为执行层返回给模型的结构化证据。
        focus_terms = self._extract_business_focus_terms(question, best_answer)
        # 2026-06-06 11:05:37 修改原因：识别泛化业务意图，不再区分任何固定业务场景。
        intent = self._business_context_intent(focus_terms)
        # 2026-06-05 18:10:08 修改原因：生成动态业务字段摘要，给 Prompt Builder 消费。
        summaries = self._business_context_summary(intent, focus_terms, best_answer)
        # 2026-06-05 17:32:11 新增原因：读取 RAG 证据 chunk，业务上下文要能回指知识库证据。
        source_chunk_ids = args.get("retrieved_chunk_ids") or context.get("retrieved_chunk_ids") or []
        # 2026-06-05 17:32:11 新增原因：构造结构化只读业务查询结果。
        result = {
            # 2026-06-05 17:32:11 新增原因：声明工具来源。
            "tool": "sql_rag_business_action",
            # 2026-06-05 17:32:11 新增原因：只读查询完成也用 succeeded，但语义由 action_name 区分。
            "status": "succeeded",
            # 2026-06-05 17:32:11 新增原因：写入归一化动作名。
            "action_name": normalized_action,
            # 2026-06-05 17:32:11 新增原因：保留原始动作名，便于 alias 审计。
            "original_action_name": original_action,
            # 2026-06-05 17:32:11 新增原因：写入动作 ID。
            "action_id": action_id,
            # 2026-06-05 17:32:11 新增原因：写入业务意图，Prompt Builder 用它判断回答形态。
            "business_intent": intent,
            # 2026-06-05 17:32:11 新增原因：写入业务关注字段，Verifier 用它做语义覆盖。
            "focus_terms": focus_terms,
            # 2026-06-05 18:10:08 新增原因：写入 RAG 证据锚点，便于 verifier 和数据飞轮复盘业务上下文来源。
            "best_answer": best_answer,
            # 2026-06-05 17:32:11 新增原因：写入业务字段摘要，避免最终答案只看到 query_tickets succeeded。
            "business_context": summaries,
            # 2026-06-05 17:32:11 新增原因：写入证据来源 chunk，保持业务工具和 RAG 证据可追溯。
            "source_chunk_ids": source_chunk_ids if isinstance(source_chunk_ids, list) else [str(source_chunk_ids)],
            # 2026-06-05 17:32:11 新增原因：明确这是只读查询，不会替用户改状态。
            "audit_only": True,
            # 2026-06-05 17:32:11 新增原因：返回可读消息用于 trace。
            "message": f"已读取 {intent}，动态主题词 {len(focus_terms)} 个。",
        }
        # 2026-06-05 17:32:11 新增原因：落 action_events，保证业务工具节点真实经过 SQL Server。
        with pyodbc.connect(self.connection_string) as connection:
            # 2026-06-05 17:32:11 新增原因：插入只读业务上下文事件，支持后续审计和数据飞轮。
            self._insert_action_event(connection, action_id, normalized_action, "succeeded", args, context, result)
            # 2026-06-05 17:32:11 新增原因：提交事件写入。
            connection.commit()
        # 2026-06-05 17:32:11 新增原因：返回结构化业务上下文。
        return result

    def _query_tickets(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action_id = new_business_id("action")
        user_id = self._context_value(context, "user_id", "anonymous")
        status = self._arg_value(args, ("status",), "")
        rows: list[dict[str, Any]] = []
        with pyodbc.connect(self.connection_string) as connection:
            if status:
                cursor = connection.execute(
                    """
                    SELECT TOP 20 ticket_id, ticket_type, status, priority, subject, order_no, contact, updated_at
                    FROM dbo.rag_customer_service_tickets
                    WHERE user_id = ? AND status = ?
                    ORDER BY updated_at DESC
                    """,
                    user_id,
                    status,
                )
            else:
                cursor = connection.execute(
                    """
                    SELECT TOP 20 ticket_id, ticket_type, status, priority, subject, order_no, contact, updated_at
                    FROM dbo.rag_customer_service_tickets
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    """,
                    user_id,
                )
            for row in cursor.fetchall():
                rows.append(
                    {
                        "ticket_id": row.ticket_id,
                        "ticket_type": row.ticket_type,
                        "status": row.status,
                        "priority": row.priority,
                        "subject": row.subject,
                        "order_no": row.order_no,
                        "contact": row.contact,
                        "updated_at": str(row.updated_at),
                    }
                )
            result = {
                "tool": "sql_rag_business_action",
                "status": "succeeded",
                "action_name": normalized_action,
                "original_action_name": original_action,
                "action_id": action_id,
                "tickets": rows,
                "message": f"已查询到 {len(rows)} 条本地客服工单。",
            }
            self._insert_action_event(connection, action_id, normalized_action, "succeeded", args, context, result)
            connection.commit()
        return result

    def _query_profile(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action_id = new_business_id("action")
        user_id = self._context_value(context, "user_id", "anonymous")
        rows: list[dict[str, Any]] = []
        with pyodbc.connect(self.connection_string) as connection:
            cursor = connection.execute(
                """
                SELECT TOP 20 memory_id, memory_key, value_json, source_id, confidence, updated_at, expiry, consent_scope
                FROM dbo.rag_customer_profile_memory
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                user_id,
            )
            for row in cursor.fetchall():
                rows.append(
                    {
                        "memory_id": row.memory_id,
                        "memory_key": row.memory_key,
                        "value": json.loads(row.value_json) if row.value_json else {},
                        "source_id": row.source_id,
                        "confidence": float(row.confidence or 0.0),
                        "updated_at": str(row.updated_at),
                        "expiry": row.expiry,
                        "consent_scope": row.consent_scope,
                    }
                )
            result = {
                "tool": "sql_rag_business_action",
                "status": "succeeded",
                "action_name": normalized_action,
                "original_action_name": original_action,
                "action_id": action_id,
                "profile_memory": rows,
                "message": f"已读取 {len(rows)} 条本地客户画像记忆。",
            }
            self._insert_action_event(connection, action_id, normalized_action, "succeeded", args, context, result)
            connection.commit()
        return result

    def _log_note(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        note_args = dict(args)
        note_args.setdefault("ticket_type", "agent_note")
        note_args.setdefault("subject", self._subject(args, context, "客服备注"))
        return self._create_ticket(normalized_action, original_action, note_args, context)

    def _unsupported_action(self, normalized_action: str, original_action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action_id = new_business_id("action")
        result = {
            "tool": "sql_rag_business_action",
            "status": "unsupported_action",
            "action_name": normalized_action,
            "original_action_name": original_action,
            "action_id": action_id,
            "supported_actions": SUPPORTED_BUSINESS_ACTIONS,
            "message": "本地业务系统不支持该动作，请改用已支持动作或转人工。",
        }
        with pyodbc.connect(self.connection_string) as connection:
            self._insert_action_event(connection, action_id, normalized_action or "unknown", "unsupported_action", args, context, result)
            connection.commit()
        return result
