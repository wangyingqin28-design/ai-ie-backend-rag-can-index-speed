
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm_models import AIGongSiYongHu
from app.schemas.user.user_schemas import AIGongSiYongHuRequest
from app.utils.auth.jwt_utils import pwd_context
from app.utils.exceptions import LoginException, NotFoundException, AppException
from app.utils.snowflake_generator import SnowFlake


def create_user(db: Session, aiGongSiYongHuRequest: AIGongSiYongHuRequest):
    """
    用户注册
    :param db: 数据库会话
    :param aiGongSiYongHuRequest: 用户注册信息请求对象
    """
    worker = SnowFlake()  # 雪花算法对象

    gsyhId = worker.generate_id()
    # 4. 构建用户对象
    new_aiGongSiYongHu = AIGongSiYongHu(
        gsyhId=gsyhId,  # 用户唯一ID
        yongHuXingMing=aiGongSiYongHuRequest.yongHuXingMing,  # 真实姓名
        xingBie=aiGongSiYongHuRequest.xingBie,  # 性别
        dianHua=aiGongSiYongHuRequest.dianHua,  # 手机号（登录标识）
        gsId=aiGongSiYongHuRequest.gsId,  # 所属公司ID
        del_flag=False,  # 未删除（逻辑删除标识）
        in_userid=gsyhId,  # 创建人与自己的主键id一致
        in_time=datetime.now(),  # 注册时间（插入时间）
        miMa=aiGongSiYongHuRequest.miMa  # 加密后的密码
    )

    # 5. 新增用户到数据库
    db.add(new_aiGongSiYongHu)


def query_user_by_dianHua(db: Session, dianHua: str) -> Optional[AIGongSiYongHu]:
    """
    根据手机号查找用户（返回对象/None，而非布尔值）
    :param db: 数据库会话
    :param dianHua: 注册手机号
    :return: 找到返回用户对象，没找到返回None
    """
    # 1. 空值拦截（避免无效查询）
    if not dianHua:
        return None

    # 2. 数据库查询：返回用户对象（找到）/None（没找到）
    aiGongsiYongHu = db.query(AIGongSiYongHu).filter(
        AIGongSiYongHu.dianHua == dianHua,
        AIGongSiYongHu.del_flag == False
    ).first()

    return aiGongsiYongHu


def authenticate_user(db: Session, dianHua: str, password: str) -> AIGongSiYongHu:
    """
    认证用户（手机号+密码）
    :param db: 数据库会话
    :param dianHua: 用户手机号
    :param password: 用户明文密码
    :return: 认证成功返回用户对象
    :raise LoginException: 业务异常（参数错误/用户不存在/密码错误）
    :raise SystemException: 系统异常（数据库查询失败）
    """
    # ==========  处理已知业务逻辑：参数校验 ==========
    if not dianHua or not password:
        raise LoginException(
            message="手机号或密码不能为空",
            details={"dianHua": dianHua, "error": "参数为空"}
        )

    # ========== 处理不可预见的系统异常：数据库查询（try兜底） ==========
    try:
        user = query_user_by_dianHua(db, dianHua)  # 可能抛数据库异常（连接失败/超时）
    except Exception as e:
        # 只捕获数据库查询的系统异常
        raise NotFoundException(
            message="用户信息查询失败",
            details={
                "error_type": type(e).__name__,
                "error_msg": str(e),
                "dianHua": dianHua
            }
        )

    # ========== 处理已知业务逻辑：身份验证 ==========
    # 3.1 用户不存在 → 业务异常
    if not user:
        raise LoginException(
            message="手机号或密码错误",  # 对外统一提示，避免暴露用户存在性
            details={"dianHua": dianHua, "error": "用户不存在"}
        )
    # 3.2 密码错误 → 业务异常
    if not verify_password(password, user.miMa):#此时的user.miMa已经是数据库里面的加过密的密码
        raise LoginException(
            message="手机号或密码错误",  # 对外统一提示
            details={"dianHua": dianHua, "error": "密码错误"}
        )

    # ========== 认证成功,返回用户对象 ==========
    return user


def get_user_by_phone(db, phone: str) -> Optional[AIGongSiYongHu]:
    """查询用户：直接使用你中间件的db，逻辑不变"""
    return db.query(AIGongSiYongHu).filter(
        AIGongSiYongHu.dianHua == phone,
        AIGongSiYongHu.del_flag == False
    ).first()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码（登录时用）"""
    if not plain_password or not hashed_password:
        return False
    try:
        # 验证：自动识别哈希算法（前提是哈希格式正确）
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        # 捕获哈希识别失败的异常，便于排查

        import logging
        logging.error(f"密码验证失败：{e}, 哈希值：{hashed_password[:20]}...")  # 只打印前20位，避免泄露
        return False


def get_gsId_by_userid(db, userid: int) -> Optional[int]:
    """根据用户ID查找到所属公司ID"""
    try:
        user = db.query(AIGongSiYongHu).filter(
            AIGongSiYongHu.gsyhId == userid
        ).first()

        return user.gsId if user else 0

    except Exception as e:
        # 记录日志
        raise AppException(
            code=500,
            message="查询用户公司ID失败: {e}"
        )


















