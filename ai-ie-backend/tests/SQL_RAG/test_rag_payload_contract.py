# -*- coding: utf-8 -*-
"""SQL_RAG 产物被通用 RAG 消费时的契约回归测试。"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_RAG_DIR = PROJECT_ROOT / "app" / "SQL_RAG"
DATA_CLEANING_DIR = SQL_RAG_DIR / "data_cleaning"
for module_dir in (SQL_RAG_DIR, DATA_CLEANING_DIR):
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))

from llama_index.core.schema import TextNode

from common.utils import sha256_text
from data_cleaning.data_structures.relation_builder import (
    apply_fusion_metadata_with_llamaindex,
    build_chunk_fusion_payloads_with_llamaindex,
    build_validation_issue_payloads,
)
from data_cleaning.storage.json_writer import llamaindex_nodes_to_storage_json
from data_cleaning.storage.sqlserver_writer import build_chunk_insert_script
from Qdrant.qdrant_sqlserver_sync import (
    CanonicalChunk,
    EmbeddingConfig,
    build_qdrant_payload,
    validate_chunks_before_qdrant,
)


QUESTION = "入账单你可以反你有反审的，对不对？"
ANSWER = "可以的，我这里。先把这个入账单财务反审，让付款状预付款的状态退回来。"


def make_qa_node(node_id: str, document_id: str, chunk_index: int, text: str, answer: str = ANSWER) -> TextNode:
    pair_text = f"问题：{QUESTION}\n答案：{answer}"
    metadata = {
        "document_id": document_id,
        "audio_no": 1,
        "audio_title": "预付款与入仓处理.m4a",
        "chunk_index": chunk_index,
        "qa_pair_id": f"pair_{node_id}",
        "qa_pair_index": chunk_index,
        "qa_similarity_score": 0.79,
        "qa_similarity_threshold": 0.08,
        "qa_pair_validated": True,
        "scene": "预付款与入仓",
        "question": QUESTION,
        "answer": answer,
        "resolution_steps": ["先把这个入账单财务反审，让付款状预付款的状态退回来。"],
        "keywords": ["预付款与入仓", "入账单", "反审", "预付款状态"],
        "entities": {"system_terms": ["入账单", "反审", "预付款状态"]},
        "source_excerpt": pair_text,
        "content_hash": sha256_text(pair_text),
        "question_hash": sha256_text(QUESTION),
        "answer_hash": sha256_text(answer),
        "global_cluster_id": "global_prepaid",
        "global_cluster_label": "预付款与入仓",
    }
    return TextNode(id_=node_id, text=text, metadata=metadata)


class RagPayloadContractTest(unittest.TestCase):
    def test_storage_payload_builds_answer_first_contract_when_node_text_is_partial(self) -> None:
        node = make_qa_node(
            "qachunk_contract",
            "qadoc_a",
            1,
            "问题：入账单你可以反你有反审的，对不对？答案：可以的，我这里。",
        )

        payload = llamaindex_nodes_to_storage_json([node])[0]

        self.assertEqual(payload["payload_schema_version"], "qa-rag-payload-v3")
        self.assertTrue(payload["qdrant_ready"])
        self.assertIn(ANSWER, payload["llm_text"])
        self.assertIn(ANSWER, payload["retrieval_text"])
        self.assertIn(ANSWER, payload["source_excerpt_full"])
        self.assertIn(ANSWER, payload["llamaindex_node"]["text"])

    def test_duplicate_context_is_merged_into_canonical_contract(self) -> None:
        canonical = make_qa_node(
            "qachunk_canonical",
            "qadoc_a",
            1,
            "问题：入账单你可以反你有反审的，对不对？答案：可以的，我这里。",
        )
        duplicate = make_qa_node(
            "qachunk_duplicate",
            "qadoc_b",
            2,
            f"问题：{QUESTION}\n答案：{ANSWER}",
        )
        duplicate.metadata["source_excerpt"] = f"问题：{QUESTION}\n答案：{ANSWER}"

        fusion_payloads = build_chunk_fusion_payloads_with_llamaindex([canonical, duplicate], similarity_threshold=0.9)
        fused_nodes = apply_fusion_metadata_with_llamaindex([canonical, duplicate], fusion_payloads)
        fused_canonical = next(node for node in fused_nodes if node.node_id == "qachunk_canonical")

        self.assertEqual(fused_canonical.metadata["fusion_status"], "canonical")
        self.assertEqual(fused_canonical.metadata["merged_duplicate_chunk_ids"], ["qachunk_duplicate"])
        self.assertIn(ANSWER, fused_canonical.metadata["duplicate_contexts"][0]["cleaned_text"])

    def test_validation_fails_when_consumable_text_drops_answer(self) -> None:
        node = make_qa_node(
            "qachunk_bad_contract",
            "qadoc_a",
            1,
            "问题：入账单你可以反你有反审的，对不对？答案：可以的，我这里。",
        )
        node.metadata["llm_text"] = "问题：入账单你可以反你有反审的，对不对？答案：可以的，我这里。"

        issues = build_validation_issue_payloads([node])
        issue_types = {issue["issue_type"] for issue in issues}

        self.assertIn("llm_text_missing_answer", issue_types)

    def test_qdrant_payload_default_text_is_answer_first_and_contract_checked(self) -> None:
        chunk = CanonicalChunk(
            chunk_id="qachunk_contract",
            document_id="qadoc_a",
            audio_no=1,
            audio_title="预付款与入仓处理.m4a",
            chunk_index=1,
            scene="预付款与入仓",
            question=QUESTION,
            answer=ANSWER,
            cleaned_text=f"问题：{QUESTION}\n答案：{ANSWER}",
            resolution_steps='["先把这个入账单财务反审，让付款状预付款的状态退回来。"]',
            keywords='["预付款与入仓","入账单","反审"]',
            entities_json='{"system_terms":["入账单","反审"]}',
            source_excerpt=f"问题：{QUESTION}\n答案：{ANSWER}",
            content_hash="hash",
            qa_pair_id="pair",
            qa_pair_index=1,
            qa_similarity_score=0.79,
            qa_similarity_threshold=0.08,
            qa_pair_validated=True,
            cluster_id="cluster",
            cluster_label="预付款与入仓",
            cluster_level="document_scene",
            cluster_path='["qadoc_a","预付款与入仓"]',
            global_cluster_id="global",
            global_cluster_label="预付款与入仓",
            global_cluster_level="global_scene",
            global_cluster_path='["global","预付款与入仓"]',
            question_hash=sha256_text(QUESTION),
            answer_hash=sha256_text(ANSWER),
            canonical_chunk_id="qachunk_contract",
            fusion_status="canonical",
            payload_schema_version="qa-rag-payload-v3",
            payload_json={},
            rag_contract_version="qa-rag-contract-v1",
            canonical_question="入仓单你可以反审的，对不对？",
            answer_text=ANSWER,
            query_aliases=["入仓单你可以反审的，对不对？"],
            source_excerpt_full=f"问题：{QUESTION}\n答案：{ANSWER}",
            llm_text="",
            retrieval_text="",
            duplicate_contexts=[],
            merged_duplicate_chunk_ids=[],
            qdrant_ready=True,
            validation_flags=[],
        )
        embedding_config = EmbeddingConfig(
            api_base="http://embedding.local/v1",
            api_key="test",
            model="test-embedding",
            dimension=3,
            batch_size=8,
        )

        validation = validate_chunks_before_qdrant([chunk])
        payload = build_qdrant_payload(chunk, embedding_config)

        self.assertEqual(validation["error_count"], 0)
        self.assertEqual(payload["rag_contract_version"], "qa-rag-contract-v1")
        self.assertIn(ANSWER, payload["text"])
        self.assertIn(ANSWER, payload["llm_text"])
        self.assertIn(ANSWER, payload["retrieval_text"])

    def test_qdrant_contract_accepts_legacy_rows_when_answer_can_rebuild_excerpt(self) -> None:
        chunk = CanonicalChunk(
            chunk_id="qachunk_legacy",
            document_id="qadoc_legacy",
            audio_no=1,
            audio_title="legacy.m4a",
            chunk_index=1,
            scene="预付款与入仓",
            question=QUESTION,
            answer=ANSWER,
            cleaned_text="问题：入账单你可以反你有反审的，对不对？答案：可以的，我这里。",
            resolution_steps="[]",
            keywords="[]",
            entities_json="{}",
            source_excerpt=f"问题：{QUESTION}\n答案：可以的，我这里。",
            content_hash="hash",
            qa_pair_id="pair",
            qa_pair_index=1,
            qa_similarity_score=0.79,
            qa_similarity_threshold=0.08,
            qa_pair_validated=True,
            cluster_id="cluster",
            cluster_label="预付款与入仓",
            cluster_level="document_scene",
            cluster_path="[]",
            global_cluster_id="global",
            global_cluster_label="预付款与入仓",
            global_cluster_level="global_scene",
            global_cluster_path="[]",
            question_hash=sha256_text(QUESTION),
            answer_hash=sha256_text(ANSWER),
            canonical_chunk_id="qachunk_legacy",
            fusion_status="canonical",
            payload_schema_version="qa-rag-payload-v2",
            payload_json={},
            rag_contract_version="qa-rag-contract-v1",
            canonical_question=QUESTION,
            answer_text=ANSWER,
            query_aliases=[],
            source_excerpt_full=f"问题：{QUESTION}\n答案：{ANSWER}",
            llm_text="",
            retrieval_text="",
            duplicate_contexts=[],
            merged_duplicate_chunk_ids=[],
            qdrant_ready=True,
            validation_flags=[],
        )

        validation = validate_chunks_before_qdrant([chunk])

        self.assertEqual(validation["error_count"], 0)

    def test_sqlserver_chunk_insert_exposes_contract_columns(self) -> None:
        node = make_qa_node(
            "qachunk_sql_contract",
            "qadoc_a",
            1,
            "问题：入账单你可以反你有反审的，对不对？答案：可以的，我这里。",
        )
        payload = llamaindex_nodes_to_storage_json([node])[0]

        sql = build_chunk_insert_script([payload])

        self.assertIn("rag_contract_version", sql)
        self.assertIn("answer_text", sql)
        self.assertIn("llm_text", sql)
        self.assertIn("retrieval_text", sql)
        self.assertIn("qdrant_ready", sql)


if __name__ == "__main__":
    unittest.main()
