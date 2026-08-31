"""In-memory capability Adapters used by contract tests."""

from __future__ import annotations

from datetime import date, datetime, timezone

from astock_core.market_data import (
    Adjustment,
    AssetType,
    Bar,
    BarInterval,
    BarQuery,
    CalendarQuery,
    Classification,
    ClassificationKind,
    ClassificationQuery,
    CSINDEX_TAXONOMY,
    BlockTradeEvent,
    Dataset,
    EASTMONEY_TAXONOMY,
    EventKind,
    EventQuery,
    FinancialPeriodType,
    FinancialSheet,
    FinancialStatement,
    FundamentalPeriod,
    FundamentalQuery,
    HolderChangeEvent,
    Instrument,
    InstrumentId,
    InstrumentNotFound,
    InstrumentProfile,
    InstrumentQuery,
    MarketEvent,
    Membership,
    MembershipQuery,
    NewsItem,
    NewsQuery,
    NoticeEvent,
    QuoteSnapshot,
    ResearchReportEvent,
    SnapshotQuery,
    StatementQuery,
    TradingDay,
    UnsupportedQuery,
    ValuationQuery,
    ValuationSnapshot,
    from_legacy_symbol,
    validate_membership_dataset,
    validate_news_dataset,
    validate_event_dataset,
)


def maotai() -> InstrumentId:
    return from_legacy_symbol("600519")


def ping_an() -> InstrumentId:
    return from_legacy_symbol("000001")


def aware_now() -> datetime:
    return datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


def make_bar(
    *,
    instrument_id: InstrumentId | None = None,
    trade_date: date = date(2026, 8, 28),
    interval: BarInterval = BarInterval.D1,
    adjustment: Adjustment = Adjustment.QFQ,
    open: float = 10.0,
    high: float = 11.0,
    low: float = 9.5,
    close: float = 10.5,
    volume: float = 1_000_000.0,
    amount: float = 10_500_000.0,
    turnover_pct: float | None = 1.25,
    adjustment_factor: float | None = 1.0,
) -> Bar:
    return Bar(
        instrument_id=instrument_id or maotai(),
        trade_date=trade_date,
        interval=interval,
        adjustment=adjustment,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
        turnover_pct=turnover_pct,
        adjustment_factor=adjustment_factor,
    )


class InMemoryBarSource:
    def __init__(
        self,
        bars: tuple[Bar, ...] = (),
        *,
        known: tuple[InstrumentId, ...] | None = None,
        source: str = "memory",
        fetched_at: datetime | None = None,
    ) -> None:
        self._bars = bars
        self._known = frozenset(known if known is not None else (bar.instrument_id for bar in bars))
        self._source = source
        self._fetched_at = fetched_at or aware_now()

    def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
        missing = [item for item in query.instruments if item not in self._known]
        if missing:
            raise InstrumentNotFound(missing[0].value)
        items = tuple(
            sorted(
                (
                    bar
                    for bar in self._bars
                    if bar.instrument_id in query.instruments
                    and query.start <= bar.trade_date <= query.end
                    and bar.interval == query.interval
                    and bar.adjustment == query.adjustment
                ),
                key=lambda bar: (bar.trade_date, bar.instrument_id.value, bar.interval, bar.adjustment),
            )
        )
        return Dataset(
            items=items,
            source=self._source,
            fetched_at=self._fetched_at,
            coverage_start=query.start,
            coverage_end=query.end,
            complete=True,
        )


class InMemoryCalendarSource:
    def __init__(
        self,
        days: tuple[TradingDay, ...] = (),
        *,
        markets: tuple[str, ...] | None = None,
        source: str = "memory",
        fetched_at: datetime | None = None,
    ) -> None:
        self._days = days
        self._markets = frozenset(markets if markets is not None else (day.market_id for day in days))
        self._source = source
        self._fetched_at = fetched_at or aware_now()

    def fetch_calendar(self, query: CalendarQuery) -> Dataset[TradingDay]:
        if query.market_id not in self._markets:
            raise UnsupportedQuery(f"unknown market {query.market_id}")
        items = tuple(
            sorted(
                (
                    day
                    for day in self._days
                    if day.market_id == query.market_id
                    and query.start <= day.trade_date <= query.end
                ),
                key=lambda day: (day.trade_date, day.market_id),
            )
        )
        return Dataset(
            items=items,
            source=self._source,
            fetched_at=self._fetched_at,
            coverage_start=query.start,
            coverage_end=query.end,
            complete=True,
        )


CN_CURRENCY = "CNY"
CN_TIMEZONE = "Asia/Shanghai"


def make_instrument(
    *,
    instrument_id: InstrumentId | None = None,
    name: str = "Kweichow Moutai",
    asset_type: AssetType = AssetType.STOCK,
    list_date: date = date(2001, 8, 27),
) -> Instrument:
    return Instrument(
        id=instrument_id or maotai(),
        asset_type=asset_type,
        name=name,
        currency=CN_CURRENCY,
        timezone=CN_TIMEZONE,
        list_date=list_date,
    )


def make_profile(
    *,
    instrument_id: InstrumentId | None = None,
    name: str = "Kweichow Moutai",
    industry: str | None = "liquor",
    region: str | None = "Guizhou",
    list_date: date = date(2001, 8, 27),
    is_st: bool = False,
) -> InstrumentProfile:
    return InstrumentProfile(
        instrument_id=instrument_id or maotai(),
        name=name,
        industry=industry,
        region=region,
        list_date=list_date,
        is_st=is_st,
    )


def make_snapshot(
    *,
    instrument_id: InstrumentId | None = None,
    observed_at: datetime | None = None,
    last_price: float | None = 1400.0,
    pre_close: float | None = 1390.0,
    average_price: float | None = 1395.0,
    high_limit: float | None = 1529.0,
    low_limit: float | None = 1251.0,
    volume_ratio: float | None = 1.1,
    outer_volume: float | None = 100.0,
    inner_volume: float | None = 80.0,
    is_suspended: bool = False,
    suspend_reason: str | None = None,
) -> QuoteSnapshot:
    return QuoteSnapshot(
        instrument_id=instrument_id or maotai(),
        observed_at=observed_at or aware_now(),
        last_price=last_price,
        pre_close=pre_close,
        average_price=average_price,
        high_limit=high_limit,
        low_limit=low_limit,
        volume_ratio=volume_ratio,
        outer_volume=outer_volume,
        inner_volume=inner_volume,
        is_suspended=is_suspended,
        suspend_reason=suspend_reason,
    )


def make_valuation(
    *,
    instrument_id: InstrumentId | None = None,
    as_of: date = date(2026, 8, 28),
    total_shares: float | None = 1.25e9,
    float_shares: float | None = 1.2e9,
    total_market_cap: float | None = 1.8e12,
    float_market_cap: float | None = 1.7e12,
    pe_ttm: float | None = 20.5,
    pe_static: float | None = 22.0,
    pb: float | None = 8.1,
) -> ValuationSnapshot:
    return ValuationSnapshot(
        instrument_id=instrument_id or maotai(),
        as_of=as_of,
        currency=CN_CURRENCY,
        total_shares=total_shares,
        float_shares=float_shares,
        total_market_cap=total_market_cap,
        float_market_cap=float_market_cap,
        pe_ttm=pe_ttm,
        pe_static=pe_static,
        pb=pb,
    )


class InMemoryInstrumentSource:
    def __init__(
        self,
        instruments: tuple[Instrument, ...] = (),
        *,
        source: str = "memory",
        fetched_at: datetime | None = None,
    ) -> None:
        self._instruments = instruments
        self._source = source
        self._fetched_at = fetched_at or aware_now()
        self.calls = 0

    def fetch_instruments(self, query: InstrumentQuery) -> Dataset[Instrument]:
        self.calls += 1
        items = tuple(
            sorted(
                (
                    item
                    for item in self._instruments
                    if (not query.instruments or item.id in query.instruments)
                    and (not query.asset_types or item.asset_type in query.asset_types)
                    and (not query.exchanges or item.id.exchange in query.exchanges)
                ),
                key=lambda item: item.id.value,
            )
        )
        return Dataset(
            items=items,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
        )


class InMemoryProfileSource:
    def __init__(
        self,
        profiles: tuple[InstrumentProfile, ...] = (),
        *,
        source: str = "memory",
        fetched_at: datetime | None = None,
        error: Exception | None = None,
    ) -> None:
        self._profiles = profiles
        self._source = source
        self._fetched_at = fetched_at or aware_now()
        self.error = error
        self.calls = 0

    def fetch_profiles(self, query: InstrumentQuery) -> Dataset[InstrumentProfile]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        wanted = frozenset(query.instruments)
        items = tuple(
            sorted(
                (item for item in self._profiles if not wanted or item.instrument_id in wanted),
                key=lambda item: item.instrument_id.value,
            )
        )
        return Dataset(
            items=items,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
        )


class InMemoryQuoteSnapshotSource:
    def __init__(
        self,
        snapshots: tuple[QuoteSnapshot, ...] = (),
        *,
        known: tuple[InstrumentId, ...] | None = None,
        source: str = "memory",
        fetched_at: datetime | None = None,
        error: Exception | None = None,
    ) -> None:
        self._snapshots = snapshots
        self._known = frozenset(
            known if known is not None else (item.instrument_id for item in snapshots)
        )
        self._source = source
        self._fetched_at = fetched_at or aware_now()
        self.error = error
        self.calls = 0

    def fetch_snapshots(self, query: SnapshotQuery) -> Dataset[QuoteSnapshot]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        missing = [item for item in query.instruments if item not in self._known]
        if missing:
            raise InstrumentNotFound(missing[0].value)
        items = tuple(
            sorted(
                (item for item in self._snapshots if item.instrument_id in query.instruments),
                key=lambda item: (item.instrument_id.value, item.observed_at),
            )
        )
        return Dataset(
            items=items,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
        )


class InMemoryValuationSource:
    def __init__(
        self,
        snapshots: tuple[ValuationSnapshot, ...] = (),
        *,
        known: tuple[InstrumentId, ...] | None = None,
        source: str = "memory",
        fetched_at: datetime | None = None,
        error: Exception | None = None,
    ) -> None:
        self._snapshots = snapshots
        self._known = frozenset(
            known if known is not None else (item.instrument_id for item in snapshots)
        )
        self._source = source
        self._fetched_at = fetched_at or aware_now()
        self.error = error
        self.calls = 0

    def fetch_valuations(self, query: ValuationQuery) -> Dataset[ValuationSnapshot]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        missing = [item for item in query.instruments if item not in self._known]
        if missing:
            raise InstrumentNotFound(missing[0].value)
        items = tuple(
            sorted(
                (
                    item
                    for item in self._snapshots
                    if item.instrument_id in query.instruments
                    and (query.as_of is None or item.as_of == query.as_of)
                ),
                key=lambda item: (item.instrument_id.value, item.as_of),
            )
        )
        return Dataset(
            items=items,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
        )


class InMemoryFundamentalSource:
    def __init__(
        self,
        periods: tuple[FundamentalPeriod, ...] = (),
        *,
        known: tuple[InstrumentId, ...] | None = None,
        source: str = "memory",
        fetched_at: datetime | None = None,
        error: Exception | None = None,
    ) -> None:
        self._periods = periods
        self._known = frozenset(
            known if known is not None else (item.instrument_id for item in periods)
        )
        self._source = source
        self._fetched_at = fetched_at or aware_now()
        self.error = error
        self.calls = 0

    def fetch_fundamentals(self, query: FundamentalQuery) -> Dataset[FundamentalPeriod]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        missing = [item for item in query.instruments if item not in self._known]
        if missing:
            raise InstrumentNotFound(missing[0].value)
        wanted_types = frozenset(query.period_types)
        items = tuple(
            sorted(
                (
                    item
                    for item in self._periods
                    if item.instrument_id in query.instruments
                    and (not wanted_types or item.period_type in wanted_types)
                    and (query.start is None or item.period_end >= query.start)
                    and (query.end is None or item.period_end <= query.end)
                ),
                key=lambda item: (item.instrument_id.value, item.period_end, item.period_type.value),
            )
        )
        return Dataset(
            items=items,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
            coverage_start=query.start,
            coverage_end=query.end,
        )


class InMemoryStatementSource:
    def __init__(
        self,
        statements: tuple[FinancialStatement, ...] = (),
        *,
        known: tuple[InstrumentId, ...] | None = None,
        source: str = "memory",
        fetched_at: datetime | None = None,
        error: Exception | None = None,
    ) -> None:
        self._statements = statements
        self._known = frozenset(
            known if known is not None else (item.instrument_id for item in statements)
        )
        self._source = source
        self._fetched_at = fetched_at or aware_now()
        self.error = error
        self.calls = 0

    def fetch_statements(self, query: StatementQuery) -> Dataset[FinancialStatement]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        missing = [item for item in query.instruments if item not in self._known]
        if missing:
            raise InstrumentNotFound(missing[0].value)
        wanted_types = frozenset(query.period_types)
        items = tuple(
            sorted(
                (
                    item
                    for item in self._statements
                    if item.instrument_id in query.instruments
                    and item.sheet is query.sheet
                    and (not wanted_types or item.period_type in wanted_types)
                    and (query.start is None or item.period_end >= query.start)
                    and (query.end is None or item.period_end <= query.end)
                ),
                key=lambda item: (item.instrument_id.value, item.period_end, item.period_type.value),
            )
        )
        return Dataset(
            items=items,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
            coverage_start=query.start,
            coverage_end=query.end,
        )


class InMemoryClassificationSource:
    def __init__(
        self,
        classifications: tuple[Classification, ...] = (),
        *,
        source: str = "memory",
        fetched_at: datetime | None = None,
    ) -> None:
        self._classifications = classifications
        self._source = source
        self._fetched_at = fetched_at or aware_now()

    def fetch_classifications(self, query: ClassificationQuery) -> Dataset[Classification]:
        items = tuple(
            sorted(
                (
                    item
                    for item in self._classifications
                    if (query.kind is None or item.kind == query.kind)
                    and (query.taxonomy is None or item.taxonomy == query.taxonomy)
                    and (not query.ids or item.id in query.ids)
                ),
                key=lambda item: (item.taxonomy, item.kind.value, item.id),
            )
        )
        return Dataset(
            items=items,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
        )


class InMemoryMembershipSource:
    def __init__(
        self,
        memberships: tuple[Membership, ...] = (),
        *,
        board_kinds: dict[str, ClassificationKind] | None = None,
        names: dict[str, str] | None = None,
        source: str = "memory",
        fetched_at: datetime | None = None,
    ) -> None:
        self._memberships = memberships
        self._board_kinds = dict(board_kinds or {})
        self._names = dict(names or {})
        self._source = source
        self._fetched_at = fetched_at or aware_now()
        self._display_names: dict[str, str] = {}

    def set_board_kind(self, board_id: str, kind: ClassificationKind) -> None:
        self._board_kinds[board_id] = kind

    def display_names(self) -> dict[str, str]:
        return dict(self._display_names)

    def fetch_memberships(self, query: MembershipQuery) -> Dataset[Membership]:
        if query.taxonomy == EASTMONEY_TAXONOMY and query.classification_id:
            if query.classification_id not in self._board_kinds:
                raise UnsupportedQuery("eastmoney board memberships require board kind")
        self._display_names = {}
        items = []
        for item in self._memberships:
            if query.taxonomy is not None and item.taxonomy != query.taxonomy:
                continue
            if (
                query.classification_id is not None
                and item.classification_id != query.classification_id
            ):
                continue
            if query.instrument_id is not None and item.instrument_id != query.instrument_id:
                continue
            code = item.instrument_id.symbol
            self._display_names[code] = self._names.get(code, code)
            items.append(item)
        ordered = tuple(
            sorted(
                items,
                key=lambda row: (
                    row.taxonomy,
                    row.classification_id,
                    row.instrument_id.value,
                    row.effective_from.isoformat() if row.effective_from else "",
                ),
            )
        )
        dataset = Dataset(
            items=ordered,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
        )
        return validate_membership_dataset(dataset, query)


class InMemoryNewsSource:
    def __init__(
        self,
        items: tuple[NewsItem, ...] = (),
        *,
        source: str = "memory",
        fetched_at: datetime | None = None,
    ) -> None:
        self._items = items
        self._source = source
        self._fetched_at = fetched_at or aware_now()

    def fetch_news(self, query: NewsQuery) -> Dataset[NewsItem]:
        selected = tuple(
            sorted(
                (
                    item
                    for item in self._items
                    if item.instrument_id in query.instruments
                    and (query.start is None or item.published_at >= query.start)
                    and (query.end is None or item.published_at <= query.end)
                ),
                key=lambda item: (item.published_at, item.id),
            )
        )
        if query.limit is not None:
            selected = selected[-query.limit :] if query.limit else ()
        dataset = Dataset(
            items=selected,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
        )
        return validate_news_dataset(dataset, query)


class InMemoryEventSource:
    def __init__(
        self,
        items: tuple[MarketEvent, ...] = (),
        *,
        source: str = "memory",
        fetched_at: datetime | None = None,
    ) -> None:
        self._items = items
        self._source = source
        self._fetched_at = fetched_at or aware_now()

    def fetch_events(self, query: EventQuery) -> Dataset[MarketEvent]:
        selected = tuple(
            sorted(
                (
                    item
                    for item in self._items
                    if item.instrument_id in query.instruments
                    and (not query.kinds or item.kind in query.kinds)
                    and (query.start is None or item.published_at >= query.start)
                    and (query.end is None or item.published_at <= query.end)
                ),
                key=lambda item: (item.published_at, item.kind.value, item.id),
            )
        )
        if query.limit is not None:
            selected = selected[-query.limit :] if query.limit else ()
        dataset = Dataset(
            items=selected,
            source=self._source,
            fetched_at=self._fetched_at,
            complete=True,
        )
        return validate_event_dataset(dataset, query)
