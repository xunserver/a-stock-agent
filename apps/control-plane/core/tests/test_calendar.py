from __future__ import annotations

from astock_control.queries import (
    calendar_get_query,
    calendar_markets_query,
    calendar_overview_query,
)
from astock_core.db import MarketDB


def test_calendar_queries(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    with MarketDB(db_path) as db:
        db.replace_calendar(
            ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-28"],
            market_id="cn_a",
        )

    markets = calendar_markets_query()
    by_id = {item["id"]: item for item in markets["markets"]}
    assert by_id["cn_a"]["title"] == "A股"
    assert by_id["cn_a"]["count"] == 4
    assert by_id["cn_futures"]["status"] == "planned"
    assert by_id["us"]["status"] == "planned"

    month = calendar_get_query(market="cn_a", year=2026, month=8)
    assert month["trading_days"] == 4
    by_date = {item["date"]: item["is_trading"] for item in month["days"]}
    assert by_date["2026-08-03"] is True
    assert by_date["2026-08-01"] is False
    assert month["title"] == "A股"
    assert "today" in month
    assert "trade_date" in month

    empty = calendar_get_query(market="us", year=2026, month=8)
    assert empty["trading_days"] == 0
    assert empty["status"] == "planned"


def test_calendar_overview(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    with MarketDB(db_path) as db:
        db.replace_calendar(["2026-08-28"], market_id="cn_a")

    overview = calendar_overview_query()
    by_id = {item["id"]: item for item in overview["markets"]}
    assert by_id["cn_a"]["title"] == "A股"
    assert by_id["cn_a"]["has_calendar"] is True
    assert by_id["cn_a"]["sessions"][0]["start"] == "09:15"
    assert by_id["cn_futures"]["status"] == "planned"
    assert by_id["us"]["sessions"][0]["end"] == "16:00"
    assert "timezone" in by_id["cn_a"]


def test_trade_calendar_market_migration(tmp_path) -> None:
    import sqlite3

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE trade_calendar (trade_date TEXT PRIMARY KEY);
        INSERT INTO trade_calendar (trade_date) VALUES ('2026-08-26');
        """
    )
    conn.close()

    with MarketDB(db_path) as db:
        assert db.is_trading_day("2026-08-26", market_id="cn_a")
        assert db.calendar_coverage(market_id="cn_a")["count"] == 1
        cols = {
            row[1] for row in db.conn.execute("PRAGMA table_info(trade_calendar)")
        }
        assert "market_id" in cols
