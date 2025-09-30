from __future__ import annotations

import logging
import sys
from typing import Optional
import os


_LOGGER_CONFIGURED = False


def _env_log_level(default_level: int) -> int:
    """Resolve log level from environment variables if provided.

    Recognized vars: LOG_LEVEL, BYBIT_LOG_LEVEL, BOT_LOG_LEVEL.
    """
    try:
        raw = os.getenv("LOG_LEVEL") or os.getenv("BYBIT_LOG_LEVEL") or os.getenv("BOT_LOG_LEVEL")
        if not raw:
            return default_level
        val = raw.strip().upper()
        mapping = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "WARN": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
            "NOTSET": logging.NOTSET,
        }
        return mapping.get(val, default_level)
    except Exception:
        return default_level


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
    # Allow env to override configured level on first init
    resolved_level = _env_log_level(level)
    root_logger.setLevel(resolved_level)
    root_logger.addHandler(handler)

    _LOGGER_CONFIGURED = True

    # Optional library logger filtering (reduce noise from dependencies)
    try:
        lib_level_env = os.getenv("LIB_LOG_LEVEL")
        if lib_level_env:
            lib_level = _env_log_level(logging.WARNING)
        else:
            # If root set to DEBUG, default third-party libs to WARNING unless user overrides
            lib_level = logging.WARNING if resolved_level <= logging.DEBUG else resolved_level
        for noisy in (
            "pybit",
            "urllib3",
            "websocket",
            "requests",
        ):
            logging.getLogger(noisy).setLevel(lib_level)
    except Exception:
        pass


def get_logger(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger.

    The first call configures the root logger with a stdout handler.
    Subsequent calls return child loggers.
    """
    _configure_root_logger(level)
    return logging.getLogger(name or "bybit_bot") 