# app/config/kafka_config.py
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()


class KafkaConfig:
    """Kafka 配置类，从环境变量读取配置"""

    # Kafka 服务器地址
    BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "YULITH:9092")

    # 公司工价表 CDC 主题
    TOPIC_GONGJIA: str = os.getenv("KAFKA_TOPIC_GONGJIA", "sqlserver.getai.dbo.AI_GongSiGongJia")

    # 消费者组 ID（用于报价更新）
    GROUP_ID_QUOTE_UPDATE: str = os.getenv("KAFKA_GROUP_ID_QUOTE_UPDATE", "quote-update-group")

    @classmethod
    def get_bootstrap_servers(cls) -> str:
        return cls.BOOTSTRAP_SERVERS

    @classmethod
    def get_topic_gongjia(cls) -> str:
        return cls.TOPIC_GONGJIA

    @classmethod
    def get_group_id(cls) -> str:
        return cls.GROUP_ID_QUOTE_UPDATE


# 创建全局配置实例（可选，便于直接导入）
kafka_config = KafkaConfig()