from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from astock_control.queries import calendar_month_all_query
from astock_core.db import MarketDB


def test_calendar_month_query_marks_open_markets(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    frozen = datetime(2026, 8, 28, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    monkeypatch.setattr("astock_control.queries.market_now", lambda now=None, *, policy=None: frozen)
    monkeypatch.setattr(
        "astock_core.session.market_now",
        lambda now=None, *, policy=None: frozen if now is None else (
            now if now.tzinfo else now.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        ),
    )
    with MarketDB(db_path) as db:
        db.replace_calendar(["2026-08-03", "2026-08-28"], market_id="cn_a")
        db.replace_calendar(["2026-08-28"], market_id="us")

    payload = calendar_month_all_query(year=2026, month=8)
    by_date = {item["date"]: item["markets"] for item in payload["days"]}
    assert by_date["2026-08-03"] == ["cn_a"]
    assert by_date["2026-08-28"] == ["cn_a", "us"]
    assert by_date["2026-08-02"] == []
    badges = {item["id"]: item["badge"] for item in payload["markets"]}
    assert badges["cn_a"] == "A"
    assert badges["us"] == "美"
    assert badges["cn_futures"] == "期"
    assert payload["today"] == "2026-08-28"
