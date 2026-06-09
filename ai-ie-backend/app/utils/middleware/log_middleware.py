import time
import uuid
from fastapi import Request
from starlette.middleware.base import RequestResponseEndpoint

from starlette.responses import Response

from app.utils.logger import logger


async def log_requests(
    request: Request,
    call_next: RequestResponseEndpoint
) -> Response:
    """请求日志中间件 —— 来了就得登记"""
    request_id = str(uuid.uuid4())[:8]

    # 把request_id存到request.state里，供后续异常处理器使用
    request.state.request_id = request_id

    logger.info(f"[{request_id}] --> {request.method} {request.url.path}")

    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    logger.info(f"[{request_id}] <-- {response.status_code} in {duration:.2f}s")
    response.headers["X-Request-ID"] = request_id

    return response