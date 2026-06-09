from loguru import logger
import sys

logger.remove()  # 先清场

# 控制台输出：花里胡哨但好用
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
           "<level>{message}</level>",
    level="DEBUG"
)

# 文件日志：朴实无华但可靠
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    level="INFO",
    rotation="00:00",      # 每天零点轮转
    retention="30 days",   # 保留 30 天
    compression="zip"      # 自动压缩，省空间
)

# 错误日志：单独伺候，VIP 待遇
logger.add(
    "logs/error_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}\n{exception}",
    level="ERROR",
    rotation="00:00",
    retention="90 days"   # 错误日志多留几天，翻旧账用得上
)
