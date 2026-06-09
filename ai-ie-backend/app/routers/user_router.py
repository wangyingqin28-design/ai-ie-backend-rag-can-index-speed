import traceback
from datetime import timedelta

from fastapi import APIRouter, Request, Body, Depends
from loguru import logger

from app.config import settings
from app.schemas.user.user_schemas import AIGongSiYongHuRequest, LoginRequest
from app.services.user.user_crud import get_user_by_phone
from app.services.user.user_service import login_verify, check_phone_exists, register, revoke_token, get_current_user, \
    verify_access_token, revoke_user_all_tokens
from app.utils.auth import jwt_utils
from app.utils.auth.jwt_utils import ACCESS_TOKEN_EXPIRE_MINUTES, \
    create_access_token, oauth2_scheme, create_tokens_pair, REFRESH_TOKEN_EXPIRE_DAYS
from app.utils.auth.login_dependencies import verify_login
from app.utils.exceptions import AppException, UserCreateException, LoginException, TokenException
from app.utils.redis.redis_utils import redis_smembers, redis_delete, redis_srem
from app.utils.redis.token import save_token, get_token, add_token_to_blacklist, USER_TOKENS_PREFIX, TOKEN_PREFIX
from app.utils.response import Success

router = APIRouter(
    prefix="/user",
    tags=["用户管理"],
    responses={404: {"description": "Not found"}},
)




@router.post("/token", summary="用户登录接口")
async def login_for_access_token(
        request: Request,
        loginRequest: LoginRequest = Body(...,description="登录请求对象")
):
    """
    用户登录核心接口
    流程：1. 校验用户身份 → 2. 生成JWT Token → 3. 返回登录结果
    """
    request.state.read_only = True

    try:
        # 调用业务逻辑层验证用户
        user = login_verify(request, loginRequest.dianHua, loginRequest.miMa)

        if not user:
            raise LoginException(
                message="手机号或密码错误",
                details={"dianHua": loginRequest.dianHua, "error": "身份验证失败"}
            )

        # 2. 生成双Token（Access Token + Refresh Token）
        access_token, refresh_token = create_tokens_pair(user.dianHua)

        # 3. 异步存入Redis（核心：双Token都要存）
        await save_token(
            token=access_token,
            phone=user.dianHua,
            token_type="access"
        )
        await save_token(
            token=refresh_token,
            phone=user.dianHua,
            token_type="refresh"
        )

        # 4. 统一返回格式（包含双Token+过期时间）
        return Success(
            msg="登录成功",
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "access_token_expires_minutes": jwt_utils.ACCESS_TOKEN_EXPIRE_MINUTES,
                "refresh_token_expires_days": jwt_utils.REFRESH_TOKEN_EXPIRE_DAYS,
                "user_info": {
                    "dianHua": user.dianHua,
                    "yongHuXingMing": getattr(user, "yongHuXingMing", "")  # 可选返回用户昵称
                }
            }
        )

    # 捕获其他自定义业务异常
    except AppException as e:
        raise e
    # 捕获所有未知异常
    except Exception as e:
        raise LoginException(
            message=f"用户登录失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None,
                "phone": loginRequest.dianHua
            }
        )


@router.post("/register",summary="用户注册接口")
async def user_register(
        request: Request,
        aiGongSiYongHu: AIGongSiYongHuRequest = Body(..., description="用户参数请求对象")
):
    """
    用户注册核心接口
    """
    try:
        # 1. 校验手机号是否已存在(调用业务逻辑层方法)（防止重复注册）
        if check_phone_exists(request,aiGongSiYongHu.dianHua):
            raise UserCreateException(message="该手机号已注册，请直接登录",details={"dianHua":aiGongSiYongHu.dianHua,"error":"手机号已存在"})

        register(request, aiGongSiYongHu)

        return Success(msg="用户注册成功")

    # 捕获所有自定义业务异常（已登记的异常）
    except AppException as e:
        raise e
        # 捕获所有未知异常
    except Exception as e:
        # 抛自定义解析异常，或直接让global_exception_handler捕获
        raise UserCreateException(
            message=f"用户注册失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )


@router.post("/logout", summary="用户注销（Token失效）")
async def user_logout(
        request: Request,
        token: str = Depends(oauth2_scheme)
):
    """
    用户注销接口：批量失效该用户所有Token
    流程：1. 验证Token → 2. 批量删除Redis Token → 3. 返回结果
    """
    try:
        # 1. 验证Token（兼容Access/Refresh Token）
        try:
            # 先尝试验证为Refresh Token（查库）
            current_user = await get_current_user(request, token)
        except:
            # 验证为Access Token（仅查Redis）
            token_info = await verify_access_token(request, token)
            phone = token_info["phone"]
            # 查库获取用户信息（可选）
            db = request.state.db

            current_user = get_user_by_phone(db, phone=phone)

        # 2. 批量注销该用户所有Token（异步Redis操作）
        await revoke_user_all_tokens(current_user.dianHua)

        # 3. 返回结果
        return Success(
            msg="注销成功",
            data={
                "dianHua": current_user.dianHua,
                "msg": "所有Token已失效，需重新登录"
            }
        )

    except AppException as e:
        raise e
    except Exception as e:
        # 兼容current_user未定义的情况
        phone = getattr(current_user, "dianHua", None) if 'current_user' in locals() else None
        raise LoginException(
            message=f"注销失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None,
                "phone": phone
            }
        )

@router.post("/refresh-token", summary="刷新Access Token")
async def refresh_access_token(
        request: Request,
        token: str = Depends(oauth2_scheme)  # 这里的token是Refresh Token
):
    """
    用Refresh Token刷新Access Token（修复版）
    核心：正确识别并拉黑旧Access Token，从集合中移除
    """
    try:
        # 1. 验证Refresh Token（查Redis+数据库）
        current_user = await get_current_user(request, token)
        phone = current_user.dianHua
        user_tokens_key = f"{USER_TOKENS_PREFIX}{phone}:tokens"

        # 2. 获取用户所有Token集合（包含Access+Refresh）
        all_old_tokens = await redis_smembers(user_tokens_key)
        #print(f"用户{phone}所有旧Token：{all_old_tokens}")

        # 3. 生成新的Access Token
        new_access_token = create_access_token(
            data={"sub": phone, "type": "access"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        # 4. 存入新Access Token到Redis（包含加入集合）
        await save_token(
            token=new_access_token,
            phone=phone,
            token_type="access"
        )

        # 5. 处理旧Access Token（核心修复）
        processed_old_tokens = []
        failed_old_tokens = []
        for old_token in all_old_tokens:
            try:
                # 跳过新生成的Token（避免误处理）
                if old_token == new_access_token:
                    continue

                # 调用get_token（已调整为抛异常），捕获Token不存在的情况
                try:
                    old_token_info = await get_token(old_token)
                except TokenException as e:
                    # Token已不存在/过期，直接从集合中移除
                    await redis_srem(user_tokens_key, old_token)
                    failed_old_tokens.append({"token": old_token[:20], "reason": str(e)})
                    continue

                # 关键修复：字段名改为token_type
                if old_token_info and old_token_info.get("token_type") == "access":
                    # 5.1 拉黑旧Access Token（5分钟过期）
                    await add_token_to_blacklist(old_token, 60 * 1)
                    # 5.2 删除旧Token详情
                    await redis_delete(f"{TOKEN_PREFIX}{old_token}")
                    # 5.3 从用户Token集合中移除旧Token
                    await redis_srem(user_tokens_key, old_token)
                    processed_old_tokens.append(old_token[:20])

            except Exception as e:
                failed_old_tokens.append({"token": old_token[:20], "reason": str(e)})

        # 打印处理结果（便于调试）
        logger.info(f"成功拉黑并删除的旧Access Token：{processed_old_tokens}")
        logger.info(f"处理失败的旧Token：{failed_old_tokens}")

        # 6. 返回结果
        return Success(
            msg="Token刷新成功",
            data={
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
                "processed_old_tokens": processed_old_tokens,  # 可选：返回处理的旧Token列表
                "failed_old_tokens": failed_old_tokens if settings.debug else []  # 调试模式返回失败列表
            }
        )

    except AppException as e:
        raise e
    except Exception as e:
        raise LoginException(
            message=f"Token刷新失败: {str(e)}",
            details={
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc().split("\n") if settings.debug else None
            }
        )


@router.get("/info", summary="获取当前用户信息")
async def get_user_info(
    request: Request,
    current_user = Depends(verify_login)  # 接入登录验证
):
    request.state.read_only = True

    # current_user 是验证通过后的用户对象，可直接使用
    return Success(
        msg="获取用户信息成功",
        data={
            "phone": current_user.dianHua,
            "name": current_user.yongHuXingMing,
        }
    )


