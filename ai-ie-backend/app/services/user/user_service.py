import traceback
from datetime import datetime

from fastapi import Request
from jose import JWTError

from app.config import settings
from app.schemas.user.user_schemas import AIGongSiYongHuRequest
from app.services.user.user_crud import query_user_by_dianHua, authenticate_user, create_user, get_user_by_phone
from app.utils.auth.jwt_utils import get_password_hash, decode_token
from app.utils.exceptions import UserCreateException, LoginException, TokenException, SystemException, NotFoundException
from app.utils.redis.token import add_token_to_blacklist, is_token_blacklisted, get_token, delete_user_all_tokens


def register(request: Request, aiGongSiYongHuRequest: AIGongSiYongHuRequest):
    """
        用户注册
        :param request: 数据库会话（中间件创建）
        :param aiGongSiYongHuRequest: 用户注册请求体
        """
    try:
        # 密码加密（不可逆，仅存储哈希值）
        hashed_password = get_password_hash(aiGongSiYongHuRequest.miMa)

        aiGongSiYongHuRequest.miMa = hashed_password  # 将明文密码加密

        # 从request.state获取中间件创建的会话，无需自己创建
        db = request.state.db
        print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

        # 调用入库函数（传入中间件的会话）
        create_user(db, aiGongSiYongHuRequest)

    except Exception as e:
        raise UserCreateException(
            message=f"用户注册失败：{str(e)}",  # 友好的错误提示
            details={"error": str(e), "type": type(e).__name__}  # 错误详情（可选）
        )


def check_phone_exists(request: Request, dianHua: str):
    """
    检查手机号是否已注册
    原理：查询AIGongSiYongHu表，判断该手机号是否存在（未删除）
    :param request: 数据库会话（中间件创建）
    :param dianHua: 待校验的手机号
    :return: 已存在返回True，否则False
    """
    try:
        # 从request.state获取中间件创建的会话，无需自己创建
        db = request.state.db
        print(f"使用中间件会话: {id(db)}, Active: {db.is_active}")

        return query_user_by_dianHua(db, dianHua)

    except Exception as e:
        raise UserCreateException(
            message=f"用户注册失败：{str(e)}",  # 友好的错误提示
            details={"error": str(e), "type": type(e).__name__}  # 错误详情（可选）
        )


def login_verify(request: Request, dianHua: str, password: str):

    """
    登录验证业务逻辑
    :param request: 请求对象（用于获取db会话）
    :param dianHua: 手机号
    :param password: 密码
    :return: 验证通过返回用户对象，否则返回None
    """
    try:
        # 从request中获取db会话（匹配你项目的db获取方式）
        db = request.state.db
        # 调用JWT的authenticate_user方法验证身份

        result = authenticate_user(db, dianHua, password)

        return result

    except Exception as e:
        raise LoginException(
            message=f"登录失败：{str(e)}",  # 友好的错误提示
            details={"error": str(e), "type": type(e).__name__}  # 错误详情（可选）
        )


async def get_current_user(request: Request, token: str):
    """
    获取当前登录用户（全量使用自定义异常，无原生HTTPException）
    :param request: 请求对象（用于取db会话）
    :param token: 前端传入的JWT Token
    :return: 验证通过的用户对象
    :raise TokenException/LoginException: Token相关异常（401）
    :raise SystemException: 系统异常（500）
    """
    try:
        # 1. 检查Redis黑名单（优先）
        if await is_token_blacklisted(token):  # 注意：is_token_in_blacklist是异步函数，需加await
            raise TokenException(
                message="Token已注销，无法使用,请重新登录",
                details={"token": token[:20] + "..." if token else None}  # 隐藏完整Token，避免泄露
            )

        # 2. 解析Token（调用core层工具）
        try:
            payload = decode_token(token)
        except JWTError as e:
            # JWT解析失败（过期/篡改/格式错误）→ 抛TokenException（401）
            raise TokenException(
                message=f"Token无效：{str(e)}",
                details={"error_type": "JWTError", "token": token[:20] + "..."}
            )

        # 3. 提取Token中的手机号
        phone: str = payload.get("sub")
        if not phone:
            raise TokenException(
                message="Token中未包含用户手机号",
                details={"payload": payload}
            )

        db = request.state.db

        # 5. 调用CRUD层查询用户
        user = get_user_by_phone(db, phone=phone)
        if not user:
            # 用户不存在 → 抛NotFoundException（404）或TokenException（401，推荐）
            # 注：为了安全，对外统一提示Token无效，不暴露用户不存在
            raise TokenException(
                message="Token无效，用户不存在",
                details={"phone": phone, "error": "用户未注册/已删除"}
            )

        # 6. 验证用户状态（未被逻辑删除）
        if user.del_flag:
            raise LoginException(
                message="用户已被删除，无法登录",
                details={"phone": phone, "gsyhId": user.gsyhId}
            )

        # 7. 验证通过，返回用户对象
        return user

    # 捕获并重新抛出自定义异常（保持原有异常信息）
    except (TokenException, LoginException, SystemException, NotFoundException) as e:
        raise e
    # 捕获所有未知异常 → 转为LoginException（401），避免暴露系统细节
    except Exception as e:
        raise LoginException(
            message=f"Token验证失败：{str(e)}",
            details={
                "error_type": type(e).__name__,
                "token": token[:20] + "..." if token else None,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None  # 调试模式返回堆栈
            }
        )


# 注销Token的service层逻辑（贴合你的分层）
async def revoke_token(request: Request, token: str):
    """将Token加入Redis黑名单"""

    try:
        # 解析Token剩余过期时间
        payload = decode_token(token)
        expire_timestamp = payload.get("exp")
        remaining_seconds = max(expire_timestamp - int(datetime.now().timestamp()), 60)

        # 调用Redis客户端（service层调用core层）
        await add_token_to_blacklist(token, remaining_seconds)
        return True
    except Exception as e:
        raise LoginException(message=f"注销失败：{str(e)}")



async def verify_access_token(request: Request, token: str) -> dict:
    """
    异步验证Access Token（仅查Redis，不查数据库，高性能）
    :param request: FastAPI Request对象（用于获取数据库会话，可选）
    :param token: Access Token字符串
    :return: Token信息字典（包含phone/token_type等）
    :raises TokenException/LoginException: Token无效/已注销/过期
    """
    try:
        # 1. 第一步：检查Token是否在黑名单（已注销）
        if await is_token_blacklisted(token):
            raise TokenException(
                message="Token已被注销，请重新登录",
                details={"token_status": "blacklisted"}
            )

        # 2. 第二步：从Redis查询Token是否有效（验证类型为access）
        token_info = await get_token(token, verify_type="access")
        if not token_info:
            raise TokenException(
                message="Access Token已过期或无效",
                details={"token_type": "access", "error": "token_not_found"}
            )

        # 3. 第三步：解析Token（验证签名+类型+手机号）
        try:
            payload = decode_token(token, verify_type="access")
        except JWTError as e:
            raise TokenException(
                message=f"Access Token解析失败：{str(e)}",
                details={"error": str(e)}
            )

        # 4. 第四步：验证Token中的手机号和Redis中一致（防止Token篡改）
        token_phone = payload.get("sub")
        redis_phone = token_info.get("phone")
        if not token_phone or token_phone != redis_phone:
            raise TokenException(
                message="Token用户信息不匹配",
                details={"token_phone": token_phone, "redis_phone": redis_phone}
            )

        # 返回Token信息（供上层使用）
        return token_info

    # 捕获自定义Token异常，直接抛出
    except TokenException as e:
        raise e
    # 捕获其他异常，封装为登录异常
    except Exception as e:
        raise LoginException(
            message=f"Access Token验证失败：{str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": str(e) if settings.debug else None
            }
        )

async def revoke_user_all_tokens(phone: str):
    """
    异步注销用户所有Token（批量删除Redis中的Access/Refresh Token，并加入黑名单）
    :param phone: 用户手机号
    :raises LoginException: 注销失败
    """
    try:
        # 调用Redis操作层的批量删除函数（核心逻辑）
        await delete_user_all_tokens(phone)
        return True
    except Exception as e:
        raise LoginException(
            message=f"注销用户Token失败：{str(e)}",
            details={
                "phone": phone,
                "error_type": type(e).__name__,
                "traceback": str(e) if settings.debug else None
            }
        )





