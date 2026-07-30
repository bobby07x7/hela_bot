"""
Central logging configuration. Every module gets a logger via
`get_logger(__name__)` so log lines are consistently formatted and can be
shipped to Sentry / Prometheus exporters later without touching call sites.
"""
from __future__ import annotations

import logging
import sys

from core.config import get_settings

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.handlers = [handler]

    # Quiet down noisy third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
