from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from astock_core.db import MarketDB
from astock_core.session import CN_A, CN_FUTURES, session_ceiling_date


SH = ZoneInfo("Asia/Shanghai")


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=SH)


def test_session_ceiling_stock_before_and_after_open() -> None:
    # 交易日 8 点前：天花板是昨天
    assert session_ceiling_date(_dt("2026-08-28T07:59:59"), policy=CN_A).isoformat() == "2026-08-27"
    # 交易日 8 点起：天花板是今天
    assert session_ceiling_date(_dt("2026-08-28T08:00:00"), policy=CN_A).isoformat() == "2026-08-28"


def test_session_ceiling_weekend() -> None:
    # 周末过了切点仍用当天天花板，再由日历回退到上一个交易日
    assert session_ceiling_date(_dt("2026-08-29T10:00:00"), policy=CN_A).isoformat() == "2026-08-29"
    assert session_ceiling_date(_dt("2026-08-30T07:00:00"), policy=CN_A).isoformat() == "2026-08-29"


def test_futures_policy_uses_evening_open() -> None:
    assert session_ceiling_date(_dt("2026-08-28T20:29:00"), policy=CN_FUTURES).isoformat() == "2026-08-27"
    assert session_ceiling_date(_dt("2026-08-28T20:30:00"), policy=CN_FUTURES).isoformat() == "2026-08-28"


def test_in_trading_hours_cn_a() -> None:
    from astock_core.session import in_trading_hours

    assert in_trading_hours(_dt("2026-08-28T10:00:00"), market_id="cn_a")
    assert not in_trading_hours(_dt("2026-08-28T12:00:00"), market_id="cn_a")
    assert in_trading_hours(_dt("2026-08-28T14:00:00"), market_id="cn_a")


def test_list_calendar_markets_includes_placeholders() -> None:
    from astock_core.session import list_calendar_markets

    ids = [item["id"] for item in list_calendar_markets()]
    assert ids == ["cn_a", "cn_futures", "us"]


def test_current_trade_date_respects_session_open(tmp_path) -> None:
    db_path = tmp_path / "market.db"
    with MarketDB(db_path) as db:
        db.replace_calendar(
            ["2026-08-26", "2026-08-27", "2026-08-28"]
        )
        before = db.current_trade_date(now=_dt("2026-08-28T07:30:00"))
        after = db.current_trade_date(now=_dt("2026-08-28T09:00:00"))
        weekend = db.current_trade_date(now=_dt("2026-08-30T12:00:00"))
    assert before == "2026-08-27"
    assert after == "2026-08-28"
    assert weekend == "2026-08-28"


def test_calendar_synced_today(tmp_path) -> None:
    db_path = tmp_path / "market.db"
    now = _dt("2026-08-28T10:00:00")
    with MarketDB(db_path) as db:
        assert db.calendar_synced_today(now=now) is False
        db.mark_calendar_synced(now=now, rows=10)
        assert db.calendar_synced_today(now=now) is True
        assert db.calendar_synced_today(now=_dt("2026-08-29T10:00:00")) is False
