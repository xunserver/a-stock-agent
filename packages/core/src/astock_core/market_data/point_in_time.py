"""Point-in-time research safety for Fundamental Period records.

``announced_at=None`` is accepted for display compatibility. It must never be
filled from ``period_end``. Research and export projections exclude such
records unless the caller opts in.
"""

from __future__ import annotations

from collections.abc import Sequence

from astock_core.market_data.models import FundamentalPeriod


def is_point_in_time_safe(period: FundamentalPeriod) -> bool:
    """Return whether ``period`` has an announcement time for point-in-time use."""
    return period.announced_at is not None


def point_in_time_safe_periods(
    periods: Sequence[FundamentalPeriod],
) -> tuple[FundamentalPeriod, ...]:
    """Return only Fundamental Periods that are safe for point-in-time research."""
    return tuple(period for period in periods if is_point_in_time_safe(period))
