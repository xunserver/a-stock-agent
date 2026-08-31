"""Structured capability fetch logging with secret redaction."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from astock_core.market_data import Dataset, MarketDataError

logger = logging.getLogger("astock.providers.market_data")

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|cookie|authorization|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(api[_-]?key|token|cookie|authorization|password|secret)=\S+"),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
)
_REDACTED = "[REDACTED]"
_MAX_QUERY_INSTRUMENTS = 8


@dataclass(frozen=True)
class CapabilityLogRecord:
    capability: str
    source: str
    query_identity: str
    attempt: int
    elapsed_ms: float
    item_count: int | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    complete: bool | None = None
    warning_count: int | None = None
    error_category: str | None = None
    outcome: str = "success"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "capability": self.capability,
            "source": self.source,
            "query_identity": self.query_identity,
            "attempt": self.attempt,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "outcome": self.outcome,
        }
        if self.item_count is not None:
            payload["item_count"] = self.item_count
        if self.coverage_start is not None:
            payload["coverage_start"] = self.coverage_start.isoformat()
        if self.coverage_end is not None:
            payload["coverage_end"] = self.coverage_end.isoformat()
        if self.complete is not None:
            payload["complete"] = self.complete
        if self.warning_count is not None:
            payload["warning_count"] = self.warning_count
        if self.error_category is not None:
            payload["error_category"] = self.error_category
        return payload

    def format_line(self) -> str:
        return "market_data_fetch " + json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True)


def redact_message(message: str) -> str:
    redacted = message
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(0).split('=')[0].split(':')[0]}={_REDACTED}", redacted)
    return redacted


def error_category(exc: BaseException) -> str:
    if isinstance(exc, MarketDataError):
        return type(exc).__name__
    return type(exc).__name__


def query_identity(query: Any) -> str:
    if query is None:
        return "null"
    instruments = getattr(query, "instruments", None)
    if instruments:
        values = [getattr(item, "value", str(item)) for item in instruments]
        if len(values) > _MAX_QUERY_INSTRUMENTS:
            head = ",".join(values[:_MAX_QUERY_INSTRUMENTS])
            return f"instruments={head},+{len(values) - _MAX_QUERY_INSTRUMENTS} more"
        return "instruments=" + ",".join(values)
    for name in (
        "market_id",
        "kind",
        "taxonomy",
        "classification_id",
        "sheet",
        "interval",
        "adjustment",
    ):
        value = getattr(query, name, None)
        if value is not None:
            return f"{name}={value}"
    start = getattr(query, "start", None)
    end = getattr(query, "end", None)
    if start is not None or end is not None:
        return f"range={start}..{end}"
    as_of = getattr(query, "as_of", None)
    if as_of is not None:
        return f"as_of={as_of}"
    return type(query).__name__


def log_capability_attempt(
    *,
    capability: str,
    source: str,
    query: Any,
    attempt: int,
    elapsed_ms: float,
    dataset: Dataset[Any] | None = None,
    error: BaseException | None = None,
    outcome: str,
) -> CapabilityLogRecord:
    record = CapabilityLogRecord(
        capability=capability,
        source=source,
        query_identity=query_identity(query),
        attempt=attempt,
        elapsed_ms=elapsed_ms,
        item_count=len(dataset.items) if dataset is not None else None,
        coverage_start=dataset.coverage_start if dataset is not None else None,
        coverage_end=dataset.coverage_end if dataset is not None else None,
        complete=dataset.complete if dataset is not None else None,
        warning_count=len(dataset.warnings) if dataset is not None else None,
        error_category=error_category(error) if error is not None else None,
        outcome=outcome,
    )
    line = redact_message(record.format_line())
    if outcome == "success":
        logger.info(line)
    elif outcome == "fallback":
        logger.warning(line)
    else:
        logger.error(line)
    return record
