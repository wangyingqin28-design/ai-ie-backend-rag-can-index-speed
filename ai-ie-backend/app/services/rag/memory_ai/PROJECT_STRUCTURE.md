# memory_ai 项目结构说明

`memory_ai` 是一个带持久化记忆能力的可插拔聊天 AI 模块，位于 `app/services/rag/memory_ai`。它的核心目标是把“会话管理、历史记忆、RAG 后端、数据持久化”拆成相对独立的层，方便在不同检索和生成方案之间切换。

> 说明：当前目录中的 Python 源文件经过加密或混淆处理，不能直接按普通源码阅读。以下结构说明基于包目录、公开导出、编译产物中的类/函数信息以及 LightRAG 工作目录文件整理。

## 顶层结构

```text
memory_ai/
├── __init__.py
├── chat_ai.py
├── config.py
├── exceptions.py
├── llm.py
├── prompts.py
├── backends/
│   ├── __init__.py
│   ├── base.py
│   ├── lightrag_backend.py
│   └── llamaindex_backend.py
├── repositories/
│   ├── __init__.py
│   ├── base.py
│   ├── orm_model.py
│   └── sqlalchemy_repo.py
└── scripts/
    ├── __init__.py
    ├── Lightrag_step.py
    ├── lightrag_ingest.py
    ├── lightrag_chat_demo.py
    └── lightrag_workdir/
```

## 分层说明

### 1. 对外 API 层

相关文件：

- `__init__.py`

这一层是模块门面，集中导出外部业务应该使用的核心对象，避免调用方直接依赖内部文件结构。

主要导出包括：

- `ChatAI`：核心入口类
- `AIConfig`：配置对象
- `MemoryAIError`：模块统一异常
- `IChatBackend`：聊天后端抽象接口
- `LlamaIndexBackend`：基于 LlamaIndex 的后端实现
- `LightRAGBackend`：基于 LightRAG 的后端实现
- `IChatRepository`：聊天记录持久化抽象接口
- `SQLAlchemyChatRepository`：默认 SQLAlchemy 持久化实现

### 2. 应用编排层

相关文件：

- `chat_ai.py`

这一层的核心类是 `ChatAI`。它负责把一次聊天请求串起来，但不直接关心具体使用哪种 RAG 技术，也不直接绑定某种数据库。

主要职责：

- 创建或恢复会话
- 管理进程内会话缓存
- 从持久化层加载历史消息
- 调用聊天后端生成回复
- 保存用户消息和助手回复
- 查询会话列表
- 删除会话
- 更新会话标题
- 按 `tenant_id` 做数据隔离

可以把 `ChatAI` 理解为业务编排中心：它负责“什么时候做什么”，但具体“怎么检索、怎么生成、怎么存储”交给下层接口实现。

### 3. 后端策略层

相关目录：

- `backends/`

这一层决定“如何根据当前问题和历史记录生成回答”。

核心文件：

- `backends/base.py`
- `backends/llamaindex_backend.py`
- `backends/lightrag_backend.py`

核心对象：

- `IChatBackend`
- `LlamaIndexBackend`
- `LightRAGBackend`

`IChatBackend` 是抽象接口，定义统一的聊天能力：

- `chat()`：普通异步聊天，返回完整回复
- `stream_chat()`：流式聊天，逐步返回增量文本

`LlamaIndexBackend` 负责把历史消息放入 LlamaIndex 的聊天引擎中。根据是否注入 retriever，可以支持纯聊天或向量 RAG。

`LightRAGBackend` 负责把 `memory_ai` 的会话历史转换成 LightRAG 能理解的格式，并通过 LightRAG 执行知识图谱 RAG 查询。默认模式倾向于 `hybrid` 检索。

这一层的意义是可插拔：如果以后要换成其他 RAG 框架，只需要新增一个实现 `IChatBackend` 的后端类，`ChatAI` 不需要大改。

### 4. 持久化层

相关目录：

- `repositories/`

这一层负责会话和消息的存储，屏蔽具体数据库实现。

核心文件：

- `repositories/base.py`
- `repositories/orm_model.py`
- `repositories/sqlalchemy_repo.py`

核心对象：

- `IChatRepository`
- `SQLAlchemyChatRepository`
- `MemoryAIMessage`
- `ChatRecord`
- `SessionMetadata`
- `SessionSummary`

`IChatRepository` 定义持久化接口，主要能力包括：

- 保存消息
- 加载会话历史
- 判断会话是否存在
- 获取会话元数据
- 查询会话列表
- 删除会话
- 更新会话标题

`SQLAlchemyChatRepository` 是默认实现，构造时注入 `session_factory`，内部自管理数据库事务。

`MemoryAIMessage` 是 SQLAlchemy ORM 模型，对应表名：

```text
memory_ai_message
```

从字段设计看，它保存了：

- 消息 ID
- 会话 ID
- 租户 ID
- 消息角色
- 消息内容
- 会话标题
- 创建时间
- 删除时间

其中删除操作倾向于软删除，即通过 `deleted_at` 标记删除状态。

### 5. LLM 适配层

相关文件：

- `llm.py`

这一层负责根据配置构建 LLM 客户端。

核心函数：

- `build_llm(config)`

它根据 `AIConfig` 创建 `llama_index.llms.openai_like.OpenAILike` 实例，参数包括模型名、API 地址、API Key、上下文窗口、是否聊天模型、超时时间等。

该层单独存在，可以避免模型初始化逻辑散落在业务编排层或后端策略层中。

### 6. 配置、提示词与异常层

相关文件：

- `config.py`
- `prompts.py`
- `exceptions.py`

`config.py` 定义 `AIConfig`，用于集中管理模型和记忆相关配置，例如：

- `model`
- `api_key`
- `base_url`
- `context_window`
- `timeout`
- `is_chat_model`
- `memory_token_limit`
- `history_token_limit`
- `system_prompt`
- `default_session_title`

`prompts.py` 保存默认系统提示词。

`exceptions.py` 定义 `MemoryAIError`，作为模块统一异常类型，方便上层捕获和处理。

### 7. 脚本与离线数据层

相关目录：

- `scripts/`

这一层主要服务 LightRAG 的初始化、演示和离线数据灌入。

核心文件：

- `scripts/Lightrag_step.py`
- `scripts/lightrag_ingest.py`
- `scripts/lightrag_chat_demo.py`
- `scripts/lightrag_workdir/`

`Lightrag_step.py` 提供 LightRAG 单例工厂，包含初始化 LLM、Embedding、工作目录和 LightRAG 存储的逻辑。

`lightrag_ingest.py` 是一次性或增量灌入脚本，用于把 markdown 文档写入 LightRAG 图谱和向量索引中。

`lightrag_workdir/` 是 LightRAG 的工作目录，包含图谱、向量库、KV 存储和缓存文件，例如：

- `graph_chunk_entity_relation.graphml`
- `vdb_chunks.json`
- `vdb_entities.json`
- `vdb_relationships.json`
- `kv_store_full_docs.json`
- `kv_store_text_chunks.json`
- `kv_store_llm_response_cache.json`

这些文件属于运行产物或索引数据，不是主要业务代码。

## 核心调用链

一次普通聊天请求的大致流程如下：

```text
外部业务
  -> 创建或获取 ChatAI
  -> ChatAI.get_or_create_session()
  -> repository.load_history()
  -> backend.chat() 或 backend.stream_chat()
     -> LlamaIndexBackend / LightRAGBackend
     -> LLM / Retriever / LightRAG
  -> ChatAI._save_round()
  -> repository.save_message(user)
  -> repository.save_message(assistant)
```

## 依赖方向

推荐理解为以下依赖方向：

```text
外部业务
  ↓
API 层 __init__.py
  ↓
应用编排层 ChatAI
  ↓                 ↓
后端策略层 backends  持久化层 repositories
  ↓                 ↓
LLM / RAG 框架       SQLAlchemy / 数据库
```

其中：

- `ChatAI` 依赖抽象接口 `IChatBackend` 和 `IChatRepository`
- `backends` 依赖 RAG 或 LLM 框架
- `repositories` 依赖数据库和 ORM
- 配置、提示词、异常为各层提供基础能力

这种结构让模块具备较好的替换能力：

- 换数据库：实现新的 `IChatRepository`
- 换 RAG 框架：实现新的 `IChatBackend`
- 换模型服务：调整 `AIConfig` 和 `build_llm`

## 分层价值

当前结构的主要优点：

- 聊天编排和 RAG 实现解耦
- 聊天编排和数据库实现解耦
- 支持普通聊天、向量 RAG、知识图谱 RAG 多种后端
- 支持流式和非流式两种响应方式
- 支持 tenant 维度的数据隔离
- 运行产物与业务代码基本分离

## 建议维护边界

后续修改时可以按以下边界放置代码：

- 会话生命周期、聊天流程、保存历史：放在 `chat_ai.py`
- 新增 RAG 或聊天生成方案：放在 `backends/`
- 新增数据库、缓存或存储实现：放在 `repositories/`
- 模型客户端构建：放在 `llm.py`
- 默认提示词：放在 `prompts.py`
- 模块级异常：放在 `exceptions.py`
- 离线灌库、索引构建、演示脚本：放在 `scripts/`

