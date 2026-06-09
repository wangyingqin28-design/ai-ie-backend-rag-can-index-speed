// 2026-06-06 10:59:53 新增原因：独立严格验收脚本，避免 PowerShell 管道把中文测试问题转成问号。
const API_URL = "http://127.0.0.1:18181/api/agent/business-brain/chat";

// 2026-06-06 10:59:53 新增原因：定义必须经过并可在 mark/trace 复查的四类证据工具。
const REQUIRED_TOOLS = ["sql_rag_retrieve", "sql_rag_graph_expand", "sql_rag_memory_read", "sql_rag_business_action"];

// 2026-06-06 10:59:53 新增原因：定义 Prompt Builder 必须包含的证据分区，保证不是空 prompt 或只走形式链路。
const REQUIRED_PROMPT_SECTIONS = ["[RAG / Qdrant / LlamaIndex]", "[Neo4j 多跳三元组图谱]", "[三层记忆]", "[业务动作]", "[回答约束]"];

// 2026-06-06 10:59:53 新增原因：定义最终模型消费阶段必须看到的通用回答约束，防止空答和错误兜底冒充模型。
const REQUIRED_PROMPT_CONSTRAINTS = [
  "必须以 RAG top1 标准答案证据的事实方向为准",
  "是/否问题第一句必须先回答“是”或“不是”",
  "模型空答时不得把兜底证据草稿标记成模型回答",
];

// 2026-06-06 10:59:53 新增原因：定义最终答案禁止泄露的内部图谱调试标记，避免用户看到 qachunk/raw triple。
const INTERNAL_TOKENS = ["qachunk", "qaglobal", "MENTIONED_IN_CHUNK", "CHUNK_IN_GLOBAL_CLUSTER", "FUSED_INTO", "Prompt Builder", "RAG", "Neo4j", "Qdrant", "LlamaIndex", "上一版", "错误答案", "纠正说明", "证据锚点", "重试"];

// 2026-06-06 10:59:53 新增原因：定义通用中文停用片段，语义贴合检查只看业务词，不被虚词刷分。
const STOP_TERMS = new Set(["问题", "客户", "这个", "那个", "如果", "但是", "因为", "所以", "需要", "可以", "进行", "应该", "当前", "相关", "之后", "之前", "时候", "以及", "不同", "对应", "直接", "确认", "建议", "处理"]);

// 2026-06-06 10:59:53 新增原因：用十条上下文有关联但业务主题不同的问题做泛化验收，不只覆盖一个截图场景。
const CASES = [
  {
    name: "入账单预付款状态退回关系",
    question: "入账单如果已经入仓了，但是预付款状态又对不上，我是不是要先让相关岗位反审单据，再把状态退回来？这一步和后面重新冲账、继续付款之间到底是什么关系？",
  },
  {
    name: "延续预付款状态退回后的重新冲账关系",
    question: "接着上一步，如果状态退回来以后还要重新冲账，应该先确认哪些单据关系？",
  },
  {
    name: "订单列表分厂国内越南产前样筛选",
    question: "客户在订单列表里想按分厂、国内、越南和产前样筛选，应该怎么判断筛选条件和历史订单信息的关系？",
  },
  {
    name: "权限按钮不可见排查关系",
    question: "权限配置里用户看不到某个按钮时，账号、角色、菜单权限和审核节点之间应该怎么排查？",
  },
  {
    name: "权限授权后菜单仍不可见",
    question: "延续刚才权限问题，如果基础资料已经授权了，菜单还是看不到，下一步应该查角色、账号还是审核节点？为什么？",
  },
  {
    name: "补料单和销售订单刷新关系",
    question: "补料单来源和销售订单刷新之间是什么关系？客户说补料后看不到变化，我应该怎么解释和验证？",
  },
  {
    name: "制造数量与转出数量关系",
    question: "制造单里原数量、转出数量和用量之间到底怎么影响？如果转出 3500，为什么还要看 8700 的依据？",
  },
  {
    name: "计件工资差额计算",
    question: "计件工资里数量和金额差 200 时，为什么要用 36 除以 200？这个差额和一包 81 的关系怎么说清楚？",
  },
  {
    name: "物料规格与加工商订单选择",
    question: "如果物料规格或加工商选择不对，订单为什么会选不出来？我应该先清掉加工商还是先选订单？",
  },
  {
    name: "返工率费用计时多工序",
    question: "返工率、返工费用、计时和多道工序之间怎么核对？客户问返工费用为什么不对时应该按什么顺序解释？",
  },
];

// 2026-06-06 10:59:53 新增原因：把文本切成通用业务候选词，避免为某个 chunk 写死关键词。
function semanticTerms(text) {
  // 2026-06-06 10:59:53 新增原因：空文本没有业务词。
  if (!text) return [];
  // 2026-06-06 10:59:53 新增原因：先按常见标点和连接词切开，得到可读业务短语。
  const fragments = String(text).split(/[，。！？；：、\s（）()“”"'\[\]【】]+|如果|但是|因为|所以|然后|之前|之后|后续|后面|时候|里面|这里|那里|这个|那个|让|把|给|再|先|后|和|与|及|或者|以及|应该|需要|可以|不能|无法|建议|说明|确认|查看|选择|使用|进行|直接|状态/g);
  // 2026-06-06 10:59:53 新增原因：初始化候选词集合，后续自动去重。
  const terms = [];
  // 2026-06-06 10:59:53 新增原因：遍历所有短语，保留业务对象和动作字段。
  for (const raw of fragments) {
    // 2026-06-06 10:59:53 新增原因：清理非中英文数字字符，避免标点影响匹配。
    const cleaned = raw.replace(/[^\u4e00-\u9fffA-Za-z0-9]/g, "");
    // 2026-06-06 10:59:53 新增原因：过短或停用词不参与语义贴合判断。
    if (cleaned.length < 2 || STOP_TERMS.has(cleaned)) continue;
    // 2026-06-06 11:24:38 修改原因：长短语不再整体入池，避免口语化 top1 生成无法匹配的整句噪声。
    if (cleaned.length <= 8) terms.push(cleaned);
    // 2026-06-06 11:24:38 新增原因：按通用字段后缀抽业务对象，兼容任意单据、状态、费用、权限等新 chunk。
    const fieldMatches = cleaned.match(/[\u4e00-\u9fffA-Za-z0-9]{0,8}(?:单据|订单|单|状态|报告|记录|批次|规则|流程|步骤|权限|角色|账号|数量|金额|日期|字段|按钮|菜单|费用|工资|规格|工序|供应商|加工商|样|率)/g) || [];
    // 2026-06-06 11:24:38 新增原因：把字段后缀命中的业务词加入候选，不依赖截图中的固定词。
    for (const match of fieldMatches) if (match && match.length >= 2) terms.push(match);
    // 2026-06-06 11:24:38 新增原因：按常见业务动作抽动词短语，避免只看名词导致步骤类答案误判。
    const actionMatches = cleaned.match(/[\u4e00-\u9fffA-Za-z0-9]{0,6}(?:审核|反审|冲账|付款|筛选|授权|刷新|导出|选择|退回|返回|核对|计算|接单|返工|补料|处理|查看)/g) || [];
    // 2026-06-06 11:24:38 新增原因：把动作短语加入候选，适配不同业务流程 chunk。
    for (const match of actionMatches) if (match && match.length >= 2) terms.push(match);
    // 2026-06-06 10:59:53 新增原因：从长片段中滑出常见业务短词，增强不同表述下的匹配鲁棒性。
    for (let size = 2; size <= Math.min(6, cleaned.length); size += 1) {
      // 2026-06-06 10:59:53 新增原因：只保留少量前缀/后缀窗口，防止生成过多噪声词。
      terms.push(cleaned.slice(0, size));
      terms.push(cleaned.slice(cleaned.length - size));
    }
  }
  // 2026-06-06 12:02:07 修改原因：保持字段词和动作词的插入顺序，不再只取最长噪声片段。
  return [...new Set(terms)].filter((term) => !STOP_TERMS.has(term)).slice(0, 28);
}

// 2026-06-06 10:59:53 新增原因：检查模型答案是否明显违背 top1 chunk 的事实方向。
function contradiction(bestAnswer, answer) {
  // 2026-06-06 10:59:53 新增原因：没有证据或答案时交给其他硬门槛处理。
  if (!bestAnswer || !answer) return "";
  // 2026-06-06 12:02:07 修改原因：只检查答案开头结论的肯定/否定方向，避免把后续风险解释误判成反向回答。
  const answerLead = String(answer).slice(0, 80);
  // 2026-06-06 10:59:53 新增原因：top1 表示可操作时，答案开头不能改成不可操作或尚未完成。
  if (/可以|应该|需要|已经|已为|现在可以|直接使用/.test(bestAnswer) && /不是|不需要|无需|不用|无法|不能|不支持|尚未|未完成|还不能/.test(answerLead)) return "answer_reverses_positive_evidence";
  // 2026-06-06 10:59:53 新增原因：top1 表示不可操作时，答案开头不能无依据改成可操作。
  if (/无法|不能|不支持|不需要|无需|需要人工/.test(bestAnswer) && /是|可以|应该|需要|直接使用|已经可以/.test(answerLead)) return "answer_reverses_negative_evidence";
  // 2026-06-06 10:59:53 新增原因：没有明显反向事实时返回空。
  return "";
}

// 2026-06-06 10:59:53 新增原因：对单条响应做严格门禁，不让“工具跑过”替代“模型吃证据答对”。
function evaluate(caseItem, data, elapsedSec) {
  // 2026-06-06 10:59:53 新增原因：读取 mark，里面包含 Prompt Builder、来源和 chunk 锚点。
  const mark = data.mark || {};
  // 2026-06-06 10:59:53 新增原因：读取最终答案，后续检查语义和内部标记泄露。
  const answer = data.answer || "";
  // 2026-06-06 10:59:53 新增原因：读取 Prompt Builder 文本，确认它真的交到模型消费通道。
  const prompt = mark.prompt_builder_context || "";
  // 2026-06-06 10:59:53 新增原因：读取工具名列表，确认四个必经节点不是漏跑。
  const tools = (data.tool_results || []).map((item) => item.tool_name);
  // 2026-06-06 10:59:53 新增原因：读取 top1 标准答案，作为 chunk 贴合度检查主证据。
  const bestAnswer = mark.best_answer || "";
  // 2026-06-06 10:59:53 新增原因：从 top1 标准答案提取业务词，不针对具体问题写死。
  const expectedTerms = semanticTerms(bestAnswer);
  // 2026-06-06 10:59:53 新增原因：统计模型答案命中的业务词，用于判断是否切中 chunk 数据。
  const matchedTerms = expectedTerms.filter((term) => answer.includes(term));
  // 2026-06-06 10:59:53 新增原因：要求至少命中两个业务词，或命中比例达到三成，避免空泛回答过关。
  const semanticPass = expectedTerms.length === 0 ? answer.length >= 20 : matchedTerms.length >= Math.min(2, expectedTerms.length) || matchedTerms.length / expectedTerms.length >= 0.3;
  // 2026-06-06 10:59:53 新增原因：检查是否出现 top1 事实方向被反写的问题。
  const contradictionReason = contradiction(bestAnswer, answer);
  // 2026-06-06 10:59:53 新增原因：汇总所有硬门槛，单项失败都不能算通过。
  const checks = {
    finalAction: data.final_action === "answer",
    modelSource: ["qwen_final_answer", "qwen_final_answer_retry"].includes(mark.draft_answer_source),
    noFallbackSource: !["evidence_fallback", "model_empty", "qwen_planner_content"].includes(mark.draft_answer_source),
    noModelEmptyFlag: !mark.model_empty_final_answer && !mark.protocol_empty_answer_fallback,
    requiredTools: REQUIRED_TOOLS.every((toolName) => tools.includes(toolName)),
    promptSections: REQUIRED_PROMPT_SECTIONS.every((section) => prompt.includes(section)),
    promptConstraints: REQUIRED_PROMPT_CONSTRAINTS.every((constraint) => prompt.includes(constraint)),
    hasTopChunk: Boolean(mark.best_answer_source_chunk_id),
    hasBestAnswer: Boolean(bestAnswer.trim()),
    answerNonEmpty: answer.trim().length >= 20,
    noInternalTokens: !INTERNAL_TOKENS.some((token) => answer.includes(token)),
    semanticPass,
    noContradiction: !contradictionReason,
  };
  // 2026-06-06 10:59:53 新增原因：生成可读摘要，便于人工复查答案是否通顺。
  return {
    name: caseItem.name,
    elapsedSec,
    passed: Object.values(checks).every(Boolean),
    checks,
    failureReasons: Object.entries(checks).filter(([, ok]) => !ok).map(([key]) => key).concat(contradictionReason ? [contradictionReason] : []),
    finalAction: data.final_action,
    answerSource: mark.draft_answer_source,
    verifier: data.verifier_result,
    tools,
    topChunk: mark.best_answer_source_chunk_id || "",
    matchedTerms,
    expectedTerms: expectedTerms.slice(0, 10),
    bestAnswer: bestAnswer.slice(0, 220),
    answer: answer.slice(0, 900),
  };
}

// 2026-06-06 10:59:53 新增原因：发送单条 WebUI 代理请求，确保测试经过前端代理和后端业务脑。
async function runCase(index) {
  // 2026-06-06 10:59:53 新增原因：读取待测问题。
  const caseItem = CASES[index];
  // 2026-06-06 10:59:53 新增原因：每条用独立 thread，避免上下文污染单条验收。
  const payload = { question: caseItem.question, user_id: "strict-e2e-user", thread_id: `strict-e2e-${Date.now()}-${String(index + 1).padStart(2, "0")}` };
  // 2026-06-06 10:59:53 新增原因：记录耗时，辅助定位模型卡顿或工具慢点。
  const started = Date.now();
  // 2026-06-06 10:59:53 新增原因：通过 WebUI /api 代理发送请求，不绕过前端服务。
  const response = await fetch(API_URL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  // 2026-06-06 10:59:53 新增原因：解析 JSON 响应，保留 mark/tool_results/answer 供严格门禁。
  const data = await response.json();
  // 2026-06-06 10:59:53 新增原因：HTTP 非 2xx 直接失败，避免错误页被当成答案。
  if (!response.ok) throw new Error(`${response.status} ${JSON.stringify(data).slice(0, 500)}`);
  // 2026-06-06 10:59:53 新增原因：返回严格检查结果。
  return evaluate(caseItem, data, Number(((Date.now() - started) / 1000).toFixed(1)));
}

// 2026-06-06 10:59:53 新增原因：解析命令行，可单条跑也可全量跑，方便长耗时测试逐条复查。
const argIndex = process.argv.indexOf("--index");
// 2026-06-06 10:59:53 新增原因：默认跑全部；传 --index 时只跑指定条，1 基序号便于人工对照。
const indexes = argIndex >= 0 ? [Number(process.argv[argIndex + 1]) - 1] : CASES.map((_, index) => index);
// 2026-06-06 10:59:53 新增原因：初始化结果列表。
const results = [];
// 2026-06-06 10:59:53 新增原因：顺序执行，避免本地 2B 模型并发导致超时或结果串扰。
for (const index of indexes) {
  // 2026-06-06 10:59:53 新增原因：校验序号有效，防止误传参数。
  if (!Number.isInteger(index) || index < 0 || index >= CASES.length) throw new Error(`invalid index: ${index + 1}`);
  // 2026-06-06 10:59:53 新增原因：执行单条严格验收。
  const result = await runCase(index);
  // 2026-06-06 10:59:53 新增原因：保存结果，供最终汇总。
  results.push(result);
  // 2026-06-06 10:59:53 新增原因：逐条输出 JSON，方便日志和人工复查。
  console.log(JSON.stringify(result, null, 2));
}
// 2026-06-06 10:59:53 新增原因：只要任一条失败，脚本用非零退出码阻断“全部通过”的误报。
if (results.some((result) => !result.passed)) process.exit(1);
