from __future__ import annotations

from datetime import date

from astock.config import history_start, quote_periods
from astock.quotes import sync_quotes
from astock_core.db import BAR_TABLES, MarketDB
from astock_core.market_data import Adjustment, Bar, BarInterval, from_legacy_symbol
from astock_core.paths import DEFAULT_ADJUST


def _period_bar(trade_date: str, *, interval: BarInterval) -> Bar:
    return Bar(
        instrument_id=from_legacy_symbol("000001"),
        trade_date=date.fromisoformat(trade_date),
        interval=interval,
        adjustment=Adjustment(DEFAULT_ADJUST),
        open=10.0,
        high=10.8,
        low=9.9,
        close=10.5,
        volume=1000.0,
        amount=1.0,
        turnover_pct=1.2,
        adjustment_factor=1.0,
    )


def test_history_start_from_settings() -> None:
    assert history_start() == "20000101"
    assert quote_periods() == ("daily", "weekly", "monthly")


def test_weekly_monthly_tables_and_upsert(tmp_path) -> None:
    db_path = tmp_path / "market.db"
    with MarketDB(db_path) as db:
        for period in ("weekly", "monthly"):
            assert BAR_TABLES[period] in {
                row[0]
                for row in db.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            n = db.upsert_standard_bars(
                [_period_bar("2026-08-22", interval=BarInterval.W1 if period == "weekly" else BarInterval.M1)]
            )
            assert n == 1
            assert db.last_bar_date("000001", adjust=DEFAULT_ADJUST, period=period) == "2026-08-22"
        counts = db.counts()
        assert counts["bars_weekly"] == 1
        assert counts["bars_monthly"] == 1


def test_sync_quotes_runs_all_periods(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    seen: list[str] = []

    def fake_calendar(_db, **kwargs):
        return 0

    def fake_ingest(db, *, codes=None, period="daily", **kwargs):
        seen.append(period)
        return {"ok": len(codes or []), "skip": 0, "empty": 0, "error": 0, "rows": len(codes or [])}

    monkeypatch.setattr("astock.quotes.ingest_calendar", fake_calendar)
    monkeypatch.setattr("astock.quotes.ingest_bars", fake_ingest)

    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行")])
        db.replace_calendar(["2026-08-26"])
        result = sync_quotes(db, codes=["000001"], refresh_calendar=True)

    assert seen == ["daily", "weekly", "monthly"]
    assert result["history_start"] == "20000101"
    assert result["daily_rows"] == 1
    assert result["weekly_rows"] == 1
    assert result["monthly_rows"] == 1
    assert result["need_full"] == 1
