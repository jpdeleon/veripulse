"""Logging setup for Veripulse."""

from loguru import logger
import sys
from pathlib import Path

from veripulse.core.config import get_config


def setup_logging() -> None:
    config = get_config()

    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stderr,
        format=log_format,
        level=config.logging.level,
        colorize=True,
    )

    log_file = Path(config.logging.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_file,
        format=log_format,
        level=config.logging.level,
        rotation=config.logging.rotation,
        retention=config.logging.retention,
        compression="zip",
    )
