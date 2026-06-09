from fastapi import Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.services.user.user_service import get_current_user
from app.utils.exceptions import TokenException
from app.utils.redis.token import is_token_blacklisted, get_token

# 定义OAuth2认证方案（匹配前端传Token的方式）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/token", auto_error=False)


async def verify_login(
        request: Request,
        token: str = Depends(oauth2_scheme)
):
    """
    通用登录验证依赖：所有需要登录的接口都依赖这个函数
    验证逻辑：
    1. Token是否为空 → 抛未登录异常
    2. Token是否在黑名单 → 抛Token已注销异常
    3. Token是否存在/有效 → 抛Token无效异常
    4. 验证通过 → 返回当前用户信息
    """
    # 1. Token为空 → 未登录
    if not token:
        raise TokenException(
            message="请先登录",
            details={"error": "token is empty"}
        )

    # 2. 检查Token是否被拉黑（注销/刷新后拉黑）
    if await is_token_blacklisted(token):
        raise TokenException(
            message="Token已注销或过期，请重新登录",
            details={"token": token[:20]}
        )

    # 3. 验证Token有效性（获取Token详情+用户信息）
    try:
        # 获取Token详情（确保是有效的access_token）
        token_info = await get_token(token, verify_type="access")
        # get_token已调整为抛异常，无需判断None
        current_user = await get_current_user(request, token)
        return current_user
    except TokenException as e:
        # 复用Token异常，统一返回401
        raise e
    except Exception as e:
        # 其他异常包装为登录异常
        raise TokenException(
            message="Token验证失败，请重新登录",
            details={
                "token": token[:20],
                "error": str(e)
            }
        )


# 可选：封装无需登录的依赖（用于部分开放接口）
async def optional_login(
        request: Request,
        token: str = Depends(oauth2_scheme)
):
    """可选登录：有Token则验证，无Token则返回None"""
    if not token:
        return None
    try:
        return await verify_login(request, token)
    except:
        return None