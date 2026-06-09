# app/services/kafka_consumer.py
import json
import asyncio
from typing import Dict, Any
from aiokafka import AIOKafkaConsumer
from loguru import logger
from app.services.working_price.quote_calculation_service import QuoteCalculationService
from app.services.working_price.sse_manager import sse_manager
from app.utils.exceptions import AppException,ServiceCallException



class GongJiaChangeConsumer:
    """Kafka 消费者，监听公司工价表变更，调用 Service 处理业务逻辑并推送 SSE"""

    def __init__(self, bootstrap_servers: str, topic: str, group_id: str):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.consumer = None
        self.quote_service = QuoteCalculationService()   # 使用报价服务

    async def start(self):
        """启动消费者"""
        try:
            logger.info(f"准备连接 Kafka: {self.bootstrap_servers}, topic={self.topic}")
            self.consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                value_deserializer=lambda v: json.loads(v.decode('utf-8'))
            )
            await self.consumer.start()
            logger.info(f"Kafka 消费者已启动: topic={self.topic}, group={self.group_id}")
        except Exception as e:
            logger.exception("Kafka 消费者启动失败")
            raise

        try:
            async for msg in self.consumer:
                try:
                    await self._process_message(msg.value)
                except Exception as e:
                    logger.exception(f"消费消息时发生异常，消息已跳过: {e}")
                    # 继续处理下一条，不中断循环
        except asyncio.CancelledError:
            logger.info("Kafka 消费者任务被取消")
        except AppException:
            raise
        except Exception as e:
            logger.exception(f"Kafka 消费者循环致命错误: {e}")
            raise AppException(
                code=500,
                message=f"Kafka 消费者循环致命错误: {e}",
            )
        finally:
            await self._stop()

    async def _stop(self):
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka 消费者已停止")

    async def _process_message(self, msg_value: Dict[str, Any]):
        """处理单条 CDC 消息（区分可重试与不可重试异常）"""
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                await self._do_process_message(msg_value)
                break  # 成功，退出重试
            except ServiceCallException as e:
                # 可重试异常：记录警告，指数退避后重试
                logger.warning(
                    f"可重试错误，尝试 {attempt}/{max_retries}，错误: {e}, 消息: {msg_value}"
                )
                if attempt == max_retries:
                    logger.error(f"重试 {max_retries} 次仍失败，消息丢弃: {msg_value}")
                    # 可选：发送到死信队列
                    return  # 直接返回，不再抛出异常
                await asyncio.sleep(2 ** attempt)  # 2,4,8 秒
            except AppException:
                raise
            except Exception as e:
                # 不可重试异常：直接记录错误，丢弃消息，不重试
                logger.error(f"不可重试错误，消息丢弃: {e}, 消息内容: {msg_value}")
                raise AppException(
                    code=500,
                    message="kafka_consumer:_process_message_failed",
                    details={"original_error": str(e), "msg_value": msg_value}
                )

    async def _do_process_message(self, msg_value: Dict[str, Any]):
        """实际处理逻辑（无重试）"""
        payload = msg_value.get('payload', {})
        op = payload.get('op')
        if op != 'u':
            return

        after = payload.get('after')
        if not after:
            return

        gs_id = after.get('gsId')
        xbgz_id = after.get('xbgzId')
        new_gongjia = after.get('gongJia')
        if not gs_id or not xbgz_id or new_gongjia is None:
            logger.debug(f"消息缺少必要字段: gsId={gs_id}, xbgzId={xbgz_id}, gongJia={new_gongjia}")
            return

        logger.info(f"检测到工价变化: gsId={gs_id}, xbgzId={xbgz_id}, 新工价={new_gongjia}")

        # 调用 Service 处理业务逻辑，返回需要广播的报价数据列表
        broadcast_data_list = await self.quote_service.handle_gongjia_change(gs_id, xbgz_id, new_gongjia)

        # 批量推送 SSE
        for xbkh_id, quote_data in broadcast_data_list:
            await sse_manager.broadcast(xbkh_id, {
                "type": "quote_update",
                "data": quote_data
            })
            logger.info(f"款号 {xbkh_id} 报价已更新并推送 SSE")

