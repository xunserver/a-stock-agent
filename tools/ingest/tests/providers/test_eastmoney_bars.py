from __future__ import annotations

from datetime import date

import pytest

from astock.providers.eastmoney import EastmoneyBarAdapter
from astock.providers.protocols import BarSource
from astock_core.market_data import (
    Adjustment,
    BarInterval,
    BarQuery,
    InstrumentNotFound,
    InvalidSourcePayload,
    SourceUnavailable,
)

from .contracts import assert_bar_source_contract
from .fixture_sources import (
    empty_bar_query,
    eastmoney_get_json,
    hs300,
    load_json,
    make_eastmoney_bar_adapter,
    unknown_bar_query,
    valid_bar_query,
)


def test_eastmoney_bar_adapter_satisfies_protocol_without_inheriting() -> None:
    source = make_eastmoney_bar_adapter()
    assert isinstance(source, BarSource)
    assert EastmoneyBarAdapter not in BarSource.__mro__
    assert BarSource not in type(source).__mro__[1:]


def test_eastmoney_bar_adapter_passes_shared_contract() -> None:
    dataset = assert_bar_source_contract(
        make_eastmoney_bar_adapter(),
        valid_query=valid_bar_query(),
        empty_query=empty_bar_query(),
        error_cases=((unknown_bar_query(), InstrumentNotFound),),
    )
    assert dataset.source == "eastmoney"
    first = dataset.items[0]
    # Eastmoney 成交量 is 手; 10000 lots * 100 = 1_000_000 shares. 成交额 is already CNY.
    assert first.volume == 1_000_000.0
    assert first.amount == 10_500_000.0
    assert first.turnover_pct == 1.25
    assert first.adjustment is Adjustment.QFQ
    assert first.interval is BarInterval.D1


def test_eastmoney_bar_adapter_covers_weekly_and_monthly() -> None:
    for interval, expected_dates in (
        (BarInterval.W1, (date(2026, 8, 7), date(2026, 8, 14))),
        (BarInterval.M1, (date(2026, 8, 31),)),
    ):
        query = BarQuery(
            instruments=valid_bar_query().instruments,
            start=date(2026, 8, 1),
            end=date(2026, 8, 31),
            interval=interval,
            adjustment=Adjustment.QFQ,
        )
        dataset = make_eastmoney_bar_adapter().fetch_bars(query)
        assert tuple(item.trade_date for item in dataset.items) == expected_dates
        assert all(item.interval is interval for item in dataset.items)
        assert dataset.items[0].volume == 1_000_000.0


def test_eastmoney_bar_adapter_maps_index_payloads() -> None:
    query = BarQuery(
        instruments=(hs300(),),
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=BarInterval.D1,
        adjustment=Adjustment.RAW,
    )
    dataset = make_eastmoney_bar_adapter().fetch_bars(query)
    assert dataset.items[0].instrument_id == hs300()
    assert dataset.items[0].volume == 5_000_000.0
    assert dataset.items[0].amount == 8_000_000_000.0
    assert dataset.items[0].turnover_pct is None
    assert dataset.items[0].adjustment is Adjustment.RAW


def test_eastmoney_bar_adapter_sorts_unsorted_klines() -> None:
    adapter = make_eastmoney_bar_adapter(
        get_json=eastmoney_get_json(stock="stock_klines_unsorted.json")
    )
    dataset = assert_bar_source_contract(
        adapter,
        valid_query=valid_bar_query(),
        empty_query=empty_bar_query(),
        error_cases=((unknown_bar_query(), InstrumentNotFound),),
    )
    assert [item.trade_date for item in dataset.items] == [date(2026, 8, 27), date(2026, 8, 28)]


def test_eastmoney_bar_adapter_rejects_duplicate_and_malformed() -> None:
    duplicate = make_eastmoney_bar_adapter(
        get_json=eastmoney_get_json(stock="stock_klines_duplicate.json")
    )
    malformed = make_eastmoney_bar_adapter(
        get_json=eastmoney_get_json(stock="stock_klines_malformed.json")
    )
    with pytest.raises(InvalidSourcePayload):
        duplicate.fetch_bars(valid_bar_query())
    with pytest.raises(InvalidSourcePayload):
        malformed.fetch_bars(valid_bar_query())


def test_eastmoney_bar_adapter_translates_transport_failure() -> None:
    def get_json(url: str, params: dict[str, str], timeout: float) -> object:
        raise ConnectionError("eastmoney timeout")

    adapter = make_eastmoney_bar_adapter(get_json=get_json)
    with pytest.raises(SourceUnavailable):
        adapter.fetch_bars(valid_bar_query())


def test_eastmoney_bar_adapter_injects_timeout_and_retries() -> None:
    seen: list[float] = []
    calls = {"n": 0}

    def get_json(url: str, params: dict[str, str], timeout: float) -> object:
        seen.append(timeout)
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("retry")
        return load_json("eastmoney", "stock_klines_empty.json")

    sleeps: list[float] = []
    adapter = make_eastmoney_bar_adapter(
        get_json=get_json,
        timeout=7.5,
        retries=3,
        sleep=sleeps.append,
    )
    dataset = adapter.fetch_bars(empty_bar_query())
    assert dataset.items == ()
    assert seen == [7.5, 7.5, 7.5]
    assert sleeps == [2, 4]
