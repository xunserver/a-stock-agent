"""Reusable News capability contract."""

from __future__ import annotations

from astock_core.market_data import (
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    reject_vendor_types,
    validate_news_dataset,
)

from astock.providers.protocols import NewsSource


def assert_news_source_contract(
    source: NewsSource,
    *,
    valid_query,
    empty_query,
    error_cases: tuple[tuple[object, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_news(valid_query)
    _assert_dataset_seam(first)
    validate_news_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid News query must return at least one NewsItem")

    second = source.fetch_news(valid_query)
    if first.items != second.items:
        raise AssertionError("News Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("News Dataset source must be stable across calls")

    empty = source.fetch_news(empty_query)
    _assert_dataset_seam(empty)
    validate_news_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty News query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty News Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_news(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"NewsSource should raise {error_type.__name__}, got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(f"NewsSource should raise {error_type.__name__} for {query}")

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(f"NewsSource must return Dataset, got {type(dataset).__name__}")
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
