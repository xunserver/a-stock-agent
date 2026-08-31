from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from astock.ingest import ingest_calendar
from astock_core.db import MarketDB
from astock_core.market_data import Dataset, TradingDay
from astock_core.session import MARKET_CN_A

SH = ZoneInfo("Asia/Shanghai")
FETCHED_AT = datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


class MemoryCalendarSource:
    def __init__(self, days: tuple[TradingDay, ...]) -> None:
        self._days = days

    def fetch_calendar(self, query) -> Dataset[TradingDay]:
        items = tuple(
            day
            for day in self._days
            if day.market_id == query.market_id and query.start <= day.trade_date <= query.end
        )
        return Dataset(
            items=items,
            source="memory",
            fetched_at=FETCHED_AT,
            coverage_start=query.start,
            coverage_end=query.end,
            complete=True,
        )


def test_ingest_calendar_skips_second_call_same_day(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "astock_core.session.market_now",
        lambda now=None, *, policy=None: datetime(2026, 8, 28, 10, 0, tzinfo=SH),
    )
    source = MemoryCalendarSource(
        (
            TradingDay(market_id=MARKET_CN_A, trade_date=date(2026, 8, 26), is_open=True),
            TradingDay(market_id=MARKET_CN_A, trade_date=date(2026, 8, 28), is_open=True),
        )
    )
    with MarketDB(tmp_path / "market.db") as db:
        assert ingest_calendar(db, calendar_source=source) == 2
        assert db.last_calendar_date() == "2026-08-28"
        assert ingest_calendar(db, calendar_source=source) == 0
        assert ingest_calendar(db, force=True, calendar_source=source) == 2
