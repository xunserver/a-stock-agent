"""Reusable Event capability contract."""

from __future__ import annotations

from astock_core.market_data import (
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    reject_vendor_types,
    validate_event_dataset,
)

from astock.providers.protocols import EventSource


def assert_event_source_contract(
    source: EventSource,
    *,
    valid_query,
    empty_query,
    error_cases: tuple[tuple[object, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_events(valid_query)
    _assert_dataset_seam(first)
    validate_event_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Event query must return at least one MarketEvent")

    second = source.fetch_events(valid_query)
    if first.items != second.items:
        raise AssertionError("Event Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("Event Dataset source must be stable across calls")

    empty = source.fetch_events(empty_query)
    _assert_dataset_seam(empty)
    validate_event_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Event query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Event Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_events(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"EventSource should raise {error_type.__name__}, got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(f"EventSource should raise {error_type.__name__} for {query}")

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(f"EventSource must return Dataset, got {type(dataset).__name__}")
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
