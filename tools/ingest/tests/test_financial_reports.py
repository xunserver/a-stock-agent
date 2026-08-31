from __future__ import annotations

from datetime import date, datetime, timezone

from astock.stock import sync_stock_info
from astock_core.db import MarketDB
from astock_core.market_data import (
    Dataset,
    FinancialPeriodType,
    FundamentalPeriod,
    from_legacy_symbol,
    is_point_in_time_safe,
    point_in_time_safe_periods,
)


FETCHED_AT = datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


def _period(**overrides) -> FundamentalPeriod:
    values = dict(
        instrument_id=from_legacy_symbol("000001"),
        period_end=date(2026, 6, 30),
        period_type=FinancialPeriodType.H1,
        currency="CNY",
        announced_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        eps=1.24,
        roe_pct=5.22,
        revenue=70617000000.0,
        revenue_yoy_pct=1.77,
        net_profit=25696000000.0,
        net_profit_yoy_pct=3.32,
        gross_margin_pct=40.0,
        net_margin_pct=36.38,
        debt_ratio_pct=90.9,
    )
    values.update(overrides)
    return FundamentalPeriod(**values)


def test_upsert_fundamental_periods_roundtrip(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        count = db.upsert_fundamental_periods(
            (
                _period(),
                _period(
                    period_end=date(2025, 12, 31),
                    period_type=FinancialPeriodType.FY,
                    announced_at=None,
                    roe_pct=10.0,
                    revenue=2.0,
                ),
            )
        )
        assert count == 2
        assert db.financial_report_count("000001") == 2
        assert db.latest_financial_report_date("000001") == "2026-06-30"
        listed = db.list_financial_reports("000001", limit=1)
        assert listed[0]["report_type"] == "2026中报"
        assert listed[0]["roe"] == 5.22
        assert listed[0]["notice_date"] == "2026-08-15"
        stock = db.get_stock("000001")
        assert stock["eps"] == 1.24
        assert stock["roe"] == 5.22


def test_sync_stock_info_persists_fundamentals(tmp_path) -> None:
    class _Profiles:
        def fetch_profiles(self, query):
            from astock_core.market_data import InstrumentProfile

            return Dataset(
                items=(
                    InstrumentProfile(
                        instrument_id=from_legacy_symbol("000001"),
                        name="平安银行",
                        is_st=False,
                    ),
                ),
                source="memory",
                fetched_at=FETCHED_AT,
            )

    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        result = sync_stock_info(
            db,
            ["000001"],
            sleep=0,
            profile_source=_Profiles(),
            snapshot_source=_ProfilesEmpty(),
            valuation_source=_ProfilesEmpty(),
            fundamental_source=_Fundamental(),
        )
        assert result["info_ok"] == 1
        reports = db.list_financial_reports("000001")
        assert reports[0]["revenue"] == 70617000000.0


class _Fundamental:
    def fetch_fundamentals(self, query):
        return Dataset(items=(_period(),), source="memory", fetched_at=FETCHED_AT)


class _ProfilesEmpty:
    def fetch_snapshots(self, query):
        from astock_core.market_data import Dataset

        return Dataset(items=(), source="memory", fetched_at=FETCHED_AT)

    def fetch_valuations(self, query):
        from astock_core.market_data import Dataset

        return Dataset(items=(), source="memory", fetched_at=FETCHED_AT)

    def fetch_profiles(self, query):
        from astock_core.market_data import Dataset

        return Dataset(items=(), source="memory", fetched_at=FETCHED_AT)


def test_point_in_time_safe_projection_excludes_missing_announcement() -> None:
    displayable = _period(announced_at=None)
    safe = _period()
    assert is_point_in_time_safe(displayable) is False
    assert point_in_time_safe_periods((displayable, safe)) == (safe,)
