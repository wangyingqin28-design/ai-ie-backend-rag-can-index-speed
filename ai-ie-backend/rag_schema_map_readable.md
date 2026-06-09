# SQL Server 2022 数据库关系型设计全量图谱

## 0. 取证范围

- 数据库：`getai`
- SQL Server：`Microsoft SQL Server 2022 (RTM-CU25-GDR) (KB5095580) - 16.0.4260.1 (X64) `
- 当前用户表：`18` 张；字段：`204` 个；主键/唯一约束：`18` 个；外键：`2` 条；索引：`28` 个；Check 约束：`0` 个。
- 取证来源：SQL Server 系统目录 `sys.tables`、`sys.columns`、`sys.key_constraints`、`sys.foreign_keys`、`sys.indexes`、`sys.default_constraints`、`sys.dm_db_partition_stats`。
- 代码链路证据：`app/SQL_RAG/data_cleaning/storage/sqlserver_writer.py`、`app/SQL_RAG/overall_planning/agent_Business_Brain/local_business_store.py`、`app/SQL_RAG/data_cleaning/integration/open_database_api.py`、`app/SQL_RAG/data_cleaning/Qdrant/qdrant_sqlserver_sync.py`。

## 1. 总关系图 + 解析

### 1.1 SQL Server 强外键图

```text
dbo.rag_qa_documents  1 ---- N  dbo.rag_qa_chunks    [document_id -> document_id]
dbo.rag_qa_documents  1 ---- N  dbo.rag_qa_clusters    [document_id -> document_id]
```

一份文档通过 `document_id` 强绑定多个问答 chunk 和多个文档内聚类。这个关系不是推断，是 SQL Server 外键约束返回的证据；当前两条外键都启用且可信。

### 1.2 完整业务链路图

```text
rag_ingestion_jobs
  -> rag_qa_documents
       1 ---- N rag_qa_chunks
       1 ---- N rag_qa_clusters
       1 - - N rag_document_versions
       1 - - N rag_entity_mentions
       1 - - N rag_validation_issues
       1 - - N rag_rag_sync_state -> Qdrant collection sql_rag_qa_chunks_v1
rag_qa_chunks
       1 - - N rag_entity_mentions
       1 - - N rag_chunk_fusion_map
       1 - - N rag_validation_issues
       N - - 1 rag_qa_clusters / rag_global_clusters
rag_customer_service_tickets
       1 - - N rag_customer_handoff_queue
       1 - - N rag_agent_followups
user_id + thread_id
       1 - - N rag_agent_action_events / rag_customer_service_tickets / rag_agent_correction_samples
user_id + memory_key
       1 ---- 1 rag_customer_profile_memory
```

这里的虚线 `- -` 是软关系证据：字段同名、索引和代码里的 `MERGE`、`DELETE`、`JOIN` 支撑它们做 SQL 查询、关联、去重、聚类、融合、校验和同步判断。它们不是不可查询的大 JSON；`payload_json`、`llamaindex_node_json`、`vector_json` 只保留 RAG/LlamaIndex/Qdrant 的结构化快照。

## 2. 表级总览

| 表 | 使用时中文名称 | 行数 | 主键 | 外键证据 | 索引数 | 主要用途 |
|---|---|---:|---|---|---:|---|
| `dbo.rag_qa_documents` | 问答文档主表 | 1 | PK__rag_qa_d__9666E8AC7362D710(document_id) | 无强外键，见软链路证据 | 1 | 一份原始知识文档的父表；每个文档用 document_id 标识，子表 chunk 和文档内 cluster 通过强外键挂到它下面。 |
| `dbo.rag_qa_chunks` | 问答 Chunk 明细表 | 97 | PK__rag_qa_c__8B0F074DDAD99D74(chunk_id) | FK_rag_qa_chunks_documents(document_id -> rag_qa_documents.document_id) | 5 | 真正可检索的问答明细；每个 chunk 有自己的问题、答案、场景、聚类、校验、融合状态和 RAG 快照。 |
| `dbo.rag_qa_clusters` | 文档内问答聚类表 | 10 | PK__rag_qa_c__29FEE76CC3476563(cluster_id) | FK_rag_qa_clusters_documents(document_id -> rag_qa_documents.document_id) | 2 | 同一文档内的场景/主题聚类；用于把多个 chunk 归成文档内语义组。 |
| `dbo.rag_global_clusters` | 跨文档全局聚类表 | 10 | PK__rag_glob__DFC1974875480147(global_cluster_id) | 无强外键，见软链路证据 | 1 | 跨文档的全局语义聚类；用于把不同文档里的相同场景统一归档。 |
| `dbo.rag_document_versions` | 文档版本表 | 1 | PK__rag_docu__07A588694EC1605D(version_id) | 无强外键，见软链路证据 | 1 | 文档版本历史；记录同一 document_id 在不同摄取任务下的 content_hash 和当前版本状态。 |
| `dbo.rag_entity_mentions` | 实体提及明细表 | 214 | PK__rag_enti__B791B2EDF6B113FE(mention_id) | 无强外键，见软链路证据 | 2 | 实体出现明细；说明某个实体出现在哪个文档、哪个 chunk、属于哪个全局聚类。 |
| `dbo.rag_entity_aliases` | 实体别名归一表 | 71 | PK__rag_enti__BAC08C22A7502C61(alias_id) | 无强外键，见软链路证据 | 1 | 实体别名到规范实体的映射；支持实体归一化和图扩展。 |
| `dbo.rag_chunk_fusion_map` | Chunk 融合去重映射表 | 31 | PK__rag_chun__7C86D5803B56442C(fusion_id) | 无强外键，见软链路证据 | 1 | 重复或相似 chunk 的融合证据；记录 canonical_chunk_id 和 duplicate_chunk_id 的对应关系。 |
| `dbo.rag_validation_issues` | 数据校验问题表 | 0 | PK__rag_vali__D6185C39C873A94B(issue_id) | 无强外键，见软链路证据 | 2 | 清洗/聚类/融合/同步时发现的问题；可以落到文档或具体 chunk。 |
| `dbo.rag_rag_sync_state` | RAG 向量同步状态表 | 2 | PK__rag_rag___54E41ED0D13EF771(sync_id) | 无强外键，见软链路证据 | 1 | SQL Server 到 Qdrant/下游向量索引的同步状态；记录是否需要重建索引。 |
| `dbo.rag_ingestion_jobs` | 知识摄取任务表 | 1 | PK__rag_inge__6E32B6A531A42F89(job_id) | 无强外键，见软链路证据 | 1 | 一次知识摄取任务的汇总记录；保存文档数、chunk 数、融合数、校验问题数。 |
| `dbo.rag_machine_integration_tests` | 外部机台集成测试表 | 0 | PK__rag_mach__3213E83FE0DC351C(id) | 无强外键，见软链路证据 | 1 | 外部机台或客户端通过开放接口写入/读取的测试数据。 |
| `dbo.rag_agent_action_events` | Agent 动作事件表 | 29 | PK__rag_agen__74EFC217EAADFBA3(action_id) | 无强外键，见软链路证据 | 2 | Agent 执行业务动作的审计日志；按 user_id、thread_id、created_at 建索引。 |
| `dbo.rag_customer_service_tickets` | 客服工单表 | 23 | PK__rag_cust__D596F96B39DB33C7(ticket_id) | 无强外键，见软链路证据 | 2 | Agent 创建或更新的客服工单；按用户、状态、更新时间建索引。 |
| `dbo.rag_customer_handoff_queue` | 转人工队列表 | 6 | PK__rag_cust__49C1B3DAFF618073(handoff_id) | 无强外键，见软链路证据 | 1 | 需要人工介入的队列；可通过 ticket_id 关联工单，但当前未建强外键。 |
| `dbo.rag_agent_followups` | Agent 跟进任务表 | 7 | PK__rag_agen__6D23A5A10824C540(followup_id) | 无强外键，见软链路证据 | 1 | Agent 创建的后续跟进任务；可通过 ticket_id 关联工单，但当前未建强外键。 |
| `dbo.rag_customer_profile_memory` | 客户画像记忆表 | 0 | PK__rag_cust__97BBB08A8735E991(memory_id) | 无强外键，见软链路证据 | 2 | 客户画像长期记忆；唯一索引保证同一用户同一 memory_key 只有一条。 |
| `dbo.rag_agent_correction_samples` | Agent 纠错样本表 | 5 | PK__rag_agen__84ACF7BA0EC95E16(sample_id) | 无强外键，见软链路证据 | 1 | 低置信或跑偏回答的纠错样本；用于后续验证和改进。 |

## 3. 链路证据清单

| 父/上游 | 子/下游 | 关联字段 | 证据类型 |
|---|---|---|---|
| `rag_qa_documents` | `rag_qa_chunks` | `document_id` | SQL Server 强外键 `FK_rag_qa_chunks_documents` |
| `rag_qa_documents` | `rag_qa_clusters` | `document_id` | SQL Server 强外键 `FK_rag_qa_clusters_documents` |
| `rag_qa_documents` | `rag_document_versions` | `document_id` | 软关系：同一文档的版本历史，写入脚本按 document_id 更新 is_current。 |
| `rag_qa_documents` | `rag_entity_mentions` | `document_id` | 软关系：实体提及保存 document_id，并建 entity_hash/document_id 索引。 |
| `rag_qa_chunks` | `rag_entity_mentions` | `chunk_id` | 软关系：实体提及保存 chunk_id，业务图扩展会 JOIN chunk。 |
| `rag_global_clusters` | `rag_entity_mentions` | `global_cluster_id` | 软关系：实体提及可挂全局聚类 ID。 |
| `rag_global_clusters` | `rag_qa_chunks` | `global_cluster_id` | 软关系：chunk 保存 global_cluster_id，并建 global_cluster/document_id 索引。 |
| `rag_qa_clusters` | `rag_qa_chunks` | `cluster_id` | 软关系：chunk 保存 cluster_id，cluster 表保存成员 chunk ids。 |
| `rag_qa_chunks` | `rag_chunk_fusion_map` | `canonical_chunk_id / duplicate_chunk_id` | 软关系：融合表记录规范 chunk 与重复 chunk。 |
| `rag_qa_documents` | `rag_chunk_fusion_map` | `canonical_document_id / duplicate_document_id` | 软关系：融合表同时记录两侧 chunk 所属文档。 |
| `rag_qa_chunks` | `rag_validation_issues` | `chunk_id` | 软关系：校验问题可定位到具体 chunk。 |
| `rag_qa_documents` | `rag_validation_issues` | `document_id` | 软关系：校验问题可定位到文档，重摄取前按 document_id 清理。 |
| `rag_qa_documents` | `rag_rag_sync_state` | `document_id` | 软关系：同步状态按 document_id/content_hash/sync_target 管理。 |
| `rag_ingestion_jobs` | `rag_document_versions` | `job_id` | 软关系：文档版本记录来自哪个摄取任务。 |
| `rag_customer_service_tickets` | `rag_customer_handoff_queue` | `ticket_id` | 软关系：转人工记录可挂工单；当前是软关系。 |
| `rag_customer_service_tickets` | `rag_agent_followups` | `ticket_id` | 软关系：跟进任务可挂工单；当前是软关系。 |
| `user/thread` | `rag_agent_action_events` | `user_id + thread_id` | 软关系：动作日志按用户和会话检索。 |
| `user/thread` | `rag_customer_service_tickets` | `user_id + thread_id` | 软关系：工单按用户、会话、状态组织。 |
| `user` | `rag_customer_profile_memory` | `user_id + memory_key` | 软关系：唯一索引保证同一用户同一画像键唯一。 |
| `user/thread` | `rag_agent_correction_samples` | `user_id + thread_id` | 软关系：纠错样本可回放到用户会话。 |

## 4. 全量表字段图 + 解析

### 4.1 `dbo.rag_qa_documents`：问答文档主表

```text
rag_qa_documents  1 ---- N  rag_qa_chunks
rag_qa_documents  1 ---- N  rag_qa_clusters
rag_qa_documents  1 - - N  rag_document_versions / rag_entity_mentions / rag_validation_issues / rag_rag_sync_state
```

解析：一份原始知识文档的父表；每个文档用 document_id 标识，子表 chunk 和文档内 cluster 通过强外键挂到它下面。
约束证据：`PK__rag_qa_d__9666E8AC7362D710` PRIMARY_KEY_CONSTRAINT(`document_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `document_id` | 文档 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `source_path` | 来源路径 | `nvarchar(800)` | 是 | 普通字段 | 业务属性字段。 |
| `source_name` | 来源文件名 | `nvarchar(260)` | 是 | 普通字段 | 业务属性字段。 |
| `title` | 文档标题 | `nvarchar(260)` | 是 | 普通字段 | 业务属性字段。 |
| `content_hash` | 内容哈希 | `nvarchar(64)` | 是 | 普通字段 | 用于去重、幂等、融合或一致性判断。 |
| `framework_reference` | 框架处理链路引用 | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `updated_at` | 更新时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `llamaindex_document_json` | LlamaIndex 文档快照 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |

### 4.2 `dbo.rag_qa_chunks`：问答 Chunk 明细表

```text
rag_qa_documents  1 ---- N  rag_qa_chunks
rag_qa_chunks     1 - - N  rag_entity_mentions / rag_chunk_fusion_map / rag_validation_issues
rag_qa_chunks     N - - 1  rag_qa_clusters / rag_global_clusters
```

解析：真正可检索的问答明细；每个 chunk 有自己的问题、答案、场景、聚类、校验、融合状态和 RAG 快照。
约束证据：`PK__rag_qa_c__8B0F074DDAD99D74` PRIMARY_KEY_CONSTRAINT(`chunk_id`)
强外键证据：`FK_rag_qa_chunks_documents` `document_id` -> `rag_qa_documents.document_id`
索引证据：`IX_rag_qa_chunks_document_id`(`document_id ASC,chunk_index ASC`); `IX_rag_qa_chunks_global_cluster`(`global_cluster_id ASC,document_id ASC`); `IX_rag_qa_chunks_question_hash`(`question_hash ASC`); `IX_rag_qa_chunks_scene`(`scene ASC,audio_no ASC`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `chunk_id` | Chunk ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `document_id` | 文档 ID | `nvarchar(80)` | 是 | FK -> rag_qa_documents.document_id; IDX: IX_rag_qa_chunks_document_id, IX_rag_qa_chunks_global_cluster | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `audio_no` | 音频编号 | `int` | 是 | IDX: IX_rag_qa_chunks_scene | 业务属性字段。 |
| `audio_title` | 音频标题 | `nvarchar(260)` | 是 | 普通字段 | 业务属性字段。 |
| `chunk_index` | Chunk 序号 | `int` | 是 | IDX: IX_rag_qa_chunks_document_id | 业务属性字段。 |
| `scene` | 问答场景 | `nvarchar(100)` | 是 | IDX: IX_rag_qa_chunks_scene | 业务属性字段。 |
| `question` | 问题文本 | `nvarchar(max)` | 是 | 普通字段 | 长文本或可变结构内容。 |
| `answer` | 答案文本 | `nvarchar(max)` | 是 | 普通字段 | 长文本或可变结构内容。 |
| `resolution_steps` | 解答步骤 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `keywords` | 关键词 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `entities_json` | 实体抽取 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `cleaned_text` | 清洗后文本 | `nvarchar(max)` | 是 | 普通字段 | 长文本或可变结构内容。 |
| `source_excerpt` | 来源片段 | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `content_hash` | 内容哈希 | `nvarchar(64)` | 是 | 普通字段 | 用于去重、幂等、融合或一致性判断。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `payload_json` | 业务载荷 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `vector_json` | 向量快照 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `vector_dim` | 向量维度 | `int` | 否 | 普通字段 | 业务属性字段。 |
| `vector_model` | 向量模型 | `nvarchar(120)` | 否 | 普通字段 | 业务属性字段。 |
| `llamaindex_node_json` | LlamaIndex 节点 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `payload_schema_version` | 载荷结构版本 | `nvarchar(60)` | 否 | 普通字段 | 业务属性字段。 |
| `qa_pair_id` | 问答对 ID | `nvarchar(80)` | 否 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `qa_pair_index` | 问答对序号 | `int` | 否 | 普通字段 | 业务属性字段。 |
| `qa_similarity_score` | 问答相似度得分 | `float` | 否 | 普通字段 | 业务属性字段。 |
| `qa_similarity_threshold` | 问答相似度阈值 | `float` | 否 | 普通字段 | 业务属性字段。 |
| `qa_pair_validated` | 问答对是否校验通过 | `bit` | 否 | 普通字段 | 业务属性字段。 |
| `cluster_id` | 文档内聚类 ID | `nvarchar(80)` | 否 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `cluster_label` | 文档内聚类标签 | `nvarchar(100)` | 否 | 普通字段 | 业务属性字段。 |
| `cluster_level` | 文档内聚类层级 | `nvarchar(60)` | 否 | 普通字段 | 业务属性字段。 |
| `cluster_path` | 文档内聚类路径 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `global_cluster_id` | 全局聚类 ID | `nvarchar(80)` | 否 | IDX: IX_rag_qa_chunks_global_cluster | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `global_cluster_label` | 全局聚类标签 | `nvarchar(100)` | 否 | 普通字段 | 业务属性字段。 |
| `global_cluster_level` | 全局聚类层级 | `nvarchar(60)` | 否 | 普通字段 | 业务属性字段。 |
| `global_cluster_path` | 全局聚类路径 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `question_hash` | 问题哈希 | `nvarchar(64)` | 否 | IDX: IX_rag_qa_chunks_question_hash | 用于去重、幂等、融合或一致性判断。 |
| `answer_hash` | 答案哈希 | `nvarchar(64)` | 否 | 普通字段 | 用于去重、幂等、融合或一致性判断。 |
| `canonical_chunk_id` | 规范 Chunk ID | `nvarchar(80)` | 否 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `fusion_status` | 融合状态 | `nvarchar(40)` | 否 | 普通字段 | 流程状态字段，用于筛选和状态机。 |

### 4.3 `dbo.rag_qa_clusters`：文档内问答聚类表

```text
rag_qa_documents  1 ---- N  rag_qa_clusters
rag_qa_clusters   1 - - N  rag_qa_chunks
```

解析：同一文档内的场景/主题聚类；用于把多个 chunk 归成文档内语义组。
约束证据：`PK__rag_qa_c__29FEE76CC3476563` PRIMARY_KEY_CONSTRAINT(`cluster_id`)
强外键证据：`FK_rag_qa_clusters_documents` `document_id` -> `rag_qa_documents.document_id`
索引证据：`IX_rag_qa_clusters_document_id`(`document_id ASC,cluster_label ASC`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `cluster_id` | 文档内聚类 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `document_id` | 文档 ID | `nvarchar(80)` | 是 | FK -> rag_qa_documents.document_id; IDX: IX_rag_qa_clusters_document_id | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `cluster_label` | 文档内聚类标签 | `nvarchar(100)` | 是 | IDX: IX_rag_qa_clusters_document_id | 业务属性字段。 |
| `cluster_level` | 文档内聚类层级 | `nvarchar(60)` | 是 | 普通字段 | 业务属性字段。 |
| `cluster_type` | 文档内聚类类型 | `nvarchar(80)` | 是 | 普通字段 | 业务属性字段。 |
| `cluster_keywords` | 文档内聚类关键词 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `cluster_member_count` | 聚类成员数 | `int` | 是 | 普通字段 | 汇总数量，便于快速展示和校验。 |
| `cluster_member_chunk_ids` | 聚类成员 Chunk ID 列表 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `cluster_node_json` | 聚类节点 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.4 `dbo.rag_global_clusters`：跨文档全局聚类表

```text
rag_global_clusters  1 - - N  rag_qa_chunks
rag_global_clusters  1 - - N  rag_entity_mentions
rag_global_clusters  1 - - N  rag_chunk_fusion_map
```

解析：跨文档的全局语义聚类；用于把不同文档里的相同场景统一归档。
约束证据：`PK__rag_glob__DFC1974875480147` PRIMARY_KEY_CONSTRAINT(`global_cluster_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `global_cluster_id` | 全局聚类 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `global_cluster_label` | 全局聚类标签 | `nvarchar(100)` | 是 | 普通字段 | 业务属性字段。 |
| `global_cluster_level` | 全局聚类层级 | `nvarchar(60)` | 是 | 普通字段 | 业务属性字段。 |
| `global_cluster_type` | 全局聚类类型 | `nvarchar(100)` | 是 | 普通字段 | 业务属性字段。 |
| `global_cluster_keywords` | 全局聚类关键词 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `member_document_ids` | 成员文档 ID 列表 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `member_cluster_ids` | 成员聚类 ID 列表 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `member_chunk_ids` | 成员 Chunk ID 列表 JSON | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `global_member_count` | 全局成员数 | `int` | 是 | 普通字段 | 汇总数量，便于快速展示和校验。 |
| `global_cluster_node_json` | 全局聚类节点 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `updated_at` | 更新时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.5 `dbo.rag_document_versions`：文档版本表

```text
rag_qa_documents  1 - - N  rag_document_versions    [document_id]
rag_ingestion_jobs  1 - - N  rag_document_versions    [job_id]
```

解析：文档版本历史；记录同一 document_id 在不同摄取任务下的 content_hash 和当前版本状态。
约束证据：`PK__rag_docu__07A588694EC1605D` PRIMARY_KEY_CONSTRAINT(`version_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `version_id` | 文档版本 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `document_id` | 文档 ID | `nvarchar(80)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `source_path` | 来源路径 | `nvarchar(800)` | 是 | 普通字段 | 业务属性字段。 |
| `source_name` | 来源文件名 | `nvarchar(260)` | 是 | 普通字段 | 业务属性字段。 |
| `content_hash` | 内容哈希 | `nvarchar(64)` | 是 | 普通字段 | 用于去重、幂等、融合或一致性判断。 |
| `job_id` | 摄取任务 ID | `nvarchar(80)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `is_current` | 是否当前版本 | `bit` | 是 | 普通字段 | 业务属性字段。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.6 `dbo.rag_entity_mentions`：实体提及明细表

```text
rag_qa_documents  1 - - N  rag_entity_mentions    [document_id]
rag_qa_chunks  1 - - N  rag_entity_mentions    [chunk_id]
rag_global_clusters  1 - - N  rag_entity_mentions    [global_cluster_id]
```

解析：实体出现明细；说明某个实体出现在哪个文档、哪个 chunk、属于哪个全局聚类。
约束证据：`PK__rag_enti__B791B2EDF6B113FE` PRIMARY_KEY_CONSTRAINT(`mention_id`)
索引证据：`IX_rag_entity_mentions_entity_hash`(`entity_hash ASC,document_id ASC`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `mention_id` | 实体提及 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `document_id` | 文档 ID | `nvarchar(80)` | 是 | IDX: IX_rag_entity_mentions_entity_hash | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `chunk_id` | Chunk ID | `nvarchar(80)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `entity_type` | 实体类型 | `nvarchar(80)` | 是 | 普通字段 | 业务属性字段。 |
| `entity_value` | 实体原始值 | `nvarchar(260)` | 是 | 普通字段 | 业务属性字段。 |
| `canonical_entity` | 规范实体名称 | `nvarchar(260)` | 是 | 普通字段 | 业务属性字段。 |
| `entity_hash` | 实体哈希 | `nvarchar(64)` | 是 | IDX: IX_rag_entity_mentions_entity_hash | 用于去重、幂等、融合或一致性判断。 |
| `global_cluster_id` | 全局聚类 ID | `nvarchar(80)` | 否 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.7 `dbo.rag_entity_aliases`：实体别名归一表

```text
rag_entity_aliases  [独立日志/状态/测试表]
```

解析：实体别名到规范实体的映射；支持实体归一化和图扩展。
约束证据：`PK__rag_enti__BAC08C22A7502C61` PRIMARY_KEY_CONSTRAINT(`alias_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `alias_id` | 实体别名 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `entity_type` | 实体类型 | `nvarchar(80)` | 是 | 普通字段 | 业务属性字段。 |
| `alias_value` | 实体别名值 | `nvarchar(260)` | 是 | 普通字段 | 业务属性字段。 |
| `canonical_entity` | 规范实体名称 | `nvarchar(260)` | 是 | 普通字段 | 业务属性字段。 |
| `entity_hash` | 实体哈希 | `nvarchar(64)` | 是 | 普通字段 | 用于去重、幂等、融合或一致性判断。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `updated_at` | 更新时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.8 `dbo.rag_chunk_fusion_map`：Chunk 融合去重映射表

```text
rag_qa_chunks  1 - - N  rag_chunk_fusion_map    [canonical_chunk_id / duplicate_chunk_id]
rag_qa_documents  1 - - N  rag_chunk_fusion_map    [canonical_document_id / duplicate_document_id]
```

解析：重复或相似 chunk 的融合证据；记录 canonical_chunk_id 和 duplicate_chunk_id 的对应关系。
约束证据：`PK__rag_chun__7C86D5803B56442C` PRIMARY_KEY_CONSTRAINT(`fusion_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `fusion_id` | 融合关系 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `canonical_chunk_id` | 规范 Chunk ID | `nvarchar(80)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `duplicate_chunk_id` | 重复 Chunk ID | `nvarchar(80)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `canonical_document_id` | 规范 Chunk 所属文档 ID | `nvarchar(80)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `duplicate_document_id` | 重复 Chunk 所属文档 ID | `nvarchar(80)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `global_cluster_id` | 全局聚类 ID | `nvarchar(80)` | 否 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `question_hash` | 问题哈希 | `nvarchar(64)` | 否 | 普通字段 | 用于去重、幂等、融合或一致性判断。 |
| `answer_hash` | 答案哈希 | `nvarchar(64)` | 否 | 普通字段 | 用于去重、幂等、融合或一致性判断。 |
| `fusion_score` | 融合分数 | `float` | 是 | 普通字段 | 业务属性字段。 |
| `fusion_rule` | 融合规则 | `nvarchar(120)` | 是 | 普通字段 | 业务属性字段。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.9 `dbo.rag_validation_issues`：数据校验问题表

```text
rag_qa_chunks  1 - - N  rag_validation_issues    [chunk_id]
rag_qa_documents  1 - - N  rag_validation_issues    [document_id]
```

解析：清洗/聚类/融合/同步时发现的问题；可以落到文档或具体 chunk。
约束证据：`PK__rag_vali__D6185C39C873A94B` PRIMARY_KEY_CONSTRAINT(`issue_id`)
索引证据：`IX_rag_validation_issues_document_id`(`document_id ASC,issue_type ASC`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `issue_id` | 校验问题 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `document_id` | 文档 ID | `nvarchar(80)` | 否 | IDX: IX_rag_validation_issues_document_id | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `chunk_id` | Chunk ID | `nvarchar(80)` | 否 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `issue_type` | 问题类型 | `nvarchar(80)` | 是 | IDX: IX_rag_validation_issues_document_id | 业务属性字段。 |
| `issue_level` | 问题级别 | `nvarchar(40)` | 是 | 普通字段 | 业务属性字段。 |
| `issue_message` | 问题说明 | `nvarchar(max)` | 是 | 普通字段 | 长文本或可变结构内容。 |
| `issue_payload_json` | 问题上下文 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.10 `dbo.rag_rag_sync_state`：RAG 向量同步状态表

```text
rag_qa_documents  1 - - N  rag_rag_sync_state    [document_id]
```

解析：SQL Server 到 Qdrant/下游向量索引的同步状态；记录是否需要重建索引。
约束证据：`PK__rag_rag___54E41ED0D13EF771` PRIMARY_KEY_CONSTRAINT(`sync_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `sync_id` | 同步状态 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `document_id` | 文档 ID | `nvarchar(80)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `content_hash` | 内容哈希 | `nvarchar(64)` | 是 | 普通字段 | 用于去重、幂等、融合或一致性判断。 |
| `sync_target` | 同步目标 | `nvarchar(120)` | 是 | 普通字段 | 业务属性字段。 |
| `sync_status` | 同步状态 | `nvarchar(40)` | 是 | 普通字段 | 流程状态字段，用于筛选和状态机。 |
| `chunk_count` | Chunk 数量 | `int` | 是 | 普通字段 | 汇总数量，便于快速展示和校验。 |
| `needs_reindex` | 是否需要重建索引 | `bit` | 是 | 普通字段 | 业务属性字段。 |
| `sync_message` | 同步说明 | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `updated_at` | 更新时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.11 `dbo.rag_ingestion_jobs`：知识摄取任务表

```text
rag_ingestion_jobs  1 - - N  rag_document_versions    [job_id]
```

解析：一次知识摄取任务的汇总记录；保存文档数、chunk 数、融合数、校验问题数。
约束证据：`PK__rag_inge__6E32B6A531A42F89` PRIMARY_KEY_CONSTRAINT(`job_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `job_id` | 摄取任务 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `input_path` | 输入路径 | `nvarchar(800)` | 是 | 普通字段 | 业务属性字段。 |
| `job_status` | 任务状态 | `nvarchar(40)` | 是 | 普通字段 | 流程状态字段，用于筛选和状态机。 |
| `document_count` | 文档数量 | `int` | 是 | 普通字段 | 汇总数量，便于快速展示和校验。 |
| `chunk_count` | Chunk 数量 | `int` | 是 | 普通字段 | 汇总数量，便于快速展示和校验。 |
| `global_cluster_count` | 全局聚类数量 | `int` | 是 | 普通字段 | 汇总数量，便于快速展示和校验。 |
| `fusion_count` | 融合关系数量 | `int` | 是 | 普通字段 | 汇总数量，便于快速展示和校验。 |
| `validation_issue_count` | 校验问题数量 | `int` | 是 | 普通字段 | 汇总数量，便于快速展示和校验。 |
| `job_options_json` | 任务参数 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `updated_at` | 更新时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.12 `dbo.rag_machine_integration_tests`：外部机台集成测试表

```text
rag_machine_integration_tests  [独立日志/状态/测试表]
```

解析：外部机台或客户端通过开放接口写入/读取的测试数据。
约束证据：`PK__rag_mach__3213E83FE0DC351C` PRIMARY_KEY_CONSTRAINT(`id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `id` | 自增记录 ID | `int` | 是 | PK; IDENTITY | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `machine_id` | 机台/客户端 ID | `nvarchar(120)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `payload_json` | 业务载荷 JSON | `nvarchar(max)` | 是 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.13 `dbo.rag_agent_action_events`：Agent 动作事件表

```text
user/thread  1 - - N  rag_agent_action_events    [user_id + thread_id]
```

解析：Agent 执行业务动作的审计日志；按 user_id、thread_id、created_at 建索引。
约束证据：`PK__rag_agen__74EFC217EAADFBA3` PRIMARY_KEY_CONSTRAINT(`action_id`)
索引证据：`IX_rag_agent_action_events_user_thread`(`user_id ASC,thread_id ASC,created_at ASC`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `action_id` | 动作事件 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `user_id` | 用户 ID | `nvarchar(160)` | 是 | IDX: IX_rag_agent_action_events_user_thread | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `thread_id` | 会话线程 ID | `nvarchar(160)` | 是 | IDX: IX_rag_agent_action_events_user_thread | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `action_name` | 动作名称 | `nvarchar(120)` | 是 | 普通字段 | 业务属性字段。 |
| `action_status` | 动作状态 | `nvarchar(60)` | 是 | 普通字段 | 流程状态字段，用于筛选和状态机。 |
| `subject` | 主题 | `nvarchar(260)` | 否 | 普通字段 | 业务属性字段。 |
| `order_no` | 订单号/业务单号 | `nvarchar(120)` | 否 | 普通字段 | 业务属性字段。 |
| `contact` | 联系方式 | `nvarchar(260)` | 否 | 普通字段 | 业务属性字段。 |
| `priority` | 优先级 | `nvarchar(40)` | 是 | 普通字段 | 业务属性字段。 |
| `payload_json` | 业务载荷 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `result_json` | 动作结果 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `source_question` | 触发问题 | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | IDX: IX_rag_agent_action_events_user_thread; DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.14 `dbo.rag_customer_service_tickets`：客服工单表

```text
rag_customer_service_tickets  1 - - N  rag_customer_handoff_queue
rag_customer_service_tickets  1 - - N  rag_agent_followups
```

解析：Agent 创建或更新的客服工单；按用户、状态、更新时间建索引。
约束证据：`PK__rag_cust__D596F96B39DB33C7` PRIMARY_KEY_CONSTRAINT(`ticket_id`)
索引证据：`IX_rag_customer_service_tickets_user_status`(`user_id ASC,status ASC,updated_at ASC`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `ticket_id` | 客服工单 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `user_id` | 用户 ID | `nvarchar(160)` | 是 | IDX: IX_rag_customer_service_tickets_user_status | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `thread_id` | 会话线程 ID | `nvarchar(160)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `ticket_type` | 工单类型 | `nvarchar(120)` | 是 | 普通字段 | 业务属性字段。 |
| `status` | 状态 | `nvarchar(60)` | 是 | IDX: IX_rag_customer_service_tickets_user_status | 流程状态字段，用于筛选和状态机。 |
| `priority` | 优先级 | `nvarchar(40)` | 是 | 普通字段 | 业务属性字段。 |
| `subject` | 主题 | `nvarchar(260)` | 是 | 普通字段 | 业务属性字段。 |
| `description` | 描述 | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `order_no` | 订单号/业务单号 | `nvarchar(120)` | 否 | 普通字段 | 业务属性字段。 |
| `contact` | 联系方式 | `nvarchar(260)` | 否 | 普通字段 | 业务属性字段。 |
| `payload_json` | 业务载荷 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `source_question` | 触发问题 | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `updated_at` | 更新时间 | `datetime2(0)` | 是 | IDX: IX_rag_customer_service_tickets_user_status; DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.15 `dbo.rag_customer_handoff_queue`：转人工队列表

```text
rag_customer_service_tickets  1 - - N  rag_customer_handoff_queue    [ticket_id]
```

解析：需要人工介入的队列；可通过 ticket_id 关联工单，但当前未建强外键。
约束证据：`PK__rag_cust__49C1B3DAFF618073` PRIMARY_KEY_CONSTRAINT(`handoff_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `handoff_id` | 转人工记录 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `ticket_id` | 客服工单 ID | `nvarchar(80)` | 否 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `user_id` | 用户 ID | `nvarchar(160)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `thread_id` | 会话线程 ID | `nvarchar(160)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `reason` | 原因 | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `priority` | 优先级 | `nvarchar(40)` | 是 | 普通字段 | 业务属性字段。 |
| `status` | 状态 | `nvarchar(60)` | 是 | 普通字段 | 流程状态字段，用于筛选和状态机。 |
| `payload_json` | 业务载荷 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `updated_at` | 更新时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.16 `dbo.rag_agent_followups`：Agent 跟进任务表

```text
rag_customer_service_tickets  1 - - N  rag_agent_followups    [ticket_id]
```

解析：Agent 创建的后续跟进任务；可通过 ticket_id 关联工单，但当前未建强外键。
约束证据：`PK__rag_agen__6D23A5A10824C540` PRIMARY_KEY_CONSTRAINT(`followup_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `followup_id` | 跟进任务 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `ticket_id` | 客服工单 ID | `nvarchar(80)` | 否 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `user_id` | 用户 ID | `nvarchar(160)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `thread_id` | 会话线程 ID | `nvarchar(160)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `due_at` | 计划跟进时间 | `nvarchar(80)` | 否 | 普通字段 | 时间审计字段。 |
| `channel` | 跟进渠道 | `nvarchar(80)` | 是 | 普通字段 | 业务属性字段。 |
| `status` | 状态 | `nvarchar(60)` | 是 | 普通字段 | 流程状态字段，用于筛选和状态机。 |
| `message` | 消息 | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `payload_json` | 业务载荷 JSON | `nvarchar(max)` | 否 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |
| `updated_at` | 更新时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

### 4.17 `dbo.rag_customer_profile_memory`：客户画像记忆表

```text
user_id + memory_key  1 ---- 1  rag_customer_profile_memory
```

解析：客户画像长期记忆；唯一索引保证同一用户同一 memory_key 只有一条。
约束证据：`PK__rag_cust__97BBB08A8735E991` PRIMARY_KEY_CONSTRAINT(`memory_id`)
索引证据：`IX_rag_customer_profile_memory_user_key`(`user_id ASC,memory_key ASC`) UNIQUE

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `memory_id` | 画像记忆 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `user_id` | 用户 ID | `nvarchar(160)` | 是 | IDX: IX_rag_customer_profile_memory_user_key UNIQUE | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `memory_key` | 画像键 | `nvarchar(160)` | 是 | IDX: IX_rag_customer_profile_memory_user_key UNIQUE | 业务属性字段。 |
| `value_json` | 画像值 JSON | `nvarchar(max)` | 是 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `source_id` | 来源 ID | `nvarchar(120)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `confidence` | 置信度 | `float` | 是 | 普通字段 | 业务属性字段。 |
| `updated_at` | 更新时间 | `datetime2(0)` | 是 | 普通字段 | 时间审计字段。 |
| `expiry` | 过期时间/策略 | `nvarchar(80)` | 否 | 普通字段 | 业务属性字段。 |
| `consent_scope` | 授权范围 | `nvarchar(120)` | 是 | 普通字段 | 业务属性字段。 |

### 4.18 `dbo.rag_agent_correction_samples`：Agent 纠错样本表

```text
user/thread  1 - - N  rag_agent_correction_samples    [user_id + thread_id]
```

解析：低置信或跑偏回答的纠错样本；用于后续验证和改进。
约束证据：`PK__rag_agen__84ACF7BA0EC95E16` PRIMARY_KEY_CONSTRAINT(`sample_id`)

| 字段 | 使用时中文名称 | 类型 | 必填 | 键/索引/默认值证据 | 关系型设计含义 |
|---|---|---|---:|---|---|
| `sample_id` | 纠错样本 ID | `nvarchar(80)` | 是 | PK | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `user_id` | 用户 ID | `nvarchar(160)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `thread_id` | 会话线程 ID | `nvarchar(160)` | 是 | 普通字段 | 标识或关联字段；强关系看 FK，软关系看索引/代码链路。 |
| `question` | 问题文本 | `nvarchar(max)` | 是 | 普通字段 | 长文本或可变结构内容。 |
| `answer` | 答案文本 | `nvarchar(max)` | 否 | 普通字段 | 长文本或可变结构内容。 |
| `failure_branch` | 失败分支 | `nvarchar(160)` | 是 | 普通字段 | 业务属性字段。 |
| `verifier_score` | 验证器得分 | `float` | 是 | 普通字段 | 业务属性字段。 |
| `mark_json` | 标注 JSON | `nvarchar(max)` | 是 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `verifier_json` | 验证器输出 JSON | `nvarchar(max)` | 是 | 普通字段 | 结构化快照或上下文，保留给 RAG/LlamaIndex/Qdrant/接口使用；不是主关系键。 |
| `created_at` | 创建时间 | `datetime2(0)` | 是 | DEFAULT (sysutcdatetime()) | 时间审计字段。 |

## 5. 最终判断

```text
不是：把整篇 Markdown 清洗结果塞成一个不可查询的大 JSON
而是：父表 + 子明细表 + 聚类表 + 实体表 + 融合表 + 校验表 + 同步状态表
```

关系型设计证据集中在这些字段上：`document_id`、`chunk_id`、`cluster_id`、`global_cluster_id`、`question_hash`、`answer_hash`、`entity_hash`、`canonical_chunk_id`、`duplicate_chunk_id`、`user_id`、`thread_id`、`ticket_id`、`memory_key`。这些字段配合主键、外键、索引和代码中的 JOIN/MERGE/DELETE，才是真正支撑 SQL 查询、关联、去重、聚类、融合、校验和同步判断的结构。
