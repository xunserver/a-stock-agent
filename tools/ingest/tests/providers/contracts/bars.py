"""Reusable Bar capability contract.

Later Adapter tests supply a fixture-backed BarSource and call
``assert_bar_source_contract``.
"""

from __future__ import annotations

from astock_core.market_data import (
    BarQuery,
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    reject_vendor_types,
    validate_bar_dataset,
)

from astock.providers.protocols import BarSource


def assert_bar_source_contract(
    source: BarSource,
    *,
    valid_query: BarQuery,
    empty_query: BarQuery,
    error_cases: tuple[tuple[BarQuery, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_bars(valid_query)
    _assert_dataset_seam(first)
    validate_bar_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Bar query must return at least one Bar")

    second = source.fetch_bars(valid_query)
    if first.items != second.items:
        raise AssertionError("Bar Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("Bar Dataset source must be stable across calls")

    empty = source.fetch_bars(empty_query)
    _assert_dataset_seam(empty)
    validate_bar_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Bar query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Bar Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_bars(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"BarSource should raise {error_type.__name__}, got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(f"BarSource should raise {error_type.__name__} for {query}")

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(f"BarSource must return Dataset, got {type(dataset).__name__}")
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
