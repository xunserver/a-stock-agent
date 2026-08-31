"""Reusable Calendar capability contract.

Later Adapter tests supply a fixture-backed CalendarSource and call
``assert_calendar_source_contract``.
"""

from __future__ import annotations

from astock_core.market_data import (
    CalendarQuery,
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    reject_vendor_types,
    validate_calendar_dataset,
)

from astock.providers.protocols import CalendarSource


def assert_calendar_source_contract(
    source: CalendarSource,
    *,
    valid_query: CalendarQuery,
    empty_query: CalendarQuery,
    error_cases: tuple[tuple[CalendarQuery, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_calendar(valid_query)
    _assert_dataset_seam(first)
    validate_calendar_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Calendar query must return at least one TradingDay")

    second = source.fetch_calendar(valid_query)
    if first.items != second.items:
        raise AssertionError("Calendar Dataset items must be deterministic across calls")

    empty = source.fetch_calendar(empty_query)
    _assert_dataset_seam(empty)
    validate_calendar_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Calendar query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Calendar Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_calendar(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"CalendarSource should raise {error_type.__name__}, got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(
                f"CalendarSource should raise {error_type.__name__} for {query}"
            )

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(f"CalendarSource must return Dataset, got {type(dataset).__name__}")
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
