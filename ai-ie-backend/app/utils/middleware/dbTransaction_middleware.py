from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.utils.database import get_db


class DBTransactionMiddleware(BaseHTTPMiddleware):
    """
    数据库事务中间件：
    - 每个请求自动绑定一个数据库会话
    - 无异常：请求结束时提交事务
    - 有异常：全局捕获并回滚事务
    """
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:

        # 定义无需数据库的接口路径（比如健康检查、静态接口）
        no_db_paths = ["/",
                       "/docs",#swagger
                       "/openapi.json"]
        if request.url.path in no_db_paths:
            # 跳过数据库会话创建，直接执行接口
            response = await call_next(request)
            return response

        # 1. 获取同步 Session（生成器取值）
        db_generator = get_db()
        db = next(db_generator)  # 同步生成器
        request.state.db = db

        try:

            response = await call_next(request)

            # 3. 只读接口跳过提交,请求标记为需要回滚也要跳过提交
            if (not hasattr(request.state, "need_rollback") or not request.state.need_rollback) and (not hasattr(request.state, "read_only") or not request.state.read_only):
                db.commit()
                print(f"事务提交成功 | 路径: {request.url.path} | 方法: {request.method}")
            else:
                db.rollback()
                if hasattr(request.state, "need_rollback") and request.state.need_rollback:
                    print(f"业务异常回滚 | 路径: {request.url.path} | 方法: {request.method}")
                else:
                    print(f"只读接口跳过提交 | 路径: {request.url.path} | 方法: {request.method}")

            return response

        except Exception as e:
            # 4. 有异常回滚
            db.rollback()
            print(f"事务回滚 | 路径: {request.url.path} | 方法: {request.method} | 异常: {str(e)}")
            raise e  # 抛给全局异常处理器

        finally:
            # 5. 关闭 Session
            db_generator.close()