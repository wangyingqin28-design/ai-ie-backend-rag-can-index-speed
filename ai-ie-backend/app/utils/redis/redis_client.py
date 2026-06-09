"""
异步Redis客户端配置
基于项目统一的Config类，使用已有Redis配置
"""
from contextlib import asynccontextmanager

from loguru import logger
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import ConnectionError as RedisConnectionError

# 导入项目统一的settings配置
from app.config import settings



# ===================== 单例异步Redis客户端 =====================
class AsyncRedisClient:
    """
    异步Redis客户端（单例模式）
    支持不同数据库编号：
    - db=1: memory_redis_url（缓存/Token）
    - db=2: celery_broker_url（Celery消息队列）
    - db=3: celery_result_backend（Celery结果存储）
    """
    _instances: dict[int, AsyncRedis] = {}  # 按db编号存储实例

    @classmethod
    async def get_client(cls, db: int = 1) -> AsyncRedis:
        """
        获取异步Redis客户端实例
        :param db: Redis数据库编号（1=缓存/Token，2=Celery Broker，3=Celery Result）
        :return: 异步Redis客户端
        """
        if db not in cls._instances:
            # 根据db编号获取对应的Redis URL（复用settings中已生成的URL）
            if db == 1:
                redis_url = settings.memory_redis_url
            elif db == 2:
                redis_url = settings.celery_broker_url
            elif db == 3:
                redis_url = settings.celery_result_backend
            elif db == 4:  # minio裁片图片文件URL专用DB配置
                redis_url = (
                    f"redis://{settings.redis_user}:{settings.redis_password}"
                    f"@{settings.redis_host}:{settings.redis_port}/4"
                )
            else:
                # 自定义db：基于settings的基础配置拼接URL
                redis_url = (
                    f"redis://{settings.redis_user}:{settings.redis_password}"
                    f"@{settings.redis_host}:{settings.redis_port}/{db}"
                )

            # 创建异步Redis客户端
            cls._instances[db] = AsyncRedis.from_url(
                redis_url,
                decode_responses=True,  # 自动将bytes转为字符串，避免b'xxx'
                socket_timeout=5,       # 连接超时5秒
                socket_connect_timeout=5,
                retry_on_timeout=True,  # 超时重试
                max_connections=100     # 连接池最大连接数
            )

            # 验证连接
            try:
                await cls._instances[db].ping()
                logger.info(f"Redis {db} 库连接成功（URL: {redis_url}）")
            except RedisConnectionError as e:
                raise RedisConnectionError(f"Redis {db} 库连接失败：{str(e)}")

        return cls._instances[db]

# ===================== FastAPI 异步依赖（核心） =====================
@asynccontextmanager
async def get_async_redis(db: int = 1):
    """
    FastAPI专用异步依赖：获取Redis客户端
    使用方式：redis_client = Depends(get_async_redis)
    :param db: 数据库编号（默认1=缓存/Token）
    """
    client = await AsyncRedisClient.get_client(db)
    try:
        yield client
    finally:
        # 释放连接（连接池复用，非真正关闭）
        await client.close()


