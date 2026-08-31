from __future__ import annotations

from datetime import date

from astock_core.db import MarketDB
from astock_core.market_data import (
    Adjustment,
    Bar,
    BarInterval,
    InstrumentId,
    InstrumentProfile,
    QuoteSnapshot,
    TradingDay,
    ValuationSnapshot,
    derive_bar_change,
    derive_price_limits,
    derive_share_counts,
    from_legacy_symbol,
    limit_ratio,
)
from astock_core.paths import DEFAULT_ADJUST


def test_derive_bar_change_uses_percentage_points() -> None:
    change_amount, pct_chg, amplitude = derive_bar_change(
        close=10.5, high=11.0, low=9.5, prev_close=10.0
    )
    assert change_amount == 0.5
    assert pct_chg == 5.0
    assert amplitude == 15.0


def test_derive_bar_change_missing_prev_close() -> None:
    assert derive_bar_change(close=10.5, high=11.0, low=9.5, prev_close=None) == (
        None,
        None,
        None,
    )
    assert derive_bar_change(close=10.5, high=11.0, low=9.5, prev_close=0) == (
        None,
        None,
        None,
    )


def _bar(
    code: str,
    day: date,
    *,
    close: float = 10.5,
    high: float = 11.0,
    low: float = 9.5,
    open_: float = 10.0,
    volume: float = 1_000_000.0,
    interval: BarInterval = BarInterval.D1,
    adjustment: Adjustment = Adjustment.QFQ,
) -> Bar:
    return Bar(
        instrument_id=from_legacy_symbol(code),
        trade_date=day,
        interval=interval,
        adjustment=adjustment,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=10_500_000.0,
        turnover_pct=1.25,
    )


def test_upsert_standard_bars_projects_shares_and_derived_fields(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        written = db.upsert_standard_bars(
            [
                _bar("000001", date(2026, 8, 27), close=10.0, high=10.2, low=9.8),
                _bar("000001", date(2026, 8, 28), close=10.5, high=11.0, low=9.5),
            ]
        )
        assert written == 2
        rows = db.list_daily_bars("000001")
        assert [row["trade_date"] for row in rows] == ["2026-08-27", "2026-08-28"]
        first, second = rows
        assert first["volume"] == 1_000_000.0
        assert first["change_amount"] is None
        assert first["pct_chg"] is None
        assert first["amplitude"] is None
        assert first["turnover"] == 1.25
        assert db.last_bar_date("000001", adjust=DEFAULT_ADJUST) == "2026-08-28"
        assert second["change_amount"] == 0.5
        assert second["pct_chg"] == 5.0
        assert second["amplitude"] == 15.0
        export = db.list_bar_export_rows()
        assert export[0]["volume"] == 1_000_000.0
        assert list(export[0]) == [
            "code",
            "date",
            "open",
            "close",
            "high",
            "low",
            "volume",
            "amount",
        ]


def test_upsert_standard_bars_uses_stored_prev_close_for_fill(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.upsert_standard_bars([_bar("000001", date(2026, 8, 26), close=10.0)])
        db.upsert_standard_bars([_bar("000001", date(2026, 8, 28), close=10.5, high=11.0, low=9.5)])
        latest = db.latest_bar("000001")
        assert latest is not None
        assert latest["pct_chg"] == 5.0
        assert latest["change_amount"] == 0.5


def test_raw_adjustment_persists_as_empty_key(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.upsert_standard_bars(
            [_bar("000001", date(2026, 8, 28), adjustment=Adjustment.RAW)]
        )
        assert db.last_bar_date("000001", adjust="") == "2026-08-28"


def test_weekly_standard_bars_use_weekly_table(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.upsert_standard_bars(
            [_bar("000001", date(2026, 8, 28), interval=BarInterval.W1)]
        )
        assert db.last_bar_date("000001", period="weekly") == "2026-08-28"
        assert db.counts()["bars_weekly"] == 1


def test_upsert_standard_index_bars_keeps_prefixed_code(tmp_path) -> None:
    bar = Bar(
        instrument_id=InstrumentId(country="CN", exchange="XSHG", symbol="000300"),
        trade_date=date(2026, 8, 28),
        interval=BarInterval.D1,
        adjustment=Adjustment.RAW,
        open=1.0,
        high=3.0,
        low=0.5,
        close=2.0,
        volume=100.0,
        amount=200.0,
    )
    with MarketDB(tmp_path / "market.db") as db:
        n = db.upsert_standard_index_bars([bar], code="sh000300", name="沪深300")
        assert n == 1
        exported = db.list_index_bar_export_rows()
        assert exported[0]["code"] == "sh000300"
        assert exported[0]["volume"] == 100.0
        stored = db.conn.execute("SELECT name FROM index_daily").fetchone()
        assert stored["name"] == "沪深300"


def test_upsert_trading_days_filters_closed_and_is_atomic(tmp_path) -> None:
    days = (
        TradingDay(market_id="cn_a", trade_date=date(2026, 8, 26), is_open=True),
        TradingDay(market_id="cn_a", trade_date=date(2026, 8, 27), is_open=False),
        TradingDay(market_id="cn_a", trade_date=date(2026, 8, 28), is_open=True),
        TradingDay(market_id="us", trade_date=date(2026, 8, 28), is_open=True),
    )
    with MarketDB(tmp_path / "market.db") as db:
        n = db.upsert_trading_days(days, market_id="cn_a")
        assert n == 2
        assert db.list_calendar_dates("2026-08-01", "2026-08-31") == [
            "2026-08-26",
            "2026-08-28",
        ]
        assert db.calendar_synced_today() is True
        assert not db.is_trading_day("2026-08-27")


def test_limit_ratio_uses_board_and_st_rules() -> None:
    assert limit_ratio("000001") == 0.10
    assert limit_ratio("600519") == 0.10
    assert limit_ratio("300001") == 0.20
    assert limit_ratio("301001") == 0.20
    assert limit_ratio("688001") == 0.20
    assert limit_ratio("430001") == 0.30
    assert limit_ratio("830001") == 0.30
    assert limit_ratio("920001") == 0.30
    assert limit_ratio("000001", is_st=True) == 0.05


def test_derive_price_limits_from_pre_close() -> None:
    assert derive_price_limits(pre_close=10.0, symbol="000001") == (11.0, 9.0)
    assert derive_price_limits(pre_close=None, last_price=10.0, symbol="000001") == (11.0, 9.0)
    assert derive_price_limits(pre_close=None, last_price=None, symbol="000001") == (None, None)


def test_derive_share_counts_from_same_as_of_price() -> None:
    assert derive_share_counts(
        last_price=10.0, total_market_cap=1000.0, float_market_cap=800.0
    ) == (100.0, 80.0)
    assert derive_share_counts(
        last_price=None, total_market_cap=1000.0, float_market_cap=800.0
    ) == (None, None)


def test_fill_quote_limits_records_warning_and_skips_when_present() -> None:
    from datetime import datetime, timezone

    from astock_core.market_data import QuoteSnapshot, fill_quote_limits

    snapshot = QuoteSnapshot(
        instrument_id=from_legacy_symbol("000001"),
        observed_at=datetime(2026, 8, 31, 7, 0, tzinfo=timezone.utc),
        last_price=10.0,
        pre_close=10.0,
        high_limit=None,
        low_limit=None,
    )
    filled, warnings = fill_quote_limits(snapshot, is_st=False)
    assert filled.high_limit == 11.0
    assert filled.low_limit == 9.0
    assert warnings
    unchanged, empty = fill_quote_limits(filled, is_st=False)
    assert unchanged is filled
    assert empty == ()


def test_upsert_standard_snapshots_project_independent_columns(tmp_path) -> None:
    from datetime import datetime, timezone

    instrument_id = from_legacy_symbol("000001")
    observed = datetime(2026, 8, 31, 7, 0, tzinfo=timezone.utc)
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        db.upsert_stock_profile(
            "000001",
            name="平安银行",
            industry="银行",
            pe_dyn=8.5,
            latest_price=9.0,
            eps=1.2,
        )
        db.upsert_instrument_profiles(
            (
                InstrumentProfile(
                    instrument_id=instrument_id,
                    name="平安银行",
                    industry="银行",
                    region="深圳板块",
                    list_date=date(1991, 4, 3),
                    is_st=False,
                ),
            )
        )
        db.upsert_quote_snapshots(
            (
                QuoteSnapshot(
                    instrument_id=instrument_id,
                    observed_at=observed,
                    last_price=10.5,
                    pre_close=10.0,
                    average_price=10.2,
                    high_limit=11.0,
                    low_limit=9.0,
                    volume_ratio=1.2,
                    outer_volume=1000.0,
                    inner_volume=800.0,
                    is_suspended=False,
                    suspend_reason=None,
                ),
            )
        )
        db.upsert_valuation_snapshots(
            (
                ValuationSnapshot(
                    instrument_id=instrument_id,
                    as_of=date(2026, 8, 31),
                    currency="CNY",
                    total_shares=1.9e10,
                    float_shares=1.9e10,
                    total_market_cap=2e11,
                    float_market_cap=2e11,
                    pe_ttm=5.2,
                    pe_static=5.0,
                    pb=0.7,
                ),
            )
        )
        got = db.get_stock("000001")
        assert got is not None
        assert got["industry"] == "银行"
        assert got["region"] == "深圳板块"
        assert got["list_date"] == "1991-04-03"
        assert got["latest_price"] == 10.5
        assert got["pre_close"] == 10.0
        assert got["pe_dyn"] == 5.2
        assert got["pe_static"] == 5.0
        assert got["pb"] == 0.7
        assert got["eps"] == 1.2
        db.upsert_quote_snapshots(())
        db.upsert_valuation_snapshots(())
        unchanged = db.get_stock("000001")
        assert unchanged is not None
        assert unchanged["latest_price"] == 10.5
        assert unchanged["pe_dyn"] == 5.2
        assert unchanged["eps"] == 1.2
