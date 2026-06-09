from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

# 导入原有模块（保持路径不变）
from app.utils.database import get_db, engine
# from models import models
from app.models import models


# 创建所有表（只执行一次）
models.Base.metadata.create_all(bind=engine)

# CORS中间件配置
def setup_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 全局异常处理
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

# 通用依赖项
def get_current_user(userid: int = Query(default=0, description="操作用户ID")):
    return userid