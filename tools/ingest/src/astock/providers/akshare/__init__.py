"""AKShare Data Source Adapters."""

from astock.providers.akshare.bars import AkshareBarAdapter
from astock.providers.akshare.calendar import AkshareCalendarAdapter
from astock.providers.akshare.classifications import (
    AkshareClassificationAdapter,
    AkshareMembershipAdapter,
)
from astock.providers.akshare.events import AkshareEventAdapter
from astock.providers.akshare.fundamentals import AkshareFundamentalAdapter
from astock.providers.akshare.instruments import AkshareInstrumentAdapter
from astock.providers.akshare.news import AkshareNewsAdapter
from astock.providers.akshare.snapshots import AkshareSnapshotAdapter
from astock.providers.akshare.statements import AkshareStatementAdapter

__all__ = [
    "AkshareBarAdapter",
    "AkshareCalendarAdapter",
    "AkshareClassificationAdapter",
    "AkshareEventAdapter",
    "AkshareFundamentalAdapter",
    "AkshareInstrumentAdapter",
    "AkshareMembershipAdapter",
    "AkshareNewsAdapter",
    "AkshareSnapshotAdapter",
    "AkshareStatementAdapter",
]
