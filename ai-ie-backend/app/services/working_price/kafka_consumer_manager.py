import asyncio
from app.services.working_price.kafka_comsumer import GongJiaChangeConsumer
from app.services.working_price.kafka_config import kafka_config
from loguru import logger

class KafkaConsumerManager:
    def __init__(self):
        self._consumer_task = None

    async def start(self):
        try:
            logger.info("正在启动 Kafka 消费者管理器...")
            consumer = GongJiaChangeConsumer(
                bootstrap_servers=kafka_config.BOOTSTRAP_SERVERS,
                topic=kafka_config.TOPIC_GONGJIA,
                group_id=kafka_config.GROUP_ID_QUOTE_UPDATE
            )
            self._consumer_task = asyncio.create_task(consumer.start())
            logger.info("Kafka consumer task started")
        except Exception as e:
            raise

    async def stop(self):
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                logger.info("Kafka consumer task cancelled")

kafka_consumer_manager = KafkaConsumerManager()