from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import get_origin, get_type_hints

import pytest

from astock.providers import protocols
from astock.providers.protocols import (
    BarSource,
    CalendarSource,
    ClassificationSource,
    EventSource,
    FundamentalSource,
    InstrumentProfileSource,
    InstrumentSource,
    MembershipSource,
    NewsSource,
    QuoteSnapshotSource,
    StatementSource,
    ValuationSource,
)
from astock_core.market_data import (
    Adjustment,
    AssetType,
    BarInterval,
    BarQuery,
    CalendarQuery,
    ClassificationKind,
    ClassificationQuery,
    Dataset,
    EventKind,
    EventQuery,
    FinancialPeriodType,
    FinancialSheet,
    FundamentalQuery,
    InstrumentQuery,
    MembershipQuery,
    NewsQuery,
    SnapshotQuery,
    StatementQuery,
    ValuationQuery,
    from_legacy_symbol,
)

from .contracts import PENDING_CAPABILITY_CONTRACTS, unimplemented_capability_contract


def _id():
    return from_legacy_symbol("600519")


def _aware() -> datetime:
    return datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


def _empty_dataset() -> Dataset:
    return Dataset(items=(), source="memory", fetched_at=_aware())


class _AllCapabilities:
    def fetch_instruments(self, query: InstrumentQuery) -> Dataset:
        return _empty_dataset()

    def fetch_profiles(self, query: InstrumentQuery) -> Dataset:
        return _empty_dataset()

    def fetch_calendar(self, query: CalendarQuery) -> Dataset:
        return _empty_dataset()

    def fetch_bars(self, query: BarQuery) -> Dataset:
        return _empty_dataset()

    def fetch_snapshots(self, query: SnapshotQuery) -> Dataset:
        return _empty_dataset()

    def fetch_valuations(self, query: ValuationQuery) -> Dataset:
        return _empty_dataset()

    def fetch_fundamentals(self, query: FundamentalQuery) -> Dataset:
        return _empty_dataset()

    def fetch_statements(self, query: StatementQuery) -> Dataset:
        return _empty_dataset()

    def fetch_classifications(self, query: ClassificationQuery) -> Dataset:
        return _empty_dataset()

    def fetch_memberships(self, query: MembershipQuery) -> Dataset:
        return _empty_dataset()

    def fetch_news(self, query: NewsQuery) -> Dataset:
        return _empty_dataset()

    def fetch_events(self, query: EventQuery) -> Dataset:
        return _empty_dataset()


def test_in_memory_fake_satisfies_every_protocol_without_inheriting() -> None:
    fake = _AllCapabilities()
    protocol_types = (
        InstrumentSource,
        InstrumentProfileSource,
        CalendarSource,
        BarSource,
        QuoteSnapshotSource,
        ValuationSource,
        FundamentalSource,
        StatementSource,
        ClassificationSource,
        MembershipSource,
        NewsSource,
        EventSource,
    )
    for protocol in protocol_types:
        assert isinstance(fake, protocol)
        assert protocol not in type(fake).__mro__[1:]


def test_protocol_methods_use_query_and_dataset_only() -> None:
    instrument = _id()
    fake = _AllCapabilities()
    fake.fetch_instruments(InstrumentQuery(asset_types=(AssetType.STOCK,)))
    fake.fetch_profiles(InstrumentQuery(instruments=(instrument,)))
    fake.fetch_calendar(CalendarQuery(market_id="cn_a", start=date(2026, 1, 1), end=date(2026, 1, 2)))
    fake.fetch_bars(
        BarQuery(
            instruments=(instrument,),
            start=date(2026, 1, 1),
            end=date(2026, 1, 2),
            interval=BarInterval.D1,
            adjustment=Adjustment.QFQ,
        )
    )
    fake.fetch_snapshots(SnapshotQuery(instruments=(instrument,)))
    fake.fetch_valuations(ValuationQuery(instruments=(instrument,)))
    fake.fetch_fundamentals(
        FundamentalQuery(instruments=(instrument,), period_types=(FinancialPeriodType.FY,))
    )
    fake.fetch_statements(
        StatementQuery(instruments=(instrument,), sheet=FinancialSheet.BALANCE)
    )
    fake.fetch_classifications(
        ClassificationQuery(kind=ClassificationKind.INDUSTRY, taxonomy="eastmoney")
    )
    fake.fetch_memberships(MembershipQuery(taxonomy="csindex"))
    fake.fetch_news(NewsQuery(instruments=(instrument,), start=_aware(), end=_aware()))
    fake.fetch_events(EventQuery(instruments=(instrument,), kinds=(EventKind.NOTICE,)))

    from typing import get_origin

    hints = get_type_hints(BarSource.fetch_bars)
    assert hints["query"] is BarQuery
    assert get_origin(hints["return"]) is Dataset or hints["return"] is Dataset


def test_protocols_module_has_no_vendor_surface() -> None:
    text = Path(protocols.__file__).read_text(encoding="utf-8")
    for token in (
        "pandas",
        "DataFrame",
        "akshare",
        "curl_cffi",
        "dict[str, Any]",
        "TOTAL_ASSETS",
        "OPERATE_INCOME",
    ):
        assert token not in text


def test_pending_contracts_are_named_and_not_passing() -> None:
    assert "bars" not in PENDING_CAPABILITY_CONTRACTS
    assert "calendar" not in PENDING_CAPABILITY_CONTRACTS
    assert "instruments" not in PENDING_CAPABILITY_CONTRACTS
    assert "quote_snapshots" not in PENDING_CAPABILITY_CONTRACTS
    assert "valuations" not in PENDING_CAPABILITY_CONTRACTS
    assert "fundamentals" not in PENDING_CAPABILITY_CONTRACTS
    assert "statements" not in PENDING_CAPABILITY_CONTRACTS
    assert "classifications" not in PENDING_CAPABILITY_CONTRACTS
    assert "memberships" not in PENDING_CAPABILITY_CONTRACTS
    assert "news" not in PENDING_CAPABILITY_CONTRACTS
    assert "events" not in PENDING_CAPABILITY_CONTRACTS
    for capability in PENDING_CAPABILITY_CONTRACTS:
        with pytest.raises(NotImplementedError, match="do not mark this capability as passing"):
            unimplemented_capability_contract(capability)
