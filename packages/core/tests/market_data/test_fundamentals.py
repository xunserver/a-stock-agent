from __future__ import annotations

from datetime import date, datetime, timezone

from astock_core.market_data import (
    FinancialPeriodType,
    FundamentalPeriod,
    from_legacy_symbol,
    is_point_in_time_safe,
    line_item,
    point_in_time_safe_periods,
)


def test_point_in_time_helper_does_not_use_period_end() -> None:
    period = FundamentalPeriod(
        instrument_id=from_legacy_symbol("600519"),
        period_end=date(2025, 12, 31),
        period_type=FinancialPeriodType.FY,
        currency="CNY",
        announced_at=None,
        revenue=1.0,
    )
    assert period.period_end is not None
    assert is_point_in_time_safe(period) is False
    announced = FundamentalPeriod(
        instrument_id=period.instrument_id,
        period_end=period.period_end,
        period_type=period.period_type,
        currency="CNY",
        announced_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        revenue=1.0,
    )
    assert point_in_time_safe_periods((period, announced)) == (announced,)


def test_line_item_registry_covers_spec_minimums() -> None:
    assert line_item("cash_and_equivalents").label == "货币资金"
    assert line_item("operating_revenue").code == "operating_revenue"
    assert line_item("net_operating_cashflow").sheet.value == "cashflow"
