from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Deque, Dict, List, Optional


class CircularLogBuffer(logging.Handler):
    """Stores the last N log records in memory for the health/logs endpoint."""

    def __init__(self, capacity: int = 100) -> None:
        super().__init__()
        self.capacity = capacity
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=capacity)
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "message_ar": getattr(record, "message_ar", None),
        }
        with self._lock:
            self._buffer.append(entry)

    def get_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            logs = list(self._buffer)
        return logs[-limit:][::-1]


_buffer_handler: Optional[CircularLogBuffer] = None


def install_log_handler(capacity: int = 100) -> CircularLogBuffer:
    global _buffer_handler
    if _buffer_handler is not None:
        return _buffer_handler

    handler = CircularLogBuffer(capacity=capacity)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    for name in ("buildopt", "buildopt.pipeline", "buildopt.jci", "buildopt.health"):
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = True

    root = logging.getLogger()
    if handler not in root.handlers:
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    _buffer_handler = handler
    return handler


def get_log_buffer() -> CircularLogBuffer:
    if _buffer_handler is None:
        return install_log_handler()
    return _buffer_handler


def log_event(level: str, message: str, message_ar: Optional[str] = None) -> None:
    logger = logging.getLogger("buildopt")
    extra = {"message_ar": message_ar} if message_ar else {}
    getattr(logger, level.lower(), logger.info)(message, extra=extra)
