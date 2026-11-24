"""
app/core/logging.py
Structured logging configuration for the application.
Produces JSON-friendly output in production and human-readable output in
development (controlled by the LOG_LEVEL / LOG_FORMAT environment variables).
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Configuration knobs (read directly from env so this module has zero imports
# from app.core.config and avoids circular dependencies)
# ---------------------------------------------------------------------------
_LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json").lower()  # "json" | "text"


class _JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter – produces one-line JSON per record."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        import json
        import traceback

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach request_id if the caller injected it into the LogRecord.
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id

        # Attach any extra fields forwarded via `extra={}`.
        for key, value in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "request_id",
            }:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exception"] = record.exc_text

        return json.dumps(payload, default=str)


class _TextFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    _FMT = (
        "%(asctime)s | %(levelname)-8s | %(name)s"
        " | %(message)s"
    )
    _DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt=self._DATE_FMT)


def _build_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    if _LOG_FORMAT == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(_TextFormatter())
    return handler


def configure_logging() -> None:
    """
    Call once at application startup (from main.py lifespan) to set up the
    root logger.  Subsequent calls are idempotent.
    """
    root = logging.getLogger()
    if root.handlers:
        # Already configured – do nothing.
        return

    root.setLevel(_LOG_LEVEL)
    root.addHandler(_build_handler())

    # Quiet down noisy third-party loggers.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str, **bound_fields: Any) -> logging.LoggerAdapter:
    """
    Return a logger adapter that pre-attaches *bound_fields* to every record.

    Usage::

        log = get_logger(__name__, service="ingest")
        log.info("Received batch", extra={"batch_id": batch_id})

    The *request_id* field is special: when present it appears as a top-level
    key in the JSON output.
    """
    logger = logging.getLogger(name)
    return logging.LoggerAdapter(logger, extra=bound_fields)
