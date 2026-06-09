# -*- coding: utf-8 -*-
# 2026-06-06 10:34:12 新增原因：声明测试文件编码，保证中文泛化业务场景断言稳定。
"""QA 清洗抽取层全局泛化合同测试。"""
# 2026-06-06 10:34:12 新增原因：说明本测试锁定入库源头不能再依赖固定业务场景词表。

# 2026-06-06 10:34:12 新增原因：导入 sys，用于把 SQL_RAG 和 data_cleaning 加入测试模块搜索路径。
import sys
# 2026-06-06 10:34:12 新增原因：导入 unittest，用标准库测试避免新增外部依赖。
import unittest
# 2026-06-06 10:34:12 新增原因：导入 Path，用于稳定定位当前 SQL_RAG 根目录。
from pathlib import Path

# 2026-06-06 10:34:12 新增原因：定位 SQL_RAG 根目录，避免依赖外层工程安装状态。
SQL_RAG_DIR = Path(__file__).resolve().parents[2]
# 2026-06-06 10:34:12 新增原因：定位 data_cleaning 根目录，兼容 qa_extractor 里的 common.* 导入方式。
DATA_CLEANING_DIR = SQL_RAG_DIR / "data_cleaning"
# 2026-06-06 10:34:12 新增原因：把 SQL_RAG 根目录加入模块搜索路径，便于导入 overall_planning 语义工具。
if str(SQL_RAG_DIR) not in sys.path:
    # 2026-06-06 10:34:12 新增原因：插到最前面，确保测试使用当前工作区源码。
    sys.path.insert(0, str(SQL_RAG_DIR))
# 2026-06-06 10:34:12 新增原因：把 data_cleaning 根目录加入模块搜索路径，便于导入 cleaning_extraction。
if str(DATA_CLEANING_DIR) not in sys.path:
    # 2026-06-06 10:34:12 新增原因：插到最前面，确保 common.constants 读取当前工作区源码。
    sys.path.insert(0, str(DATA_CLEANING_DIR))

# 2026-06-06 10:34:12 新增原因：导入 QA 抽取函数，直接验证清洗入库源头的泛化行为。
from cleaning_extraction.qa_extractor import apply_business_term_aliases, build_query_aliases, detect_scene, extract_entities, extract_keywords
# 2026-06-06 10:34:12 新增原因：导入语义抽词函数，验证下游 Agent 使用的主题词不再产生滑窗碎片。
from overall_planning.semantic_evidence import extract_semantic_terms


# 2026-06-06 10:34:12 新增原因：集中测试清洗抽取和语义抽词不再针对单一截图场景打补丁。
class QaExtractorGeneralizationTest(unittest.TestCase):
    # 2026-06-06 10:34:12 新增原因：验证任意新业务 chunk 都能动态产生场景和术语，而不是落回固定白名单。
    def test_dynamic_scene_and_terms_are_extracted_from_unseen_business_chunk(self) -> None:
        # 2026-06-06 10:34:12 新增原因：构造不属于旧固定场景词表的质检导出业务问题。
        text = "质检报告导出时，客户想按供应商和检验批次筛选异常记录，然后导出明细。"
        # 2026-06-06 10:34:12 新增原因：识别场景，期望运行时从文本动态提炼业务场景名。
        scene = detect_scene(text)
        # 2026-06-06 10:34:12 新增原因：抽取实体，期望 system_terms 来自当前文本而非固定场景白名单。
        entities = extract_entities(text)
        # 2026-06-06 10:34:12 新增原因：抽取关键词，期望关键词能覆盖当前 chunk 的真实字段。
        keywords = extract_keywords(text, scene, entities)
        # 2026-06-06 10:34:12 新增原因：断言场景是动态场景，避免任何未知业务都被写成系统操作问答。
        self.assertTrue(scene.startswith("动态业务场景："), scene)
        # 2026-06-06 10:34:12 新增原因：断言新业务主题词进入实体，证明不需要事先写死质检场景。
        self.assertIn("质检报告", entities["system_terms"])
        # 2026-06-06 10:34:12 新增原因：断言供应商字段被动态抽取，保证后续 Prompt Builder 有业务焦点。
        self.assertIn("供应商", entities["system_terms"])
        # 2026-06-06 10:34:12 新增原因：断言检验批次字段被动态抽取，覆盖任意业务字段组合。
        self.assertIn("检验批次", entities["system_terms"])
        # 2026-06-06 10:34:12 新增原因：断言异常记录被动态抽取，避免只认订单、入账单等旧字段。
        self.assertIn("异常记录", entities["system_terms"])
        # 2026-06-06 10:34:12 新增原因：断言关键词也继承动态主题，保证 Qdrant payload 可被召回消费。
        self.assertIn("质检报告", keywords)

    # 2026-06-06 10:34:12 新增原因：验证清洗层不再把当前业务词强行改写成旧截图场景的别名。
    def test_business_term_normalization_does_not_rewrite_current_domain_terms(self) -> None:
        # 2026-06-06 10:34:12 新增原因：构造同时含有两个业务词的文本，验证不再固定替换成单一规范词。
        text = "入账单和入仓单都在原始问题里出现时，不应该由固定别名强行互相替换。"
        # 2026-06-06 10:34:12 新增原因：断言规范化只做通用清理，不做业务语义改写。
        self.assertEqual(apply_business_term_aliases(text), text)

    # 2026-06-06 10:34:12 新增原因：验证检索别名来自当前问题和实体动态主题，而不是固定别名字典。
    def test_query_aliases_are_dynamic_terms_from_current_question(self) -> None:
        # 2026-06-06 10:34:12 新增原因：构造新的业务问法，避免旧场景词表碰巧命中。
        question = "质检报告导出时怎么按供应商和检验批次筛选异常记录？"
        # 2026-06-06 10:34:12 新增原因：抽取当前问题实体，供 query aliases 生成。
        entities = extract_entities(question)
        # 2026-06-06 10:34:12 新增原因：生成动态检索别名，后续 Qdrant 召回应吃到这些主题词。
        aliases = build_query_aliases(question, entities)
        # 2026-06-06 10:34:12 新增原因：断言质检报告作为当前问题主题进入别名。
        self.assertIn("质检报告", aliases)
        # 2026-06-06 10:34:12 新增原因：断言供应商作为当前问题主题进入别名。
        self.assertIn("供应商", aliases)
        # 2026-06-06 10:34:12 新增原因：断言检验批次作为当前问题主题进入别名。
        self.assertIn("检验批次", aliases)

    # 2026-06-06 10:34:12 新增原因：验证语义抽词按可读主题排序，不再把连接词附近的滑窗碎片喂给 Verifier。
    def test_semantic_terms_prefer_readable_business_phrases_over_sliding_fragments(self) -> None:
        # 2026-06-06 10:34:12 新增原因：构造截图同类长问，但断言目标是泛化抽词质量而非固定业务答案。
        question = "入账单如果已经入仓了，但是预付款状态又对不上，我是不是要先让财务反审入账单，再把付款状态退回来？"
        # 2026-06-06 10:34:12 新增原因：抽取主题词，后续业务工具、图谱排序和 verifier 都会消费这一结果。
        terms = extract_semantic_terms(question, limit=12)
        # 2026-06-06 10:34:12 新增原因：断言核心业务对象保留为可读词。
        self.assertIn("入账单", terms)
        # 2026-06-06 10:34:12 新增原因：断言状态字段保留为可读词。
        self.assertIn("预付款状态", terms)
        # 2026-06-06 10:34:12 新增原因：断言动作词保留为可读词。
        self.assertIn("反审", terms)
        # 2026-06-06 10:34:12 新增原因：断言连接词片段不能进入主题词，避免全链路误判。
        self.assertFalse(any("如果" in term or "已经" in term or "但是" in term for term in terms), terms)


# 2026-06-06 10:34:12 新增原因：允许直接运行本文件，便于本地快速红绿验证。
if __name__ == "__main__":
    # 2026-06-06 10:34:12 新增原因：启动标准 unittest runner。
    unittest.main()
