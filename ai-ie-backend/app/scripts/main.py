# app/main.py
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from typing import Optional
import os
from ingest_rules_to_qdrant import rebuild_knowledge_base

app = FastAPI(title="箱包规则管理 API")

# 从环境变量读取管理员密钥
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")


def verify_admin(api_key: Optional[str] = Header(None)):
    if not api_key or api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing admin API key")


@app.post("/admin/rebuild-knowledge-base")
async def trigger_rebuild(background_tasks: BackgroundTasks, api_key: str = Header(...)):
    verify_admin(api_key)

    # 添加后台任务（立即返回，避免长时间等待）
    background_tasks.add_task(rebuild_knowledge_base)

    return {
        "message": "知识库重建任务已启动（后台执行）",
        "note": "请通过日志监控进度，完成后可通过 /search 测试"
    }