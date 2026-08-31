from __future__ import annotations

from datetime import date

import pytest

from astock.providers.fallback import (
    FallbackExhausted,
    fetch_with_fallback,
    should_try_next_source,
)
from astock_core.market_data import (
    AuthenticationFailed,
    Bar,
    BarQuery,
    Dataset,
    InstrumentNotFound,
    InvalidSourcePayload,
    NoData,
    SourceUnavailable,
    UnsupportedQuery,
    from_legacy_symbol,
)
from .fakes import InMemoryBarSource, make_bar


def _query() -> BarQuery:
    return BarQuery(
        instruments=(from_legacy_symbol("600519"),),
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=make_bar().interval,
        adjustment=make_bar().adjustment,
    )


def test_first_source_success() -> None:
    primary = InMemoryBarSource((make_bar(),), source="eastmoney")
    secondary = InMemoryBarSource((make_bar(close=20.0),), source="akshare")
    dataset = fetch_with_fallback(
        capability="bars",
        source_names=("eastmoney", "akshare"),
        sources=(primary, secondary),
        query=_query(),
        fetch=lambda adapter, query: adapter.fetch_bars(query),
    )
    assert dataset.source == "eastmoney"
    assert len(dataset.items) == 1


def test_retryable_failure_selects_second() -> None:
    class FailSource:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            raise SourceUnavailable("timeout")

    secondary = InMemoryBarSource((make_bar(),), source="akshare")
    dataset = fetch_with_fallback(
        capability="bars",
        source_names=("eastmoney", "akshare"),
        sources=(FailSource(), secondary),
        query=_query(),
        fetch=lambda adapter, query: adapter.fetch_bars(query),
    )
    assert dataset.source == "akshare"


def test_unsupported_query_selects_second() -> None:
    class Unsupported:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            raise UnsupportedQuery("weekly only")

    secondary = InMemoryBarSource((make_bar(),), source="akshare")
    dataset = fetch_with_fallback(
        capability="bars",
        source_names=("eastmoney", "akshare"),
        sources=(Unsupported(), secondary),
        query=_query(),
        fetch=lambda adapter, query: adapter.fetch_bars(query),
    )
    assert dataset.source == "akshare"


def test_successful_empty_dataset_stops() -> None:
    primary = InMemoryBarSource((), known=(from_legacy_symbol("600519"),), source="eastmoney")
    secondary = InMemoryBarSource((make_bar(),), source="akshare")

    class ShouldNotRun:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            raise AssertionError("fallback must not run after successful empty dataset")

    dataset = fetch_with_fallback(
        capability="bars",
        source_names=("eastmoney", "akshare"),
        sources=(primary, ShouldNotRun()),
        query=_query(),
        fetch=lambda adapter, query: adapter.fetch_bars(query),
    )
    assert dataset.source == "eastmoney"
    assert dataset.items == ()


def test_no_data_defaults_to_stop() -> None:
    class NoDataSource:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            raise NoData("missing history")

    class ShouldNotRun:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            raise AssertionError("NoData must stop by default")

    with pytest.raises(NoData, match="missing history"):
        fetch_with_fallback(
            capability="bars",
            source_names=("eastmoney", "akshare"),
            sources=(NoDataSource(), ShouldNotRun()),
            query=_query(),
            fetch=lambda adapter, query: adapter.fetch_bars(query),
        )


def test_authentication_failure_may_select_next_but_not_retry_same() -> None:
    calls: list[str] = []

    class AuthFail:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            calls.append("eastmoney")
            raise AuthenticationFailed("api_key=super-secret-token")

    secondary = InMemoryBarSource((make_bar(),), source="akshare")
    dataset = fetch_with_fallback(
        capability="bars",
        source_names=("eastmoney", "akshare"),
        sources=(AuthFail(), secondary),
        query=_query(),
        fetch=lambda adapter, query: adapter.fetch_bars(query),
    )
    assert calls == ["eastmoney"]
    assert dataset.source == "akshare"


def test_invalid_payload_selects_next() -> None:
    class BadPayload:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            raise InvalidSourcePayload("malformed")

    secondary = InMemoryBarSource((make_bar(),), source="akshare")
    dataset = fetch_with_fallback(
        capability="bars",
        source_names=("eastmoney", "akshare"),
        sources=(BadPayload(), secondary),
        query=_query(),
        fetch=lambda adapter, query: adapter.fetch_bars(query),
    )
    assert dataset.source == "akshare"


def test_exhaustion_contains_categorized_attempts_without_secrets() -> None:
    class AuthFail:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            raise AuthenticationFailed("token=abc123")

    class Missing:
        def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
            raise InstrumentNotFound("CN.XSHE.000001")

    with pytest.raises(FallbackExhausted) as excinfo:
        fetch_with_fallback(
            capability="bars",
            source_names=("eastmoney", "akshare"),
            sources=(AuthFail(), Missing()),
            query=_query(),
            fetch=lambda adapter, query: adapter.fetch_bars(query),
        )
    message = str(excinfo.value)
    assert "AuthenticationFailed" in message
    assert "InstrumentNotFound" in message
    assert "abc123" not in message
    assert excinfo.value.attempts[0].message == "AuthenticationFailed"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (UnsupportedQuery("x"), True),
        (InstrumentNotFound("x"), True),
        (InvalidSourcePayload("x"), True),
        (AuthenticationFailed("x"), True),
        (SourceUnavailable("x"), True),
        (NoData("x"), False),
    ],
)
def test_should_try_next_source_table(error, expected) -> None:
    assert should_try_next_source(error, capability="bars") is expected
