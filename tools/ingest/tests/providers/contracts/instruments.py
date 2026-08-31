"""Reusable Instrument capability contract."""

from __future__ import annotations

from astock_core.market_data import (
    Dataset,
    InstrumentQuery,
    InvalidSourcePayload,
    MarketDataError,
    reject_vendor_types,
    validate_instrument_dataset,
)

from astock.providers.protocols import InstrumentSource


def assert_instrument_source_contract(
    source: InstrumentSource,
    *,
    valid_query: InstrumentQuery,
    empty_query: InstrumentQuery,
    error_cases: tuple[tuple[InstrumentQuery, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_instruments(valid_query)
    _assert_dataset_seam(first)
    validate_instrument_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Instrument query must return at least one Instrument")

    second = source.fetch_instruments(valid_query)
    if first.items != second.items:
        raise AssertionError("Instrument Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("Instrument Dataset source must be stable across calls")

    empty = source.fetch_instruments(empty_query)
    _assert_dataset_seam(empty)
    validate_instrument_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Instrument query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Instrument Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_instruments(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"InstrumentSource should raise {error_type.__name__}, got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(f"InstrumentSource should raise {error_type.__name__} for {query}")

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(f"InstrumentSource must return Dataset, got {type(dataset).__name__}")
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
