# SQL_RAG Backend

This directory is the fixed backend root for SQL_RAG. It starts SQL Server 2022, Qdrant, the Markdown cleaning pipeline, Qdrant synchronization, and the open HTTP integration API.

## Start

```powershell
cd "D:\wkt\ai-ie-backend-feature-rag-new (1)\ai-ie-backend\app\SQL_RAG"
docker compose --env-file .\.env -f .\docker-compose.yml up -d
..\..\.venv\Scripts\python.exe .\main.py --input "C:\Users\DELL\Desktop\audio_merged_transcription.md" --db-backend sqlcmd
..\..\.venv\Scripts\python.exe .\data_cleaning\Qdrant\qdrant_sqlserver_sync.py --recreate
..\..\.venv\Scripts\python.exe -m uvicorn data_cleaning.integration.open_database_api:app --host 0.0.0.0 --port 18080
```

Or run the connection check script:

```powershell
.\check-connection.ps1
```

## Connection

Use these values in the backend `.env`:

```env
DB_HOST=127.0.0.1
DB_PORT=1433
DB_NAME=getai
DB_USER=dev
DB_PASSWORD=123456
DB_DRIVER=ODBC+Driver+17+for+SQL+Server
```

SQLAlchemy URL:

```text
mssql+pyodbc://dev:123456@127.0.0.1:1433/getai?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=no&encrypt=no
```

The `sa` password is configured in this directory's `.env` as `MSSQL_SA_PASSWORD`.

## Qdrant Connection

```text
Qdrant URL: http://127.0.0.1:6333
Collection: sql_rag_qa_chunks_v1
Vector size: 1024
Distance: Cosine
```

Qdrant dashboard:

```text
http://127.0.0.1:6333/dashboard
```

Open API docs:

```text
http://127.0.0.1:18080/docs
```

## Local Qwen Agent

The Agent expects a local OpenAI-compatible Qwen chat service:

```env
QWEN_AGENT_MODEL=Qwen/Qwen3.5-35B-A3B
QWEN_AGENT_MODEL_SERVER=http://127.0.0.1:8000/v1
QWEN_AGENT_API_KEY=local-qwen
```

After the local model server is running, execute a full customer-service Agent call:

```powershell
cd "D:\wkt\ai-ie-backend-feature-rag-new (1)\ai-ie-backend\app\SQL_RAG"
..\..\.venv\Scripts\python.exe .\main.py agent --question "客户说订单一直没有审核，帮我查知识库并创建跟进工单" --user-id local-user-001 --thread-id local-thread-001
```

The business tool now writes real local SQL Server records, not a placeholder. Supported actions include:

```text
create_ticket / complaint / return_order / exchange_order / cancel_order / change_address
transfer_human / request_human
create_followup / set_reminder
record_customer_profile / record_preference
update_ticket_status / close_ticket
query_tickets / query_profile / log_note
```

You can inspect executed operations through the open API:

```text
http://127.0.0.1:18080/agent/actions
http://127.0.0.1:18080/agent/tickets
http://127.0.0.1:18080/agent/handoffs
http://127.0.0.1:18080/agent/followups
http://127.0.0.1:18080/agent/profile-memory
http://127.0.0.1:18080/agent/correction-samples
```

Low-confidence answers are written to `dbo.rag_agent_correction_samples` first; if `LANGSMITH_API_KEY` is configured, the same sample is also pushed to LangSmith. Verifier-triggered transfer creates a row in `dbo.rag_customer_handoff_queue`.

## Refresh Data

After SQL Server and Qdrant are running, use these commands when a new Markdown file or directory needs to be cleaned, stored, and synchronized:

```powershell
cd "D:\wkt\ai-ie-backend-feature-rag-new (1)\ai-ie-backend\app\SQL_RAG"
..\..\.venv\Scripts\python.exe .\main.py --input "C:\Users\DELL\Desktop\audio_merged_transcription.md" --db-backend sqlcmd
..\..\.venv\Scripts\python.exe .\data_cleaning\Qdrant\qdrant_sqlserver_sync.py --recreate
```

The old `app\SQL_RAG\data_cleaning\main.py` path is kept only as a compatibility forwarder.
