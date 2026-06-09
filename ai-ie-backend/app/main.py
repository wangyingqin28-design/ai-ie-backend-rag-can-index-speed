from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from llama_index.core import PromptTemplate
from starlette.responses import RedirectResponse

from app.routers.admin_router import router as admin_router
from app.routers.LiShiGongJia_router import router as LiShiGongJia_router
from app.routers.XiangBaoBuWei_router import router as XiangBaoBuWei_router
from app.routers.XiangBaoCaiZhi_router import router as XiangBaoCaiZhi_router
from app.routers.XiangBaoBaoXing_router import router as XiangBaoBaoXing_router
from app.routers.user_router import router as user_router
from app.utils.exception_handler import app_exception_handler, global_exception_handler
from app.utils.exceptions import AppException
from app.services.working_price.kafka_consumer_manager import kafka_consumer_manager
from app.utils.middleware.dbTransaction_middleware import DBTransactionMiddleware
from app.utils.middleware.log_middleware import log_requests
from app.routers.dxf_router import router as dxf_router  # 导入路由
from app.routers.BiaoZhunGongXu_router import router as BiaoZhunGongXu_router
from app.routers.XiangBaoGongZhong_router import router as XiangBaoGongZhong_router
from app.routers.QuYuGongJia_router import router as QuYuGongJia_router
from app.routers.GongSiGongJia_router import router as GongSiGongJia_router
from app.routers.rag_router import router as rag_router
from app.routers.DocumentIndex_router import router as DocumentIndex_router
from app.routers.DiQuBianMa_router import router as DiQuBianMa_router
from app.routers.CaiZhiLeiXing_router import router as CaiZhiLeiXing_router
from app.routers.time_price_infer_router import router as time_price_infer_router
from app.routers.CaiZhiJiaGe_router import router as CaiZhiJiaGe_router

# 导入 lifespan 和全局状态
from app.services.rag.RAG import global_state, init_llm_and_embeddings, init_qdrant
# 提示词
from app.services.rag.prompt import BAG_EXPERT_PROMPT


from app.routers.document_index_router import router as document_index_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # ========== 启动阶段 ==========
    logger.info("正在初始化应用...")

    # 1. 初始化 LLM 和嵌入模型
    init_llm_and_embeddings()

    # 2. 初始化 Qdrant
    try:
        client, index = init_qdrant()
        global_state.qdrant_client = client
        global_state.vector_index = index
    except Exception as e:
        logger.critical(f"启动失败: {str(e)}")
        logger.exception("详细异常信息:")
        raise

    # 3. 设置查询模板
    global_state.query_template = PromptTemplate(BAG_EXPERT_PROMPT)

    logger.info("应用初始化成功")

    # 4. 启动 Kafka 消费者（非必须，失败不影响主应用）
    try:
        await kafka_consumer_manager.start()
        logger.info("Kafka 消费者管理器启动成功")
    except Exception as e:
        logger.exception("Kafka 消费者管理器启动失败，应用将继续运行但不会实时更新报价")
        # 不抛出异常，让应用继续运行

    yield

    # ========== 关闭阶段 ==========
    logger.info("正在关闭应用...")

    # 关闭 Kafka 消费者
    try:
        await kafka_consumer_manager.stop()
        logger.info("Kafka 消费者管理器已停止")
    except Exception as e:
        logger.exception("关闭 Kafka 消费者管理器时出错")

    # 关闭 Qdrant 客户端
    if global_state.qdrant_client:
        global_state.qdrant_client.close()

    logger.info("应用关闭完成")


# 创建FastAPI应用
app = FastAPI(
    title="箱包AI IE工程师",
    description="dxf上传解析拆工序打工价接口API",
    version="1.0.0",
    docs_url=None,  # 禁用默认的docs
    redoc_url=None,  # 禁用默认的redoc
    lifespan=lifespan,
)

# 注册事务中间件（必须在路由/异常处理器之前注册）
app.add_middleware(DBTransactionMiddleware)
# 注册日志中间件
app.middleware("http")(log_requests)

# FastAPI官方的CORSMiddleware(跨域中间件)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境替换为具体域名
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册异常处理器
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# 根目录（/）重定向配置
@app.get("/", include_in_schema=False)
async def redirect_root():
    """访问根目录时，重定向到FastAPI内置文档页面/docs"""
    return RedirectResponse(url="/docs")


# 自定义Swagger UI路由
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        swagger_js_url="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.17.14/swagger-ui-bundle.min.js",
        swagger_css_url="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.17.14/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


# 自定义ReDoc路由
@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="http://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.min.js",
        redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        with_google_fonts=False,
    )


# 包含路由
app.include_router(dxf_router, prefix="/api")
app.include_router(BiaoZhunGongXu_router, prefix="/api")
app.include_router(XiangBaoGongZhong_router, prefix="/api")
app.include_router(GongSiGongJia_router, prefix="/api")
app.include_router(QuYuGongJia_router, prefix="/api")
app.include_router(DocumentIndex_router, prefix="/api")
app.include_router(DiQuBianMa_router, prefix="/api")
app.include_router(CaiZhiLeiXing_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(LiShiGongJia_router, prefix="/api")
app.include_router(XiangBaoCaiZhi_router, prefix="/api")
app.include_router(XiangBaoBuWei_router, prefix="/api")
app.include_router(XiangBaoBaoXing_router, prefix="/api")
app.include_router(CaiZhiJiaGe_router, prefix="/api")

app.include_router(user_router, prefix="/api")
app.include_router(document_index_router, prefix="/api")


app.include_router(time_price_infer_router, prefix="/api")

app.include_router(admin_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # 监听所有网络接口
        port=8000,        # 使用8000端口
        reload=True,      # 开发模式下开启热重载
    )