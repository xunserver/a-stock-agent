from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from astock_core.market_data import (
    AuthenticationFailed,
    Dataset,
    InstrumentNotFound,
    InvalidSourcePayload,
    MarketDataError,
    NoData,
    RateLimited,
    SourceUnavailable,
    UnsupportedQuery,
)


def _aware() -> datetime:
    return datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


def test_dataset_accepts_tuple_items_and_warnings() -> None:
    dataset = Dataset(
        items=(1, 2),
        source="eastmoney",
        fetched_at=_aware(),
        coverage_start=date(2026, 1, 1),
        coverage_end=date(2026, 1, 31),
        complete=True,
        warnings=("partial session",),
    )
    assert dataset.items == (1, 2)
    assert dataset.source == "eastmoney"
    assert dataset.complete is True
    assert dataset.warnings == ("partial session",)


def test_dataset_rejects_empty_source() -> None:
    with pytest.raises(ValueError, match="source"):
        Dataset(items=(), source="", fetched_at=_aware())
    with pytest.raises(ValueError, match="source"):
        Dataset(items=(), source="   ", fetched_at=_aware())


def test_dataset_rejects_naive_fetched_at() -> None:
    with pytest.raises(ValueError, match="timezone"):
        Dataset(items=(), source="akshare", fetched_at=datetime(2026, 8, 31, 9, 30))


def test_dataset_rejects_inverted_coverage() -> None:
    with pytest.raises(ValueError, match="coverage"):
        Dataset(
            items=(),
            source="akshare",
            fetched_at=_aware(),
            coverage_start=date(2026, 1, 31),
            coverage_end=date(2026, 1, 1),
        )


def test_dataset_rejects_mutable_collection_inputs() -> None:
    with pytest.raises(ValueError, match="tuple"):
        Dataset(items=[1], source="akshare", fetched_at=_aware())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="tuple"):
        Dataset(
            items=(),
            source="akshare",
            fetched_at=_aware(),
            warnings=["late"],  # type: ignore[arg-type]
        )


def test_dataset_allows_one_sided_coverage() -> None:
    start_only = Dataset(
        items=(),
        source="akshare",
        fetched_at=_aware(),
        coverage_start=date(2026, 1, 1),
    )
    end_only = Dataset(
        items=(),
        source="akshare",
        fetched_at=_aware(),
        coverage_end=date(2026, 1, 31),
    )
    assert start_only.coverage_end is None
    assert end_only.coverage_start is None


def test_empty_dataset_is_distinct_from_error_types() -> None:
    empty = Dataset(items=(), source="akshare", fetched_at=_aware(), complete=True)
    assert empty.items == ()
    assert not isinstance(empty, MarketDataError)


@pytest.mark.parametrize(
    "error_type",
    [
        UnsupportedQuery,
        InstrumentNotFound,
        NoData,
        RateLimited,
        SourceUnavailable,
        InvalidSourcePayload,
        AuthenticationFailed,
    ],
)
def test_capability_errors_derive_from_market_data_error(error_type: type[MarketDataError]) -> None:
    error = error_type("example")
    assert isinstance(error, MarketDataError)
    assert isinstance(error, Exception)
    assert str(error) == "example"
