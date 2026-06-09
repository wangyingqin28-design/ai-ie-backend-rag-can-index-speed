# SQL Server 2022 数据库关系型设计图谱（无宽表版）

说明：本版不使用横向大表，避免中文、主键、外键和用途说明挤在一起。每一块都按“图 + 下方解析”的方式阅读。

## 0. 取证范围

- 数据库：`getai`
- SQL Server：`Microsoft SQL Server 2022 (RTM-CU25-GDR) (KB5095580) - 16.0.4260.1 (X64) `
- 用户表：`18` 张
- 字段：`204` 个
- 主键/唯一约束：`18` 个
- 外键：`2` 条
- 索引：`28` 个
- Check 约束：`0` 个
- 元数据来源：SQL Server 系统目录 `sys.tables`、`sys.columns`、`sys.key_constraints`、`sys.foreign_keys`、`sys.indexes`、`sys.default_constraints`、`sys.dm_db_partition_stats`。

## 1. 总链路图

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
       1 - - N rag_agent_action_events
       1 - - N rag_customer_service_tickets
       1 - - N rag_agent_correction_samples

user_id + memory_key
       1 ---- 1 rag_customer_profile_memory
```

解析：`----` 表示 SQL Server 明确声明的强外键或唯一约束；`- -` 表示由 ID 字段、索引和代码里的 `JOIN`、`MERGE`、`DELETE` 共同证明的软关系。`payload_json`、`llamaindex_node_json`、`vector_json` 是结构化快照，不是把整篇 Markdown 塞进一个不可查询的大 JSON。真正用于 SQL 查询、关联、去重、聚类和融合判断的是 `document_id`、`chunk_id`、`cluster_id`、`global_cluster_id`、`question_hash`、`answer_hash`、`entity_hash` 等关系型字段。

## 2. SQL Server 强外键证据

```text
dbo.rag_qa_documents  1 ---- N  dbo.rag_qa_chunks
字段：document_id -> document_id
约束：FK_rag_qa_chunks_documents
```
解析：子表 `rag_qa_chunks` 通过 `document_id` 绑定父表 `rag_qa_documents`。这是 SQL Server `sys.foreign_keys` 返回的真实外键证据。

```text
dbo.rag_qa_documents  1 ---- N  dbo.rag_qa_clusters
字段：document_id -> document_id
约束：FK_rag_qa_clusters_documents
```
解析：子表 `rag_qa_clusters` 通过 `document_id` 绑定父表 `rag_qa_documents`。这是 SQL Server `sys.foreign_keys` 返回的真实外键证据。

## 3. 软关系链路证据

```text
rag_qa_documents  1 - - N  rag_document_versions
字段：document_id
```
解析：同一文档的版本历史，写入脚本按 document_id 更新 is_current。

```text
rag_qa_documents  1 - - N  rag_entity_mentions
字段：document_id
```
解析：实体提及保存 document_id，并建 entity_hash/document_id 索引。

```text
rag_qa_chunks  1 - - N  rag_entity_mentions
字段：chunk_id
```
解析：实体提及保存 chunk_id，业务图扩展会 JOIN chunk。

```text
rag_global_clusters  1 - - N  rag_entity_mentions
字段：global_cluster_id
```
解析：实体提及可挂全局聚类 ID。

```text
rag_global_clusters  1 - - N  rag_qa_chunks
字段：global_cluster_id
```
解析：chunk 保存 global_cluster_id，并建 global_cluster/document_id 索引。

```text
rag_qa_clusters  1 - - N  rag_qa_chunks
字段：cluster_id
```
解析：chunk 保存 cluster_id，cluster 表保存成员 chunk ids。

```text
rag_qa_chunks  1 - - N  rag_chunk_fusion_map
字段：canonical_chunk_id / duplicate_chunk_id
```
解析：融合表记录规范 chunk 与重复 chunk。

```text
rag_qa_documents  1 - - N  rag_chunk_fusion_map
字段：canonical_document_id / duplicate_document_id
```
解析：融合表同时记录两侧 chunk 所属文档。

```text
rag_qa_chunks  1 - - N  rag_validation_issues
字段：chunk_id
```
解析：校验问题可定位到具体 chunk。

```text
rag_qa_documents  1 - - N  rag_validation_issues
字段：document_id
```
解析：校验问题可定位到文档，重摄取前按 document_id 清理。

```text
rag_qa_documents  1 - - N  rag_rag_sync_state
字段：document_id
```
解析：同步状态按 document_id/content_hash/sync_target 管理。

```text
rag_ingestion_jobs  1 - - N  rag_document_versions
字段：job_id
```
解析：文档版本记录来自哪个摄取任务。

```text
rag_customer_service_tickets  1 - - N  rag_customer_handoff_queue
字段：ticket_id
```
解析：转人工记录可挂工单；当前是软关系。

```text
rag_customer_service_tickets  1 - - N  rag_agent_followups
字段：ticket_id
```
解析：跟进任务可挂工单；当前是软关系。

```text
user/thread  1 - - N  rag_agent_action_events
字段：user_id + thread_id
```
解析：动作日志按用户和会话检索。

```text
user/thread  1 - - N  rag_customer_service_tickets
字段：user_id + thread_id
```
解析：工单按用户、会话、状态组织。

```text
user  1 - - N  rag_customer_profile_memory
字段：user_id + memory_key
```
解析：唯一索引保证同一用户同一画像键唯一。

```text
user/thread  1 - - N  rag_agent_correction_samples
字段：user_id + thread_id
```
解析：纠错样本可回放到用户会话。

## 4. 全量表与字段

### 4.1 `dbo.rag_qa_documents`

```text
表中文名：问答文档主表
行数：1
主键：PK__rag_qa_d__9666E8AC7362D710 (document_id)
强外键：无
索引：无非主键索引
关系图：
  rag_qa_documents  1 ---- N  rag_qa_chunks
  rag_qa_documents  1 ---- N  rag_qa_clusters
  rag_qa_documents  1 - - N  rag_document_versions / rag_entity_mentions / rag_validation_issues / rag_rag_sync_state
```

解析：一份原始知识文档的父表。每个文档用 document_id 标识；chunk 和文档内 cluster 通过 document_id 强外键挂在它下面。

字段明细：

- `document_id`：文档 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `source_path`：来源路径。类型 `nvarchar(800)`，必填。证据：普通字段。用途：业务属性字段。
- `source_name`：来源文件名。类型 `nvarchar(260)`，必填。证据：普通字段。用途：业务属性字段。
- `title`：文档标题。类型 `nvarchar(260)`，必填。证据：普通字段。用途：业务属性字段。
- `content_hash`：内容哈希。类型 `nvarchar(64)`，必填。证据：普通字段。用途：用于去重、幂等、融合或一致性判断。
- `framework_reference`：框架处理链路引用。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `updated_at`：更新时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `llamaindex_document_json`：LlamaIndex 文档快照 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。

### 4.2 `dbo.rag_qa_chunks`

```text
表中文名：问答 Chunk 明细表
行数：97
主键：PK__rag_qa_c__8B0F074DDAD99D74 (chunk_id)
强外键：FK_rag_qa_chunks_documents  document_id -> rag_qa_documents.document_id
索引：
  - IX_rag_qa_chunks_document_id (document_id ASC,chunk_index ASC)
  - IX_rag_qa_chunks_global_cluster (global_cluster_id ASC,document_id ASC)
  - IX_rag_qa_chunks_question_hash (question_hash ASC)
  - IX_rag_qa_chunks_scene (scene ASC,audio_no ASC)
关系图：
  rag_qa_documents  1 ---- N  rag_qa_chunks
  rag_qa_chunks     1 - - N  rag_entity_mentions / rag_chunk_fusion_map / rag_validation_issues
  rag_qa_chunks     N - - 1  rag_qa_clusters / rag_global_clusters
```

解析：真正可检索的问答明细。每个 chunk 有自己的问题、答案、场景、聚类、校验、融合状态和 RAG 快照。

字段明细：

- `chunk_id`：Chunk ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `document_id`：文档 ID。类型 `nvarchar(80)`，必填。证据：FK -> rag_qa_documents.document_id；IDX: IX_rag_qa_chunks_document_id, IX_rag_qa_chunks_global_cluster。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `audio_no`：音频编号。类型 `int`，必填。证据：IDX: IX_rag_qa_chunks_scene。用途：业务属性字段。
- `audio_title`：音频标题。类型 `nvarchar(260)`，必填。证据：普通字段。用途：业务属性字段。
- `chunk_index`：Chunk 序号。类型 `int`，必填。证据：IDX: IX_rag_qa_chunks_document_id。用途：业务属性字段。
- `scene`：问答场景。类型 `nvarchar(100)`，必填。证据：IDX: IX_rag_qa_chunks_scene。用途：业务属性字段。
- `question`：问题文本。类型 `nvarchar(max)`，必填。证据：普通字段。用途：长文本或可变结构内容。
- `answer`：答案文本。类型 `nvarchar(max)`，必填。证据：普通字段。用途：长文本或可变结构内容。
- `resolution_steps`：解答步骤 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `keywords`：关键词 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `entities_json`：实体抽取 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `cleaned_text`：清洗后文本。类型 `nvarchar(max)`，必填。证据：普通字段。用途：长文本或可变结构内容。
- `source_excerpt`：来源片段。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `content_hash`：内容哈希。类型 `nvarchar(64)`，必填。证据：普通字段。用途：用于去重、幂等、融合或一致性判断。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `payload_json`：业务/RAG 载荷 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `vector_json`：向量快照 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `vector_dim`：向量维度。类型 `int`，可空。证据：普通字段。用途：业务属性字段。
- `vector_model`：向量模型。类型 `nvarchar(120)`，可空。证据：普通字段。用途：业务属性字段。
- `llamaindex_node_json`：LlamaIndex 节点 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `payload_schema_version`：载荷结构版本。类型 `nvarchar(60)`，可空。证据：普通字段。用途：业务属性字段。
- `qa_pair_id`：问答对 ID。类型 `nvarchar(80)`，可空。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `qa_pair_index`：问答对序号。类型 `int`，可空。证据：普通字段。用途：业务属性字段。
- `qa_similarity_score`：问答相似度得分。类型 `float`，可空。证据：普通字段。用途：业务属性字段。
- `qa_similarity_threshold`：问答相似度阈值。类型 `float`，可空。证据：普通字段。用途：业务属性字段。
- `qa_pair_validated`：问答对是否校验通过。类型 `bit`，可空。证据：普通字段。用途：业务属性字段。
- `cluster_id`：文档内聚类 ID。类型 `nvarchar(80)`，可空。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `cluster_label`：文档内聚类标签。类型 `nvarchar(100)`，可空。证据：普通字段。用途：业务属性字段。
- `cluster_level`：文档内聚类层级。类型 `nvarchar(60)`，可空。证据：普通字段。用途：业务属性字段。
- `cluster_path`：文档内聚类路径 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `global_cluster_id`：全局聚类 ID。类型 `nvarchar(80)`，可空。证据：IDX: IX_rag_qa_chunks_global_cluster。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `global_cluster_label`：全局聚类标签。类型 `nvarchar(100)`，可空。证据：普通字段。用途：业务属性字段。
- `global_cluster_level`：全局聚类层级。类型 `nvarchar(60)`，可空。证据：普通字段。用途：业务属性字段。
- `global_cluster_path`：全局聚类路径 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `question_hash`：问题哈希。类型 `nvarchar(64)`，可空。证据：IDX: IX_rag_qa_chunks_question_hash。用途：用于去重、幂等、融合或一致性判断。
- `answer_hash`：答案哈希。类型 `nvarchar(64)`，可空。证据：普通字段。用途：用于去重、幂等、融合或一致性判断。
- `canonical_chunk_id`：规范 Chunk ID。类型 `nvarchar(80)`，可空。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `fusion_status`：融合状态。类型 `nvarchar(40)`，可空。证据：普通字段。用途：流程状态字段，用于筛选和状态机。

### 4.3 `dbo.rag_qa_clusters`

```text
表中文名：文档内问答聚类表
行数：10
主键：PK__rag_qa_c__29FEE76CC3476563 (cluster_id)
强外键：FK_rag_qa_clusters_documents  document_id -> rag_qa_documents.document_id
索引：
  - IX_rag_qa_clusters_document_id (document_id ASC,cluster_label ASC)
关系图：
  rag_qa_documents  1 ---- N  rag_qa_clusters
  rag_qa_clusters   1 - - N  rag_qa_chunks
```

解析：同一文档内的场景或主题聚类。用于把多个 chunk 归成文档内语义组。

字段明细：

- `cluster_id`：文档内聚类 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `document_id`：文档 ID。类型 `nvarchar(80)`，必填。证据：FK -> rag_qa_documents.document_id；IDX: IX_rag_qa_clusters_document_id。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `cluster_label`：文档内聚类标签。类型 `nvarchar(100)`，必填。证据：IDX: IX_rag_qa_clusters_document_id。用途：业务属性字段。
- `cluster_level`：文档内聚类层级。类型 `nvarchar(60)`，必填。证据：普通字段。用途：业务属性字段。
- `cluster_type`：文档内聚类类型。类型 `nvarchar(80)`，必填。证据：普通字段。用途：业务属性字段。
- `cluster_keywords`：文档内聚类关键词 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `cluster_member_count`：聚类成员数。类型 `int`，必填。证据：普通字段。用途：汇总数量，便于快速展示和校验。
- `cluster_member_chunk_ids`：聚类成员 Chunk ID 列表 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `cluster_node_json`：聚类节点 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.4 `dbo.rag_global_clusters`

```text
表中文名：跨文档全局聚类表
行数：10
主键：PK__rag_glob__DFC1974875480147 (global_cluster_id)
强外键：无
索引：无非主键索引
关系图：
  rag_global_clusters  1 - - N  rag_entity_mentions   [global_cluster_id]
  rag_global_clusters  1 - - N  rag_qa_chunks   [global_cluster_id]
```

解析：跨文档的全局语义聚类。用于把不同文档里的相同场景统一归档。

字段明细：

- `global_cluster_id`：全局聚类 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `global_cluster_label`：全局聚类标签。类型 `nvarchar(100)`，必填。证据：普通字段。用途：业务属性字段。
- `global_cluster_level`：全局聚类层级。类型 `nvarchar(60)`，必填。证据：普通字段。用途：业务属性字段。
- `global_cluster_type`：全局聚类类型。类型 `nvarchar(100)`，必填。证据：普通字段。用途：业务属性字段。
- `global_cluster_keywords`：全局聚类关键词 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `member_document_ids`：成员文档 ID 列表 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `member_cluster_ids`：成员聚类 ID 列表 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `member_chunk_ids`：成员 Chunk ID 列表 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `global_member_count`：全局成员数。类型 `int`，必填。证据：普通字段。用途：汇总数量，便于快速展示和校验。
- `global_cluster_node_json`：全局聚类节点 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `updated_at`：更新时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.5 `dbo.rag_document_versions`

```text
表中文名：文档版本表
行数：1
主键：PK__rag_docu__07A588694EC1605D (version_id)
强外键：无
索引：无非主键索引
关系图：
  rag_qa_documents  1 - - N  rag_document_versions   [document_id]
  rag_ingestion_jobs  1 - - N  rag_document_versions   [job_id]
```

解析：文档版本历史。记录同一 document_id 在不同摄取任务下的 content_hash 和当前版本状态。

字段明细：

- `version_id`：文档版本 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `document_id`：文档 ID。类型 `nvarchar(80)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `source_path`：来源路径。类型 `nvarchar(800)`，必填。证据：普通字段。用途：业务属性字段。
- `source_name`：来源文件名。类型 `nvarchar(260)`，必填。证据：普通字段。用途：业务属性字段。
- `content_hash`：内容哈希。类型 `nvarchar(64)`，必填。证据：普通字段。用途：用于去重、幂等、融合或一致性判断。
- `job_id`：摄取任务 ID。类型 `nvarchar(80)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `is_current`：是否当前版本。类型 `bit`，必填。证据：普通字段。用途：业务属性字段。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.6 `dbo.rag_entity_mentions`

```text
表中文名：实体提及明细表
行数：214
主键：PK__rag_enti__B791B2EDF6B113FE (mention_id)
强外键：无
索引：
  - IX_rag_entity_mentions_entity_hash (entity_hash ASC,document_id ASC)
关系图：
  rag_qa_documents  1 - - N  rag_entity_mentions   [document_id]
  rag_qa_chunks  1 - - N  rag_entity_mentions   [chunk_id]
  rag_global_clusters  1 - - N  rag_entity_mentions   [global_cluster_id]
```

解析：实体出现明细。说明某个实体出现在哪个文档、哪个 chunk、属于哪个全局聚类。

字段明细：

- `mention_id`：实体提及 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `document_id`：文档 ID。类型 `nvarchar(80)`，必填。证据：IDX: IX_rag_entity_mentions_entity_hash。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `chunk_id`：Chunk ID。类型 `nvarchar(80)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `entity_type`：实体类型。类型 `nvarchar(80)`，必填。证据：普通字段。用途：业务属性字段。
- `entity_value`：实体原始值。类型 `nvarchar(260)`，必填。证据：普通字段。用途：业务属性字段。
- `canonical_entity`：规范实体名称。类型 `nvarchar(260)`，必填。证据：普通字段。用途：业务属性字段。
- `entity_hash`：实体哈希。类型 `nvarchar(64)`，必填。证据：IDX: IX_rag_entity_mentions_entity_hash。用途：用于去重、幂等、融合或一致性判断。
- `global_cluster_id`：全局聚类 ID。类型 `nvarchar(80)`，可空。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.7 `dbo.rag_entity_aliases`

```text
表中文名：实体别名归一表
行数：71
主键：PK__rag_enti__BAC08C22A7502C61 (alias_id)
强外键：无
索引：无非主键索引
关系图：
  独立日志/状态/测试表
```

解析：实体别名到规范实体的映射。支持实体归一化和图扩展。

字段明细：

- `alias_id`：实体别名 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `entity_type`：实体类型。类型 `nvarchar(80)`，必填。证据：普通字段。用途：业务属性字段。
- `alias_value`：实体别名值。类型 `nvarchar(260)`，必填。证据：普通字段。用途：业务属性字段。
- `canonical_entity`：规范实体名称。类型 `nvarchar(260)`，必填。证据：普通字段。用途：业务属性字段。
- `entity_hash`：实体哈希。类型 `nvarchar(64)`，必填。证据：普通字段。用途：用于去重、幂等、融合或一致性判断。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `updated_at`：更新时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.8 `dbo.rag_chunk_fusion_map`

```text
表中文名：Chunk 融合去重映射表
行数：31
主键：PK__rag_chun__7C86D5803B56442C (fusion_id)
强外键：无
索引：无非主键索引
关系图：
  rag_qa_chunks  1 - - N  rag_chunk_fusion_map   [canonical_chunk_id / duplicate_chunk_id]
  rag_qa_documents  1 - - N  rag_chunk_fusion_map   [canonical_document_id / duplicate_document_id]
```

解析：重复或相似 chunk 的融合证据。记录 canonical_chunk_id 和 duplicate_chunk_id 的对应关系。

字段明细：

- `fusion_id`：融合关系 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `canonical_chunk_id`：规范 Chunk ID。类型 `nvarchar(80)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `duplicate_chunk_id`：重复 Chunk ID。类型 `nvarchar(80)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `canonical_document_id`：规范 Chunk 所属文档 ID。类型 `nvarchar(80)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `duplicate_document_id`：重复 Chunk 所属文档 ID。类型 `nvarchar(80)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `global_cluster_id`：全局聚类 ID。类型 `nvarchar(80)`，可空。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `question_hash`：问题哈希。类型 `nvarchar(64)`，可空。证据：普通字段。用途：用于去重、幂等、融合或一致性判断。
- `answer_hash`：答案哈希。类型 `nvarchar(64)`，可空。证据：普通字段。用途：用于去重、幂等、融合或一致性判断。
- `fusion_score`：融合分数。类型 `float`，必填。证据：普通字段。用途：业务属性字段。
- `fusion_rule`：融合规则。类型 `nvarchar(120)`，必填。证据：普通字段。用途：业务属性字段。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.9 `dbo.rag_validation_issues`

```text
表中文名：数据校验问题表
行数：0
主键：PK__rag_vali__D6185C39C873A94B (issue_id)
强外键：无
索引：
  - IX_rag_validation_issues_document_id (document_id ASC,issue_type ASC)
关系图：
  rag_qa_chunks  1 - - N  rag_validation_issues   [chunk_id]
  rag_qa_documents  1 - - N  rag_validation_issues   [document_id]
```

解析：清洗、聚类、融合、同步时发现的问题。可以落到文档或具体 chunk。

字段明细：

- `issue_id`：校验问题 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `document_id`：文档 ID。类型 `nvarchar(80)`，可空。证据：IDX: IX_rag_validation_issues_document_id。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `chunk_id`：Chunk ID。类型 `nvarchar(80)`，可空。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `issue_type`：问题类型。类型 `nvarchar(80)`，必填。证据：IDX: IX_rag_validation_issues_document_id。用途：业务属性字段。
- `issue_level`：问题级别。类型 `nvarchar(40)`，必填。证据：普通字段。用途：业务属性字段。
- `issue_message`：问题说明。类型 `nvarchar(max)`，必填。证据：普通字段。用途：长文本或可变结构内容。
- `issue_payload_json`：问题上下文 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.10 `dbo.rag_rag_sync_state`

```text
表中文名：RAG 向量同步状态表
行数：2
主键：PK__rag_rag___54E41ED0D13EF771 (sync_id)
强外键：无
索引：无非主键索引
关系图：
  rag_qa_documents  1 - - N  rag_rag_sync_state   [document_id]
```

解析：SQL Server 到 Qdrant 或下游向量索引的同步状态。记录是否需要重建索引。

字段明细：

- `sync_id`：同步状态 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `document_id`：文档 ID。类型 `nvarchar(80)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `content_hash`：内容哈希。类型 `nvarchar(64)`，必填。证据：普通字段。用途：用于去重、幂等、融合或一致性判断。
- `sync_target`：同步目标。类型 `nvarchar(120)`，必填。证据：普通字段。用途：业务属性字段。
- `sync_status`：同步状态。类型 `nvarchar(40)`，必填。证据：普通字段。用途：流程状态字段，用于筛选和状态机。
- `chunk_count`：Chunk 数量。类型 `int`，必填。证据：普通字段。用途：汇总数量，便于快速展示和校验。
- `needs_reindex`：是否需要重建索引。类型 `bit`，必填。证据：普通字段。用途：业务属性字段。
- `sync_message`：同步说明。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `updated_at`：更新时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.11 `dbo.rag_ingestion_jobs`

```text
表中文名：知识摄取任务表
行数：1
主键：PK__rag_inge__6E32B6A531A42F89 (job_id)
强外键：无
索引：无非主键索引
关系图：
  rag_ingestion_jobs  1 - - N  rag_document_versions   [job_id]
```

解析：一次知识摄取任务的汇总记录。保存文档数、chunk 数、融合数、校验问题数。

字段明细：

- `job_id`：摄取任务 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `input_path`：输入路径。类型 `nvarchar(800)`，必填。证据：普通字段。用途：业务属性字段。
- `job_status`：任务状态。类型 `nvarchar(40)`，必填。证据：普通字段。用途：流程状态字段，用于筛选和状态机。
- `document_count`：文档数量。类型 `int`，必填。证据：普通字段。用途：汇总数量，便于快速展示和校验。
- `chunk_count`：Chunk 数量。类型 `int`，必填。证据：普通字段。用途：汇总数量，便于快速展示和校验。
- `global_cluster_count`：全局聚类数量。类型 `int`，必填。证据：普通字段。用途：汇总数量，便于快速展示和校验。
- `fusion_count`：融合关系数量。类型 `int`，必填。证据：普通字段。用途：汇总数量，便于快速展示和校验。
- `validation_issue_count`：校验问题数量。类型 `int`，必填。证据：普通字段。用途：汇总数量，便于快速展示和校验。
- `job_options_json`：任务参数 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `updated_at`：更新时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.12 `dbo.rag_machine_integration_tests`

```text
表中文名：外部机台集成测试表
行数：0
主键：PK__rag_mach__3213E83FE0DC351C (id)
强外键：无
索引：无非主键索引
关系图：
  独立日志/状态/测试表
```

解析：外部机台或客户端通过开放接口写入和读取的测试数据。

字段明细：

- `id`：自增记录 ID。类型 `int`，必填。证据：PK；IDENTITY。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `machine_id`：机台或客户端 ID。类型 `nvarchar(120)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `payload_json`：业务/RAG 载荷 JSON。类型 `nvarchar(max)`，必填。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.13 `dbo.rag_agent_action_events`

```text
表中文名：Agent 动作事件表
行数：31
主键：PK__rag_agen__74EFC217EAADFBA3 (action_id)
强外键：无
索引：
  - IX_rag_agent_action_events_user_thread (user_id ASC,thread_id ASC,created_at ASC)
关系图：
  user/thread  1 - - N  rag_agent_action_events   [user_id + thread_id]
```

解析：Agent 执行业务动作的审计日志。按 user_id、thread_id、created_at 建索引。

字段明细：

- `action_id`：动作事件 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `user_id`：用户 ID。类型 `nvarchar(160)`，必填。证据：IDX: IX_rag_agent_action_events_user_thread。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `thread_id`：会话线程 ID。类型 `nvarchar(160)`，必填。证据：IDX: IX_rag_agent_action_events_user_thread。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `action_name`：动作名称。类型 `nvarchar(120)`，必填。证据：普通字段。用途：业务属性字段。
- `action_status`：动作状态。类型 `nvarchar(60)`，必填。证据：普通字段。用途：流程状态字段，用于筛选和状态机。
- `subject`：主题。类型 `nvarchar(260)`，可空。证据：普通字段。用途：业务属性字段。
- `order_no`：订单号或业务单号。类型 `nvarchar(120)`，可空。证据：普通字段。用途：业务属性字段。
- `contact`：联系方式。类型 `nvarchar(260)`，可空。证据：普通字段。用途：业务属性字段。
- `priority`：优先级。类型 `nvarchar(40)`，必填。证据：普通字段。用途：业务属性字段。
- `payload_json`：业务/RAG 载荷 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `result_json`：动作结果 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `source_question`：触发问题。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：IDX: IX_rag_agent_action_events_user_thread；DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.14 `dbo.rag_customer_service_tickets`

```text
表中文名：客服工单表
行数：25
主键：PK__rag_cust__D596F96B39DB33C7 (ticket_id)
强外键：无
索引：
  - IX_rag_customer_service_tickets_user_status (user_id ASC,status ASC,updated_at ASC)
关系图：
  rag_customer_service_tickets  1 - - N  rag_customer_handoff_queue
  rag_customer_service_tickets  1 - - N  rag_agent_followups
```

解析：Agent 创建或更新的客服工单。按用户、状态、更新时间建索引。

字段明细：

- `ticket_id`：客服工单 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `user_id`：用户 ID。类型 `nvarchar(160)`，必填。证据：IDX: IX_rag_customer_service_tickets_user_status。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `thread_id`：会话线程 ID。类型 `nvarchar(160)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `ticket_type`：工单类型。类型 `nvarchar(120)`，必填。证据：普通字段。用途：业务属性字段。
- `status`：状态。类型 `nvarchar(60)`，必填。证据：IDX: IX_rag_customer_service_tickets_user_status。用途：流程状态字段，用于筛选和状态机。
- `priority`：优先级。类型 `nvarchar(40)`，必填。证据：普通字段。用途：业务属性字段。
- `subject`：主题。类型 `nvarchar(260)`，必填。证据：普通字段。用途：业务属性字段。
- `description`：描述。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `order_no`：订单号或业务单号。类型 `nvarchar(120)`，可空。证据：普通字段。用途：业务属性字段。
- `contact`：联系方式。类型 `nvarchar(260)`，可空。证据：普通字段。用途：业务属性字段。
- `payload_json`：业务/RAG 载荷 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `source_question`：触发问题。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `updated_at`：更新时间。类型 `datetime2(0)`，必填。证据：IDX: IX_rag_customer_service_tickets_user_status；DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.15 `dbo.rag_customer_handoff_queue`

```text
表中文名：转人工队列表
行数：7
主键：PK__rag_cust__49C1B3DAFF618073 (handoff_id)
强外键：无
索引：无非主键索引
关系图：
  rag_customer_service_tickets  1 - - N  rag_customer_handoff_queue   [ticket_id]
```

解析：需要人工介入的队列。可通过 ticket_id 关联工单，但当前没有强外键。

字段明细：

- `handoff_id`：转人工记录 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `ticket_id`：客服工单 ID。类型 `nvarchar(80)`，可空。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `user_id`：用户 ID。类型 `nvarchar(160)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `thread_id`：会话线程 ID。类型 `nvarchar(160)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `reason`：原因。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `priority`：优先级。类型 `nvarchar(40)`，必填。证据：普通字段。用途：业务属性字段。
- `status`：状态。类型 `nvarchar(60)`，必填。证据：普通字段。用途：流程状态字段，用于筛选和状态机。
- `payload_json`：业务/RAG 载荷 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `updated_at`：更新时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.16 `dbo.rag_agent_followups`

```text
表中文名：Agent 跟进任务表
行数：8
主键：PK__rag_agen__6D23A5A10824C540 (followup_id)
强外键：无
索引：无非主键索引
关系图：
  rag_customer_service_tickets  1 - - N  rag_agent_followups   [ticket_id]
```

解析：Agent 创建的后续跟进任务。可通过 ticket_id 关联工单，但当前没有强外键。

字段明细：

- `followup_id`：跟进任务 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `ticket_id`：客服工单 ID。类型 `nvarchar(80)`，可空。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `user_id`：用户 ID。类型 `nvarchar(160)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `thread_id`：会话线程 ID。类型 `nvarchar(160)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `due_at`：计划跟进时间。类型 `nvarchar(80)`，可空。证据：普通字段。用途：时间审计字段。
- `channel`：跟进渠道。类型 `nvarchar(80)`，必填。证据：普通字段。用途：业务属性字段。
- `status`：状态。类型 `nvarchar(60)`，必填。证据：普通字段。用途：流程状态字段，用于筛选和状态机。
- `message`：消息。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `payload_json`：业务/RAG 载荷 JSON。类型 `nvarchar(max)`，可空。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。
- `updated_at`：更新时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

### 4.17 `dbo.rag_customer_profile_memory`

```text
表中文名：客户画像记忆表
行数：0
主键：PK__rag_cust__97BBB08A8735E991 (memory_id)
强外键：无
索引：
  - IX_rag_customer_profile_memory_user_key (user_id ASC,memory_key ASC) UNIQUE
关系图：
  user_id + memory_key  1 ---- 1  rag_customer_profile_memory
```

解析：客户画像长期记忆。唯一索引保证同一用户同一 memory_key 只有一条。

字段明细：

- `memory_id`：画像记忆 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `user_id`：用户 ID。类型 `nvarchar(160)`，必填。证据：IDX: IX_rag_customer_profile_memory_user_key UNIQUE。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `memory_key`：画像键。类型 `nvarchar(160)`，必填。证据：IDX: IX_rag_customer_profile_memory_user_key UNIQUE。用途：业务属性字段。
- `value_json`：画像值 JSON。类型 `nvarchar(max)`，必填。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `source_id`：来源 ID。类型 `nvarchar(120)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `confidence`：置信度。类型 `float`，必填。证据：普通字段。用途：业务属性字段。
- `updated_at`：更新时间。类型 `datetime2(0)`，必填。证据：普通字段。用途：时间审计字段。
- `expiry`：过期时间或策略。类型 `nvarchar(80)`，可空。证据：普通字段。用途：业务属性字段。
- `consent_scope`：授权范围。类型 `nvarchar(120)`，必填。证据：普通字段。用途：业务属性字段。

### 4.18 `dbo.rag_agent_correction_samples`

```text
表中文名：Agent 纠错样本表
行数：6
主键：PK__rag_agen__84ACF7BA0EC95E16 (sample_id)
强外键：无
索引：无非主键索引
关系图：
  user/thread  1 - - N  rag_agent_correction_samples   [user_id + thread_id]
```

解析：低置信或跑偏回答的纠错样本。用于后续验证和改进。

字段明细：

- `sample_id`：纠错样本 ID。类型 `nvarchar(80)`，必填。证据：PK。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `user_id`：用户 ID。类型 `nvarchar(160)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `thread_id`：会话线程 ID。类型 `nvarchar(160)`，必填。证据：普通字段。用途：标识或关联字段；强关系看 FK，软关系看索引和代码链路。
- `question`：问题文本。类型 `nvarchar(max)`，必填。证据：普通字段。用途：长文本或可变结构内容。
- `answer`：答案文本。类型 `nvarchar(max)`，可空。证据：普通字段。用途：长文本或可变结构内容。
- `failure_branch`：失败分支。类型 `nvarchar(160)`，必填。证据：普通字段。用途：业务属性字段。
- `verifier_score`：验证器得分。类型 `float`，必填。证据：普通字段。用途：业务属性字段。
- `mark_json`：标注 JSON。类型 `nvarchar(max)`，必填。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `verifier_json`：验证器输出 JSON。类型 `nvarchar(max)`，必填。证据：普通字段。用途：结构化快照或上下文；保留给 RAG、LlamaIndex、Qdrant 或接口使用。
- `created_at`：创建时间。类型 `datetime2(0)`，必填。证据：DEFAULT (sysutcdatetime())。用途：时间审计字段。

## 5. 最终判断

```text
不是：整篇 Markdown 清洗结果 -> 一个不可查询的大 JSON
而是：文档父表 -> 问答明细表 -> 聚类/实体/融合/校验/同步状态表
```

这份库的关系型证据是：18 张表都有主键；`rag_qa_chunks` 和 `rag_qa_clusters` 通过 SQL Server 强外键绑定 `rag_qa_documents`；其他业务链路通过 ID 字段、索引和代码中的 JOIN/MERGE/DELETE 形成软关系。JSON 字段保留运行时快照，真正支撑查询和关联的是关系型字段。
