"""
路由模块初始化文件
"""
from app.api.system_manage.router.tools_router import router as tools_router
from app.api.system_manage.router.BiaoZhunGongXu_router import router as BiaoZhunGongXu_router
from app.api.system_manage.router.XiangBaoGongZhong_router import router as XiangBaoGongZhong_router

__all__ = ["tools_router", "BiaoZhunGongXu_router","XiangBaoGongZhong_router"]