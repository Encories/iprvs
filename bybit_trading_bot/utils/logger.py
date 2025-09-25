from __future__ import annotations

import logging
import sys
from typing import Optional


_LOGGER_CONFIGURED = False


def _configure_root_logger(level: int = logging.INFO) -> None:
    global _LOGGER_CONFIGURED
    if _LOGGER_CONFIGURED:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    _LOGGER_CONFIGURED = True


def get_logger(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger.

    The first call configures the root logger with a stdout handler.
    Subsequent calls return child loggers.
    """
    _configure_root_logger(level)
    return logging.getLogger(name or "bybit_bot") 