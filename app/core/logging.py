"""Structured logging configuration for the application."""

import logging
import sys
from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configure and return root application logger."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Silence overly verbose external loggers if needed
    logging.getLogger("fiona").setLevel(logging.WARNING)
    logging.getLogger("pyogrio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    logger = logging.getLogger(settings.APP_NAME)
    return logger


logger = setup_logging()
