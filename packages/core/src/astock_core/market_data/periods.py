"""Reporting-period helpers shared by Fundamental Period and Financial Statement records."""

from __future__ import annotations

from datetime import date

from astock_core.market_data.enums import FinancialPeriodType
from astock_core.market_data.errors import InvalidSourcePayload

_PERIOD_ENDS: dict[tuple[int, int], FinancialPeriodType] = {
    (3, 31): FinancialPeriodType.Q1,
    (6, 30): FinancialPeriodType.H1,
    (9, 30): FinancialPeriodType.Q3,
    (12, 31): FinancialPeriodType.FY,
}


def period_type_from_end(period_end: date) -> FinancialPeriodType:
    """Return the reporting period type for a calendar period-end date.

    Only standard A-share quarter-ends are accepted. Callers must not
    substitute a nearby date or invent a period type.
    """
    key = (period_end.month, period_end.day)
    period_type = _PERIOD_ENDS.get(key)
    if period_type is None:
        raise InvalidSourcePayload(
            f"period_end {period_end.isoformat()} is not a reporting period end"
        )
    return period_type
