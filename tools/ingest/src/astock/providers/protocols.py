"""Runtime-checkable market-data capability interfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from astock_core.market_data import (
    Bar,
    BarQuery,
    CalendarQuery,
    Classification,
    ClassificationQuery,
    Dataset,
    EventQuery,
    FinancialStatement,
    FundamentalPeriod,
    FundamentalQuery,
    Instrument,
    InstrumentProfile,
    InstrumentQuery,
    MarketEvent,
    Membership,
    MembershipQuery,
    NewsItem,
    NewsQuery,
    QuoteSnapshot,
    SnapshotQuery,
    StatementQuery,
    TradingDay,
    ValuationQuery,
    ValuationSnapshot,
)


@runtime_checkable
class InstrumentSource(Protocol):
    def fetch_instruments(self, query: InstrumentQuery) -> Dataset[Instrument]: ...


@runtime_checkable
class InstrumentProfileSource(Protocol):
    def fetch_profiles(self, query: InstrumentQuery) -> Dataset[InstrumentProfile]: ...


@runtime_checkable
class CalendarSource(Protocol):
    def fetch_calendar(self, query: CalendarQuery) -> Dataset[TradingDay]: ...


@runtime_checkable
class BarSource(Protocol):
    def fetch_bars(self, query: BarQuery) -> Dataset[Bar]: ...


@runtime_checkable
class QuoteSnapshotSource(Protocol):
    def fetch_snapshots(self, query: SnapshotQuery) -> Dataset[QuoteSnapshot]: ...


@runtime_checkable
class ValuationSource(Protocol):
    def fetch_valuations(self, query: ValuationQuery) -> Dataset[ValuationSnapshot]: ...


@runtime_checkable
class FundamentalSource(Protocol):
    def fetch_fundamentals(self, query: FundamentalQuery) -> Dataset[FundamentalPeriod]: ...


@runtime_checkable
class StatementSource(Protocol):
    def fetch_statements(self, query: StatementQuery) -> Dataset[FinancialStatement]: ...


@runtime_checkable
class ClassificationSource(Protocol):
    def fetch_classifications(self, query: ClassificationQuery) -> Dataset[Classification]: ...


@runtime_checkable
class MembershipSource(Protocol):
    def fetch_memberships(self, query: MembershipQuery) -> Dataset[Membership]: ...


@runtime_checkable
class NewsSource(Protocol):
    def fetch_news(self, query: NewsQuery) -> Dataset[NewsItem]: ...


@runtime_checkable
class EventSource(Protocol):
    def fetch_events(self, query: EventQuery) -> Dataset[MarketEvent]: ...
