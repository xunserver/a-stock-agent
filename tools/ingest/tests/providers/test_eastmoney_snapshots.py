from __future__ import annotations

import pytest

from astock.providers.eastmoney import EastmoneySnapshotAdapter
from astock.providers.protocols import (
    InstrumentProfileSource,
    QuoteSnapshotSource,
    ValuationSource,
)
from astock_core.market_data import InstrumentNotFound, InvalidSourcePayload, SourceUnavailable

from .contracts import assert_quote_snapshot_source_contract, assert_valuation_source_contract
from .fixture_sources import (
    empty_snapshot_query,
    empty_valuation_query,
    eastmoney_quote_get_json,
    make_eastmoney_snapshot_adapter,
    unknown_snapshot_query,
    unknown_valuation_query,
    valid_snapshot_query,
    valid_valuation_query,
)


def test_eastmoney_snapshot_adapter_satisfies_protocols_without_inheriting() -> None:
    source = make_eastmoney_snapshot_adapter()
    assert isinstance(source, QuoteSnapshotSource)
    assert isinstance(source, ValuationSource)
    assert isinstance(source, InstrumentProfileSource)
    assert EastmoneySnapshotAdapter not in QuoteSnapshotSource.__mro__


def test_eastmoney_snapshot_adapter_passes_shared_contracts() -> None:
    source = make_eastmoney_snapshot_adapter()
    quotes = assert_quote_snapshot_source_contract(
        source,
        valid_query=valid_snapshot_query(),
        empty_query=empty_snapshot_query(),
        error_cases=((unknown_snapshot_query(), InstrumentNotFound),),
    )
    assert quotes.source == "eastmoney"
    first = quotes.items[0]
    assert first.last_price == 1400.0
    assert first.pre_close == 1390.0
    assert first.average_price == 1395.0
    assert first.volume_ratio == 1.1
    assert first.outer_volume == 100.0
    assert first.observed_at.tzinfo is not None

    valuations = assert_valuation_source_contract(
        make_eastmoney_snapshot_adapter(),
        valid_query=valid_valuation_query(),
        empty_query=empty_valuation_query(),
        error_cases=((unknown_valuation_query(), InstrumentNotFound),),
    )
    assert valuations.source == "eastmoney"
    value = valuations.items[0]
    assert value.pe_ttm == 20.5
    assert value.pe_static == 22.0
    assert value.pb == 8.1
    assert value.total_shares == 1254198000
    assert value.currency == "CNY"


def test_eastmoney_snapshot_adapter_maps_profile_fields() -> None:
    from astock_core.market_data import InstrumentQuery

    from .fakes import maotai

    dataset = make_eastmoney_snapshot_adapter().fetch_profiles(
        InstrumentQuery(instruments=(maotai(),))
    )
    profile = dataset.items[0]
    assert profile.name == "贵州茅台"
    assert profile.industry == "白酒"
    assert profile.region == "贵州板块"
    assert profile.list_date.isoformat() == "2001-08-27"
    assert profile.is_st is False


def test_eastmoney_snapshot_adapter_rejects_invalid_numerics() -> None:
    source = make_eastmoney_snapshot_adapter(
        get_json=eastmoney_quote_get_json(malformed="stock_quote_malformed.json")
    )
    with pytest.raises(InvalidSourcePayload, match="last_price"):
        source.fetch_snapshots(valid_snapshot_query())


def test_eastmoney_snapshot_adapter_translates_transport_errors() -> None:
    def boom(url: str, params: dict[str, str], timeout: float) -> object:
        raise TimeoutError("timed out")

    source = make_eastmoney_snapshot_adapter(get_json=boom)
    with pytest.raises(SourceUnavailable):
        source.fetch_snapshots(valid_snapshot_query())
