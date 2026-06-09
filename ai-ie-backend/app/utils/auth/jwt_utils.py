"""
JWT登录和权限校验模块
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Annotated, Optional, Tuple

from fastapi import Depends  # 新增Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

# ====================== 1. 配置读取（不变） ======================
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))  # Refresh Token配置

# ====================== 2. 密码加密工具（不变） ======================
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],  # 替换为pbkdf2_sha256算法
    default="pbkdf2_sha256",
    pbkdf2_sha256__default_rounds=300000  # 加密轮数（越高越安全，30万轮是标准）
)

def get_password_hash(password: str) -> str:
    """生成密码哈希（注册/改密时用）"""
    if not password:
        raise ValueError("密码不能为空")
    return pwd_context.hash(password)  # 生成pbkdf2_sha256格式的哈希

# ====================== 3. OAuth2配置 ======================
# OAuth2密码模式：前端传Token的请求头格式 → Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/user/token",  # 登录接口地址（仅用于文档）
    auto_error=False,  # 不自动返回401，由我们自己的代码处理
    scheme_name="JWT Token"  # 自定义名称，Swagger里更清晰
)

# Token依赖项：用于接口层提取Token
TOKEN_DEPENDENCY = Annotated[str, Depends(oauth2_scheme)]


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成Token：逻辑不变"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now()+ expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_tokens_pair(phone: str) -> Tuple[str, str]:
    """生成Access Token + Refresh Token 对（核心新增）"""
    # 1. 生成Access Token（15分钟，标记type=access）
    access_token = create_access_token(
        data={"sub": phone, "type": "access"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # 2. 生成Refresh Token（7天，标记type=refresh）
    refresh_token = create_access_token(
        data={"sub": phone, "type": "refresh"},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    return access_token, refresh_token


def decode_token(token: str, verify_type: Optional[str] = None) -> dict:
    """
    解析Token并验证有效性
    :param token: JWT Token字符串
    :param verify_type: 验证Token类型（access/refresh），None=不验证
    :return: Token载荷（payload）
    :raises JWTError: Token无效/过期/类型错误
    """
    try:
        # 解析Token（自动验证签名+过期时间）
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": True}  # 强制验证过期时间
        )

        # 验证Token类型（防止Refresh Token被用作Access Token）
        if verify_type and payload.get("type") != verify_type:
            raise JWTError(f"Token类型错误，预期：{verify_type}，实际：{payload.get('type')}")

        # 验证手机号存在
        phone: str = payload.get("sub")
        if not phone:
            raise JWTError("Token中无用户手机号（sub字段缺失）")

        return payload
    except JWTError as e:
        logging.error(f"Token解析失败：{str(e)}")
        raise  # 抛出异常，由上层捕获处理
