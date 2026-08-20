"""Cau hinh logging: ghi ra console va file logs/crawler.log."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

_CONFIGURED = False
DEFAULT_LOG_DIR = "logs"


def setup_logging(log_dir: str = DEFAULT_LOG_DIR, level: int = logging.INFO) -> logging.Logger:
    """Khoi tao root logger (idempotent)."""
    global _CONFIGURED
    root = logging.getLogger("mql5")
    if _CONFIGURED:
        return root

    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "crawler.log"), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        root.warning("Khong tao duoc thu muc log %s", log_dir)

    _CONFIGURED = True
    return root


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"mql5.{name}")
