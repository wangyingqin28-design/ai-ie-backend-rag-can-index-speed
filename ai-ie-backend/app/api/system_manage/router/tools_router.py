"""
工具接口路由
"""
from datetime import datetime
from fastapi import APIRouter
from fastapi.openapi.docs import get_swagger_ui_html

from app.utils.response import Success

router = APIRouter(prefix="", tags=["工具接口"])


@router.get("/", summary="API根路径")
async def root():
    """API根路径，返回基本信息"""
    return {
        "app": "标准工序管理系统",
        "version": "1.0.0",
        "docs": "/docs",
        "health_check": "/health"
    }


@router.get("/health", summary="健康检查")
async def health_check():
    """健康检查接口，用于监控系统状态"""
    return Success(
        msg="服务正常",
        data={
            "status": "healthy",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "service": "标准工序管理系统"
        }
    )


# 自定义Swagger UI路由
@router.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="管理系统 API - Swagger UI",
        swagger_js_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.3/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.3/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )