from __future__ import annotations

from astock.providers.akshare import AkshareInstrumentAdapter, AkshareSnapshotAdapter
from astock.providers.protocols import InstrumentSource, QuoteSnapshotSource, ValuationSource
from astock_core.market_data import InstrumentNotFound, InstrumentQuery

from .contracts import (
    assert_instrument_source_contract,
    assert_quote_snapshot_source_contract,
    assert_valuation_source_contract,
)
from .fixture_sources import (
    empty_instrument_query,
    empty_snapshot_query,
    empty_valuation_query,
    make_akshare_instrument_adapter,
    make_akshare_snapshot_adapter,
    unknown_snapshot_query,
    unknown_valuation_query,
    valid_instrument_query,
    valid_snapshot_query,
    valid_valuation_query,
)
from .fakes import maotai


def test_akshare_instrument_adapter_satisfies_protocol_without_inheriting() -> None:
    source = make_akshare_instrument_adapter()
    assert isinstance(source, InstrumentSource)
    assert AkshareInstrumentAdapter not in InstrumentSource.__mro__


def test_akshare_instrument_adapter_passes_shared_contract() -> None:
    dataset = assert_instrument_source_contract(
        make_akshare_instrument_adapter(),
        valid_query=valid_instrument_query(),
        empty_query=empty_instrument_query(),
    )
    assert dataset.source == "akshare"
    assert [item.id.symbol for item in dataset.items] == ["000001", "600519"]
    assert dataset.items[0].currency == "CNY"
    assert dataset.items[0].timezone == "Asia/Shanghai"


def test_akshare_snapshot_adapter_passes_shared_contracts() -> None:
    source = make_akshare_snapshot_adapter()
    assert isinstance(source, QuoteSnapshotSource)
    assert isinstance(source, ValuationSource)
    assert AkshareSnapshotAdapter not in QuoteSnapshotSource.__mro__

    quotes = assert_quote_snapshot_source_contract(
        source,
        valid_query=valid_snapshot_query(),
        empty_query=empty_snapshot_query(),
        error_cases=((unknown_snapshot_query(), InstrumentNotFound),),
    )
    assert quotes.source == "akshare"
    first = quotes.items[0]
    assert first.last_price == 1400.0
    assert first.pre_close == 1390.0
    assert first.average_price == 1395.0
    assert first.observed_at.tzinfo is not None

    valuations = assert_valuation_source_contract(
        make_akshare_snapshot_adapter(),
        valid_query=valid_valuation_query(),
        empty_query=empty_valuation_query(),
        error_cases=((unknown_valuation_query(), InstrumentNotFound),),
    )
    assert valuations.items[0].pe_ttm == 20.5
    assert valuations.items[0].pe_static == 22.0
    assert valuations.items[0].total_shares == 1254198000


def test_akshare_snapshot_adapter_maps_profile_and_optional_missing_values() -> None:
    source = make_akshare_snapshot_adapter()
    profiles = source.fetch_profiles(InstrumentQuery(instruments=(maotai(),)))
    profile = profiles.items[0]
    assert profile.name == "贵州茅台"
    assert profile.industry == "白酒"
    assert profile.region is None
    assert profile.list_date.isoformat() == "2001-08-27"
    assert profile.is_st is False
    snapshots = source.fetch_snapshots(valid_snapshot_query())
    assert snapshots.items[0].suspend_reason is None
    assert snapshots.items[0].is_suspended is False
