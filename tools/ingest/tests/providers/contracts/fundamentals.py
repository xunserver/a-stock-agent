"""Reusable Fundamental Period capability contract."""

from __future__ import annotations

from astock_core.market_data import (
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    reject_vendor_types,
    validate_fundamental_dataset,
)

from astock.providers.protocols import FundamentalSource


def assert_fundamental_source_contract(
    source: FundamentalSource,
    *,
    valid_query,
    empty_query,
    error_cases: tuple[tuple[object, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_fundamentals(valid_query)
    _assert_dataset_seam(first)
    validate_fundamental_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Fundamental query must return at least one FundamentalPeriod")
    currencies = {item.currency for item in first.items}
    if currencies != {"CNY"}:
        raise AssertionError(f"FundamentalPeriod.currency must be CNY, got {currencies}")
    for item in first.items:
        if item.announced_at is not None and item.announced_at.tzinfo is None:
            raise AssertionError("FundamentalPeriod.announced_at must be timezone-aware when present")

    second = source.fetch_fundamentals(valid_query)
    if first.items != second.items:
        raise AssertionError("Fundamental Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("Fundamental Dataset source must be stable across calls")

    empty = source.fetch_fundamentals(empty_query)
    _assert_dataset_seam(empty)
    validate_fundamental_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Fundamental query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Fundamental Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_fundamentals(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"FundamentalSource should raise {error_type.__name__}, "
                f"got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(
                f"FundamentalSource should raise {error_type.__name__} for {query}"
            )

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(
            f"FundamentalSource must return Dataset, got {type(dataset).__name__}"
        )
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
