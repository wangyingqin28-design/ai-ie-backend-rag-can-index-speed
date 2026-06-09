"""
管理系统 - FastAPI主程序
"""
from fastapi import FastAPI
from app.config import settings
from app.utils.exception_handler import app_exception_handler, global_exception_handler
from app.utils.exceptions import AppException


# 导入路由
from app.api.system_manage.router import tools_router, BiaoZhunGongXu_router,XiangBaoGongZhong_router
from app.utils.middleware.dbTransaction_middleware import DBTransactionMiddleware

settings.debug = True
# 创建FastAPI应用
app = FastAPI(
    title="管理系统 API",
    description="提供标准工序的完整CRUD操作，包括创建、查询、更新和软删除功能",
    version="1.0.0",
    docs_url=None,  # 禁用默认的docs
    openapi_tags=[
        {
            "name": "标准工序管理",
            "description": "标准工序的增删改查操作",
        },
        {
            "name": "工具接口",
            "description": "系统工具和健康检查接口",
        },
        {
            "name": "箱包工种管理",
            "description": "工种的增删改查操作",
        }
    ]
)

# 注册异常处理器
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# 注册事务中间件（必须在路由/异常处理器之前注册）
app.add_middleware(DBTransactionMiddleware)

# 注册路由
app.include_router(tools_router)
app.include_router(BiaoZhunGongXu_router)
app.include_router(XiangBaoGongZhong_router)


# ==================== 运行应用程序 ====================
if __name__ == "__main__":
    import uvicorn
    # 启动服务器
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # 监听所有网络接口
        port=8001,  # 使用8000端口
        reload=settings.debug  # 开发模式下开启热重载
    )
