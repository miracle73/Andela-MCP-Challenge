"""Structured logging + lightweight token/latency tracking."""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

_PIN_PATTERN = re.compile(r'("?pin"?\s*[:=]\s*")(\d{3,6})(")', re.IGNORECASE)


def _redact(text: str) -> str:
    """Mask PINs in any structured payload before it hits logs."""
    return _PIN_PATTERN.sub(r"\1****\3", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return _redact(json.dumps(payload, default=str))


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def log_event(logger: logging.Logger, msg: str, **fields: Any) -> None:
    logger.info(msg, extra={"extra_fields": fields})


@dataclass
class TraceMetrics:
    """Per-turn metrics — model usage, tool calls, latency."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": round(self.latency_ms, 1),
            "tool_calls": self.tool_calls,
        }


@contextmanager
def time_block(metrics: TraceMetrics) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        metrics.latency_ms += (time.perf_counter() - start) * 1000
