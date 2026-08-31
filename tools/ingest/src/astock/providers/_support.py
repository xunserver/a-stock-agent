"""Shared Adapter transport helpers. Not a public capability interface."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TypeVar

from astock_core.market_data import (
    AuthenticationFailed,
    InvalidSourcePayload,
    MarketDataError,
    RateLimited,
    SourceUnavailable,
)

T = TypeVar("T")

_RETRYABLE = (RateLimited, SourceUnavailable)


def call_with_retries(
    operation: Callable[[], T],
    *,
    retries: int,
    sleep: Callable[[float], None],
) -> T:
    if retries < 1:
        raise ValueError("retries must be >= 1")
    last_error: MarketDataError | None = None
    for attempt in range(1, retries + 1):
        try:
            return operation()
        except _RETRYABLE as exc:
            last_error = exc
            if attempt >= retries:
                raise
            sleep(min(2**attempt, 16))
        except MarketDataError:
            raise
    assert last_error is not None
    raise last_error


def translate_transport_error(exc: BaseException) -> MarketDataError:
    if isinstance(exc, MarketDataError):
        return exc
    status = _http_status(exc)
    if status in {401, 403}:
        return AuthenticationFailed(str(exc) or type(exc).__name__)
    if status == 429:
        return RateLimited(str(exc) or type(exc).__name__)
    name = type(exc).__name__.lower()
    if isinstance(exc, json.JSONDecodeError) or "jsondecode" in name:
        return InvalidSourcePayload(str(exc) or type(exc).__name__)
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)) or "timeout" in name or "connection" in name:
        return SourceUnavailable(str(exc) or type(exc).__name__)
    if status is not None:
        return SourceUnavailable(str(exc) or type(exc).__name__)
    return SourceUnavailable(str(exc) or type(exc).__name__)


def _http_status(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", None) if response is not None else None
    if code is None:
        code = getattr(exc, "status_code", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None
