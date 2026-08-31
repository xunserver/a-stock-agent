"""Cross-source capability fallback following specification section 9."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from astock_core.market_data import (
    AuthenticationFailed,
    Dataset,
    InstrumentNotFound,
    InvalidSourcePayload,
    MarketDataError,
    NoData,
    RateLimited,
    SourceUnavailable,
    UnsupportedQuery,
)

from astock.providers.observability import log_capability_attempt

T = TypeVar("T")
FetchFn = Callable[[Any], Dataset[T]]

# Capabilities where NoData may trigger the next configured source.
_NO_DATA_FALLBACK_CAPABILITIES: frozenset[str] = frozenset()


class FallbackExhausted(MarketDataError):
    """Every configured source failed for a capability fetch."""

    def __init__(self, capability: str, attempts: tuple["AttemptSummary", ...]) -> None:
        self.capability = capability
        self.attempts = attempts
        parts = [
            f"{item.source}:{item.error_category}"
            for item in attempts
        ]
        super().__init__(f"{capability} sources exhausted: " + "; ".join(parts))


@dataclass(frozen=True)
class AttemptSummary:
    source: str
    attempt: int
    error_category: str
    message: str


def should_try_next_source(error: MarketDataError, *, capability: str) -> bool:
    if isinstance(error, NoData):
        return capability in _NO_DATA_FALLBACK_CAPABILITIES
    if isinstance(error, AuthenticationFailed):
        return True
    if isinstance(error, (UnsupportedQuery, InstrumentNotFound, InvalidSourcePayload)):
        return True
    if isinstance(error, (RateLimited, SourceUnavailable)):
        return True
    return False


def fetch_with_fallback(
    *,
    capability: str,
    source_names: tuple[str, ...],
    sources: tuple[Any, ...],
    query: Any,
    fetch: FetchFn[T],
) -> Dataset[T]:
    if not source_names:
        raise ValueError(f"{capability} requires at least one source")
    if len(source_names) != len(sources):
        raise ValueError(f"{capability} source names and adapters must align")

    summaries: list[AttemptSummary] = []
    for attempt_index, (source_name, adapter) in enumerate(zip(source_names, sources, strict=True), start=1):
        started = time.perf_counter()
        try:
            dataset = fetch(adapter, query)
        except MarketDataError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            try_next = (
                attempt_index < len(source_names)
                and should_try_next_source(exc, capability=capability)
            )
            log_capability_attempt(
                capability=capability,
                source=source_name,
                query=query,
                attempt=attempt_index,
                elapsed_ms=elapsed_ms,
                error=exc,
                outcome="fallback" if try_next else "failure",
            )
            summaries.append(
                AttemptSummary(
                    source=source_name,
                    attempt=attempt_index,
                    error_category=type(exc).__name__,
                    message=_safe_message(exc),
                )
            )
            if not should_try_next_source(exc, capability=capability):
                raise
            if attempt_index >= len(source_names):
                raise FallbackExhausted(capability, tuple(summaries)) from exc
            continue

        elapsed_ms = (time.perf_counter() - started) * 1000
        log_capability_attempt(
            capability=capability,
            source=source_name,
            query=query,
            attempt=attempt_index,
            elapsed_ms=elapsed_ms,
            dataset=dataset,
            outcome="success",
        )
        return dataset

    raise FallbackExhausted(capability, tuple(summaries))


def _safe_message(exc: BaseException) -> str:
    message = str(exc) or type(exc).__name__
    for token in ("api_key", "token", "cookie", "password", "secret", "authorization"):
        if token in message.lower():
            return type(exc).__name__
    return message[:240]


class FallbackCapability(Generic[T]):
    """Bind a fetch method to an ordered source list."""

    def __init__(
        self,
        *,
        capability: str,
        source_names: tuple[str, ...],
        sources: tuple[Any, ...],
        fetch: FetchFn[T],
    ) -> None:
        self._capability = capability
        self._source_names = source_names
        self._sources = sources
        self._fetch = fetch

    def fetch(self, query: Any) -> Dataset[T]:
        return fetch_with_fallback(
            capability=self._capability,
            source_names=self._source_names,
            sources=self._sources,
            query=query,
            fetch=self._fetch,
        )
