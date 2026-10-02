"""Shared logging configuration for pipeline scripts."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from config import LOG_DIR, LOG_LEVEL


def setup_logging(script_name: str) -> logging.Logger:
    """Configure console and file logging; return a named logger."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{script_name}_{timestamp}.log"

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logger = logging.getLogger(script_name)
    logger.info("Logging initialized → %s", log_file)
    return logger
