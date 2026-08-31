from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from astock.providers.akshare import AkshareBarAdapter
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
    load_json,
    make_akshare_bar_adapter,
    unknown_bar_query,
    valid_bar_query,
)


def test_akshare_bar_adapter_satisfies_protocol_without_inheriting() -> None:
    source = make_akshare_bar_adapter()
    assert isinstance(source, BarSource)
    assert BarSource not in type(source).__mro__[1:]


def test_akshare_bar_adapter_passes_shared_contract() -> None:
    dataset = assert_bar_source_contract(
        make_akshare_bar_adapter(),
        valid_query=valid_bar_query(),
        empty_query=empty_bar_query(),
        error_cases=((unknown_bar_query(), InstrumentNotFound),),
    )
    assert dataset.source == "akshare"
    first = dataset.items[0]
    # Tencent hist_tx already reports volume in shares and amount in CNY.
    assert first.volume == 1_000_000.0
    assert first.amount == 10_500_000.0
    assert first.turnover_pct == 1.25


def test_akshare_bar_adapter_does_not_return_pandas() -> None:
    frame = pd.DataFrame(load_json("akshare", "hist_tx_valid.json"))
    adapter = make_akshare_bar_adapter(hist_tx_rows=frame)
    dataset = adapter.fetch_bars(valid_bar_query())
    assert type(dataset.items) is tuple
    assert dataset.items[0].volume == 1_000_000.0
    assert not hasattr(dataset.items[0], "iloc")


def test_akshare_bar_adapter_maps_chinese_hist_columns_and_lots() -> None:
    query = BarQuery(
        instruments=valid_bar_query().instruments,
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=BarInterval.W1,
        adjustment=Adjustment.QFQ,
    )
    dataset = make_akshare_bar_adapter().fetch_bars(query)
    assert tuple(item.trade_date for item in dataset.items) == (date(2026, 8, 7), date(2026, 8, 14))
    # Eastmoney-backed hist 成交量 is 手.
    assert dataset.items[0].volume == 1_000_000.0
    assert dataset.items[0].amount == 10_500_000.0
    assert dataset.items[0].turnover_pct == 1.25


def test_akshare_bar_adapter_covers_monthly_interval() -> None:
    query = BarQuery(
        instruments=valid_bar_query().instruments,
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=BarInterval.M1,
        adjustment=Adjustment.HFQ,
    )
    dataset = make_akshare_bar_adapter().fetch_bars(query)
    assert len(dataset.items) == 1
    assert dataset.items[0].trade_date == date(2026, 8, 31)
    assert dataset.items[0].adjustment is Adjustment.HFQ


def test_akshare_bar_adapter_falls_back_from_tencent_to_sina() -> None:
    sina_rows = load_json("akshare", "hist_tx_valid.json")
    adapter = make_akshare_bar_adapter(hist_tx_rows=[], daily_rows=sina_rows)
    dataset = adapter.fetch_bars(valid_bar_query())
    assert len(dataset.items) == 2
    assert dataset.source == "akshare"


def test_akshare_bar_adapter_converts_pandas_na_before_the_seam() -> None:
    rows = [
        {
            "date": "2026-08-27",
            "open": 10.0,
            "close": float("nan"),
            "high": 11.0,
            "low": 9.5,
            "volume": 1_000_000,
            "amount": 10_500_000.0,
        }
    ]
    adapter = make_akshare_bar_adapter(hist_tx_rows=pd.DataFrame(rows))
    with pytest.raises(InvalidSourcePayload):
        adapter.fetch_bars(valid_bar_query())


def test_akshare_bar_adapter_rejects_malformed_payload() -> None:
    adapter = make_akshare_bar_adapter(
        hist_tx_rows=[{"date": "2026-08-27", "open": "x", "close": 1, "high": 1, "low": 1, "volume": 1, "amount": 1}]
    )
    with pytest.raises(InvalidSourcePayload):
        adapter.fetch_bars(valid_bar_query())


def test_akshare_bar_adapter_translates_transport_failure() -> None:
    def hist_tx(*args, **kwargs):
        raise ConnectionError("tencent down")

    def daily(*args, **kwargs):
        raise TimeoutError("sina down")

    adapter = make_akshare_bar_adapter(hist_tx=hist_tx, daily=daily)
    with pytest.raises(SourceUnavailable):
        adapter.fetch_bars(valid_bar_query())
