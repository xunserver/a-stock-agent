from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from astock.providers.akshare import AkshareCalendarAdapter
from astock.providers.protocols import CalendarSource
from astock_core.market_data import InvalidSourcePayload, SourceUnavailable, UnsupportedQuery

from .contracts import assert_calendar_source_contract
from .fixture_sources import (
    empty_calendar_query,
    load_json,
    make_akshare_calendar_adapter,
    unknown_calendar_query,
    valid_calendar_query,
)


def test_akshare_calendar_adapter_satisfies_protocol_without_inheriting() -> None:
    source = make_akshare_calendar_adapter()
    assert isinstance(source, CalendarSource)
    assert CalendarSource not in type(source).__mro__[1:]


def test_akshare_calendar_adapter_passes_shared_contract() -> None:
    dataset = assert_calendar_source_contract(
        make_akshare_calendar_adapter(),
        valid_query=valid_calendar_query(),
        empty_query=empty_calendar_query(),
        error_cases=((unknown_calendar_query(), UnsupportedQuery),),
    )
    assert dataset.source == "akshare"
    assert dataset.coverage_start == date(2026, 8, 1)
    assert dataset.coverage_end == date(2026, 8, 31)
    assert dataset.complete is True
    assert [item.trade_date for item in dataset.items] == [date(2026, 8, 3), date(2026, 8, 4)]
    assert all(item.is_open for item in dataset.items)


def test_akshare_calendar_adapter_sorts_unsorted_fixture() -> None:
    dataset = assert_calendar_source_contract(
        make_akshare_calendar_adapter(rows=load_json("akshare", "calendar_unsorted.json")),
        valid_query=valid_calendar_query(),
        empty_query=empty_calendar_query(),
        error_cases=((unknown_calendar_query(), UnsupportedQuery),),
    )
    assert [item.trade_date for item in dataset.items] == [date(2026, 8, 3), date(2026, 8, 4)]


def test_akshare_calendar_adapter_rejects_duplicate_fixture() -> None:
    adapter = make_akshare_calendar_adapter(rows=load_json("akshare", "calendar_duplicate.json"))
    with pytest.raises(InvalidSourcePayload, match="duplicate"):
        adapter.fetch_calendar(valid_calendar_query())


def test_akshare_calendar_adapter_rejects_malformed_and_missing_columns() -> None:
    malformed = make_akshare_calendar_adapter(rows=load_json("akshare", "calendar_malformed.json"))
    missing = make_akshare_calendar_adapter(rows=load_json("akshare", "calendar_missing_column.json"))
    with pytest.raises(InvalidSourcePayload):
        malformed.fetch_calendar(valid_calendar_query())
    with pytest.raises(InvalidSourcePayload, match="trade_date"):
        missing.fetch_calendar(valid_calendar_query())


def test_akshare_calendar_adapter_translates_network_failure() -> None:
    def trade_date_hist():
        raise ConnectionError("sina calendar down")

    adapter = make_akshare_calendar_adapter(trade_date_hist=trade_date_hist)
    with pytest.raises(SourceUnavailable):
        adapter.fetch_calendar(valid_calendar_query())


def test_akshare_calendar_adapter_accepts_dataframe_without_leaking_pandas() -> None:
    frame = pd.DataFrame(load_json("akshare", "calendar_valid.json"))
    dataset = make_akshare_calendar_adapter(rows=frame).fetch_calendar(valid_calendar_query())
    assert type(dataset.items) is tuple
    assert dataset.items[0].trade_date == date(2026, 8, 3)
    assert not hasattr(dataset.items[0], "iloc")
