"""core/redis/base.py：通用Redis异步操作（所有业务复用）"""
import json
from datetime import datetime
from typing import Any, Optional

from app.utils.redis.redis_client import AsyncRedisClient

class RedisDBConfig:
    """Redis数据库编号配置（按业务隔离）"""
    TOKEN = 1               # Token/用户认证缓存
    CELERY_BROKER = 2       # Celery消息队列
    CELERY_RESULT = 3       # Celery结果存储
    FILE_URL = 4            # 文件/图片URL缓存
    DEFAULT = TOKEN         # 默认DB（保持原有Token默认）\
    PAGE_DROPDOWN = 5       #网页下拉栏缓存

# 快捷常量（兼容原有代码）
DEFAULT_DB = RedisDBConfig.TOKEN
FILE_URL_DB = RedisDBConfig.FILE_URL
PAGE_DROPDOWN = RedisDBConfig.PAGE_DROPDOWN

async def redis_set(
    key: str,
    value: Any,
    expire_seconds: Optional[int] = None,
    db: int = DEFAULT_DB
):
    """异步设置Redis键值对（自动JSON序列化）"""
    client = await AsyncRedisClient.get_client(db)
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    await client.set(key, value, ex=expire_seconds)

async def redis_get(
    key: str,
    db: int = DEFAULT_DB,
    parse_json: bool = True
) -> Optional[Any]:
    """异步获取Redis值（自动JSON反序列化）"""
    client = await AsyncRedisClient.get_client(db)
    value = await client.get(key)
    if value and parse_json:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value

async def redis_delete(key: str, db: int = DEFAULT_DB):
    """异步删除Redis键"""
    client = await AsyncRedisClient.get_client(db)
    await client.delete(key)

async def redis_sadd(key: str, *members, db: int = DEFAULT_DB):
    """异步添加集合元素"""
    client = await AsyncRedisClient.get_client(db)
    await client.sadd(key, *members)

async def redis_smembers(key: str, db: int = DEFAULT_DB):
    """异步获取集合所有元素"""
    client = await AsyncRedisClient.get_client(db)
    return await client.smembers(key)

async def redis_expire(key: str, expire_seconds: int, db: int = DEFAULT_DB):
    """异步设置键过期时间"""
    client = await AsyncRedisClient.get_client(db)
    await client.expire(key, expire_seconds)

async def redis_persist(key: str, db: int = DEFAULT_DB):
    """
    异步移除Redis键的过期时间（使其永久存在）
    防止用户-Token集合被提前过期删除的问题
    """
    client = await AsyncRedisClient.get_client(db)
    return await client.persist(key)

async def redis_exists(key: str, db: int = DEFAULT_DB):
    """
    异步检查Redis Key是否存在
    """
    client = await AsyncRedisClient.get_client(db)
    exists = await client.exists(key)
    return exists > 0

async def redis_srem(key: str, *members, db: int = DEFAULT_DB):
    """异步从集合中移除元素"""
    client = await AsyncRedisClient.get_client(db)
    await client.srem(key, *members)

def to_redis_str(value):
    """
    健壮的Redis字符串转换函数，处理所有类型和None值
    """
    if value is None:
        return ""
    elif isinstance(value, (int, float, bool)):
        return str(value)
    elif isinstance(value, str):
        return value.strip() if value.strip() else ""
    elif isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return str(value)

def from_redis_str(value, target_type):
    """从Redis字符串转回目标类型"""
    if value == "" or value is None:
        return None if target_type in (int, bool, str) else ""
    elif target_type == bool:
        return value == "1"
    elif target_type == int:
        return int(value)
    elif target_type == str:
        return str(value)
    else:
        return value