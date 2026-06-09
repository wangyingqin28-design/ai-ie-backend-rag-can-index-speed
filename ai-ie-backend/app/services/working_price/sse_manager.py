import asyncio
import json
from typing import Dict, Set
from loguru import logger

from app.utils.exceptions import ValidationException


class SSEManager:
    def __init__(self, queue_maxsize: int = 10):
        if queue_maxsize <= 0:
            raise ValidationException("queue_maxsize 必须为正数")
        self.active_connections: Dict[int, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self.queue_maxsize = queue_maxsize   # 可配置的背压阈值

    async def connect(self, xbkhId: int) -> asyncio.Queue:
        """建立 SSE 连接，为款号创建一个有界队列"""
        queue = asyncio.Queue(maxsize=self.queue_maxsize)
        async with self._lock:
            self.active_connections.setdefault(xbkhId, set()).add(queue)
        logger.debug(f"SSE 连接建立: xbkhId={xbkhId}, 当前队列数={len(self.active_connections.get(xbkhId, []))}")
        return queue

    async def disconnect(self, xbkhId: int, queue: asyncio.Queue):
        """断开 SSE 连接，移除队列"""
        async with self._lock:
            if xbkhId in self.active_connections:
                self.active_connections[xbkhId].discard(queue)
                if not self.active_connections[xbkhId]:
                    del self.active_connections[xbkhId]
                    logger.debug(f"SSE 连接清理完毕: xbkhId={xbkhId}")
                else:
                    logger.debug(f"SSE 连接断开: xbkhId={xbkhId}, 剩余队列数={len(self.active_connections[xbkhId])}")

    async def broadcast(self, xbkhId: int, data: dict):
        """
        向指定款号的所有 SSE 客户端广播消息。
        使用非阻塞写入，队列满时丢弃消息，避免阻塞。
        """
        async with self._lock:
            if xbkhId not in self.active_connections:
                return
            # 拷贝队列列表，避免持锁执行 put_nowait
            queues = list(self.active_connections[xbkhId])
        if not queues:
            return
        message = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        dropped = 0
        for queue in queues:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                dropped += 1
            except Exception as e:
                logger.error(f"广播异常 (xbkhId={xbkhId}): {e}", exc_info=True)
                dropped += 1  # 视为丢弃，避免中断其他客户端
                # 可选：记录监控指标，例如 logger.debug 或 metrics counter
        if dropped and (dropped == len(queues) or dropped > 5):
            logger.warning(f"SSE 广播丢消息: xbkhId={xbkhId}, 丢弃数={dropped}/{len(queues)}")

# 全局单例，可配置 maxsize
sse_manager = SSEManager(queue_maxsize=10)   # 根据业务调整