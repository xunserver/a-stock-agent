from __future__ import annotations

from datetime import date

import pytest

from astock_core.market_data import (
    FinancialPeriodType,
    is_point_in_time_safe,
    point_in_time_safe_periods,
)

from .contracts import assert_fundamental_source_contract
from .fakes import InMemoryFundamentalSource, ping_an
from .fixture_sources import (
    empty_fundamental_query,
    make_akshare_fundamental_adapter_batch,
    make_akshare_fundamental_adapter_single,
    valid_batch_fundamental_query,
    valid_fundamental_query,
)


def test_in_memory_and_single_adapter_pass_fundamental_contract() -> None:
    memory = InMemoryFundamentalSource(
        known=(ping_an(),),
        periods=make_akshare_fundamental_adapter_single()
        .fetch_fundamentals(valid_fundamental_query())
        .items,
    )
    assert_fundamental_source_contract(
        memory,
        valid_query=valid_fundamental_query(),
        empty_query=empty_fundamental_query(),
    )
    dataset = assert_fundamental_source_contract(
        make_akshare_fundamental_adapter_single(),
        valid_query=valid_fundamental_query(),
        empty_query=empty_fundamental_query(),
    )
    by_key = {item.natural_key: item for item in dataset.items}
    fy = by_key[(ping_an(), date(2025, 12, 31), FinancialPeriodType.FY)]
    assert fy.announced_at is not None
    assert fy.announced_at.date() == date(2026, 4, 20)
    q3 = by_key[(ping_an(), date(2025, 9, 30), FinancialPeriodType.Q3)]
    assert q3.announced_at is None
    assert is_point_in_time_safe(q3) is False
    assert fy.eps == 2.1


def test_batch_adapter_passes_the_same_fundamental_contract() -> None:
    dataset = assert_fundamental_source_contract(
        make_akshare_fundamental_adapter_batch(),
        valid_query=valid_batch_fundamental_query(),
        empty_query=empty_fundamental_query(),
    )
    ping = [item for item in dataset.items if item.instrument_id == ping_an()]
    assert len(ping) == 1
    period = ping[0]
    assert period.natural_key == (ping_an(), date(2026, 6, 30), FinancialPeriodType.H1)
    assert period.currency == "CNY"
    assert period.revenue == 70617000000.0
    assert period.debt_ratio_pct == 90.9
    assert period.net_margin_pct == pytest.approx(period.net_profit / period.revenue * 100)


def test_single_and_batch_share_standard_record_shape() -> None:
    single = make_akshare_fundamental_adapter_single().fetch_fundamentals(
        valid_fundamental_query()
    )
    batch = make_akshare_fundamental_adapter_batch().fetch_fundamentals(
        valid_batch_fundamental_query()
    )
    single_h1 = next(item for item in single.items if item.period_end == date(2026, 6, 30))
    batch_h1 = next(item for item in batch.items if item.instrument_id == ping_an())
    assert single_h1.natural_key == batch_h1.natural_key
    assert set(single_h1.__dataclass_fields__) == set(batch_h1.__dataclass_fields__)
    assert single_h1.revenue == batch_h1.revenue
    assert single_h1.roe_pct == batch_h1.roe_pct


def test_missing_announcement_is_displayable_but_not_point_in_time_safe() -> None:
    dataset = make_akshare_fundamental_adapter_single().fetch_fundamentals(
        valid_fundamental_query()
    )
    unsafe = [item for item in dataset.items if not is_point_in_time_safe(item)]
    assert unsafe
    assert all(item.announced_at is None for item in unsafe)
    safe = point_in_time_safe_periods(dataset.items)
    assert all(item.announced_at is not None for item in safe)
    assert len(safe) == len(dataset.items) - len(unsafe)
