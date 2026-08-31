"""Reusable Classification capability contract."""

from __future__ import annotations

from astock_core.market_data import (
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    reject_vendor_types,
    validate_classification_dataset,
)

from astock.providers.protocols import ClassificationSource


def assert_classification_source_contract(
    source: ClassificationSource,
    *,
    valid_query,
    empty_query,
    error_cases: tuple[tuple[object, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_classifications(valid_query)
    _assert_dataset_seam(first)
    validate_classification_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Classification query must return at least one Classification")

    second = source.fetch_classifications(valid_query)
    if first.items != second.items:
        raise AssertionError("Classification Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("Classification Dataset source must be stable across calls")

    keys = {item.natural_key for item in first.items}
    if len(keys) != len(first.items):
        raise AssertionError("Classification natural keys must be unique within a Dataset")

    empty = source.fetch_classifications(empty_query)
    _assert_dataset_seam(empty)
    validate_classification_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Classification query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Classification Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_classifications(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"ClassificationSource should raise {error_type.__name__}, "
                f"got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(
                f"ClassificationSource should raise {error_type.__name__} for {query}"
            )

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(
            f"ClassificationSource must return Dataset, got {type(dataset).__name__}"
        )
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
