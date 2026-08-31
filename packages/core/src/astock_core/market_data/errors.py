"""Typed errors raised by market-data capabilities."""

from __future__ import annotations


class MarketDataError(Exception):
    """Base error for every market-data capability failure."""


class UnsupportedQuery(MarketDataError):
    """The Data Source cannot serve this capability or query."""


class InstrumentNotFound(MarketDataError):
    """The Data Source does not recognize the requested Instrument."""


class NoData(MarketDataError):
    """The Instrument exists but the requested dataset is unavailable."""


class RateLimited(MarketDataError):
    """The Data Source rejected the request because of rate limits."""


class SourceUnavailable(MarketDataError):
    """Timeout, transport failure, or other temporary upstream failure."""


class InvalidSourcePayload(MarketDataError):
    """The payload violates the expected source or Standard Record shape."""


class AuthenticationFailed(MarketDataError):
    """Credentials are missing or were rejected."""
