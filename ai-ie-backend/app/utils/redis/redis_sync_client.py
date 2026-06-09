"""Redis同步客户端（适配SQL Server同步架构）"""
from typing import Any
import json
import redis
from loguru import logger

from app.config import settings
from app.utils.redis.redis_utils import DEFAULT_DB, FILE_URL_DB, PAGE_DROPDOWN


class SyncRedisClient:
    """Redis同步客户端（单例模式，避免重复创建连接）"""
    _instances: dict[int, redis.Redis] = {}

    @classmethod
    def get_client(cls, db: int = DEFAULT_DB) -> redis.Redis:
        """获取指定DB的Redis同步客户端"""
        if db not in cls._instances:
            try:
                # 构建Redis连接参数
                client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    username=settings.redis_user,
                    password=settings.redis_password,
                    db=db,
                    decode_responses=True,  # 自动解码为字符串
                    socket_timeout=5,        # 连接超时5秒
                    socket_connect_timeout=5,
                    retry_on_timeout=True,   # 超时重试
                    health_check_interval=30  # 健康检查间隔
                )
                # 验证连接
                client.ping()
                cls._instances[db] = client
                logger.info(f"Redis同步客户端连接成功（DB={db}）")
            except redis.RedisError as e:
                logger.error(f"Redis同步客户端连接失败（DB={db}）：{str(e)}")
                raise

        return cls._instances[db]

# ------------------------------
# 同步Redis操作封装（直接调用）
# ------------------------------
def redis_sadd_sync(key: str, *values: Any, db: int = DEFAULT_DB) -> int:
    """同步执行SADD：向集合添加元素（自动去重）"""
    client = SyncRedisClient.get_client(db)
    return client.sadd(key, *values)

def redis_expire_sync(key: str, seconds: int, db: int = DEFAULT_DB) -> bool:
    """同步执行EXPIRE：设置Key过期时间"""
    client = SyncRedisClient.get_client(db)
    return client.expire(key, seconds)

def redis_smembers_sync(key: str, db: int = DEFAULT_DB) -> set:
    """同步执行SMEMBERS：获取集合所有元素"""
    client = SyncRedisClient.get_client(db)
    return client.smembers(key)

def redis_delete_sync(key: str, db: int = DEFAULT_DB) -> int:
    """同步执行DEL：删除指定Key"""
    client = SyncRedisClient.get_client(db)
    return client.delete(key)

def redis_hmset_sync(key: str, mapping: dict, db: int = DEFAULT_DB) -> bool:
    """同步执行HMSET：批量设置Hash字段"""
    client = SyncRedisClient.get_client(db)
    return client.hmset(key, mapping)

def redis_hgetall_sync(key: str, db: int = DEFAULT_DB) -> dict:
    """同步执行HGETALL：获取Hash所有字段"""
    client = SyncRedisClient.get_client(db)
    return client.hgetall(key)

def redis_hget_sync(key: str, field: str, db: int = DEFAULT_DB) -> str:
    """同步执行HGET：获取Hash单个字段"""
    client = SyncRedisClient.get_client(db)
    return client.hget(key, field)

def redis_rpush_sync(key: str, *values, db: int):
    """
    同步向Redis List尾部追加元素
    :param key: Redis键名
    :param values: 要追加的元素（可变参数）
    :param db: 数据库编号
    """
    try:
        if not values:
            return

        client = SyncRedisClient.get_client(db)

        client.select(db)
        client.rpush(key, *values)
    except Exception as e:
        logger.error(f"Redis写入List失败 | key={key} | error={str(e)}", exc_info=True)


def redis_lrange_sync(key: str, start: int, end: int, db: int) -> list:
    """
    同步读取Redis List指定范围的元素（兼容你的项目工具函数风格）
    :param key: Redis键名（如 dxf:pieces:order:1330392414380320）
    :param start: 起始索引（0表示第一个元素，-1表示最后一个元素）
    :param end: 结束索引（-1表示读取所有元素）
    :param db: Redis数据库编号（对应你的 FILE_URL_DB）
    :return: List[str] - 返回Redis List中的元素列表（元素为字符串类型）
    """
    try:
        # 1. 切换到指定的Redis数据库
        client = SyncRedisClient.get_client(db)

        # 2. 执行LRANGE命令读取列表元素（Redis原生命令）
        # 返回值：列表中的元素，每个元素都是字符串类型（对应你存储的xbcpId字符串）
        result = client.lrange(key, start, end)

        # 3. 兼容Redis客户端返回的字节串（部分客户端会返回bytes，需转为str）
        # 例如：b'1330392414380321' → '1330392414380321'
        str_result = []
        for item in result:
            if isinstance(item, bytes):
                str_result.append(item.decode('utf-8'))
            else:
                str_result.append(str(item))

        logger.debug(f"Redis LRANGE成功 | key={key} | start={start} | end={end} | 元素数={len(str_result)}")
        return str_result

    except Exception as e:
        # 捕获所有异常，记录日志并返回空列表（避免业务逻辑中断）
        logger.error(f"Redis LRANGE失败 | key={key} | start={start} | end={end} | db={db} | error={str(e)}",
                     exc_info=True)
        return []
def redis_set_sync(key: str, value: Any, ex: int = None,db:int =PAGE_DROPDOWN) -> bool:
    """
    同步执行SET:存储String类型数据（支持过期时间）
    """
    try:
        client = SyncRedisClient.get_client(db)
        #序列化为JSON字符串，确保中文不转义、兼容复杂类型
        json_value = json.dumps(value,ensure_ascii=False)
        return client.set(key, json_value, ex=ex)
    except redis.RedisError as e:
        logger.error(f"Redis SET失败 | key={key} | error={str(e)}", exc_info=True)
        raise
def redis_get_sync(key: str, db: int =PAGE_DROPDOWN) -> Any|None:
    """
    同步执行GET：获取String类型数据（自动反序列化为原类型）
    """
    try:
        client = SyncRedisClient.get_client(db)
        value = client.get(key)
        if value is None:
            return None
        #反序列化为原Python类型（列表/字典）
        return json.loads(value)
    except redis.RedisError as e:
        logger.error(f"Redis GET失败 | key={key} | error={str(e)}", exc_info=True)
        raise
