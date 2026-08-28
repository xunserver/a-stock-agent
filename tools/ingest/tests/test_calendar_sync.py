from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from astock.ingest import ingest_calendar
from astock_core.db import MarketDB


SH = ZoneInfo("Asia/Shanghai")


def test_ingest_calendar_skips_second_call_same_day(tmp_path, monkeypatch) -> None:
    calls = {"n": 0}

    def fake_call(fn, *args, **kwargs):
        calls["n"] += 1
        return {"trade_date": SimpleNamespace(tolist=lambda: ["2026-08-26", "2026-08-28"])}

    monkeypatch.setattr("astock.ingest._call", fake_call)
    monkeypatch.setattr(
        "astock_core.session.market_now",
        lambda now=None, *, policy=None: datetime(2026, 8, 28, 10, 0, tzinfo=SH),
    )

    db_path = tmp_path / "market.db"
    with MarketDB(db_path) as db:
        assert ingest_calendar(db) == 2
        assert calls["n"] == 1
        assert db.last_calendar_date() == "2026-08-28"
        assert ingest_calendar(db) == 0
        assert calls["n"] == 1
        assert ingest_calendar(db, force=True) == 2
        assert calls["n"] == 2
