"""core/redis/token.py：Token场景专用Redis操作"""
from datetime import datetime
from typing import Optional, Dict, Any, Set

from app.utils.auth.jwt_utils import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from app.utils.exceptions import TokenException, DeleteFailedException, SystemException
from app.utils.redis.redis_utils import redis_set, redis_sadd, redis_get, redis_delete, redis_smembers, \
    redis_persist, redis_exists

# Token相关Key前缀
TOKEN_PREFIX = "user:token:"
USER_TOKENS_PREFIX = "user:phone:"
BLACKLIST_PREFIX = "blacklist:token:"


async def save_token(
        token: str,
        phone: str,
        token_type: str = "access",  # access/refresh
        expire_minutes: int = None
):
    """
    保存Token到Redis（Token详情+用户-Token映射）
    """
    # 1. 确定过期时间
    final_expire_minutes = expire_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    if token_type == "refresh":
        final_expire_minutes = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60
    expire_seconds = final_expire_minutes * 60

    # 2. 存储Token详情
    token_key = f"{TOKEN_PREFIX}{token}"
    token_info: Dict[str, Any] = {
        "phone": phone,
        "token_type": token_type,
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expire_minutes": final_expire_minutes,
        "status": "active"
    }
    await redis_set(token_key, token_info, expire_seconds)

    # 3. 维护用户-Token映射（集合）
    user_tokens_key = f"{USER_TOKENS_PREFIX}{phone}:tokens"
    await redis_sadd(user_tokens_key, token)
    await redis_persist(user_tokens_key)  # 确保集合永久存在，防止被提前删除


async def get_token(token: str, verify_type: Optional[str] = None) -> Dict[str, Any]:
    """
    获取Token详情（验证类型）
    调整逻辑：Token不存在/类型不匹配抛TokenException，不再返回None
    """
    # 1. 防御性校验：Token为空直接抛异常
    if not token:
        raise TokenException(
            message="Token参数为空，无法获取详情",
            details={"token": token, "verify_type": verify_type}
        )

    token_key = f"{TOKEN_PREFIX}{token}"

    try:
        # 2. 从Redis获取Token详情
        token_info = await redis_get(token_key)

        # 3. Token不存在 → 抛TokenException
        if not token_info:
            raise TokenException(
                message="Token不存在或已过期",
                details={
                    "token": token[:20],
                    "verify_type": verify_type,
                    "token_key": token_key
                }
            )

        # 4. Token类型不匹配 → 抛TokenException（核心调整）
        if verify_type and token_info.get("token_type") != verify_type:
            raise TokenException(
                message=f"Token类型不匹配，预期{verify_type}，实际{token_info.get('token_type')}",
                details={
                    "token": token[:20],
                    "verify_type": verify_type,
                    "actual_type": token_info.get("token_type"),
                    "token_key": token_key
                }
            )

        # 5. 校验通过 → 返回Token详情（不再返回None）
        return token_info

    except TokenException:
        # 捕获所有Token业务异常，直接重新抛出
        raise
    except Exception as e:
        # 捕获Redis操作异常，包装为系统异常
        raise SystemException(
            message="获取Token详情系统异常",
            details={
                "token": token[:20],  # 脱敏：仅保留前20位
                "verify_type": verify_type,
                "token_key": token_key,
                "error": str(e)
            }
        )


async def delete_token(token: str):
    """删除单个Token详情（抛出自定义异常）"""
    try:
        token_key = f"{TOKEN_PREFIX}{token}"
        await redis_delete(token_key)
    except Exception as e:
        raise DeleteFailedException(
            message=f"删除Token详情失败",
            details={"token": token[:20], "error": str(e)}
        )


async def delete_user_all_tokens(phone: str):
    """
    批量删除用户所有Token（仅抛出自定义异常，无日志）
    """
    # 1. 定义核心Key
    user_tokens_key = f"{USER_TOKENS_PREFIX}{phone}:tokens"

    try:
        # 2. 防御性校验：集合不存在则抛出异常（按需选择，也可直接返回）
        if not await redis_exists(user_tokens_key):
            raise TokenException(
                message="用户Token集合不存在，无需注销",
                details={"phone": phone, "user_tokens_key": user_tokens_key}
            )

        # 3. 获取用户所有Token
        tokens: Set[str] = await redis_smembers(user_tokens_key)
        if not tokens:
            # 无Token可处理，直接删除空集合后返回（不抛异常）
            await redis_delete(user_tokens_key)
            return

        # 4. 遍历处理Token（单个失败则整体抛出异常）
        for token in tokens:
            await delete_token(token)
            await add_token_to_blacklist(token, 60 * 1)  # 黑名单保留1分钟

        # 5. 删除用户-Token映射
        delete_result = await redis_delete(user_tokens_key)
        if delete_result == 0:
            # 删除集合失败时抛出异常
            raise DeleteFailedException(
                message="删除用户Token映射集合失败",
                details={"phone": phone, "user_tokens_key": user_tokens_key}
            )

    except (DeleteFailedException, TokenException):
        # 捕获业务异常，直接重新抛出
        raise
    except Exception as e:
        # 捕获系统异常，包装为自定义系统异常
        raise SystemException(
            message="批量注销用户Token系统异常",
            details={"phone": phone, "error": str(e)}
        )


async def add_token_to_blacklist(token: str, expire_seconds: int):
    """添加Token到黑名单（抛出自定义异常）"""
    try:
        blacklist_key = f"{BLACKLIST_PREFIX}{token}"
        await redis_set(blacklist_key, "invalid", expire_seconds)
    except Exception as e:
        raise TokenException(
            message=f"Token加入黑名单失败",
            details={"token": token[:20], "error": str(e)}
        )


async def is_token_blacklisted(token: str) -> bool:
    """
    检查Token是否在黑名单
    """
    # 1. 防御性参数校验：Token为空直接抛异常
    if not token:
        raise TokenException(
            message="Token参数为空，无法检查黑名单状态",
            details={"token": token}
        )

    blacklist_key = f"{BLACKLIST_PREFIX}{token}"

    try:
        # 2. 从Redis查询黑名单状态（原有核心逻辑）
        blacklist_value = await redis_get(blacklist_key)

        # 3. 原有返回逻辑：存在则返回True，否则返回False
        return blacklist_value is not None

    except TokenException:
        # 捕获参数校验抛出的Token异常，直接重新抛出
        raise
    except Exception as e:
        # 捕获Redis操作异常（连接超时/权限不足等），包装为系统异常
        raise SystemException(
            message="检查Token黑名单状态系统异常",
            details={
                "token": token[:20],  # 脱敏：仅保留前20位
                "blacklist_key": blacklist_key,
                "error": str(e)
            }
        )