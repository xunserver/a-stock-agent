"""Deterministic derived fields computed after Standard Record normalization."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from astock_core.market_data.identity import to_legacy_symbol
from astock_core.market_data.models import QuoteSnapshot, ValuationSnapshot


def limit_ratio(symbol: str, *, is_st: bool = False) -> float:
    """Return the A-share daily limit ratio for ``symbol``.

    Ratios are fractions: ``0.10`` means 10%. This is the single exchange-board
    rule table; Adapters must not duplicate it.
    """
    if is_st:
        return 0.05
    if symbol.startswith(("300", "301", "688")):
        return 0.20
    if symbol.startswith(("4", "8", "92")):
        return 0.30
    return 0.10


def derive_price_limits(
    *,
    pre_close: float | None,
    last_price: float | None = None,
    symbol: str,
    is_st: bool = False,
) -> tuple[float | None, float | None]:
    """Return ``(high_limit, low_limit)`` rounded to 2 decimal places.

    Uses ``pre_close`` when present, otherwise ``last_price``. Both results are
    ``None`` when no positive base price is available.
    """
    base = pre_close if pre_close not in (None, 0) else last_price
    if base in (None, 0):
        return None, None
    price = float(base)
    ratio = limit_ratio(symbol, is_st=is_st)
    return round(price * (1 + ratio), 2), round(price * (1 - ratio), 2)


def derive_share_counts(
    *,
    last_price: float | None,
    total_market_cap: float | None,
    float_market_cap: float | None,
) -> tuple[float | None, float | None]:
    """Return ``(total_shares, float_shares)`` from capitalization and price.

    Derives a share count only when that field's market cap and ``last_price``
    are present and ``last_price`` is not zero. Callers must ensure the price
    and capitalization share a compatible as-of date.
    """
    if last_price in (None, 0):
        return None, None
    price = float(last_price)
    total_shares = None if total_market_cap is None else float(total_market_cap) / price
    float_shares = None if float_market_cap is None else float(float_market_cap) / price
    return total_shares, float_shares


def fill_quote_limits(
    snapshot: QuoteSnapshot, *, is_st: bool = False
) -> tuple[QuoteSnapshot, tuple[str, ...]]:
    """Fill missing price limits from board rules. Adapters must not duplicate this."""
    if snapshot.high_limit is not None and snapshot.low_limit is not None:
        return snapshot, ()
    derived_high, derived_low = derive_price_limits(
        pre_close=snapshot.pre_close,
        last_price=snapshot.last_price,
        symbol=to_legacy_symbol(snapshot.instrument_id),
        is_st=is_st,
    )
    warnings: list[str] = []
    high = snapshot.high_limit
    low = snapshot.low_limit
    if high is None and derived_high is not None:
        high = derived_high
        warnings.append("derived high_limit from pre_close and board rules")
    if low is None and derived_low is not None:
        low = derived_low
        warnings.append("derived low_limit from pre_close and board rules")
    if not warnings:
        return snapshot, ()
    return replace(snapshot, high_limit=high, low_limit=low), tuple(warnings)


def fill_share_counts(
    snapshot: ValuationSnapshot,
    *,
    last_price: float | None,
    price_as_of: date | None,
) -> tuple[ValuationSnapshot, tuple[str, ...]]:
    """Fill missing share counts only when price and capitalization share ``as_of``."""
    if price_as_of is None or price_as_of != snapshot.as_of:
        return snapshot, ()
    if snapshot.total_shares is not None and snapshot.float_shares is not None:
        return snapshot, ()
    derived_total, derived_float = derive_share_counts(
        last_price=last_price,
        total_market_cap=snapshot.total_market_cap,
        float_market_cap=snapshot.float_market_cap,
    )
    warnings: list[str] = []
    total_shares = snapshot.total_shares
    float_shares = snapshot.float_shares
    if total_shares is None and derived_total is not None:
        total_shares = derived_total
        warnings.append("derived total_shares from total_market_cap and last_price")
    if float_shares is None and derived_float is not None:
        float_shares = derived_float
        warnings.append("derived float_shares from float_market_cap and last_price")
    if not warnings:
        return snapshot, ()
    return replace(snapshot, total_shares=total_shares, float_shares=float_shares), tuple(
        warnings
    )


def derive_bar_change(
    *,
    close: float,
    high: float,
    low: float,
    prev_close: float | None,
) -> tuple[float | None, float | None, float | None]:
    """Return ``(change_amount, pct_chg, amplitude)`` in percentage points.

    ``pct_chg`` and ``amplitude`` use percentage points: ``1.25`` means ``1.25%``.
    All three values are ``None`` when ``prev_close`` is missing or zero.
    """
    if prev_close in (None, 0):
        return None, None, None
    previous = float(prev_close)
    change_amount = float(close) - previous
    pct_chg = change_amount / previous * 100
    amplitude = (float(high) - float(low)) / previous * 100
    return change_amount, pct_chg, amplitude
