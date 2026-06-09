from typing import Any, Optional
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
import traceback
from app.config import settings
from app.utils.logger import logger

from app.utils.exceptions import AppException, NotFoundException
from app.utils.response import Success



# ====================== 1. 自定义失败响应类（统一保险输出格式） ======================
class Fail(JSONResponse):
    """
    自定义失败响应类 - 所有错误响应的统一输出格式（保险结果单）
    结构：{code: 状态码/错误码, msg: 错误信息, data: 附加数据}
    """

    def __init__(
            self,
            code: int = 400,  # 业务错误码（默认400客户端错误）
            msg: Optional[str] = None,  # 错误提示信息（必填，明确说明问题）
            data: Optional[Any] = None,  # 附加数据（如校验失败字段、堆栈信息）
            http_status_code: int = 400,  # 单独的HTTP状态码参数
            **kwargs,  # 扩展字段（兼容特殊场景）
    ):
        # 构建标准化错误响应体（统一保险结果格式）
        content = {"code": code, "msg": msg, "data": data}
        content.update(kwargs)
        # 调用父类构造方法，返回JSON格式响应
        #print(f"Fail类设置的HTTP状态码: {http_status_code}")  # 看控制台输出
        super().__init__(content=content, status_code=http_status_code)


# ====================== 2. 初始化FastAPI应用 ======================
app = FastAPI()


# ====================== 3. 异常处理器 ======================
@app.exception_handler(AppException)
async def app_exception_handler(request: Request,exc: AppException):
    """
    第二道保险：业务异常处理器 —— 处理"登记在册的坏消息"
    对应：已知的、可预期的业务异常（如权限不足、数据不存在）
    """
    # 读取日志中间件生成的request_id（核心！关联链路）
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", "unknown"))

    # 标记事务需要回滚
    request.state.need_rollback = True

    #计入日志
    logger.warning(
         f"[{request_id}] 业务异常 [{exc.code}]: {exc.message}", #加[request_id]
        extra={
            "request_id": request_id,  # 日志字段里也加request_id，方便ELK等工具检索
            "path": request.url.path,
            "method": request.method,
            "code": exc.code,
            "details": exc.details
        }
    )

    # 用Fail类返回，统一响应格式
    return Fail(
        code=exc.code,  # 业务错误码
        msg=exc.message,  # 错误提示
        data=exc.details,  # 附加详情（如校验失败字段）
        http_status_code=exc.status_code  # HTTP状态码
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request,exc: Exception):
    """
    最后一道保险：全局异常处理器 —— 处理"突发的意外惊喜"
    对应：未知的、未捕获的异常（如代码bug、数据库连接失败）
    """
    # 读取request_id
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", "unknown"))
    # 基础错误信息（生产环境隐藏敏感内容）
    msg = "发生未知异常，请重试."
    data = None

    # 开发环境：展示完整调试信息（把底裤都露出来）
    if settings.debug:
        msg = str(exc)
        data = {
            "type": type(exc).__name__,  # 异常类型（如AttributeError）
            "traceback": traceback.format_exc().split("\n")  # 完整堆栈
        }

    #记录完整异常日志（排查问题的关键，无论环境都要记录）
    logger.error(
        f"[{request_id}] 未处理的异常: {type(exc).__name__}: {str(exc)}",  # 加[request_id]
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        }
    )

    # 改用Fail类返回500错误，统一响应格式
    return Fail(
        code=500,  # HTTP状态码
        msg=msg,  # 错误提示
        data=data,  # 附加调试信息（开发环境）
        http_status_code=500  # HTTP状态码
    )


# ====================== 4. 示例接口（演示保险流程） ======================
@app.get("/user/{user_id}")
async def get_user(user_id: int):
    # 第一道保险：手动调用Fail处理可预判错误（如参数非法）
    if user_id <= 0:
        return Fail(code=400, msg="用户ID不能为负数", data={"user_id": user_id})

    # 模拟抛出业务异常（触发第二道保险）
    if user_id == 999:
        
        # 方式1：直接抛基础AppException
        # raise AppException(code=404, message="用户不存在", details={"user_id": user_id}, status_code=404)

        # 方式2：抛简化的子类（代码更简洁）
        raise NotFoundException(message="用户不存在", details={"user_id": user_id})

    # 模拟未知异常（触发最后一道保险）
    if user_id == 888:
        # 代码bug：None没有id属性
        user = None
        return user.id  # 触发AttributeError

    # 正常响应（Success类）
    return Success(data={"user_id": user_id})


#================如何正确、规范地使用 try...except，核心原则是：只捕获「能预判、能处理」的异常，保留异常上下文，不掩盖问题。================
# @app.post("/create")
# async def create_user(username: str, email: str):
#     try:
#         # 可能抛异常的数据库操作
#         new_user = AIXiangBaoKuanHao(username=username, email=email)
#         db.add(new_user)
#         db.commit()
#         db.refresh(new_user)
#     except SQLAlchemyError as e:
#         # 关键：数据库异常必须回滚
#         db.rollback()
#         # 转成业务异常，交给app_exception_handler处理（保留原异常堆栈）
#         raise AppException(
#             code=5001,  # 自定义业务错误码
#             message="创建用户失败：数据库操作异常",
#             details=str(e) if settings.DEBUG else None,  # 开发环境显示详情
#             status_code=500
#         ) from e  # 保留原异常上下文，日志里能看到完整原因
#     # 无异常时返回成功响应
#     return Success(data={"user_id": new_user.id, "username": new_user.username})