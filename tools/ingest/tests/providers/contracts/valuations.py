"""Reusable Valuation Snapshot capability contract."""

from __future__ import annotations

from astock_core.market_data import (
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    ValuationQuery,
    reject_vendor_types,
    validate_valuation_dataset,
)

from astock.providers.protocols import ValuationSource


def assert_valuation_source_contract(
    source: ValuationSource,
    *,
    valid_query: ValuationQuery,
    empty_query: ValuationQuery,
    error_cases: tuple[tuple[ValuationQuery, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_valuations(valid_query)
    _assert_dataset_seam(first)
    validate_valuation_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Valuation query must return at least one ValuationSnapshot")

    second = source.fetch_valuations(valid_query)
    if first.items != second.items:
        raise AssertionError("Valuation Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("Valuation Dataset source must be stable across calls")

    empty = source.fetch_valuations(empty_query)
    _assert_dataset_seam(empty)
    validate_valuation_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Valuation query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Valuation Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_valuations(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"ValuationSource should raise {error_type.__name__}, got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(f"ValuationSource should raise {error_type.__name__} for {query}")

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(f"ValuationSource must return Dataset, got {type(dataset).__name__}")
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
