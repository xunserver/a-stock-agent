"""Capability interfaces and Data Source Adapters."""

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

__all__ = [
    "BarSource",
    "CalendarSource",
    "ClassificationSource",
    "EventSource",
    "FundamentalSource",
    "InstrumentProfileSource",
    "InstrumentSource",
    "MembershipSource",
    "NewsSource",
    "QuoteSnapshotSource",
    "StatementSource",
    "ValuationSource",
]
