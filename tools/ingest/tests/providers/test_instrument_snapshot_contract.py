from __future__ import annotations

import pytest

from astock.providers.protocols import (
    InstrumentSource,
    QuoteSnapshotSource,
    ValuationSource,
)
from astock_core.market_data import (
    AssetType,
    InstrumentNotFound,
    InstrumentQuery,
    InvalidSourcePayload,
    SnapshotQuery,
    ValuationQuery,
    from_legacy_symbol,
)

from .contracts import (
    assert_instrument_source_contract,
    assert_quote_snapshot_source_contract,
    assert_valuation_source_contract,
)
from .fakes import (
    InMemoryInstrumentSource,
    InMemoryQuoteSnapshotSource,
    InMemoryValuationSource,
    aware_now,
    maotai,
    make_instrument,
    make_snapshot,
    make_valuation,
    ping_an,
)


def test_in_memory_instrument_source_passes_reusable_contract() -> None:
    source = InMemoryInstrumentSource((make_instrument(), make_instrument(instrument_id=ping_an(), name="Ping An Bank")))
    dataset = assert_instrument_source_contract(
        source,
        valid_query=InstrumentQuery(asset_types=(AssetType.STOCK,)),
        empty_query=InstrumentQuery(asset_types=(AssetType.ETF,)),
    )
    assert dataset.source == "memory"
    assert dataset.items[0].id == ping_an()


def test_in_memory_quote_snapshot_source_passes_reusable_contract() -> None:
    source = InMemoryQuoteSnapshotSource((make_snapshot(),), known=(maotai(), ping_an()))
    dataset = assert_quote_snapshot_source_contract(
        source,
        valid_query=SnapshotQuery(instruments=(maotai(),)),
        empty_query=SnapshotQuery(instruments=(ping_an(),)),
        error_cases=((SnapshotQuery(instruments=(from_legacy_symbol("000002"),)), InstrumentNotFound),),
    )
    assert dataset.items[0].last_price == 1400.0
    assert dataset.items[0].observed_at.tzinfo is not None


def test_in_memory_quote_empty_when_known_without_rows() -> None:
    source = InMemoryQuoteSnapshotSource((), known=(maotai(), ping_an()))
    empty = source.fetch_snapshots(SnapshotQuery(instruments=(maotai(),)))
    assert empty.items == ()
    assert empty.complete is True


def test_in_memory_valuation_source_passes_reusable_contract() -> None:
    source = InMemoryValuationSource((make_valuation(),), known=(maotai(), ping_an()))
    dataset = assert_valuation_source_contract(
        source,
        valid_query=ValuationQuery(instruments=(maotai(),)),
        empty_query=ValuationQuery(instruments=(ping_an(),)),
        error_cases=((ValuationQuery(instruments=(from_legacy_symbol("000002"),)), InstrumentNotFound),),
    )
    assert dataset.items[0].pe_ttm == 20.5
    assert dataset.items[0].currency == "CNY"


def test_in_memory_sources_satisfy_protocols_without_inheriting() -> None:
    instrument_source = InMemoryInstrumentSource((make_instrument(),))
    snapshot_source = InMemoryQuoteSnapshotSource((make_snapshot(),))
    valuation_source = InMemoryValuationSource((make_valuation(),))
    assert isinstance(instrument_source, InstrumentSource)
    assert isinstance(snapshot_source, QuoteSnapshotSource)
    assert isinstance(valuation_source, ValuationSource)
    assert InstrumentSource not in type(instrument_source).__mro__[1:]
    assert QuoteSnapshotSource not in type(snapshot_source).__mro__[1:]
    assert ValuationSource not in type(valuation_source).__mro__[1:]


def test_broken_snapshot_source_fails_for_invalid_numeric() -> None:
    class NanSnapshotSource:
        def fetch_snapshots(self, query: SnapshotQuery):
            snapshot = make_snapshot(last_price=float("nan"))
            from astock_core.market_data import Dataset

            return Dataset(items=(snapshot,), source="memory", fetched_at=aware_now())

    with pytest.raises((InvalidSourcePayload, AssertionError)):
        assert_quote_snapshot_source_contract(
            NanSnapshotSource(),
            valid_query=SnapshotQuery(instruments=(maotai(),)),
            empty_query=SnapshotQuery(instruments=(ping_an(),)),
        )
