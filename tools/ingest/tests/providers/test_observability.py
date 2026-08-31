from __future__ import annotations

import logging
from datetime import date

from astock.providers.observability import log_capability_attempt, query_identity, redact_message
from astock_core.market_data import BarQuery, Dataset, SourceUnavailable, from_legacy_symbol

from .fakes import aware_now, make_bar


def test_query_identity_truncates_large_instrument_lists() -> None:
    instruments = tuple(from_legacy_symbol(f"{idx:06d}") for idx in range(20))
    query = BarQuery(
        instruments=instruments,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        interval=make_bar().interval,
        adjustment=make_bar().adjustment,
    )
    identity = query_identity(query)
    assert "+12 more" in identity


def test_redact_message_masks_secrets() -> None:
    raw = "AuthenticationFailed api_key=super-secret-token please retry"
    redacted = redact_message(raw)
    assert "super-secret-token" not in redacted
    assert "REDACTED" in redacted


def test_log_capability_attempt_emits_required_fields(caplog) -> None:
    caplog.set_level(logging.INFO, logger="astock.providers.market_data")
    dataset = Dataset(
        items=(make_bar(),),
        source="eastmoney",
        fetched_at=aware_now(),
        coverage_start=date(2026, 8, 1),
        coverage_end=date(2026, 8, 31),
        complete=True,
        warnings=("token=hidden",),
    )
    query = BarQuery(
        instruments=(from_legacy_symbol("600519"),),
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=make_bar().interval,
        adjustment=make_bar().adjustment,
    )
    record = log_capability_attempt(
        capability="bars",
        source="eastmoney",
        query=query,
        attempt=1,
        elapsed_ms=12.5,
        dataset=dataset,
        outcome="success",
    )
    line = caplog.records[-1].message
    assert "capability" in line
    assert "query_identity" in line
    assert "item_count" in line
    assert "warning_count" in line
    assert record.error_category is None


def test_failure_log_redacts_error_message(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="astock.providers.market_data")
    query = BarQuery(
        instruments=(from_legacy_symbol("600519"),),
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=make_bar().interval,
        adjustment=make_bar().adjustment,
    )
    log_capability_attempt(
        capability="bars",
        source="eastmoney",
        query=query,
        attempt=1,
        elapsed_ms=3.0,
        error=SourceUnavailable("cookie=abc123"),
        outcome="failure",
    )
    assert "abc123" not in caplog.records[-1].message
