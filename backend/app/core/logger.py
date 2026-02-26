"""
结构化日志配置 — 基于 loguru
"""
import sys
from loguru import logger

from app.core.config import settings

# 移除默认 handler
logger.remove()

# 控制台输出
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
)

# 文件输出 — 按天轮转，保留30天
logger.add(
    str(settings.LOGS_DIR / "app_{time:YYYY-MM-DD}.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="00:00",
    retention="30 days",
    compression="zip",
    level="INFO",
    encoding="utf-8",
)

__all__ = ["logger"]
