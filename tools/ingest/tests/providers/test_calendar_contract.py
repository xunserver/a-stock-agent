from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from astock.providers.protocols import CalendarSource
from astock_core.market_data import (
    CalendarQuery,
    Dataset,
    InvalidSourcePayload,
    TradingDay,
    UnsupportedQuery,
)

from .contracts import assert_calendar_source_contract
from .fakes import InMemoryCalendarSource, aware_now


def _day(trade_date: date, *, market_id: str = "cn_a", is_open: bool = True) -> TradingDay:
    return TradingDay(market_id=market_id, trade_date=trade_date, is_open=is_open)


def _valid_query() -> CalendarQuery:
    return CalendarQuery(market_id="cn_a", start=date(2026, 8, 1), end=date(2026, 8, 31))


def _empty_query() -> CalendarQuery:
    return CalendarQuery(market_id="cn_a", start=date(2020, 1, 1), end=date(2020, 1, 2))


def _passing_source() -> InMemoryCalendarSource:
    return InMemoryCalendarSource(
        (
            _day(date(2026, 8, 3)),
            _day(date(2026, 8, 4)),
        ),
        markets=("cn_a",),
    )


def test_in_memory_calendar_source_satisfies_protocol_without_inheriting() -> None:
    source = _passing_source()
    assert isinstance(source, CalendarSource)
    assert CalendarSource not in type(source).__mro__[1:]


def test_in_memory_calendar_source_passes_reusable_contract() -> None:
    unknown_market = CalendarQuery(
        market_id="us",
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
    )
    dataset = assert_calendar_source_contract(
        _passing_source(),
        valid_query=_valid_query(),
        empty_query=_empty_query(),
        error_cases=((unknown_market, UnsupportedQuery),),
    )
    assert dataset.source == "memory"
    assert dataset.items[0].trade_date == date(2026, 8, 3)


def test_broken_calendar_source_fails_for_ordering() -> None:
    class UnorderedCalendarSource:
        def fetch_calendar(self, query: CalendarQuery) -> Dataset:
            good = _passing_source().fetch_calendar(query)
            return Dataset(
                items=tuple(reversed(good.items)),
                source=good.source,
                fetched_at=good.fetched_at,
                coverage_start=good.coverage_start,
                coverage_end=good.coverage_end,
                complete=good.complete,
            )

    with pytest.raises((InvalidSourcePayload, AssertionError)):
        assert_calendar_source_contract(
            UnorderedCalendarSource(),
            valid_query=_valid_query(),
            empty_query=_empty_query(),
        )


def test_broken_calendar_source_fails_for_duplicates() -> None:
    class DuplicateCalendarSource:
        def fetch_calendar(self, query: CalendarQuery) -> Dataset:
            day = _day(date(2026, 8, 3))
            return Dataset(
                items=(day, day),
                source="memory",
                fetched_at=aware_now(),
                coverage_start=query.start,
                coverage_end=query.end,
            )

    with pytest.raises((InvalidSourcePayload, AssertionError)):
        assert_calendar_source_contract(
            DuplicateCalendarSource(),
            valid_query=_valid_query(),
            empty_query=_empty_query(),
        )


def test_broken_calendar_source_fails_for_timezone() -> None:
    class NaiveTimezoneCalendarSource:
        def fetch_calendar(self, query: CalendarQuery) -> Dataset:
            return Dataset(
                items=(_day(date(2026, 8, 3)),),
                source="memory",
                fetched_at=datetime(2026, 8, 31, 9, 30),
                coverage_start=query.start,
                coverage_end=query.end,
            )

    with pytest.raises((ValueError, InvalidSourcePayload, AssertionError)):
        assert_calendar_source_contract(
            NaiveTimezoneCalendarSource(),
            valid_query=_valid_query(),
            empty_query=_empty_query(),
        )


def test_broken_calendar_source_fails_for_range() -> None:
    class OutOfRangeCalendarSource:
        def fetch_calendar(self, query: CalendarQuery) -> Dataset:
            return Dataset(
                items=(_day(date(2019, 1, 2)),),
                source="memory",
                fetched_at=datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc),
                coverage_start=query.start,
                coverage_end=query.end,
            )

    with pytest.raises((InvalidSourcePayload, AssertionError)):
        assert_calendar_source_contract(
            OutOfRangeCalendarSource(),
            valid_query=_valid_query(),
            empty_query=_empty_query(),
        )
