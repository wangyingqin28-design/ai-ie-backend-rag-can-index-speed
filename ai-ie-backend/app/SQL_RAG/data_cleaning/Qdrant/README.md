# SQL Server canonical QA chunk 同步到 Qdrant

修改日期：2026-06-01 17:52:00。  
修改理由：把 SQL Server 2022 主库中的清洗结果封装成 Qdrant 向量检索索引，供后续 RAG 和其他机台直接连接使用。

## 本机同步命令

```powershell
cd "D:\wkt\ai-ie-backend-feature-rag-new (1)\ai-ie-backend"
.\.venv\Scripts\python.exe .\app\SQL_RAG\data_cleaning\Qdrant\qdrant_sqlserver_sync.py --recreate
```

## 本机校验命令

```powershell
curl http://127.0.0.1:6333/collections/sql_rag_qa_chunks_v1
```

## 其他机台连接命令

把 `服务器IP` 换成当前机器在局域网里的 IP，例如 `172.18.1.220`。

```powershell
python .\machine_qdrant_client_sample.py --qdrant-url "http://服务器IP:6333" --collection "sql_rag_qa_chunks_v1" --query "补料单怎么操作？"
```

