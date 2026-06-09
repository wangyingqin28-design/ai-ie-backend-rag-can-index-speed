// 定义业务脑接口基础路径，实际请求由 agent_webUI 本地服务代理到 18180。
const API_BASE = "/api/agent/business-brain";

// 获取消息列表 DOM。
const messagesEl = document.getElementById("messages");
// 获取输入表单 DOM。
const composerEl = document.getElementById("composer");
// 获取问题输入框 DOM。
const questionInputEl = document.getElementById("questionInput");
// 获取发送按钮 DOM。
const sendButtonEl = document.getElementById("sendButton");
// 获取新会话按钮 DOM。
const newChatButtonEl = document.getElementById("newChatButton");
// 获取线程展示 DOM。
const threadPillEl = document.getElementById("threadPill");
// 获取服务状态列表 DOM。
const statusListEl = document.getElementById("statusList");
// 获取工具清单 DOM。
const toolListEl = document.getElementById("toolList");
// 获取右侧摘要 DOM。
const summaryGridEl = document.getElementById("summaryGrid");
// 获取助手消息模板。
const assistantTemplateEl = document.getElementById("assistantTemplate");

// 记录当前前端是否正在等待业务脑响应。
let isBusy = false;
// 记录当前会话线程 ID。
let threadId = readOrCreateThreadId();
// 记录当前用户 ID，供后端三层记忆和工单隔离使用。
const userId = readOrCreateUserId();

// 页面加载后刷新 thread 展示。
renderThreadPill();
// 页面加载后立即检查业务脑健康状态。
refreshHealth();
// 页面加载后读取工具契约。
refreshTools();

// 绑定发送表单事件。
composerEl.addEventListener("submit", (event) => {
  // 阻止表单默认刷新页面。
  event.preventDefault();
  // 触发发送流程。
  sendCurrentQuestion();
});

// 绑定输入框快捷发送事件。
questionInputEl.addEventListener("keydown", (event) => {
  // Ctrl+Enter 用于发送，普通 Enter 保持换行。
  if (event.key === "Enter" && event.ctrlKey) {
    // 阻止默认换行。
    event.preventDefault();
    // 触发发送流程。
    sendCurrentQuestion();
  }
});

// 绑定新会话按钮。
newChatButtonEl.addEventListener("click", () => {
  // 生成新的 LangGraph thread_id。
  threadId = createId("thread");
  // 持久化新的 thread_id。
  localStorage.setItem("sql_rag_agent_thread_id", threadId);
  // 刷新顶部展示。
  renderThreadPill();
  // 清空现有消息。
  messagesEl.innerHTML = "";
  // 添加初始助手消息。
  appendSimpleAssistantMessage("可以开始输入客户业务问题。");
  // 清空右侧摘要。
  renderSummary(null);
});

// 绑定示例问题按钮。
document.querySelectorAll("[data-prompt]").forEach((button) => {
  // 每个示例按钮点击后把问题写入输入框。
  button.addEventListener("click", () => {
    // 写入示例问题。
    questionInputEl.value = button.dataset.prompt || "";
    // 聚焦输入框。
    questionInputEl.focus();
  });
});

// 读取或创建用户 ID。
function readOrCreateUserId() {
  // 从本地存储读取用户 ID。
  const existing = localStorage.getItem("sql_rag_agent_user_id");
  // 如果已存在则复用。
  if (existing) {
    // 返回现有用户 ID。
    return existing;
  }
  // 创建新的用户 ID。
  const next = createId("webui-user");
  // 写入本地存储。
  localStorage.setItem("sql_rag_agent_user_id", next);
  // 返回新用户 ID。
  return next;
}

// 读取或创建线程 ID。
function readOrCreateThreadId() {
  // 从本地存储读取线程 ID。
  const existing = localStorage.getItem("sql_rag_agent_thread_id");
  // 如果已存在则复用。
  if (existing) {
    // 返回现有线程 ID。
    return existing;
  }
  // 创建新的线程 ID。
  const next = createId("thread");
  // 写入本地存储。
  localStorage.setItem("sql_rag_agent_thread_id", next);
  // 返回新线程 ID。
  return next;
}

// 创建业务可读的短 ID。
function createId(prefix) {
  // 生成随机字符串。
  const randomPart = Math.random().toString(16).slice(2, 10);
  // 生成时间字符串。
  const timePart = Date.now().toString(36);
  // 拼接前缀、时间和随机片段。
  return `${prefix}_${timePart}_${randomPart}`;
}

// 渲染顶部 thread 展示。
function renderThreadPill() {
  // 写入当前 thread_id。
  threadPillEl.textContent = `thread: ${threadId}`;
}

// 发送当前输入框问题。
async function sendCurrentQuestion() {
  // 读取并清理用户输入。
  const question = questionInputEl.value.trim();
  // 空问题直接返回。
  if (!question) {
    // 结束空输入处理。
    return;
  }
  // 忙碌中禁止重复提交。
  if (isBusy) {
    // 结束重复提交处理。
    return;
  }
  // 设置忙碌状态。
  setBusy(true);
  // 添加用户消息。
  appendUserMessage(question);
  // 清空输入框。
  questionInputEl.value = "";
  // 创建助手消息容器。
  const assistantView = appendStreamingAssistantMessage();
  // 构造后端请求 payload。
  const payload = {
    // 用户业务问题。
    question,
    // 当前 WebUI 用户 ID。
    user_id: userId,
    // 当前 LangGraph 线程 ID。
    thread_id: threadId,
    // 上层元数据。
    metadata: {
      // 标记请求来自前端工作台。
      source: "agent_webUI",
      // 记录当前浏览器语言。
      language: navigator.language || "zh-CN",
    },
  };
  // 等待后端流式真实结果。
  let result;
  // 捕获后端错误并在聊天框展示。
  try {
    // 2026-06-04 17:17:41 修改原因：改用后端 NDJSON trace 流，不再用前端固定步骤假装执行过程。
    result = await postChatStream(payload, async (traceEvent) => {
      // 2026-06-04 17:17:41 新增原因：逐字吐露后端真实公开 trace event。
      await typeLiveProcess(assistantView.reasoningText, traceEvent);
    });
  } catch (error) {
    // 写入错误摘要。
    await typeText(assistantView.answerText, `请求失败：${error.message || error}`, 10);
    // 刷新忙碌状态。
    setBusy(false);
    // 返回错误处理。
    return;
  }
  // 如果后端没有流式事件，则用最终结果里的 trace_events 补齐展示。
  if (!assistantView.reasoningText.textContent.trim()) {
    // 生成公开可展示链路，不暴露模型隐藏思维链。
    const traceText = buildPublicTrace(result);
    // 逐字吐露真实链路摘要。
    await typeText(assistantView.reasoningText, traceText, 6);
  }
  // 主动折叠解析过程。
  assistantView.reasoningBox.open = false;
  // 生成汇报答案和执行结果。
  const finalReport = buildFinalReport(result);
  // 逐字吐露最终可见答案。
  await typeText(assistantView.answerText, finalReport, 10);
  // 渲染右侧摘要。
  renderSummary(result);
  // 刷新忙碌状态。
  setBusy(false);
}

// 设置忙碌状态。
function setBusy(nextBusy) {
  // 更新全局状态。
  isBusy = nextBusy;
  // 控制发送按钮是否可用。
  sendButtonEl.disabled = nextBusy;
  // 控制输入框是否可用。
  questionInputEl.disabled = nextBusy;
}

// 调用业务脑 chat 接口。
async function postChat(payload) {
  // 发送 JSON 请求。
  const response = await fetch(`${API_BASE}/chat`, {
    // 使用 POST。
    method: "POST",
    // 设置请求头。
    headers: {
      // 告诉后端请求体是 JSON。
      "Content-Type": "application/json",
    },
    // 序列化请求体。
    body: JSON.stringify(payload),
  });
  // 非 2xx 响应视为错误。
  if (!response.ok) {
    // 读取错误文本。
    const errorText = await response.text();
    // 抛出包含状态码的错误。
    throw new Error(`${response.status} ${response.statusText}: ${errorText}`);
  }
  // 解析 JSON 响应。
  return response.json();
}

// 2026-06-04 17:18:22 新增原因：调用业务脑流式接口，逐行读取真实 trace events。
async function postChatStream(payload, onTraceEvent) {
  // 2026-06-04 17:18:22 新增原因：发送 NDJSON 流式请求。
  const response = await fetch(`${API_BASE}/chat-stream`, {
    // 2026-06-04 17:18:22 新增原因：使用 POST。
    method: "POST",
    // 2026-06-04 17:18:22 新增原因：设置 JSON 请求头。
    headers: {
      "Content-Type": "application/json",
    },
    // 2026-06-04 17:18:22 新增原因：序列化请求体。
    body: JSON.stringify(payload),
  });
  // 2026-06-04 17:18:22 新增原因：非 2xx 响应视为错误。
  if (!response.ok) {
    // 2026-06-04 17:18:22 新增原因：读取错误文本。
    const errorText = await response.text();
    // 2026-06-04 17:18:22 新增原因：抛出包含状态码的错误。
    throw new Error(`${response.status} ${response.statusText}: ${errorText}`);
  }
  // 2026-06-04 17:18:22 新增原因：没有 ReadableStream 时回退普通 JSON 接口。
  if (!response.body) {
    // 2026-06-04 17:18:22 新增原因：调用普通接口兜底。
    return postChat(payload);
  }
  // 2026-06-04 17:18:22 新增原因：创建 stream reader。
  const reader = response.body.getReader();
  // 2026-06-04 17:18:22 新增原因：创建 UTF-8 decoder。
  const decoder = new TextDecoder("utf-8");
  // 2026-06-04 17:18:22 新增原因：保存未解析完的行缓存。
  let buffer = "";
  // 2026-06-04 17:18:22 新增原因：保存最终结果。
  let finalResult = null;
  // 2026-06-04 17:18:22 新增原因：循环读取流。
  while (true) {
    // 2026-06-04 17:18:22 新增原因：读取下一块。
    const { value, done } = await reader.read();
    // 2026-06-04 17:18:22 新增原因：把当前块解码进缓存。
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    // 2026-06-04 17:18:22 新增原因：按换行拆 NDJSON。
    const lines = buffer.split("\n");
    // 2026-06-04 17:18:22 新增原因：最后一段可能是不完整 JSON，继续留在缓存里。
    buffer = lines.pop() || "";
    // 2026-06-04 17:18:22 新增原因：处理完整 JSON 行。
    for (const line of lines) {
      // 2026-06-04 17:18:22 新增原因：空行跳过。
      if (!line.trim()) {
        continue;
      }
      // 2026-06-04 17:18:22 新增原因：解析事件 JSON。
      const event = JSON.parse(line);
      // 2026-06-04 17:18:22 新增原因：trace 事件交给前端逐字展示。
      if (event.type === "trace") {
        await onTraceEvent(event.event || {});
      }
      // 2026-06-04 17:18:22 新增原因：final 事件保存完整结果。
      if (event.type === "final") {
        finalResult = event.result || {};
      }
      // 2026-06-04 17:18:22 新增原因：error 事件抛出，避免继续展示错误结果。
      if (event.type === "error") {
        throw new Error(event.detail || "后端流式接口返回错误。");
      }
    }
    // 2026-06-04 17:18:22 新增原因：流结束时退出循环。
    if (done) {
      break;
    }
  }
  // 2026-06-04 17:18:22 新增原因：处理流结束后残留的最后一行。
  if (buffer.trim()) {
    // 2026-06-04 17:18:22 新增原因：解析残留事件。
    const event = JSON.parse(buffer);
    // 2026-06-04 17:18:22 新增原因：残留 trace 也展示。
    if (event.type === "trace") {
      await onTraceEvent(event.event || {});
    }
    // 2026-06-04 17:18:22 新增原因：残留 final 保存结果。
    if (event.type === "final") {
      finalResult = event.result || {};
    }
    // 2026-06-04 17:18:22 新增原因：残留 error 抛出。
    if (event.type === "error") {
      throw new Error(event.detail || "后端流式接口返回错误。");
    }
  }
  // 2026-06-04 17:18:22 新增原因：没有最终结果时抛出明确错误。
  if (!finalResult) {
    throw new Error("后端流式接口没有返回 final 结果。");
  }
  // 2026-06-04 17:18:22 新增原因：返回最终业务脑结果。
  return finalResult;
}

// 在后端执行期间展示公开解析步骤。
async function typeLiveProcess(targetEl, traceEvent) {
  // 2026-06-04 17:18:22 修改原因：读取后端 trace event，而不是前端固定步骤数组。
  const line = formatTraceEvent(traceEvent);
  // 2026-06-04 17:18:22 新增原因：逐字吐露真实执行事件。
  await typeText(targetEl, `${line}\n`, 9);
}

// 2026-06-04 17:18:22 新增原因：把后端公开 trace event 格式化为前端可读文本。
function formatTraceEvent(traceEvent) {
  // 2026-06-04 17:18:22 新增原因：读取事件标题。
  const title = traceEvent.title || traceEvent.event_type || "执行事件";
  // 2026-06-04 17:18:22 新增原因：读取事件详情。
  const detail = traceEvent.detail || "";
  // 2026-06-04 17:18:22 新增原因：读取工具名。
  const toolName = traceEvent.tool_name ? ` [${traceEvent.tool_name}]` : "";
  // 2026-06-04 17:18:22 新增原因：读取时间。
  const timestamp = traceEvent.timestamp ? `${traceEvent.timestamp} ` : "";
  // 2026-06-04 17:18:22 新增原因：返回公开 trace 行。
  return `· ${timestamp}${title}${toolName}：${detail}`;
}

// 逐字吐露文本。
async function typeText(targetEl, text, delayMs) {
  // 遍历字符串中的每个字符。
  for (const char of text) {
    // 写入前判断用户是否仍停留在底部附近。
    const shouldStickToBottom = isMessagesNearBottom();
    // 追加当前字符。
    targetEl.textContent += char;
    // 用户仍在底部时才自动跟随，避免拖动查看上文时被拉回底部。
    scrollMessagesToBottom(shouldStickToBottom);
    // 等待下一字符。
    await sleep(delayMs);
  }
}

// 等待指定毫秒。
function sleep(ms) {
  // 返回 Promise 形式的计时器。
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

// 添加用户消息。
function appendUserMessage(text) {
  // 创建消息外层。
  const article = document.createElement("article");
  // 设置消息 class。
  article.className = "message user-message";
  // 写入消息 HTML。
  article.innerHTML = `
    <div class="avatar user-avatar" aria-hidden="true">我</div>
    <div class="message-body">
      <div class="message-meta">客户问题</div>
      <pre class="message-text"></pre>
    </div>
  `;
  // 写入用户文本，避免 HTML 注入。
  article.querySelector(".message-text").textContent = text;
  // 插入消息列表。
  messagesEl.appendChild(article);
  // 新消息进入时强制滚动到底部。
  scrollMessagesToBottom(true);
}

// 添加简单助手消息。
function appendSimpleAssistantMessage(text) {
  // 创建消息外层。
  const article = document.createElement("article");
  // 设置消息 class。
  article.className = "message assistant-message";
  // 写入消息 HTML。
  article.innerHTML = `
    <div class="avatar assistant-avatar" aria-hidden="true">AI</div>
    <div class="message-body">
      <div class="message-meta">SQL_RAG 业务脑</div>
      <div class="message-text"></div>
    </div>
  `;
  // 写入助手文本。
  article.querySelector(".message-text").textContent = text;
  // 插入消息列表。
  messagesEl.appendChild(article);
  // 新消息进入时强制滚动到底部。
  scrollMessagesToBottom(true);
}

// 添加支持流式展示的助手消息。
function appendStreamingAssistantMessage() {
  // 克隆助手模板。
  const fragment = assistantTemplateEl.content.cloneNode(true);
  // 获取消息节点。
  const article = fragment.querySelector(".message");
  // 获取解析过程折叠框。
  const reasoningBox = fragment.querySelector(".reasoning-box");
  // 获取解析文本节点。
  const reasoningText = fragment.querySelector(".reasoning-text");
  // 获取答案文本节点。
  const answerText = fragment.querySelector(".answer-text");
  // 插入消息列表。
  messagesEl.appendChild(fragment);
  // 新消息进入时强制滚动到底部。
  scrollMessagesToBottom(true);
  // 返回后续写入所需节点。
  return { article, reasoningBox, reasoningText, answerText };
}

// 判断消息区是否接近底部。
function isMessagesNearBottom() {
  // 计算距离底部的像素距离。
  const distanceToBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight;
  // 80 像素以内认为用户仍想跟随最新输出。
  return distanceToBottom < 80;
}

// 滚动消息到底部。
function scrollMessagesToBottom(force = false) {
  // 如果不是强制滚动，并且用户已经离开底部，就尊重用户拖动位置。
  if (!force) {
    // 结束非强制滚动。
    return;
  }
  // 设置滚动位置为最大高度。
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// 构建公开可展示解析链路。
function buildPublicTrace(result) {
  // 2026-06-04 17:20:09 新增原因：优先读取后端顶层 trace_events，保持与流式事件同源。
  const traceEvents = Array.isArray(result.trace_events) ? result.trace_events : [];
  // 2026-06-04 17:20:09 新增原因：如果有真实事件，直接格式化展示，不再走固定模板。
  if (traceEvents.length) {
    // 2026-06-04 17:20:09 新增原因：返回真实 trace events 的多行文本。
    return traceEvents.map((event) => formatTraceEvent(event)).join("\n") + "\n";
  }
  // 读取 mark。
  const mark = result.mark || {};
  // 读取工具结果。
  const toolResults = Array.isArray(result.tool_results) ? result.tool_results : [];
  // 读取图谱工具结果。
  const graphResult = readToolResult(toolResults, "sql_rag_graph_expand");
  // 读取业务动作结果。
  const businessResult = readToolResult(toolResults, "sql_rag_business_action");
  // 读取召回 chunk。
  const chunkIds = Array.isArray(mark.retrieved_chunk_ids) ? mark.retrieved_chunk_ids : [];
  // 读取图谱实体。
  const kgEntities = Array.isArray(mark.kg_entities) ? mark.kg_entities : readArray(graphResult.entities);
  // 读取图谱边。
  const kgEdges = Array.isArray(mark.kg_edges) ? mark.kg_edges : readArray(graphResult.edges);
  // 读取记忆 ID。
  const memoryIds = Array.isArray(mark.memory_read_ids) ? mark.memory_read_ids : [];
  // 组装公开链路行。
  const lines = [];
  // 写入意图节点。
  lines.push(`意图节点：${mark.intent_node || "planner_intent_reasoner"}`);
  // 写入检索查询。
  lines.push(`检索查询：${mark.retrieval_query || result.question || "客户问题原文"}`);
  // 写入召回结果。
  lines.push(`知识召回：${chunkIds.length} 条 chunk${chunkIds.length ? `（${chunkIds.slice(0, 5).join("，")}）` : ""}`);
  // 写入图谱结果。
  lines.push(`图谱扩展：${kgEntities.length} 个实体，${kgEdges.length} 条边，策略 ${graphResult.match_strategy || "source_chunk_ids / keyword_terms"}`);
  // 写入实体样例。
  if (kgEntities.length) {
    // 取前几个实体值。
    const entitySample = kgEntities.slice(0, 6).map((item) => item.entity_value || item.canonical_entity || "").filter(Boolean).join("，");
    // 写入实体样例。
    lines.push(`实体样例：${entitySample}`);
  }
  // 写入记忆结果。
  lines.push(`记忆读取：${memoryIds.length} 条记忆引用`);
  // 写入业务动作。
  if (businessResult.action_name) {
    // 写入业务动作摘要。
    lines.push(`业务动作：${businessResult.action_name} / ${businessResult.status || "unknown"}`);
  } else {
    // 写入无业务动作。
    lines.push("业务动作：本轮未触发写入动作");
  }
  // 写入校验结果。
  lines.push(`校验结果：score=${mark.verifier_score ?? "未返回"}，final_action=${result.final_action || mark.final_action || "answer"}`);
  // 写入说明边界。
  lines.push("说明：以上为公开执行链路摘要，不展示模型隐藏思维链。");
  // 返回多行文本。
  return lines.join("\n") + "\n";
}

// 构建最终答案和执行结果。
function buildFinalReport(result) {
  // 读取 mark。
  const mark = result.mark || {};
  // 读取工具结果。
  const toolResults = Array.isArray(result.tool_results) ? result.tool_results : [];
  // 读取图谱工具结果。
  const graphResult = readToolResult(toolResults, "sql_rag_graph_expand");
  // 读取业务动作结果。
  const businessResult = readToolResult(toolResults, "sql_rag_business_action");
  // 读取召回 chunk。
  const chunkIds = Array.isArray(mark.retrieved_chunk_ids) ? mark.retrieved_chunk_ids : [];
  // 读取图谱实体和边。
  const kgEntities = Array.isArray(mark.kg_entities) ? mark.kg_entities : readArray(graphResult.entities);
  // 读取图谱边。
  const kgEdges = Array.isArray(mark.kg_edges) ? mark.kg_edges : readArray(graphResult.edges);
  // 读取答案。
  const answer = result.answer || "后端没有返回答案文本。";
  // 组装执行结果。
  const lines = [
    answer,
    "",
    "执行结果",
    `- 最终动作：${result.final_action || mark.final_action || "answer"}`,
    `- 校验分数：${mark.verifier_score ?? "未返回"}`,
    `- 召回证据：${chunkIds.length} 条`,
    `- 图谱关系：${kgEntities.length} 个实体 / ${kgEdges.length} 条边`,
  ];
  // 如果存在业务动作，则补充业务动作细节。
  if (businessResult.action_name) {
    // 写入业务动作。
    lines.push(`- 业务动作：${businessResult.action_name} / ${businessResult.status || "unknown"}`);
    // 写入工单 ID。
    if (businessResult.ticket_id || businessResult.ticket?.ticket_id) {
      // 追加工单 ID。
      lines.push(`- 工单 ID：${businessResult.ticket_id || businessResult.ticket.ticket_id}`);
    }
    // 写入跟进 ID。
    if (businessResult.followup_id) {
      // 追加跟进 ID。
      lines.push(`- 跟进 ID：${businessResult.followup_id}`);
    }
    // 写入转人工 ID。
    if (businessResult.handoff_id) {
      // 追加转人工 ID。
      lines.push(`- 转人工 ID：${businessResult.handoff_id}`);
    }
  }
  // 返回最终文本。
  return lines.join("\n");
}

// 从工具结果列表中读取指定工具结果。
function readToolResult(toolResults, toolName) {
  // 查找匹配工具名的工具信封。
  const envelope = toolResults.find((item) => item && item.tool_name === toolName);
  // 返回工具内部 result。
  return envelope && envelope.result && typeof envelope.result === "object" ? envelope.result : {};
}

// 安全读取数组。
function readArray(value) {
  // 如果是数组则直接返回。
  if (Array.isArray(value)) {
    // 返回原数组。
    return value;
  }
  // 否则返回空数组。
  return [];
}

// 刷新健康状态。
async function refreshHealth() {
  // 捕获健康检查异常。
  try {
    // 请求健康检查。
    const response = await fetch(`${API_BASE}/health`);
    // 解析 JSON。
    const health = await response.json();
    // 渲染健康检查。
    renderHealth(health);
  } catch (error) {
    // 渲染异常状态。
    statusListEl.innerHTML = `<div class="status-row"><span>业务脑</span><span class="status-bad">离线</span></div>`;
  }
}

// 渲染健康状态。
function renderHealth(health) {
  // 读取检查项。
  const checks = health.checks || {};
  // 定义需要展示的核心检查。
  const rows = [
    ["Qwen", checks.qwen_openai_compatible_service?.ready],
    ["Qdrant", checks.qdrant?.ready],
    ["SQL Server", checks.sqlserver?.ready],
    ["Embedding", checks.embedding_config?.ready],
  ];
  // 渲染状态行。
  statusListEl.innerHTML = rows.map(([name, ready]) => {
    // 根据状态选择 class。
    const className = ready ? "status-ok" : "status-bad";
    // 根据状态选择文本。
    const label = ready ? "ready" : "check";
    // 返回行 HTML。
    return `<div class="status-row"><span>${escapeHtml(name)}</span><span class="${className}">${label}</span></div>`;
  }).join("");
}

// 刷新工具契约。
async function refreshTools() {
  // 捕获工具读取异常。
  try {
    // 请求工具 manifest。
    const response = await fetch(`${API_BASE}/tools`);
    // 解析 JSON。
    const manifest = await response.json();
    // 渲染工具列表。
    renderTools(manifest.tools || []);
  } catch (error) {
    // 渲染失败状态。
    toolListEl.innerHTML = `<div class="summary-empty">工具契约读取失败</div>`;
  }
}

// 渲染工具清单。
function renderTools(tools) {
  // 无工具时显示空状态。
  if (!tools.length) {
    // 写入空状态。
    toolListEl.innerHTML = `<div class="summary-empty">暂无工具</div>`;
    // 结束渲染。
    return;
  }
  // 写入工具列表。
  toolListEl.innerHTML = tools.map((tool) => `
    <div class="tool-item">
      <div class="tool-name">${escapeHtml(tool.name || "")}</div>
      <div class="tool-role">${escapeHtml(tool.role || "")}</div>
    </div>
  `).join("");
}

// 渲染右侧摘要。
function renderSummary(result) {
  // 空结果时显示等待状态。
  if (!result) {
    // 写入空摘要。
    summaryGridEl.innerHTML = `<div class="summary-empty">等待请求</div>`;
    // 结束渲染。
    return;
  }
  // 读取 mark。
  const mark = result.mark || {};
  // 读取工具结果。
  const toolResults = Array.isArray(result.tool_results) ? result.tool_results : [];
  // 读取图谱结果。
  const graphResult = readToolResult(toolResults, "sql_rag_graph_expand");
  // 读取业务结果。
  const businessResult = readToolResult(toolResults, "sql_rag_business_action");
  // 读取召回数。
  const retrievedCount = Array.isArray(mark.retrieved_chunk_ids) ? mark.retrieved_chunk_ids.length : 0;
  // 读取实体数。
  const entityCount = Array.isArray(mark.kg_entities) ? mark.kg_entities.length : readArray(graphResult.entities).length;
  // 读取边数。
  const edgeCount = Array.isArray(mark.kg_edges) ? mark.kg_edges.length : readArray(graphResult.edges).length;
  // 定义摘要项。
  const items = [
    ["最终动作", result.final_action || mark.final_action || "-"],
    ["校验分", mark.verifier_score ?? "-"],
    ["召回", `${retrievedCount} 条`],
    ["图谱", `${entityCount}/${edgeCount}`],
    ["业务动作", businessResult.action_name || "-"],
    ["状态", businessResult.status || "ok"],
  ];
  // 渲染摘要项。
  summaryGridEl.innerHTML = items.map(([label, value]) => `
    <div class="summary-item">
      <div class="summary-label">${escapeHtml(label)}</div>
      <div class="summary-value">${escapeHtml(String(value))}</div>
    </div>
  `).join("");
}

// HTML 转义，避免工具结果文本注入 DOM。
function escapeHtml(value) {
  // 把输入统一转成字符串。
  return String(value)
    // 转义 &。
    .replaceAll("&", "&amp;")
    // 转义 <。
    .replaceAll("<", "&lt;")
    // 转义 >。
    .replaceAll(">", "&gt;")
    // 转义双引号。
    .replaceAll('"', "&quot;")
    // 转义单引号。
    .replaceAll("'", "&#039;");
}
