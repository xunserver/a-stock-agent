from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from astock.ingest import ingest_bars, ingest_calendar, ingest_indexes, instrument_id_for_index_code
from astock_core.db import MarketDB
from astock_core.market_data import (
    Adjustment,
    Bar,
    BarInterval,
    BarQuery,
    Dataset,
    InstrumentId,
    InstrumentNotFound,
    SourceUnavailable,
    TradingDay,
    from_legacy_symbol,
)
from astock_core.session import MARKET_CN_A

SH = ZoneInfo("Asia/Shanghai")
FETCHED_AT = datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


def _bar(
    *,
    instrument_id: InstrumentId,
    trade_date: date,
    interval: BarInterval = BarInterval.D1,
    close: float = 10.5,
    high: float = 11.0,
    low: float = 9.5,
    volume: float = 1_000_000.0,
    adjustment: Adjustment = Adjustment.QFQ,
) -> Bar:
    return Bar(
        instrument_id=instrument_id,
        trade_date=trade_date,
        interval=interval,
        adjustment=adjustment,
        open=10.0,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=10_500_000.0,
        turnover_pct=1.25,
    )


class RecordingBarSource:
    def __init__(self, handler) -> None:
        self.queries: list[BarQuery] = []
        self._handler = handler

    def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
        self.queries.append(query)
        return self._handler(query)


class FixedBarSource:
    def __init__(self, bars: tuple[Bar, ...]) -> None:
        self._bars = bars

    def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
        items = tuple(
            bar
            for bar in self._bars
            if bar.instrument_id in query.instruments
            and query.start <= bar.trade_date <= query.end
            and bar.interval == query.interval
            and bar.adjustment == query.adjustment
        )
        return Dataset(
            items=items,
            source="memory",
            fetched_at=FETCHED_AT,
            coverage_start=query.start,
            coverage_end=query.end,
            complete=True,
        )


class MemoryCalendarSource:
    def __init__(self, days: tuple[TradingDay, ...], *, markets: tuple[str, ...]) -> None:
        self._days = days
        self._markets = frozenset(markets)

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


def _freeze_session(monkeypatch, when: datetime) -> None:
    monkeypatch.setattr(
        "astock_core.session.market_now",
        lambda now=None, *, policy=None: when
        if now is None
        else (now if now.tzinfo else now.replace(tzinfo=when.tzinfo)),
    )


def _open_day(day: date, *, market_id: str = MARKET_CN_A) -> TradingDay:
    return TradingDay(market_id=market_id, trade_date=day, is_open=True)


def test_instrument_id_for_index_code_preserves_shanghai_hs300() -> None:
    instrument_id = instrument_id_for_index_code("sh000300")
    assert instrument_id is not None
    assert instrument_id.value == "CN.XSHG.000300"
    assert instrument_id_for_index_code("000001") is None


@pytest.mark.parametrize("period,interval", [("daily", BarInterval.D1), ("weekly", BarInterval.W1), ("monthly", BarInterval.M1)])
def test_ingest_bars_new_fill_current_empty_partial_and_typed_failure(
    tmp_path, monkeypatch, period: str, interval: BarInterval
) -> None:
    _freeze_session(monkeypatch, datetime(2026, 8, 28, 10, 0, tzinfo=SH))
    monkeypatch.setattr("astock.ingest.time.sleep", lambda _seconds: None)
    new_code = "600519"
    fill_code = "000001"
    current_code = "000002"
    empty_code = "000003"
    partial_code = "000004"
    missing_code = "000005"
    unavailable_code = "000006"

    def handler(query: BarQuery) -> Dataset[Bar]:
        instrument_id = query.instruments[0]
        symbol = instrument_id.symbol
        if symbol == missing_code:
            raise InstrumentNotFound(instrument_id.value)
        if symbol == unavailable_code:
            raise SourceUnavailable("timeout")
        if symbol == empty_code:
            items: tuple[Bar, ...] = ()
            complete = True
            warnings: tuple[str, ...] = ()
        elif symbol == partial_code:
            items = (
                _bar(
                    instrument_id=instrument_id,
                    trade_date=date(2026, 8, 28),
                    interval=interval,
                    volume=500_000.0,
                ),
            )
            complete = False
            warnings = ("truncated",)
        elif symbol == new_code:
            items = (
                _bar(
                    instrument_id=instrument_id,
                    trade_date=date(2026, 8, 26),
                    interval=interval,
                    close=10.0,
                    high=10.2,
                    low=9.8,
                    volume=1_000_000.0,
                ),
                _bar(
                    instrument_id=instrument_id,
                    trade_date=date(2026, 8, 28),
                    interval=interval,
                    close=10.5,
                    high=11.0,
                    low=9.5,
                    volume=1_000_000.0,
                ),
            )
            complete = True
            warnings = ()
        else:
            items = (
                _bar(
                    instrument_id=instrument_id,
                    trade_date=date(2026, 8, 28),
                    interval=interval,
                    close=10.5,
                    high=11.0,
                    low=9.5,
                ),
            )
            complete = True
            warnings = ()
        return Dataset(
            items=items,
            source="memory",
            fetched_at=FETCHED_AT,
            coverage_start=query.start,
            coverage_end=query.end,
            complete=complete,
            warnings=warnings,
        )

    source = RecordingBarSource(handler)
    db_path = tmp_path / "market.db"
    with MarketDB(db_path) as db:
        db.replace_calendar(["2026-08-26", "2026-08-28"])
        db.add_stocks(
            [
                (new_code, "贵州茅台"),
                (fill_code, "平安银行"),
                (current_code, "万科A"),
                (empty_code, "空"),
                (partial_code, "部分"),
                (missing_code, "缺失"),
                (unavailable_code, "超时"),
            ]
        )
        db.upsert_standard_bars(
            [
                _bar(
                    instrument_id=from_legacy_symbol(fill_code),
                    trade_date=date(2026, 8, 26),
                    interval=interval,
                    close=10.0,
                ),
                _bar(
                    instrument_id=from_legacy_symbol(current_code),
                    trade_date=date(2026, 8, 28),
                    interval=interval,
                    close=10.0,
                ),
            ]
        )
        stats = ingest_bars(
            db,
            codes=[
                new_code,
                fill_code,
                current_code,
                empty_code,
                partial_code,
                missing_code,
                unavailable_code,
            ],
            period=period,
            sleep=0,
            bar_source=source,
        )

        assert stats["ok"] == 3
        assert stats["skip"] == 1
        assert stats["empty"] == 1
        assert stats["error"] == 2
        queried = {query.instruments[0].symbol: query for query in source.queries}
        assert current_code not in queried
        assert queried[new_code].start == date(2000, 1, 1)
        assert queried[new_code].end == date.today()
        assert queried[fill_code].start == date(2026, 8, 27)
        assert queried[fill_code].end == date.today()
        assert queried[new_code].interval == interval
        assert queried[new_code].adjustment is Adjustment.QFQ
        maotai = db.list_bars(new_code, period=period)
        assert [row["trade_date"] for row in maotai] == ["2026-08-26", "2026-08-28"]
        assert maotai[0]["volume"] == 1_000_000.0
        assert maotai[0]["pct_chg"] is None
        assert maotai[1]["pct_chg"] == 5.0
        filled = db.list_bars(fill_code, period=period)
        assert filled[-1]["trade_date"] == "2026-08-28"
        assert filled[-1]["pct_chg"] == 5.0
        partial = db.list_bars(partial_code, period=period)
        assert len(partial) == 1
        assert db.last_bar_date(empty_code, period=period) is None
        kinds = {"daily": "stock", "weekly": "stock_weekly", "monthly": "stock_monthly"}
        states = {
            row["code"]: row["status"]
            for row in db.conn.execute(
                "SELECT code, status FROM ingest_state WHERE kind = ?",
                (kinds[period],),
            )
        }
        assert states[new_code] == "ok"
        assert states[fill_code] == "ok"
        assert states[empty_code] == "empty"
        assert states[partial_code] == "ok"
        assert states[missing_code] == "error"
        assert states[unavailable_code] == "error"


def test_ingest_indexes_uses_standard_bars_and_prefixed_code(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("astock.ingest.time.sleep", lambda _seconds: None)
    instrument_id = instrument_id_for_index_code("sh000300")
    assert instrument_id is not None
    bar = Bar(
        instrument_id=instrument_id,
        trade_date=date(2026, 8, 28),
        interval=BarInterval.D1,
        adjustment=Adjustment.RAW,
        open=1.0,
        high=3.0,
        low=0.5,
        close=2.0,
        volume=12_345.0,
        amount=67_890.0,
    )
    source = FixedBarSource((bar,))
    with MarketDB(tmp_path / "market.db") as db:
        n = ingest_indexes(
            db,
            indexes=(("sh000300", "沪深300"),),
            start_date="20260801",
            bar_source=source,
        )
        assert n == 1
        exported = db.list_index_bar_export_rows()
        assert exported[0]["code"] == "sh000300"
        assert exported[0]["volume"] == 12_345.0
        name = db.conn.execute("SELECT name FROM index_daily").fetchone()["name"]
        assert name == "沪深300"


def test_ingest_indexes_skips_already_current(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("astock.ingest.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("astock.ingest._today_yyyymmdd", lambda: "20260828")
    calls: list[BarQuery] = []

    class RejectSource:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            calls.append(query)
            raise AssertionError("already-current index must not fetch")

    with MarketDB(tmp_path / "market.db") as db:
        db.upsert_standard_index_bars(
            [
                _bar(
                    instrument_id=instrument_id_for_index_code("sh000300"),
                    trade_date=date(2026, 8, 28),
                    close=2.0,
                    high=3.0,
                    low=0.5,
                    volume=100.0,
                )
            ],
            code="sh000300",
            name="沪深300",
        )
        n = ingest_indexes(
            db,
            indexes=(("sh000300", "沪深300"),),
            bar_source=RejectSource(),
        )
        assert n == 0
        assert calls == []


def test_ingest_calendar_skips_second_call_same_day(tmp_path, monkeypatch) -> None:
    _freeze_session(monkeypatch, datetime(2026, 8, 28, 10, 0, tzinfo=SH))
    days = (
        _open_day(date(2026, 8, 26)),
        _open_day(date(2026, 8, 28)),
        TradingDay(market_id=MARKET_CN_A, trade_date=date(2026, 8, 27), is_open=False),
    )
    source = MemoryCalendarSource(days, markets=(MARKET_CN_A,))
    with MarketDB(tmp_path / "market.db") as db:
        assert ingest_calendar(db, calendar_source=source) == 2
        assert db.last_calendar_date() == "2026-08-28"
        assert not db.is_trading_day("2026-08-27")
        assert db.calendar_synced_today() is True
        assert ingest_calendar(db, calendar_source=source) == 0
        assert ingest_calendar(db, force=True, calendar_source=source) == 2


def test_ingest_calendar_rejects_empty_dataset(tmp_path) -> None:
    source = MemoryCalendarSource((), markets=(MARKET_CN_A,))
    with MarketDB(tmp_path / "market.db") as db:
        db.replace_calendar(["2026-08-26"])
        with pytest.raises(ValueError, match="交易日历为空"):
            ingest_calendar(db, calendar_source=source)
        assert db.last_calendar_date() == "2026-08-26"
