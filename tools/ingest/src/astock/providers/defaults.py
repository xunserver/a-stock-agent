"""Default Adapter construction for ingest composition roots.

Plan 08 replaces these helpers with the per-capability source registry.
"""

from __future__ import annotations

from dataclasses import replace
from zoneinfo import ZoneInfo

from astock.providers.akshare import (
    AkshareCalendarAdapter,
    AkshareFundamentalAdapter,
    AkshareInstrumentAdapter,
    AkshareSnapshotAdapter,
    AkshareStatementAdapter,
)
from astock.providers.eastmoney import EastmoneyBarAdapter, EastmoneySnapshotAdapter
from astock.providers.eastmoney.snapshots import CN_TIMEZONE
from astock.providers.protocols import (
    BarSource,
    CalendarSource,
    FundamentalSource,
    InstrumentProfileSource,
    InstrumentSource,
    QuoteSnapshotSource,
    StatementSource,
    ValuationSource,
)
from astock_core.market_data import (
    Dataset,
    InstrumentQuery,
    MarketDataError,
    SnapshotQuery,
    ValuationQuery,
    to_legacy_symbol,
)


def default_bar_source() -> BarSource:
    from astock.config import request_retries

    return EastmoneyBarAdapter(retries=request_retries())


def default_calendar_source() -> CalendarSource:
    from astock.config import request_retries

    return AkshareCalendarAdapter(retries=request_retries())


def default_instrument_source() -> InstrumentSource:
    from astock.config import request_retries

    return AkshareInstrumentAdapter(retries=request_retries())


def default_stock_info_source(*, pause: float = 0.0) -> "DefaultStockInfoAdapter":
    from astock.config import request_retries

    retries = request_retries()
    return DefaultStockInfoAdapter(
        primary=EastmoneySnapshotAdapter(retries=retries, pause=pause),
        overlay=AkshareSnapshotAdapter(retries=retries, pause=pause),
    )


def default_profile_source(*, pause: float = 0.0) -> InstrumentProfileSource:
    return default_stock_info_source(pause=pause)


def default_quote_snapshot_source(*, pause: float = 0.0) -> QuoteSnapshotSource:
    return default_stock_info_source(pause=pause)


def default_valuation_source(*, pause: float = 0.0) -> ValuationSource:
    return default_stock_info_source(pause=pause)


def default_fundamental_source() -> FundamentalSource:
    from astock.config import request_retries

    return AkshareFundamentalAdapter(retries=request_retries())


def default_statement_source() -> StatementSource:
    from astock.config import request_retries

    return AkshareStatementAdapter(retries=request_retries())


class DefaultStockInfoAdapter:
    """Eastmoney records plus AKShare ST/suspend overlay.

    Dataset.source stays the primary Eastmoney source. Plan 08 replaces this
    composition with the per-capability registry.
    """

    def __init__(
        self,
        *,
        primary: EastmoneySnapshotAdapter,
        overlay: AkshareSnapshotAdapter,
    ) -> None:
        self._primary = primary
        self._overlay = overlay

    def fetch_profiles(self, query: InstrumentQuery) -> Dataset:
        dataset = self._primary.fetch_profiles(query)
        try:
            st_codes = self._overlay.st_codes()
        except MarketDataError:
            return dataset
        items = []
        for profile in dataset.items:
            code = to_legacy_symbol(profile.instrument_id)
            if profile.is_st or code not in st_codes:
                items.append(profile)
                continue
            items.append(replace(profile, is_st=True))
        return Dataset(
            items=tuple(items),
            source=dataset.source,
            fetched_at=dataset.fetched_at,
            coverage_start=dataset.coverage_start,
            coverage_end=dataset.coverage_end,
            complete=dataset.complete,
            warnings=dataset.warnings,
        )

    def fetch_snapshots(self, query: SnapshotQuery) -> Dataset:
        dataset = self._primary.fetch_snapshots(query)
        try:
            mapping = self._overlay.suspend_reasons(
                dataset.fetched_at.astimezone(ZoneInfo(CN_TIMEZONE)).date()
            )
        except MarketDataError:
            return dataset
        items = []
        for snapshot in dataset.items:
            code = to_legacy_symbol(snapshot.instrument_id)
            reason = mapping.get(code)
            if not reason:
                items.append(snapshot)
                continue
            items.append(
                replace(snapshot, is_suspended=True, suspend_reason=reason)
            )
        return Dataset(
            items=tuple(items),
            source=dataset.source,
            fetched_at=dataset.fetched_at,
            coverage_start=dataset.coverage_start,
            coverage_end=dataset.coverage_end,
            complete=dataset.complete,
            warnings=dataset.warnings,
        )

    def fetch_valuations(self, query: ValuationQuery) -> Dataset:
        return self._primary.fetch_valuations(query)
