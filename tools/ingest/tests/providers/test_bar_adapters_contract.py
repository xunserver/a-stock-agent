from __future__ import annotations

import pytest

from astock.providers.akshare import AkshareBarAdapter
from astock.providers.eastmoney import EastmoneyBarAdapter
from astock_core.market_data import InstrumentNotFound

from .contracts import assert_bar_source_contract
from .fixture_sources import empty_bar_query, make_akshare_bar_adapter, make_eastmoney_bar_adapter, unknown_bar_query, valid_bar_query


@pytest.mark.parametrize(
    ("factory", "source_name"),
    (
        (make_eastmoney_bar_adapter, "eastmoney"),
        (make_akshare_bar_adapter, "akshare"),
    ),
)
def test_both_bar_adapters_pass_one_shared_contract(factory, source_name: str) -> None:
    dataset = assert_bar_source_contract(
        factory(),
        valid_query=valid_bar_query(),
        empty_query=empty_bar_query(),
        error_cases=((unknown_bar_query(), InstrumentNotFound),),
    )
    assert dataset.source == source_name
    assert dataset.items[0].volume == 1_000_000.0
    assert dataset.items[0].amount == 10_500_000.0
    assert type(factory()).__name__ in {EastmoneyBarAdapter.__name__, AkshareBarAdapter.__name__}
