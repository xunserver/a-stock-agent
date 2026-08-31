from __future__ import annotations

from datetime import date

from astock_core.market_data import Adjustment, Bar, BarInterval, from_legacy_symbol


def make_test_bar(
    code: str,
    trade_date: str,
    *,
    pct_chg: float = 1.0,
    adjust: Adjustment = Adjustment.QFQ,
    interval: BarInterval = BarInterval.D1,
    close: float = 10.5,
) -> Bar:
    return Bar(
        instrument_id=from_legacy_symbol(code),
        trade_date=date.fromisoformat(trade_date),
        interval=interval,
        adjustment=adjust,
        open=10.0,
        high=max(close, 10.8),
        low=min(close, 9.9),
        close=close,
        volume=1000.0,
        amount=10000.0,
        turnover_pct=1.2,
        adjustment_factor=1.0,
    )
