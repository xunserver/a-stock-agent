"""Reusable Quote Snapshot capability contract."""

from __future__ import annotations

from astock_core.market_data import (
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    SnapshotQuery,
    reject_vendor_types,
    validate_quote_snapshot_dataset,
)

from astock.providers.protocols import QuoteSnapshotSource


def assert_quote_snapshot_source_contract(
    source: QuoteSnapshotSource,
    *,
    valid_query: SnapshotQuery,
    empty_query: SnapshotQuery,
    error_cases: tuple[tuple[SnapshotQuery, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_snapshots(valid_query)
    _assert_dataset_seam(first)
    validate_quote_snapshot_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Snapshot query must return at least one QuoteSnapshot")
    for item in first.items:
        if item.observed_at.tzinfo is None:
            raise AssertionError("QuoteSnapshot.observed_at must be timezone-aware")

    second = source.fetch_snapshots(valid_query)
    if first.items != second.items:
        raise AssertionError("Quote Snapshot Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("Quote Snapshot Dataset source must be stable across calls")

    empty = source.fetch_snapshots(empty_query)
    _assert_dataset_seam(empty)
    validate_quote_snapshot_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Snapshot query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Quote Snapshot Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_snapshots(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"QuoteSnapshotSource should raise {error_type.__name__}, "
                f"got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(
                f"QuoteSnapshotSource should raise {error_type.__name__} for {query}"
            )

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(
            f"QuoteSnapshotSource must return Dataset, got {type(dataset).__name__}"
        )
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
