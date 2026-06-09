# -*- coding: utf-8 -*-
"""SQL_RAG 泛化语义证据工具。"""

# 2026-06-05 18:10:08 新增原因：导入 JSON，用于把结构化工具结果转成可抽词文本。
import json
# 2026-06-05 18:10:08 新增原因：导入正则，用于动态抽取任意业务 chunk 的主题词。
import re
# 2026-06-05 18:10:08 新增原因：导入 Any，保证工具函数可接收 dict/list/str 等证据对象。
from typing import Any


# 2026-06-06 11:02:18 修改原因：定义通用停用词，不绑定任何具体业务场景。
GENERIC_STOP_TERMS = {
    # 2026-06-05 18:10:08 新增原因：过滤疑问虚词，避免把“怎么/如何”当业务主题。
    "怎么",
    # 2026-06-05 18:10:08 新增原因：过滤疑问虚词。
    "如何",
    # 2026-06-05 18:10:08 新增原因：过滤原因询问虚词。
    "为什么",
    # 2026-06-05 18:10:08 新增原因：过滤是非问虚词。
    "是否",
    # 2026-06-05 18:10:08 新增原因：过滤是非问虚词。
    "是不是",
    # 2026-06-05 18:10:08 新增原因：过滤语气词。
    "可以",
    # 2026-06-05 18:10:08 新增原因：过滤泛称对象，不让“客户”压过真实业务词。
    "客户",
    # 2026-06-05 18:10:08 新增原因：过滤泛称对象。
    "用户",
    # 2026-06-05 18:10:08 新增原因：过滤泛称问题词。
    "问题",
    # 2026-06-05 18:10:08 新增原因：过滤泛称操作词。
    "操作",
    # 2026-06-05 18:10:08 新增原因：过滤泛称提示词。
    "提示",
    # 2026-06-06 10:41:26 新增原因：过滤条件连接词，避免“如果/已经/但是”进入业务主题。
    "如果",
    # 2026-06-06 10:41:26 新增原因：过滤状态叙述连接词，避免滑窗碎片污染 verifier。
    "已经",
    # 2026-06-06 10:41:26 新增原因：过滤转折连接词，避免当前问题主题被语气词抢占。
    "但是",
    # 2026-06-06 10:41:26 新增原因：过滤泛化代词，避免“这一类”压过真实业务字段。
    "这个",
    # 2026-06-06 10:41:26 新增原因：过滤泛化代词，避免“那个”进入 Prompt Builder 主题。
    "那个",
}


# 2026-06-05 18:10:08 新增原因：定义内部图谱标记，避免 qachunk 和内部边名参与最终语义覆盖。
INTERNAL_GRAPH_MARKERS = {
    # 2026-06-05 18:10:08 新增原因：过滤 chunk 提及边。
    "MENTIONED_IN_CHUNK",
    # 2026-06-05 18:10:08 新增原因：过滤全局簇内部边。
    "CHUNK_IN_GLOBAL_CLUSTER",
    # 2026-06-05 18:10:08 新增原因：过滤融合内部边。
    "FUSED_INTO",
}


# 2026-06-06 14:54:36 修改原因：扩展答案开头“是/是的”肯定结论，避免否定证据被模型用“是”反写后漏检。
POSITIVE_POLARITY_PATTERN = re.compile(r"((?:^|[。！？\n])\s*(?:结论[:：]?\s*)?是(?:的)?(?=[，。；、\s]|$)|可以|可直接|应该|应当|应先|需先|需要|必须|建议|允许|能够|能|已经|已为|直接使用|(?<!不)要(?!不)|先.+再|先.+后)")


# 2026-06-06 11:24:38 新增原因：定义通用否定极性词，覆盖不是、不需要、不能、无法等任意业务场景的反向回答。
NEGATIVE_POLARITY_PATTERN = re.compile(r"(不是|不需要|不用|无需|不要|不能|无法|不支持|不可|禁止|还不能|尚未|未完成)")


# 2026-06-06 13:17:22 新增原因：返回极性模式在文本中的首个位置，让 top1 首个事实方向优先于后文混合风险词。
def _first_polarity_index(pattern: re.Pattern[str], text: str) -> int:
    # 2026-06-06 13:17:22 新增原因：执行正则搜索，兼容任意业务文本。
    match = pattern.search(text)
    # 2026-06-06 13:17:22 新增原因：命中时返回起点，未命中返回 -1 便于比较。
    return match.start() if match else -1


# 2026-06-06 13:17:22 新增原因：按文本最先出现的肯定/否定线索判断主方向，避免全文词袋把方向互相抵消。
def _leading_polarity(text: str) -> str:
    # 2026-06-06 13:17:22 新增原因：读取首个肯定线索位置。
    positive_index = _first_polarity_index(POSITIVE_POLARITY_PATTERN, text)
    # 2026-06-06 13:17:22 新增原因：读取首个否定线索位置。
    negative_index = _first_polarity_index(NEGATIVE_POLARITY_PATTERN, text)
    # 2026-06-06 13:17:22 新增原因：没有任何极性线索时返回空方向。
    if positive_index < 0 and negative_index < 0:
        # 2026-06-06 13:17:22 新增原因：返回空方向，交给其他语义覆盖规则处理。
        return ""
    # 2026-06-06 13:17:22 新增原因：没有否定线索或肯定线索更靠前时，主方向为肯定。
    if negative_index < 0 or (positive_index >= 0 and positive_index <= negative_index):
        # 2026-06-06 13:17:22 新增原因：返回肯定方向。
        return "positive"
    # 2026-06-06 13:17:22 新增原因：否定线索更靠前时，主方向为否定。
    return "negative"


# 2026-06-05 18:10:08 新增原因：定义中文切分连接词，让未知业务句子也能拆出主题词。
CHINESE_SPLIT_PATTERN = re.compile(r"(?:如何|怎么|为什么|是否|是不是|能不能|可不可以|如果|已经|但是|以及|或者|并且|然后|之前|之后|的时候|里面|这里|那里|里|中|按|把|给|让|再|先|后面|后续|后|和|与|或|的|了|在|查看|查询|筛选出|筛选|区分|选择|使用|功能|不同|特定|联系|关联|影响|对不上|不清楚|不应该|应该|需要|想|要|如|吗|呢|请|又|时)")


# 2026-06-06 10:41:26 新增原因：定义连接词片段，专门剔除“账单如果”这类跨语义边界滑窗。
GENERIC_CONNECTOR_FRAGMENTS = (
    # 2026-06-06 10:41:26 新增原因：条件词不能参与业务主题。
    "如果",
    # 2026-06-06 10:41:26 新增原因：状态叙述词不能参与业务主题。
    "已经",
    # 2026-06-06 10:41:26 新增原因：转折词不能参与业务主题。
    "但是",
    # 2026-06-06 10:41:26 新增原因：口语泛指词不能参与业务主题。
    "这个",
    # 2026-06-06 10:41:26 新增原因：口语泛指词不能参与业务主题。
    "那个",
    # 2026-06-06 16:26:53 新增原因：口语执行胶水不能参与业务主题，避免跨动作长片段压住真实字段。
    "也进行",
    # 2026-06-06 16:26:53 新增原因：通用动作词边界不能参与主题，保留后面的业务动作或字段。
    "进行",
    # 2026-06-06 16:26:53 新增原因：口语等价表达不能参与主题，避免“等于让X”压住 X 字段。
    "等于让",
    # 2026-06-06 16:26:53 新增原因：通用执行表达不能参与主题，避免“直接做Y”压住 Y 字段。
    "直接做",
    # 2026-06-08 18:18:06 Added: spoken transcript location words are not stable business terms.
    "\u8fd9\u91cc",
    "\u90a3\u91cc",
    # 2026-06-08 18:18:06 Added: ordinal spoken fragments should not become chunk equivalence terms.
    "\u8fd9\u4e00",
    "\u90a3\u4e00",
    "\u4e00\u90e8\u5206",
    "\u4e0d\u6b62",
    "\u7b49\u4e00\u4e0b",
    "\u6b65\u548c",
    # 2026-06-08 18:18:06 Added: pronoun action glue is transcript noise, not a database fact.
    "\u4ed6\u628a",
    "\u5979\u628a",
    "\u4f60\u628a",
    "\u6211\u628a",
    # 2026-06-08 18:31:09 Added: OCR payment-status boundary fragments are not standalone business terms.
    "\u72b6\u9884",
)


# 2026-06-06 10:41:26 新增原因：定义通用字段后缀，不绑定具体业务场景，只用词形识别任意业务字段。
GENERIC_FIELD_SUFFIXES = (
    # 2026-06-06 10:41:26 新增原因：单据类后缀，覆盖任意业务单据而非某个固定单据。
    "单",
    # 2026-06-06 10:41:26 新增原因：单据类复合后缀。
    "单据",
    # 2026-06-06 10:41:26 新增原因：状态字段后缀。
    "状态",
    # 2026-06-06 10:41:26 新增原因：报表类字段后缀。
    "报告",
    # 2026-06-06 10:41:26 新增原因：记录类字段后缀。
    "记录",
    # 2026-06-06 10:55:04 新增原因：列表类字段后缀，泛化覆盖任意清单/列表查询场景。
    "列表",
    # 2026-06-06 10:41:26 新增原因：批次类字段后缀。
    "批次",
    # 2026-06-06 10:41:26 新增原因：规则类字段后缀。
    "规则",
    # 2026-06-06 10:41:26 新增原因：流程类字段后缀。
    "流程",
    # 2026-06-06 10:41:26 新增原因：步骤类字段后缀。
    "步骤",
    # 2026-06-06 10:41:26 新增原因：权限类字段后缀。
    "权限",
    # 2026-06-06 10:41:26 新增原因：角色类字段后缀。
    "角色",
    # 2026-06-06 10:41:26 新增原因：账号类字段后缀。
    "账号",
    # 2026-06-06 10:41:26 新增原因：数量类字段后缀。
    "数量",
    # 2026-06-06 10:41:26 新增原因：金额类字段后缀。
    "金额",
    # 2026-06-06 10:41:26 新增原因：日期类字段后缀。
    "日期",
    # 2026-06-06 10:41:26 新增原因：字段类后缀。
    "字段",
    # 2026-06-06 11:12:44 新增原因：职责/职能字段后缀，泛化覆盖任意职能主体类业务词。
    "务",
    # 2026-06-06 10:41:26 新增原因：按钮类字段后缀。
    "按钮",
    # 2026-06-06 10:41:26 新增原因：菜单类字段后缀。
    "菜单",
    # 2026-06-06 11:02:18 修改原因：组织/地点字段后缀，泛化覆盖任意组织、地点或部门类业务对象。
    "厂",
    # 2026-06-06 11:02:18 修改原因：样本/样式字段后缀，泛化覆盖任意样品或样式类业务对象。
    "样",
    # 2026-06-06 11:02:18 修改原因：商户类对象后缀，泛化覆盖任意商业主体字段。
    "商",
    # 2026-06-06 11:02:18 修改原因：审核类动作后缀，覆盖任意审核动作文本。
    "审",
    # 2026-06-06 14:54:36 新增原因：款项类字段后缀，泛化覆盖预付款、尾款、货款等金额状态。
    "款",
    # 2026-06-06 14:54:36 新增原因：单价/价格类字段后缀，避免计件工资类 chunk 只抽出数字。
    "价",
    # 2026-06-06 14:54:36 新增原因：费用类字段后缀，覆盖返工费用、运费等未知业务费用。
    "费",
    # 2026-06-06 14:54:36 新增原因：比率类字段后缀，覆盖返工率、合格率等统计字段。
    "率",
    # 2026-06-06 14:54:36 新增原因：用量类字段后缀，覆盖制造/物料消耗问题。
    "用量",
)


# 2026-06-06 14:54:36 新增原因：定义通用业务动作词，不绑定具体场景，只覆盖常见业务动词形态。
GENERIC_ACTION_TERMS = (
    # 2026-06-06 14:54:36 新增原因：审核动作，覆盖正审/反审/复审等场景。
    "审核",
    # 2026-06-06 14:54:36 新增原因：反审动作，覆盖财务和业务单据回退。
    "反审",
    # 2026-06-06 14:54:36 新增原因：冲账动作，覆盖财务状态处理。
    "冲账",
    # 2026-06-06 14:54:36 新增原因：付款动作，覆盖付款单和预付款。
    "付款",
    # 2026-06-06 14:54:36 新增原因：筛选动作，覆盖列表查询类问题。
    "筛选",
    # 2026-06-06 14:54:36 新增原因：授权动作，覆盖权限配置类问题。
    "授权",
    # 2026-06-06 14:54:36 新增原因：刷新动作，覆盖同步和更新类问题。
    "刷新",
    # 2026-06-06 14:54:36 新增原因：选择动作，覆盖订单/物料选择类问题。
    "选择",
    # 2026-06-06 14:54:36 新增原因：退回动作，覆盖状态回退类问题。
    "退回",
    # 2026-06-06 14:54:36 新增原因：返回动作，覆盖状态返回类口语表达。
    "返回",
    # 2026-06-06 14:54:36 新增原因：核对动作，覆盖排查和校验类问题。
    "核对",
    # 2026-06-06 14:54:36 新增原因：计算动作，覆盖工资/费用计算类问题。
    "计算",
    # 2026-06-06 14:54:36 新增原因：转出动作，覆盖数量流转类问题。
    "转出",
    # 2026-06-06 14:54:36 新增原因：分析动作，覆盖费用和异常原因分析。
    "分析",
    # 2026-06-06 14:54:36 新增原因：计时动作，覆盖工序计时类问题。
    "计时",
    # 2026-06-06 14:54:36 新增原因：录入动作，覆盖单据和工序录入。
    "录入",
    # 2026-06-06 14:54:36 新增原因：返工动作，覆盖异常工序场景。
    "返工",
    # 2026-06-06 14:54:36 新增原因：补料动作，覆盖销售订单刷新类问题。
    "补料",
    # 2026-06-06 14:54:36 新增原因：处理动作，覆盖通用业务后续动作。
    "处理",
    # 2026-06-06 14:54:36 新增原因：查看动作，覆盖查询和列表类问题。
    "查看",
)


# 2026-06-06 14:54:36 新增原因：定义业务短语前缀清理规则，把“这张/直接做/然后”等口语包装剥离。
BUSINESS_PREFIX_PATTERN = re.compile(r"^(\u6709\u4e2a|\u4e0d\u80fd\u7ed9|\u4e0d\u80fd|\u65e0\u6cd5|\u4e0d\u53ef\u4ee5|\u5982\u679c|\u5df2\u7ecf|\u4f46\u662f|\u662f\u4e0d\u662f|\u53c8|\u548c|\u4e0e|\u6216|\u6309|\u6211|\u8fd9\u5f20|\u90a3\u5f20|\u8fd9\u4e2a|\u90a3\u4e2a|\u4f60\u7684|\u6211\u7684|\u8be5|\u5176|\u8fd9|\u90a3|\u4e2a|\u4e5f|\u7b49\u4e8e|\u76f4\u63a5|\u5148|\u518d|\u7136\u540e|\u7ee7\u7eed|\u8fdb\u884c|\u505a|\u8ba9|\u628a|\u7ed9|\u8981|\u9700\u8981)+")


# 2026-06-06 10:41:26 新增原因：判断候选词是否跨了连接词边界，避免错误碎片进入主题词。
def _has_connector_fragment(term: str) -> bool:
    # 2026-06-06 10:41:26 新增原因：只要包含连接词片段就视为低质量候选。
    return any(fragment in term for fragment in GENERIC_CONNECTOR_FRAGMENTS)


# 2026-06-06 10:41:26 新增原因：判断候选词是否像通用业务字段，不依赖固定场景词白名单。
def _looks_like_business_field(term: str) -> bool:
    # 2026-06-06 10:41:26 新增原因：字段后缀命中说明它更可能是可读业务对象。
    return any(term.endswith(suffix) for suffix in GENERIC_FIELD_SUFFIXES)


# 2026-06-06 14:54:36 新增原因：清洗直接抽出的业务短语，保留“入仓单/充账状态/付款单”这类可读最小字段。
def _normalize_business_phrase(term: str) -> str:
    # 2026-06-06 14:54:36 新增原因：去除首尾空白，兼容正则捕获结果。
    cleaned = term.strip()
    # 2026-06-06 14:54:36 新增原因：有“的”时优先保留后半字段，避免“预付款的充账状态”压住“充账状态”。
    if "的" in cleaned:
        # 2026-06-06 14:54:36 新增原因：保留最后一个“的”后的业务字段。
        cleaned = cleaned.rsplit("的", 1)[-1]
    # 2026-06-06 14:54:36 新增原因：循环剥离口语前缀，兼容“直接做付款单/这张入仓单”。
    previous = ""
    # 2026-06-06 14:54:36 新增原因：前缀可能连续出现，直到不再变化。
    while cleaned and cleaned != previous:
        # 2026-06-06 14:54:36 新增原因：记录本轮清洗前文本。
        previous = cleaned
        # 2026-06-06 14:54:36 新增原因：删除通用前缀。
        cleaned = BUSINESS_PREFIX_PATTERN.sub("", cleaned)
    # 2026-06-08 18:18:06 Added: OCR/transcript edge fragments shrink to the readable field.
    if cleaned.startswith("\u6b3e\u72b6") and len(cleaned) > 3 and _looks_like_business_field(cleaned[2:]):
        cleaned = cleaned[2:]
    if cleaned.startswith("\u72b6") and len(cleaned) > 2 and _looks_like_business_field(cleaned[1:]):
        cleaned = cleaned[1:]
    # 2026-06-08 18:18:06 Added: long audit phrases keep the nearest actor plus action.
    for action in ("\u5ba1\u6838", "\u53cd\u5ba1"):
        action_index = cleaned.rfind(action)
        if action_index > 2 and action_index + len(action) == len(cleaned):
            cleaned = cleaned[max(0, action_index - 2) :]
            break
    # 2026-06-06 14:54:36 新增原因：返回最终可读短语。
    for action in GENERIC_ACTION_TERMS:
        if action == "付款":
            action_index = cleaned.find(action)
            tail = cleaned[action_index + len(action):].strip() if action_index >= 0 else ""
            if tail.startswith("\u72b6") and len(tail) > 2 and _looks_like_business_field(tail[1:]):
                cleaned = tail[1:]
                break
            continue
        action_index = cleaned.rfind(action)
        if action_index >= 0 and action_index + len(action) < len(cleaned):
            tail = cleaned[action_index + len(action):].strip()
            if len(tail) >= 2 and _looks_like_business_field(tail):
                cleaned = tail
                break
    return cleaned.strip()


# 2026-06-06 14:54:36 新增原因：从原文直接抽取字段和动作，避免通用切分把口语 top1 切成过长噪声。
def _append_direct_business_phrases(target: list[str], text: str) -> None:
    # 2026-06-06 14:54:36 新增原因：按字段后缀生成正则，覆盖任意未知业务对象。
    field_suffix_pattern = "|".join(re.escape(suffix) for suffix in sorted(GENERIC_FIELD_SUFFIXES, key=len, reverse=True))
    # 2026-06-06 14:54:36 新增原因：字段前缀最多 8 字，避免整句被抽成一个候选。
    field_pattern = re.compile(rf"[一-鿿A-Za-z0-9的]{{0,8}}(?:{field_suffix_pattern})")
    # 2026-06-06 14:54:36 新增原因：遍历字段候选。
    for match in field_pattern.finditer(text):
        # 2026-06-06 14:54:36 新增原因：标准化字段候选。
        phrase = _normalize_business_phrase(match.group(0))
        # 2026-06-06 14:54:36 新增原因：保留二字以上字段。
        if len(phrase) >= 2:
            # 2026-06-06 14:54:36 新增原因：追加字段候选。
            target.append(phrase)
    # 2026-06-06 14:54:36 新增原因：按通用动作词生成正则，覆盖任意流程步骤。
    action_pattern = re.compile(rf"[一-鿿A-Za-z0-9]{{0,6}}(?:{'|'.join(re.escape(action) for action in GENERIC_ACTION_TERMS)})")
    # 2026-06-06 14:54:36 新增原因：遍历动作候选。
    for match in action_pattern.finditer(text):
        # 2026-06-06 14:54:36 新增原因：标准化动作候选。
        phrase = _normalize_business_phrase(match.group(0))
        # 2026-06-06 14:54:36 新增原因：保留二字以上动作。
        if len(phrase) >= 2:
            # 2026-06-06 14:54:36 新增原因：追加动作候选。
            target.append(phrase)


# 2026-06-06 10:41:26 新增原因：按泛化质量给候选词打分，替代原始滑窗先到先得。
def _semantic_candidate_score(term: str, value_texts: list[str], first_index: int) -> float:
    # 2026-06-06 10:41:26 新增原因：连接词碎片直接降权，防止“账单如果”等噪声排前。
    if _has_connector_fragment(term):
        # 2026-06-06 10:41:26 新增原因：返回强负分，让调用方自然过滤。
        return -1000.0
    # 2026-06-06 10:41:26 新增原因：停用词和内部图谱标记没有业务区分度。
    if term in GENERIC_STOP_TERMS or term in INTERNAL_GRAPH_MARKERS:
        # 2026-06-06 10:41:26 新增原因：返回强负分，让调用方自然过滤。
        return -1000.0
    # 2026-06-06 10:41:26 新增原因：统计候选词在问题、RAG、图谱等多源文本中的命中次数。
    occurrence_count = sum(text.count(term) for text in value_texts)
    # 2026-06-06 10:41:26 新增原因：基础分用长度和出现次数，让可读短语优先于短碎片。
    score = len(term) * 2 + occurrence_count * 6
    # 2026-06-06 11:02:18 修改原因：通用字段形态加权，泛化优先当前文本里的可读业务字段。
    if _looks_like_business_field(term):
        # 2026-06-06 10:41:26 新增原因：字段类词更适合作为 Prompt Builder 主题。
        score += 16
    # 2026-06-06 10:41:26 新增原因：四字以上短语通常比二字滑窗更有业务辨识度。
    if len(term) >= 4:
        # 2026-06-06 10:41:26 新增原因：提高完整短语优先级。
        score += 8
    # 2026-06-06 14:54:36 新增原因：超长候选更可能是口语整句，降低权重让可读最小字段排前。
    if len(term) > 8:
        # 2026-06-06 14:54:36 新增原因：按超出长度递减，避免“入仓单也进行财务反审”压过“入仓单”。
        score -= (len(term) - 8) * 12
    # 2026-06-06 10:41:26 新增原因：二字词只有在字段形态或重复出现时才保留较高权重。
    if len(term) == 2 and not _looks_like_business_field(term) and occurrence_count <= 1:
        # 2026-06-06 10:41:26 新增原因：降低普通二字噪声。
        score -= 8
    # 2026-06-06 11:02:18 修改原因：二字字段/动作词通常是完整最小语义单元，应排在半截三字词前。
    if len(term) == 2 and _looks_like_business_field(term):
        # 2026-06-06 10:49:37 新增原因：提高完整二字业务词权重，保持抽词泛化且不绑定具体场景。
        score += 12
    # 2026-06-06 10:41:26 新增原因：轻微保留原文先后顺序，分数相同时更贴近用户表达。
    return score - first_index * 0.001


# 2026-06-05 18:10:08 新增原因：统一把任意证据对象转为文本，供动态抽词和覆盖率计算。
def semantic_text(value: Any) -> str:
    # 2026-06-05 18:10:08 新增原因：字符串证据直接使用。
    if isinstance(value, str):
        # 2026-06-05 18:10:08 新增原因：返回字符串原文。
        text = value
    # 2026-06-05 18:10:08 新增原因：结构化证据转 JSON，保留 key 和 value 里的业务语义。
    else:
        # 2026-06-05 18:10:08 新增原因：序列化失败时兜底使用 str，不丢证据。
        text = json.dumps(value, ensure_ascii=False, default=str) if value is not None else ""
    # 2026-06-05 18:10:08 新增原因：移除 qachunk/qaglobal 这类内部节点，避免模型最终答案泄漏内部 ID。
    text = re.sub(r"qa(?:chunk|global)_[A-Za-z0-9_:-]+", " ", text)
    # 2026-06-05 18:10:08 新增原因：移除内部图谱关系名，保留业务语义词而非调试关系。
    text = re.sub("|".join(re.escape(item) for item in INTERNAL_GRAPH_MARKERS), " ", text)
    # 2026-06-05 18:10:08 新增原因：压缩空白，保证后续抽词稳定。
    return re.sub(r"\s+", " ", text).strip()


# 2026-06-06 10:41:26 修改原因：生成候选词时按字段形态补全短语，避免纯滑窗碎片先进入主题。
def _append_chinese_windows(target: list[str], segment: str) -> None:
    # 2026-06-06 10:41:26 修改原因：清理片段，避免空白和连接词残片进入候选。
    clean_segment = segment.strip()
    # 2026-06-06 10:41:26 修改原因：过短片段没有业务区分度，直接跳过。
    if len(clean_segment) < 2:
        # 2026-06-06 10:41:26 修改原因：返回调用方继续处理其他片段。
        return
    # 2026-06-06 10:41:26 修改原因：没有连接词的短片段通常就是完整字段词，先加入候选。
    if len(clean_segment) <= 12 and not _has_connector_fragment(clean_segment):
        # 2026-06-06 10:41:26 修改原因：追加完整片段，后续由打分排序决定是否保留。
        target.append(clean_segment)
    # 2026-06-06 10:41:26 新增原因：枚举通用字段后缀短语，让未知业务词也能形成完整可读字段。
    for start in range(0, len(clean_segment)):
        # 2026-06-06 10:41:26 新增原因：限制候选最大长度，避免整句进入 Prompt Builder。
        max_end = min(len(clean_segment), start + 12)
        # 2026-06-06 10:41:26 新增原因：遍历候选终点，覆盖二到十二字业务短语。
        for end in range(start + 2, max_end + 1):
            # 2026-06-06 10:41:26 新增原因：读取候选短语。
            candidate = clean_segment[start:end]
            # 2026-06-06 10:41:26 新增原因：只把字段形态候选提前加入，避免过量滑窗噪声。
            if _looks_like_business_field(candidate) and not _has_connector_fragment(candidate):
                # 2026-06-06 10:41:26 新增原因：追加字段候选，供后续统一排序去重。
                target.append(candidate)
    # 2026-06-06 10:41:26 修改原因：保留少量 4/3/2 字窗口作为未知字段兜底，但由评分防止噪声排前。
    for size in (4, 3, 2):
        # 2026-06-06 10:41:26 修改原因：片段短于窗口时跳过该窗口。
        if len(clean_segment) < size:
            # 2026-06-06 10:41:26 修改原因：继续尝试更小窗口。
            continue
        # 2026-06-06 10:41:26 修改原因：滑动生成候选词。
        for index in range(0, len(clean_segment) - size + 1):
            # 2026-06-06 10:41:26 修改原因：读取窗口候选。
            candidate = clean_segment[index : index + size]
            # 2026-06-06 10:41:26 修改原因：过滤跨连接词边界的窗口候选。
            if _has_connector_fragment(candidate):
                # 2026-06-06 10:41:26 修改原因：继续检查下一个窗口。
                continue
            # 2026-06-06 10:41:26 修改原因：追加窗口候选，后续由评分决定优先级。
            target.append(candidate)


# 2026-06-05 18:10:08 新增原因：从问题、RAG、图谱、业务工具中泛化抽取主题词，不维护场景词白名单。
def extract_semantic_terms(*values: Any, limit: int = 16) -> list[str]:
    # 2026-06-06 10:41:26 修改原因：分别保留每个证据文本，便于统计多源重复命中并做动态排序。
    value_texts = [semantic_text(value) for value in values if value is not None]
    # 2026-06-06 10:41:26 修改原因：合并所有证据文本，保证当前 chunk 里的词可以参与抽取。
    merged_text = " ".join(value_texts)
    # 2026-06-05 18:10:08 新增原因：初始化候选词列表。
    candidates: list[str] = []
    # 2026-06-06 14:54:36 新增原因：先从原文直接抽字段/动作，避免后续连接词切分吞掉可读业务短语。
    _append_direct_business_phrases(candidates, merged_text)
    # 2026-06-05 18:10:08 新增原因：遍历中英文连续片段，避免标点影响抽取。
    for raw_segment in re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", merged_text):
        # 2026-06-05 18:10:08 新增原因：英文和数字字段直接作为候选。
        if re.fullmatch(r"[A-Za-z0-9_]{2,}", raw_segment):
            # 2026-06-05 18:10:08 新增原因：追加英文或数字字段。
            candidates.append(raw_segment)
            # 2026-06-05 18:10:08 新增原因：继续处理下一个片段。
            continue
        # 2026-06-05 18:10:08 新增原因：中文片段先按通用连接词拆开，避免整句被硬截断。
        for segment in CHINESE_SPLIT_PATTERN.split(raw_segment):
            # 2026-06-05 18:10:08 新增原因：清理拆分后的空白。
            clean_segment = segment.strip()
            # 2026-06-05 18:10:08 新增原因：从中文片段生成动态窗口词。
            _append_chinese_windows(candidates, clean_segment)
    # 2026-06-06 10:41:26 修改原因：记录每个候选的首次位置，用于排序时保留用户表达顺序。
    first_index_by_term: dict[str, int] = {}
    # 2026-06-06 10:41:26 修改原因：遍历候选，先去重再打分。
    for index, term in enumerate(candidates):
        # 2026-06-06 10:41:26 修改原因：清理候选前后空白。
        clean_term = term.strip()
        # 2026-06-06 10:41:26 修改原因：空候选直接跳过。
        if not clean_term:
            # 2026-06-06 10:41:26 修改原因：继续检查下一个候选。
            continue
        # 2026-06-06 10:41:26 修改原因：首次出现才记录，防止重复候选影响顺序。
        # 2026-06-06 16:26:53 新增原因：候选入池前统一剥离通用口语前缀，避免“这张X/直接做Y/也进行Z”压住真正业务字段。
        normalized_term = _normalize_business_phrase(clean_term)
        # 2026-06-06 16:26:53 新增原因：标准化后为空说明只是连接词或口语胶水，跳过以保护 Prompt Builder 主题词质量。
        if not normalized_term:
            # 2026-06-06 16:26:53 新增原因：继续检查下一个候选。
            continue
        # 2026-06-06 10:41:26 修改原因：首次出现才记录，防止重复候选影响顺序。
        first_index_by_term.setdefault(normalized_term, index)
    # 2026-06-06 10:41:26 修改原因：按泛化语义分数排序，而不是按原始滑窗顺序截断。
    ranked_terms = sorted(first_index_by_term, key=lambda term: _semantic_candidate_score(term, value_texts, first_index_by_term[term]), reverse=True)
    # 2026-06-06 10:41:26 修改原因：初始化最终主题词列表。
    terms: list[str] = []
    # 2026-06-06 10:41:26 修改原因：遍历已排序候选，做最终过滤和子串压缩。
    for term in ranked_terms:
        # 2026-06-06 10:41:26 修改原因：低分候选多为连接词碎片或停用词。
        if _semantic_candidate_score(term, value_texts, first_index_by_term[term]) <= 0:
            # 2026-06-06 10:41:26 修改原因：继续检查下一个候选。
            continue
        # 2026-06-06 10:41:26 修改原因：如果更长可读字段已覆盖当前短子串，就跳过普通短子串。
        if any(term in existing and len(existing) > len(term) and not _looks_like_business_field(term) for existing in terms):
            # 2026-06-06 10:41:26 修改原因：继续检查下一个候选。
            continue
        # 2026-06-06 10:41:26 修改原因：追加泛化主题词。
        terms.append(term)
        # 2026-06-06 10:41:26 修改原因：达到上限就停止，控制 Prompt Builder 长度。
        if len(terms) >= limit:
            # 2026-06-06 10:41:26 修改原因：跳出循环。
            break
    # 2026-06-06 10:41:26 修改原因：返回按可读业务字段排序后的泛化主题词。
    return terms


# 2026-06-05 18:10:08 新增原因：识别复杂业务问题，基于问题形态和动态主题词，不再靠固定业务词表。
def question_requires_semantic_agent_chain(question: str) -> bool:
    # 2026-06-05 18:10:08 新增原因：清理问题文本。
    text = semantic_text(question)
    # 2026-06-05 18:10:08 新增原因：空问题不触发完整链。
    if not text:
        # 2026-06-05 18:10:08 新增原因：返回 False。
        return False
    # 2026-06-05 18:10:08 新增原因：提取动态主题词。
    terms = extract_semantic_terms(text, limit=8)
    # 2026-06-08 17:52:14 Added: pure side-effect commands should not trigger the full evidence chain.
    explicit_side_effect = bool(re.search(r"(\u521b\u5efa|\u65b0\u5efa|\u5f00|\u8bbe\u7f6e|\u6dfb\u52a0|\u5efa\u7acb).{0,8}(\u5de5\u5355|\u63d0\u9192|\u8ddf\u8fdb)|\u8f6c\u4eba\u5de5|\u4eba\u5de5\u63a5\u7ba1|\u4eba\u5de5\u5904\u7406", text))
    # 2026-06-08 17:52:14 Added: only reasoning/troubleshooting shapes need RAG/graph/memory on top of an action request.
    has_reasoning_shape = bool(re.search(r"\u5982\u4f55|\u600e\u4e48|\u4e3a\u4ec0\u4e48|\u662f\u5426|\u662f\u4e0d\u662f|\u5bf9\u4e0d\u5bf9|\u8981\u4e0d\u8981|\u5e94\u8be5|\u9700\u8981|\u80fd\u4e0d\u80fd|\u53ef\u4e0d\u53ef\u4ee5|\u5173\u7cfb|\u539f\u56e0|\u6b65\u9aa4|\u6d41\u7a0b|\u72b6\u6001|\u89c4\u5219|\u6743\u9650|\u7b5b\u9009|\u5bfc\u51fa|\u67e5\u8be2|\u67e5\u770b|\u5224\u65ad|\u89e3\u91ca|\u9a8c\u8bc1|\u6838\u5bf9|\u6392\u67e5", text))
    if explicit_side_effect and not has_reasoning_shape:
        return False
    # 2026-06-05 18:10:08 修改原因：识别需要判断、原因、步骤、筛选、状态、关系等证据支撑的问题形态，覆盖任意业务对象的是非问和操作问。
    has_business_shape = has_reasoning_shape
    # 2026-06-05 18:10:08 新增原因：长问题且有两个以上主题词时，也按复杂业务问题处理。
    has_semantic_density = len(text) >= 12 and len(terms) >= 2
    # 2026-06-05 18:10:08 新增原因：返回泛化完整链触发结果。
    return has_business_shape and has_semantic_density


# 2026-06-05 18:10:08 新增原因：收集 evidence 里的可读文本，供 verifier 做主题覆盖，而不是只看工具是否成功。
def collect_evidence_texts(evidence: list[dict[str, Any]]) -> list[str]:
    # 2026-06-05 18:10:08 新增原因：初始化证据文本列表。
    texts: list[str] = []
    # 2026-06-05 18:10:08 新增原因：遍历工具证据。
    for evidence_item in evidence or []:
        # 2026-06-05 18:10:08 新增原因：读取工具结果。
        result = evidence_item.get("result", {}) if isinstance(evidence_item, dict) else {}
        # 2026-06-05 18:10:08 新增原因：非字典结果按普通文本保留。
        if not isinstance(result, dict):
            # 2026-06-05 18:10:08 新增原因：追加非字典工具结果。
            texts.append(semantic_text(result))
            # 2026-06-05 18:10:08 新增原因：继续下一个证据项。
            continue
        # 2026-06-05 18:10:08 新增原因：RAG top1 是最强答案证据，必须参与主题覆盖。
        texts.append(semantic_text(result.get("best_answer", "")))
        # 2026-06-05 18:10:08 新增原因：业务工具动态主题词必须参与主题覆盖。
        texts.append(semantic_text(result.get("focus_terms", [])))
        # 2026-06-05 18:10:08 新增原因：业务工具上下文摘要必须参与主题覆盖。
        texts.append(semantic_text(result.get("business_context", [])))
        # 2026-06-05 18:10:08 新增原因：图谱三元组也作为语义证据参与覆盖。
        texts.append(semantic_text(result.get("triples", [])))
        # 2026-06-05 18:10:08 新增原因：图谱路径也作为语义证据参与覆盖。
        texts.append(semantic_text(result.get("paths", [])))
    # 2026-06-05 18:10:08 新增原因：返回非空证据文本。
    return [text for text in texts if text]


# 2026-06-05 18:10:08 新增原因：计算答案是否覆盖当前问题主题，阻断错业务场景答案 0.8 通过。
def semantic_answer_coverage(question: str, answer: str, evidence_texts: list[str] | None = None) -> dict[str, Any]:
    # 2026-06-05 18:10:08 新增原因：清理答案文本。
    answer_text = semantic_text(answer)
    # 2026-06-05 18:10:08 新增原因：空答案一定不满足。
    if not answer_text:
        # 2026-06-05 18:10:08 新增原因：返回空答案覆盖结果。
        return {"satisfied": False, "required_terms": [], "matched_terms": [], "missing_terms": [], "reason": "empty_answer"}
    # 2026-06-05 18:10:08 修改原因：从问题优先抽取更多动态主题候选，避免中文滑窗前几项过碎误杀正确 RAG。
    required_terms = extract_semantic_terms(question, limit=30)
    # 2026-06-05 18:10:08 新增原因：问题词不足时才从证据补充，避免证据里的无关词反向污染用户意图。
    if len(required_terms) < 2 and evidence_texts:
        # 2026-06-05 18:10:08 新增原因：追加证据主题词。
        required_terms.extend(term for term in extract_semantic_terms(*evidence_texts, limit=12) if term not in required_terms)
    # 2026-06-05 18:10:08 新增原因：过滤泛称停用词。
    required_terms = [term for term in required_terms if term not in GENERIC_STOP_TERMS]
    # 2026-06-05 18:10:08 新增原因：没有主题词时只要求答案非空。
    if not required_terms:
        # 2026-06-05 18:10:08 新增原因：返回满足。
        return {"satisfied": True, "required_terms": [], "matched_terms": [], "missing_terms": [], "reason": ""}
    # 2026-06-05 18:10:08 新增原因：统计答案命中的主题词。
    matched_terms = [term for term in required_terms if term in answer_text]
    # 2026-06-05 18:10:08 新增原因：至少覆盖两个主题词；主题词很少时至少覆盖一个。
    required_hit_count = 1 if len(required_terms) <= 3 else 2
    # 2026-06-05 18:10:08 新增原因：判断覆盖是否满足。
    satisfied = len(matched_terms) >= required_hit_count
    # 2026-06-05 18:10:08 新增原因：返回覆盖详情，供 trace 和数据飞轮定位。
    return {
        "satisfied": satisfied,
        "required_terms": required_terms,
        "matched_terms": matched_terms,
        "missing_terms": [term for term in required_terms if term not in matched_terms],
        "reason": "" if satisfied else "answer_topic_mismatch",
    }


# 2026-06-06 11:24:38 新增原因：检测任意业务答案是否把 RAG 证据的肯定/否定方向反写，补足语义覆盖无法发现的极性问题。

# 2026-06-08 15:44:31 新增原因：建立最终答案与 RAG top1/chunk 证据的全局等价校验。
def _first_embedded_business_field(term: str) -> str:
    # 2026-06-08 18:26:51 Added: shrink noisy composites to the first readable business field.
    suffixes = [suffix for suffix in GENERIC_FIELD_SUFFIXES if suffix not in {"\u5ba1"}]
    for suffix in sorted(suffixes, key=len, reverse=True):
        pattern = re.compile(rf"[\u4e00-\u9fffA-Za-z0-9]{{1,6}}{re.escape(suffix)}")
        for match in pattern.finditer(term):
            candidate = _normalize_business_phrase(match.group(0))
            if candidate and candidate != term and len(candidate) >= 2 and not _has_connector_fragment(candidate):
                return candidate
    return term


def _is_grounded_equivalence_term(term: str, question_text: str) -> bool:
    # 2026-06-08 19:13:09 Added: chunk equivalence terms must be business-shaped, not arbitrary transcript windows.
    if term in question_text:
        return True
    if term in GENERIC_ACTION_TERMS:
        return True
    if any(action in term for action in GENERIC_ACTION_TERMS):
        return True
    return _looks_like_business_field(term)


def semantic_answer_grounded_equivalence(question: str, answer: str, evidence_texts: list[str] | None = None) -> dict[str, Any]:
    # 2026-06-08 15:44:31 新增原因：统一清理答案文本，空答直接失败。
    answer_text = semantic_text(answer)
    # 2026-06-08 15:44:31 新增原因：按证据顺序保留 RAG top1 锚点。
    evidence_items = [semantic_text(item) for item in (evidence_texts or []) if semantic_text(item)]
    # 2026-06-08 15:44:31 新增原因：第一条有效证据是最强答案锚点。
    anchor_text = evidence_items[0] if evidence_items else ""
    # 2026-06-08 15:44:31 新增原因：模型空答不进入 renderer。
    if not answer_text:
        # 2026-06-08 15:44:31 新增原因：返回空答原因供回流。
        return {"equivalent": False, "required_terms": [], "matched_terms": [], "missing_terms": [], "reason": "empty_answer"}
    # 2026-06-08 15:44:31 新增原因：缺少证据锚点不能声称切中 chunk。
    if not anchor_text:
        # 2026-06-08 15:44:31 新增原因：返回缺证据原因。
        return {"equivalent": False, "required_terms": [], "matched_terms": [], "missing_terms": [], "reason": "missing_anchor_evidence"}
    # 2026-06-08 15:44:31 新增原因：从问题和证据动态抽取关键业务词。
    direct_terms: list[str] = []
    _append_direct_business_phrases(direct_terms, anchor_text)
    raw_terms = direct_terms + extract_semantic_terms(anchor_text, limit=30)
    required_terms: list[str] = []
    question_text = semantic_text(question)
    noise_terms = {'业务', '记录', '动作', '客户', '服务', '人员', '条业务', '业务记录'}
    spoken_noise_fragments = ("\u4ed6", "\u5979", "\u6211", "\u4f60", "\u96be\u602a", "\u90e8\u5206", "\u4e00\u5355")
    question_fragments = ('是不是', '能不能', '为什么', '如何', '怎么', '什么', '是否')
    polarity_prefix_pattern = re.compile(r"^(可以|应该|应当|应先|需先|需要|必须|建议|允许|能够|能|已经|已为|先|再|继续|确认)+")
    for raw_term in raw_terms:
        term = polarity_prefix_pattern.sub("", raw_term)
        term = _normalize_business_phrase(term)
        term = _first_embedded_business_field(term)
        if not term or term in required_terms:
            continue
        if term.endswith("\u53cd") and not term.endswith("\u53cd\u5ba1"):
            continue
        if term in GENERIC_STOP_TERMS or term in noise_terms or any(noise in term for noise in noise_terms):
            continue
        if any(fragment in term for fragment in spoken_noise_fragments):
            continue
        if term.isdigit() and term not in question_text:
            continue
        if not _is_grounded_equivalence_term(term, question_text):
            continue
        if _has_connector_fragment(term):
            continue
        if any(marker in term for marker in INTERNAL_GRAPH_MARKERS):
            continue
        if any(fragment in term for fragment in question_fragments):
            continue
        if len(term) < 2 or len(term) > 8:
            continue
        if any(term in kept or kept in term for kept in required_terms):
            continue
        required_terms.append(term)
        if len(required_terms) >= 12:
            break
    if not required_terms:
        required_terms = [term for term in extract_semantic_terms(anchor_text, limit=12) if 2 <= len(term) <= 8]
    matched_terms = [term for term in required_terms if term in answer_text]
    if len(required_terms) <= 2:
        required_hit_count = 1
    elif len(required_terms) <= 4:
        required_hit_count = 2
    elif len(required_terms) <= 6:
        required_hit_count = 3
    else:
        required_hit_count = max(3, min(4, (len(required_terms) + 2) // 3))
    # 2026-06-08 15:44:31 新增原因：检查答案是否反写证据极性。
    polarity_check = semantic_answer_polarity_conflict(answer_text, evidence_items)
    # 2026-06-08 15:44:31 新增原因：检查模型是否在证据充足时逃逸。
    evasion_check = semantic_answer_evasion(answer_text, evidence_items)
    # 2026-06-08 15:44:31 新增原因：检查最终答案是否泄露内部标记。
    internal_leak_check = semantic_answer_internal_token_leak(answer_text)
    # 2026-06-08 20:01:18 Reason: troubleshooting questions are not yes/no answers; do not reintroduce yes/no polarity in the lead.
    procedure_question = bool(re.search("\u6392\u67e5|\u6b65\u9aa4|\u600e\u4e48|\u5982\u4f55|\u786e\u8ba4|\u68c0\u67e5", question_text)) and not bool(re.search("\u662f\u5426|\u662f\u4e0d\u662f|\u5bf9\u4e0d\u5bf9|\u80fd\u4e0d\u80fd|\u8981\u4e0d\u8981|\u53ef\u4e0d\u53ef\u4ee5", question_text))
    # 2026-06-08 20:01:18 Reason: strict E2E rejects negative-evidence procedure answers that lead with positive yes/should/need markers.
    procedure_positive_lead = bool(re.search(r"(^|[\s\u3002\uff0c\uff1b\uff1a\u3001])(?:\*\*)?\u662f(?:\*\*)?(?=$|[\s\u3002\uff0c\uff1b\uff1a\u3001])|\u53ef\u4ee5|\u5e94\u8be5|\u9700\u8981", answer_text[:100]))
    # 2026-06-08 20:01:18 Reason: force the correction loop to rewrite procedural answers instead of accepting polarity-looking prose.
    procedural_polarity_conflict = bool(procedure_question and polarity_check.get("evidence_polarity") == "negative" and procedure_positive_lead)
    # 2026-06-08 20:01:18 Reason: detect hallucinated business modules not anchored in the user question or top1 chunk.
    anchor_question_text = f"{anchor_text} {question_text}"
    # 2026-06-08 20:27:53 Reason: compare drift terms against normalized business terms from both the question and top1 anchor.
    anchor_terms = set(required_terms)
    for raw_anchor_term in extract_semantic_terms(anchor_question_text, limit=60):
        anchor_term = _first_embedded_business_field(_normalize_business_phrase(raw_anchor_term))
        if anchor_term and 2 <= len(anchor_term) <= 10:
            anchor_terms.add(anchor_term)
    # 2026-06-08 20:01:18 Reason: collect business-shaped answer terms that cannot be justified by the current question or top1 evidence.
    unanchored_terms: list[str] = []
    # 2026-06-08 20:01:18 Reason: use the same generalized extractor as Prompt Builder so this is not tied to one permission case.
    for raw_answer_term in extract_semantic_terms(answer_text, limit=36):
        term = _normalize_business_phrase(raw_answer_term)
        term = _first_embedded_business_field(term)
        if not term or term in unanchored_terms:
            continue
        if term in required_terms or any(term in kept or kept in term for kept in required_terms):
            continue
        if term in anchor_question_text:
            continue
        if any(anchor_term and (anchor_term in term or term in anchor_term) for anchor_term in anchor_terms):
            continue
        if term in GENERIC_STOP_TERMS or term in noise_terms or any(noise in term for noise in noise_terms):
            continue
        if any(fragment in term for fragment in spoken_noise_fragments):
            continue
        if _has_connector_fragment(term) or any(fragment in term for fragment in question_fragments):
            continue
        if len(term) < 2 or len(term) > 10:
            continue
        if not _is_grounded_equivalence_term(term, question_text):
            continue
        unanchored_terms.append(term)
    # 2026-06-08 20:01:18 Reason: a few synonyms are tolerable; many extra modules mean the model drifted beyond chunk evidence.
    drift_conflict = len(unanchored_terms) >= 5 and len(unanchored_terms) > max(2, len(matched_terms))
    # 2026-06-08 15:44:31 新增原因：四类门禁同时通过才算等价。
    # 2026-06-08 20:01:18 Reason: all gates must pass before renderer can trust a model answer.
    equivalent = len(matched_terms) >= required_hit_count and not polarity_check.get("conflict") and not evasion_check.get("evasive") and not internal_leak_check.get("leaked") and not procedural_polarity_conflict and not drift_conflict
    # 2026-06-08 20:05:34 Reason: expose the first actionable failure reason for the correction loop.
    if equivalent:
        reason = ""
    elif polarity_check.get("reason"):
        reason = str(polarity_check.get("reason"))
    elif evasion_check.get("reason"):
        reason = str(evasion_check.get("reason"))
    elif internal_leak_check.get("reason"):
        reason = str(internal_leak_check.get("reason"))
    elif procedural_polarity_conflict:
        reason = "procedural_answer_reintroduces_yes_no_polarity"
    elif drift_conflict:
        reason = "answer_unanchored_business_drift"
    else:
        reason = "answer_not_equivalent_to_top1"
    # 2026-06-08 20:01:18 Reason: return structured quality details so downstream verifier and tests can audit the decision.
    return {"equivalent": equivalent, "required_terms": required_terms, "matched_terms": matched_terms, "missing_terms": [term for term in required_terms if term not in matched_terms], "required_hit_count": required_hit_count, "reason": reason, "polarity_check": polarity_check, "procedural_polarity_check": {"conflict": procedural_polarity_conflict, "reason": "procedural_answer_reintroduces_yes_no_polarity" if procedural_polarity_conflict else ""}, "drift_check": {"conflict": drift_conflict, "unanchored_terms": unanchored_terms, "reason": "answer_unanchored_business_drift" if drift_conflict else ""}, "evasion_check": evasion_check, "internal_leak_check": internal_leak_check}


def semantic_answer_polarity_conflict(answer: str, evidence_texts: list[str] | None = None) -> dict[str, Any]:
    # 2026-06-06 11:24:38 新增原因：标准化答案文本，避免标点和结构化 JSON 影响正则判断。
    answer_text = semantic_text(answer)
    # 2026-06-06 13:17:22 修改原因：逐条标准化证据，保留第一条 top1 证据的方向优先级。
    evidence_items = [semantic_text(item) for item in (evidence_texts or []) if semantic_text(item)]
    # 2026-06-06 11:24:38 新增原因：标准化证据文本，供旧的全量极性判断继续兜底。
    evidence_text = semantic_text("\n".join(evidence_items))
    # 2026-06-06 11:24:38 新增原因：空答案或空证据不做极性判断，交给非空和证据链门槛处理。
    if not answer_text or not evidence_text:
        # 2026-06-06 11:24:38 新增原因：返回无冲突状态。
        return {"conflict": False, "evidence_polarity": "", "answer_polarity": "", "reason": ""}
    # 2026-06-06 13:17:22 新增原因：优先读取第一条证据，调用方会把 RAG top1 放在最前。
    primary_evidence_text = evidence_items[0] if evidence_items else evidence_text
    # 2026-06-06 13:17:22 新增原因：用第一条证据的首个极性词判断事实主方向。
    primary_evidence_polarity = _leading_polarity(primary_evidence_text)
    # 2026-06-06 11:24:38 新增原因：证据同时含肯定/否定时，只在答案第一句明显反向时判冲突，避免复杂说明误伤。
    answer_lead = answer_text[:80]
    # 2026-06-06 13:17:22 新增原因：用答案开头的首个极性词判断用户可见结论方向。
    answer_lead_polarity = _leading_polarity(answer_lead)
    # 2026-06-08 20:16:47 Reason: procedure negative evidence can start with a sequence label; keep the first real condition polarity.
    if primary_evidence_polarity == "negative" and answer_lead.startswith(("\u6392\u67e5\u987a\u5e8f", "\u5904\u7406\u987a\u5e8f")) and NEGATIVE_POLARITY_PATTERN.search(answer_lead):
        answer_lead_polarity = "negative"
    # 2026-06-06 11:24:38 新增原因：判断证据是否表达肯定方向。
    evidence_positive = bool(POSITIVE_POLARITY_PATTERN.search(evidence_text))
    # 2026-06-06 11:24:38 新增原因：判断证据是否表达否定方向。
    evidence_negative = bool(NEGATIVE_POLARITY_PATTERN.search(evidence_text))
    # 2026-06-06 11:24:38 新增原因：判断答案是否表达肯定方向。
    answer_positive = bool(POSITIVE_POLARITY_PATTERN.search(answer_text))
    # 2026-06-06 11:24:38 新增原因：判断答案是否表达否定方向。
    answer_negative = bool(NEGATIVE_POLARITY_PATTERN.search(answer_text))
    # 2026-06-06 13:17:22 新增原因：如果 top1 首个方向和答案开头方向相反，直接判冲突，不让后文混合词抵消。
    primary_conflict = (primary_evidence_polarity == "positive" and answer_lead_polarity == "negative") or (primary_evidence_polarity == "negative" and answer_lead_polarity == "positive")
    # 2026-06-06 13:41:09 修改原因：单向肯定证据只用答案首个结论方向判冲突，避免后续原因说明里的“无法/不能”误杀正确答案。
    positive_conflict = evidence_positive and not evidence_negative and answer_lead_polarity == "negative"
    # 2026-06-06 13:41:09 修改原因：单向否定证据只用答案首个结论方向判冲突，避免后续解释里的“可以/需要”误杀正确否定答案。
    negative_conflict = evidence_negative and not evidence_positive and answer_lead_polarity == "positive"
    # 2026-06-06 13:41:09 修改原因：混合证据只按第一条 top1 主方向判冲突，避免风险说明里的“不能/无法”误杀正确肯定答案。
    mixed_positive_conflict = primary_evidence_polarity == "positive" and answer_lead_polarity == "negative" and not answer_lead.startswith("证据不足")
    # 2026-06-06 13:41:09 修改原因：混合证据只在 top1 主方向为否定时拦截答案开头强肯定，不再用全量证据词袋误判。
    mixed_negative_conflict = primary_evidence_polarity == "negative" and answer_lead_polarity == "positive" and not answer_lead.startswith("证据不足")
    # 2026-06-06 13:41:09 修改原因：合并冲突判断，所有分支都以首个结论方向为准，不再用全文词袋抵消或误伤。
    conflict = primary_conflict or positive_conflict or negative_conflict or mixed_positive_conflict or mixed_negative_conflict
    # 2026-06-06 11:24:38 新增原因：返回可观测详情，便于 trace 和数据飞轮定位极性反写。
    return {
        "conflict": conflict,
        "evidence_polarity": primary_evidence_polarity or ("positive" if evidence_positive and not evidence_negative else "negative" if evidence_negative and not evidence_positive else "mixed" if evidence_positive or evidence_negative else ""),
        "answer_polarity": answer_lead_polarity or ("positive" if answer_positive and not answer_negative else "negative" if answer_negative and not answer_positive else "mixed" if answer_positive or answer_negative else ""),
        "reason": "answer_polarity_conflict" if conflict else "",
    }


# 2026-06-06 14:54:36 新增原因：定义最终答案内部链路词模式，防止用户看到 RAG/Neo4j/qachunk 等调试实现。
FINAL_ANSWER_INTERNAL_TOKEN_PATTERN = re.compile(r"(qachunk|qaglobal|MENTIONED_IN_CHUNK|CHUNK_IN_GLOBAL_CLUSTER|FUSED_INTO|Prompt Builder|RAG|Neo4j|Qdrant|LlamaIndex|上一版|错误答案|纠正说明|证据锚点|重试)", re.IGNORECASE)


# 2026-06-06 14:54:36 新增原因：判断最终答案是否泄露内部链路词，驱动模型重试而不是把内部实现展示给用户。
def semantic_answer_internal_token_leak(answer: str) -> dict[str, Any]:
    # 2026-06-06 14:54:36 新增原因：标准化答案文本，兼容不同模型输出格式。
    answer_text = semantic_text(answer)
    # 2026-06-06 14:54:36 新增原因：空答案不在泄露检测里处理，交给空答分支。
    if not answer_text:
        # 2026-06-06 14:54:36 新增原因：返回非泄露状态。
        return {"leaked": False, "tokens": [], "reason": ""}
    # 2026-06-06 14:54:36 新增原因：查找所有内部链路词。
    tokens = sorted({match.group(0) for match in FINAL_ANSWER_INTERNAL_TOKEN_PATTERN.finditer(answer_text)})
    # 2026-06-06 14:54:36 新增原因：返回结构化结果，供最终回答节点和 verifier 共用。
    return {"leaked": bool(tokens), "tokens": tokens, "reason": "answer_internal_token_leak" if tokens else ""}


# 2026-06-06 14:02:18 新增原因：定义通用逃逸话术模式，避免模型拿到充分证据后仍以证据不足/人工确认绕开回答。
EVASIVE_FINAL_ANSWER_PATTERN = re.compile(
    # 2026-06-06 14:02:18 新增原因：覆盖证据不足、无法判断、不能给结论、需要人工确认等跨业务通用表达。
    r"(证据不足|信息不足|资料不足|缺少.{0,8}证据|无法.{0,6}(确定|判断|确认)|不能.{0,8}(给出|直接给出|确定).{0,8}(结论|答案)|需要.{0,8}(人工|客服|业务人员).{0,8}(确认|介入|处理)|建议.{0,8}(人工|客服|业务人员).{0,8}(确认|介入|处理))"
)


# 2026-06-06 14:02:18 新增原因：判断最终回答是否在证据已存在时逃逸，驱动模型重试而不是硬编码兜底。
def semantic_answer_evasion(answer: str, evidence_texts: list[str] | None = None) -> dict[str, Any]:
    # 2026-06-06 14:02:18 新增原因：标准化模型答案，避免标点和空白影响逃逸识别。
    answer_text = semantic_text(answer)
    # 2026-06-06 14:02:18 新增原因：标准化证据文本列表，保持跨 RAG、图谱、业务工具的通用判断。
    evidence_items = [semantic_text(item) for item in (evidence_texts or []) if semantic_text(item)]
    # 2026-06-06 14:02:18 新增原因：空回答不在这里处理，交给模型空答重试分支。
    if not answer_text:
        # 2026-06-06 14:02:18 新增原因：返回非逃逸，避免和空答路径重复计数。
        return {"evasive": False, "has_evidence": bool(evidence_items), "reason": ""}
    # 2026-06-06 14:02:18 新增原因：没有证据时允许模型说需要人工确认，不能误判为逃逸。
    if not evidence_items:
        # 2026-06-06 14:02:18 新增原因：返回非逃逸，证据链不足应由 verifier 或转人工处理。
        return {"evasive": False, "has_evidence": False, "reason": ""}
    # 2026-06-06 14:02:18 新增原因：抽取可消费证据长度，避免只有内部结构空壳时误以为证据充分。
    evidence_char_count = sum(len(item) for item in evidence_items)
    # 2026-06-06 14:02:18 新增原因：证据过短时不强制重试，防止无意义短词触发模型来回空转。
    if evidence_char_count < 12:
        # 2026-06-06 14:02:18 新增原因：返回非逃逸，把短证据交给 verifier 判定置信度。
        return {"evasive": False, "has_evidence": True, "reason": ""}
    # 2026-06-06 14:02:18 新增原因：检测回答是否含通用逃逸话术。
    evasive = bool(EVASIVE_FINAL_ANSWER_PATTERN.search(answer_text))
    # 2026-06-06 14:02:18 新增原因：返回结构化结果，供 trace、测试和数据飞轮复查。
    return {"evasive": evasive, "has_evidence": True, "reason": "answer_evasive_with_evidence" if evasive else ""}
