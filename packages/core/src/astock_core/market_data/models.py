"""Standard Records consumed on the market-data seam."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from astock_core.market_data.enums import (
    Adjustment,
    AssetType,
    BarInterval,
    ClassificationKind,
    EventKind,
    FinancialPeriodType,
    FinancialSheet,
    StatementUnit,
)
from astock_core.market_data.identity import InstrumentId

CANONICAL_BALANCE_ITEMS: tuple[str, ...] = (
    "cash_and_equivalents",
    "accounts_receivable",
    "inventory",
    "total_current_assets",
    "total_assets",
    "total_current_liabilities",
    "total_liabilities",
    "total_parent_equity",
    "total_equity",
)
CANONICAL_PROFIT_ITEMS: tuple[str, ...] = (
    "total_revenue",
    "operating_revenue",
    "operating_profit",
    "total_profit",
    "net_profit",
    "parent_net_profit",
    "basic_eps",
)
CANONICAL_CASHFLOW_ITEMS: tuple[str, ...] = (
    "operating_cash_inflow",
    "operating_cash_outflow",
    "net_operating_cashflow",
    "net_investing_cashflow",
    "net_financing_cashflow",
    "net_change_in_cash",
    "ending_cash",
)
CANONICAL_STATEMENT_ITEMS: dict[FinancialSheet, tuple[str, ...]] = {
    FinancialSheet.BALANCE: CANONICAL_BALANCE_ITEMS,
    FinancialSheet.PROFIT: CANONICAL_PROFIT_ITEMS,
    FinancialSheet.CASHFLOW: CANONICAL_CASHFLOW_ITEMS,
}


def _require_text(value: str, *, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")


def _require_optional_text(value: str | None, *, field: str) -> None:
    if value is not None and not value:
        raise ValueError(f"{field} must be None or a non-empty string")


def _require_tuple(value: object, *, field: str) -> None:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple, got {type(value).__name__}")


@dataclass(frozen=True, kw_only=True)
class Instrument:
    id: InstrumentId
    asset_type: AssetType
    name: str
    currency: str
    timezone: str
    list_date: date | None = None
    delist_date: date | None = None

    def __post_init__(self) -> None:
        _require_text(self.name, field="name")
        _require_text(self.currency, field="currency")
        _require_text(self.timezone, field="timezone")

    @property
    def natural_key(self) -> InstrumentId:
        return self.id


@dataclass(frozen=True, kw_only=True)
class TradingDay:
    market_id: str
    trade_date: date
    is_open: bool
    session_type: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.market_id, field="market_id")
        _require_optional_text(self.session_type, field="session_type")

    @property
    def natural_key(self) -> tuple[str, date]:
        return (self.market_id, self.trade_date)


@dataclass(frozen=True, kw_only=True)
class Bar:
    instrument_id: InstrumentId
    trade_date: date
    interval: BarInterval
    adjustment: Adjustment
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    turnover_pct: float | None = None
    adjustment_factor: float | None = None

    @property
    def natural_key(self) -> tuple[InstrumentId, date, BarInterval, Adjustment]:
        return (self.instrument_id, self.trade_date, self.interval, self.adjustment)


@dataclass(frozen=True, kw_only=True)
class InstrumentProfile:
    instrument_id: InstrumentId
    name: str
    industry: str | None = None
    region: str | None = None
    list_date: date | None = None
    is_st: bool = False

    def __post_init__(self) -> None:
        _require_text(self.name, field="name")
        _require_optional_text(self.industry, field="industry")
        _require_optional_text(self.region, field="region")

    @property
    def natural_key(self) -> InstrumentId:
        return self.instrument_id


@dataclass(frozen=True, kw_only=True)
class QuoteSnapshot:
    instrument_id: InstrumentId
    observed_at: datetime
    last_price: float | None = None
    pre_close: float | None = None
    average_price: float | None = None
    high_limit: float | None = None
    low_limit: float | None = None
    volume_ratio: float | None = None
    outer_volume: float | None = None
    inner_volume: float | None = None
    is_suspended: bool = False
    suspend_reason: str | None = None

    def __post_init__(self) -> None:
        _require_optional_text(self.suspend_reason, field="suspend_reason")

    @property
    def natural_key(self) -> tuple[InstrumentId, datetime]:
        return (self.instrument_id, self.observed_at)


@dataclass(frozen=True, kw_only=True)
class ValuationSnapshot:
    instrument_id: InstrumentId
    as_of: date
    currency: str
    total_shares: float | None = None
    float_shares: float | None = None
    total_market_cap: float | None = None
    float_market_cap: float | None = None
    pe_ttm: float | None = None
    pe_static: float | None = None
    pb: float | None = None

    def __post_init__(self) -> None:
        _require_text(self.currency, field="currency")

    @property
    def natural_key(self) -> tuple[InstrumentId, date]:
        return (self.instrument_id, self.as_of)


@dataclass(frozen=True, kw_only=True)
class FundamentalPeriod:
    instrument_id: InstrumentId
    period_end: date
    period_type: FinancialPeriodType
    currency: str
    announced_at: datetime | None = None
    eps: float | None = None
    bps: float | None = None
    roe_pct: float | None = None
    revenue: float | None = None
    revenue_yoy_pct: float | None = None
    net_profit: float | None = None
    net_profit_yoy_pct: float | None = None
    gross_margin_pct: float | None = None
    net_margin_pct: float | None = None
    debt_ratio_pct: float | None = None

    def __post_init__(self) -> None:
        _require_text(self.currency, field="currency")

    @property
    def natural_key(self) -> tuple[InstrumentId, date, FinancialPeriodType]:
        return (self.instrument_id, self.period_end, self.period_type)


@dataclass(frozen=True, kw_only=True)
class StatementItem:
    code: str
    label: str
    value: float | str
    unit: StatementUnit
    yoy_pct: float | None = None
    qoq_pct: float | None = None

    def __post_init__(self) -> None:
        _require_text(self.code, field="code")
        _require_text(self.label, field="label")
        if not self.code.isascii() or " " in self.code or self.code != self.code.lower():
            raise ValueError(
                f"StatementItem.code must be a stable snake_case identifier, got {self.code!r}"
            )


@dataclass(frozen=True, kw_only=True)
class FinancialStatement:
    instrument_id: InstrumentId
    sheet: FinancialSheet
    period_end: date
    period_type: FinancialPeriodType
    currency: str
    items: tuple[StatementItem, ...]
    announced_at: datetime | None = None
    source_payload: object | None = None

    def __post_init__(self) -> None:
        _require_text(self.currency, field="currency")
        _require_tuple(self.items, field="items")

    @property
    def natural_key(self) -> tuple[InstrumentId, FinancialSheet, date, FinancialPeriodType]:
        return (self.instrument_id, self.sheet, self.period_end, self.period_type)


@dataclass(frozen=True, kw_only=True)
class Classification:
    id: str
    kind: ClassificationKind
    name: str
    taxonomy: str

    def __post_init__(self) -> None:
        _require_text(self.id, field="id")
        _require_text(self.name, field="name")
        _require_text(self.taxonomy, field="taxonomy")

    @property
    def natural_key(self) -> tuple[str, str]:
        return (self.taxonomy, self.id)


@dataclass(frozen=True, kw_only=True)
class Membership:
    classification_id: str
    taxonomy: str
    instrument_id: InstrumentId
    effective_from: date | None = None
    effective_to: date | None = None
    weight_pct: float | None = None

    def __post_init__(self) -> None:
        _require_text(self.classification_id, field="classification_id")
        _require_text(self.taxonomy, field="taxonomy")

    @property
    def natural_key(self) -> tuple[str, str, InstrumentId, date | None]:
        return (
            self.taxonomy,
            self.classification_id,
            self.instrument_id,
            self.effective_from,
        )


@dataclass(frozen=True, kw_only=True)
class NewsItem:
    id: str
    instrument_id: InstrumentId
    title: str
    published_at: datetime
    publisher: str | None = None
    summary: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, field="id")
        _require_text(self.title, field="title")
        _require_optional_text(self.publisher, field="publisher")
        _require_optional_text(self.summary, field="summary")
        _require_optional_text(self.url, field="url")

    @property
    def natural_key(self) -> str:
        return self.id


@dataclass(frozen=True, kw_only=True)
class NoticeEvent:
    id: str
    instrument_id: InstrumentId
    title: str
    published_at: datetime
    source: str | None = None
    url: str | None = None
    notice_type: str | None = None
    summary: str | None = None
    kind: EventKind = EventKind.NOTICE

    def __post_init__(self) -> None:
        _require_event_header(self)
        _require_optional_text(self.notice_type, field="notice_type")
        _require_optional_text(self.summary, field="summary")
        if self.kind is not EventKind.NOTICE:
            raise ValueError(f"NoticeEvent.kind must be {EventKind.NOTICE}, got {self.kind!r}")

    @property
    def natural_key(self) -> str:
        return self.id


@dataclass(frozen=True, kw_only=True)
class ResearchReportEvent:
    id: str
    instrument_id: InstrumentId
    title: str
    published_at: datetime
    source: str | None = None
    url: str | None = None
    organization: str | None = None
    rating: str | None = None
    summary: str | None = None
    pdf_url: str | None = None
    kind: EventKind = EventKind.RESEARCH_REPORT

    def __post_init__(self) -> None:
        _require_event_header(self)
        _require_optional_text(self.organization, field="organization")
        _require_optional_text(self.rating, field="rating")
        _require_optional_text(self.summary, field="summary")
        _require_optional_text(self.pdf_url, field="pdf_url")
        if self.kind is not EventKind.RESEARCH_REPORT:
            raise ValueError(
                f"ResearchReportEvent.kind must be {EventKind.RESEARCH_REPORT}, got {self.kind!r}"
            )

    @property
    def natural_key(self) -> str:
        return self.id


@dataclass(frozen=True, kw_only=True)
class BlockTradeEvent:
    id: str
    instrument_id: InstrumentId
    title: str
    published_at: datetime
    source: str | None = None
    url: str | None = None
    deal_price: float | None = None
    volume: float | None = None
    amount: float | None = None
    premium_pct: float | None = None
    buyer: str | None = None
    seller: str | None = None
    close_price: float | None = None
    pct_change: float | None = None
    kind: EventKind = EventKind.BLOCK_TRADE

    def __post_init__(self) -> None:
        _require_event_header(self)
        _require_optional_text(self.buyer, field="buyer")
        _require_optional_text(self.seller, field="seller")
        if self.kind is not EventKind.BLOCK_TRADE:
            raise ValueError(
                f"BlockTradeEvent.kind must be {EventKind.BLOCK_TRADE}, got {self.kind!r}"
            )

    @property
    def natural_key(self) -> str:
        return self.id


@dataclass(frozen=True, kw_only=True)
class HolderChangeEvent:
    id: str
    instrument_id: InstrumentId
    title: str
    published_at: datetime
    source: str | None = None
    url: str | None = None
    person: str | None = None
    role: str | None = None
    change_shares: float | None = None
    average_price: float | None = None
    reason: str | None = None
    kind: EventKind = EventKind.HOLDER_CHANGE

    def __post_init__(self) -> None:
        _require_event_header(self)
        _require_optional_text(self.person, field="person")
        _require_optional_text(self.role, field="role")
        _require_optional_text(self.reason, field="reason")
        if self.kind is not EventKind.HOLDER_CHANGE:
            raise ValueError(
                f"HolderChangeEvent.kind must be {EventKind.HOLDER_CHANGE}, got {self.kind!r}"
            )

    @property
    def natural_key(self) -> str:
        return self.id


MarketEvent = NoticeEvent | ResearchReportEvent | BlockTradeEvent | HolderChangeEvent
MARKET_EVENT_TYPES: tuple[type[MarketEvent], ...] = (
    NoticeEvent,
    ResearchReportEvent,
    BlockTradeEvent,
    HolderChangeEvent,
)


def _require_event_header(event: object) -> None:
    _require_text(getattr(event, "id"), field="id")
    _require_text(getattr(event, "title"), field="title")
    _require_optional_text(getattr(event, "source"), field="source")
    _require_optional_text(getattr(event, "url"), field="url")
