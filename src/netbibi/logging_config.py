"""JSON-formatted logging for netbibi.

Emits one JSON object per record on stderr. Standard fields:
ts, level, logger, event. Extras passed via `logger.info("event",
extra={"url": ..., "depth": ...})` are merged into the same object,
so downstream `jq` consumers see a flat schema.

LOG_LEVEL env var controls verbosity (defaults to INFO).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# Names always present on a logging.LogRecord — we don't want to surface
# them as extras (they would either be redundant with the structured
# fields we emit, or reveal internal noise).
_RESERVED_FIELDS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """One-line JSON per record, no external deps."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_FIELDS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            exc_type = record.exc_info[0]
            payload["error_type"] = exc_type.__name__ if exc_type else None
            payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str | None = None) -> None:
    """Wire JSON logging onto stderr. Idempotent.

    Resolves level from arg, then $LOG_LEVEL, then defaults to INFO.
    Replaces any existing root handlers so calling twice is safe.
    """
    resolved_level = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved_level)
