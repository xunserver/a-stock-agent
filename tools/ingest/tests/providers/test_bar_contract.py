from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from astock.providers.protocols import BarSource
from astock_core.market_data import (
    Adjustment,
    BarInterval,
    BarQuery,
    Dataset,
    InstrumentNotFound,
    InvalidSourcePayload,
)

from .contracts import assert_bar_source_contract
from .fakes import InMemoryBarSource, aware_now, maotai, make_bar, ping_an


def _valid_query() -> BarQuery:
    return BarQuery(
        instruments=(maotai(),),
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=BarInterval.D1,
        adjustment=Adjustment.QFQ,
    )


def _empty_query() -> BarQuery:
    return BarQuery(
        instruments=(maotai(),),
        start=date(2020, 1, 1),
        end=date(2020, 1, 2),
        interval=BarInterval.D1,
        adjustment=Adjustment.QFQ,
    )


def _passing_source() -> InMemoryBarSource:
    return InMemoryBarSource(
        (
            make_bar(trade_date=date(2026, 8, 27)),
            make_bar(trade_date=date(2026, 8, 28)),
        ),
        known=(maotai(),),
    )


def test_in_memory_bar_source_satisfies_protocol_without_inheriting() -> None:
    source = _passing_source()
    assert isinstance(source, BarSource)
    assert BarSource not in type(source).__bases__
    assert BarSource not in type(source).__mro__[1:]


def test_in_memory_bar_source_passes_reusable_contract() -> None:
    unknown = BarQuery(
        instruments=(ping_an(),),
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=BarInterval.D1,
        adjustment=Adjustment.QFQ,
    )
    dataset = assert_bar_source_contract(
        _passing_source(),
        valid_query=_valid_query(),
        empty_query=_empty_query(),
        error_cases=((unknown, InstrumentNotFound),),
    )
    assert dataset.source == "memory"
    assert dataset.items[0].volume == 1_000_000.0
    assert dataset.items[0].amount == 10_500_000.0


def test_broken_bar_source_fails_for_ordering() -> None:
    class UnorderedBarSource:
        def fetch_bars(self, query: BarQuery) -> Dataset:
            good = InMemoryBarSource(
                (
                    make_bar(trade_date=date(2026, 8, 27)),
                    make_bar(trade_date=date(2026, 8, 28)),
                )
            ).fetch_bars(query)
            return Dataset(
                items=tuple(reversed(good.items)),
                source=good.source,
                fetched_at=good.fetched_at,
                coverage_start=good.coverage_start,
                coverage_end=good.coverage_end,
                complete=good.complete,
            )

    with pytest.raises((InvalidSourcePayload, AssertionError)):
        assert_bar_source_contract(
            UnorderedBarSource(),
            valid_query=_valid_query(),
            empty_query=_empty_query(),
        )


def test_broken_bar_source_fails_for_duplicates() -> None:
    class DuplicateBarSource:
        def fetch_bars(self, query: BarQuery) -> Dataset:
            bar = make_bar()
            return Dataset(
                items=(bar, bar),
                source="memory",
                fetched_at=aware_now(),
                coverage_start=query.start,
                coverage_end=query.end,
            )

    with pytest.raises((InvalidSourcePayload, AssertionError)):
        assert_bar_source_contract(
            DuplicateBarSource(),
            valid_query=_valid_query(),
            empty_query=_empty_query(),
        )


def test_broken_bar_source_fails_for_timezone() -> None:
    class NaiveTimezoneBarSource:
        def fetch_bars(self, query: BarQuery) -> Dataset:
            return Dataset(
                items=(make_bar(),),
                source="memory",
                fetched_at=datetime(2026, 8, 31, 9, 30),
                coverage_start=query.start,
                coverage_end=query.end,
            )

    with pytest.raises((ValueError, InvalidSourcePayload, AssertionError)):
        assert_bar_source_contract(
            NaiveTimezoneBarSource(),
            valid_query=_valid_query(),
            empty_query=_empty_query(),
        )


def test_broken_bar_source_fails_for_range() -> None:
    class OutOfRangeBarSource:
        def fetch_bars(self, query: BarQuery) -> Dataset:
            return Dataset(
                items=(make_bar(trade_date=date(2019, 1, 2)),),
                source="memory",
                fetched_at=datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc),
                coverage_start=query.start,
                coverage_end=query.end,
            )

    with pytest.raises((InvalidSourcePayload, AssertionError)):
        assert_bar_source_contract(
            OutOfRangeBarSource(),
            valid_query=_valid_query(),
            empty_query=_empty_query(),
        )
