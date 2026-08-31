"""Capability query types."""

from __future__ import annotations

from collections.abc import Sequence
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
)
from astock_core.market_data.identity import InstrumentId


def _freeze_tuple(value: object, *, field: str) -> tuple:
    if isinstance(value, tuple):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(value)
    raise TypeError(f"{field} must be a sequence, got {type(value).__name__}")


def _require_instruments(instruments: tuple[InstrumentId, ...], *, field: str) -> None:
    if not instruments:
        raise ValueError(f"{field} must contain at least one InstrumentId")
    for item in instruments:
        if not isinstance(item, InstrumentId):
            raise TypeError(f"{field} items must be InstrumentId values")


def _require_inclusive_dates(
    start: date | None,
    end: date | None,
    *,
    start_field: str,
    end_field: str,
) -> None:
    if start is not None and end is not None and end < start:
        raise ValueError(f"{end_field} must be on or after {start_field}")


def _require_inclusive_datetimes(
    start: datetime | None,
    end: datetime | None,
    *,
    start_field: str,
    end_field: str,
) -> None:
    if start is not None and start.tzinfo is None:
        raise ValueError(f"{start_field} must be timezone-aware")
    if end is not None and end.tzinfo is None:
        raise ValueError(f"{end_field} must be timezone-aware")
    if start is not None and end is not None and end < start:
        raise ValueError(f"{end_field} must be on or after {start_field}")


@dataclass(frozen=True, kw_only=True)
class InstrumentQuery:
    asset_types: tuple[AssetType, ...] = ()
    exchanges: tuple[str, ...] = ()
    instruments: tuple[InstrumentId, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_types", _freeze_tuple(self.asset_types, field="asset_types"))
        object.__setattr__(self, "exchanges", _freeze_tuple(self.exchanges, field="exchanges"))
        object.__setattr__(
            self, "instruments", _freeze_tuple(self.instruments, field="instruments")
        )


@dataclass(frozen=True, kw_only=True)
class CalendarQuery:
    market_id: str
    start: date
    end: date

    def __post_init__(self) -> None:
        if not self.market_id:
            raise ValueError("CalendarQuery.market_id must be a non-empty string")
        _require_inclusive_dates(self.start, self.end, start_field="start", end_field="end")


@dataclass(frozen=True, kw_only=True)
class BarQuery:
    instruments: tuple[InstrumentId, ...]
    start: date
    end: date
    interval: BarInterval
    adjustment: Adjustment

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "instruments", _freeze_tuple(self.instruments, field="instruments")
        )
        _require_instruments(self.instruments, field="BarQuery.instruments")
        _require_inclusive_dates(self.start, self.end, start_field="start", end_field="end")


@dataclass(frozen=True, kw_only=True)
class SnapshotQuery:
    instruments: tuple[InstrumentId, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "instruments", _freeze_tuple(self.instruments, field="instruments")
        )
        _require_instruments(self.instruments, field="SnapshotQuery.instruments")


@dataclass(frozen=True, kw_only=True)
class ValuationQuery:
    instruments: tuple[InstrumentId, ...]
    as_of: date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "instruments", _freeze_tuple(self.instruments, field="instruments")
        )
        _require_instruments(self.instruments, field="ValuationQuery.instruments")


@dataclass(frozen=True, kw_only=True)
class FundamentalQuery:
    instruments: tuple[InstrumentId, ...]
    period_types: tuple[FinancialPeriodType, ...] = ()
    start: date | None = None
    end: date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "instruments", _freeze_tuple(self.instruments, field="instruments")
        )
        object.__setattr__(
            self, "period_types", _freeze_tuple(self.period_types, field="period_types")
        )
        _require_instruments(self.instruments, field="FundamentalQuery.instruments")
        _require_inclusive_dates(self.start, self.end, start_field="start", end_field="end")


@dataclass(frozen=True, kw_only=True)
class StatementQuery:
    instruments: tuple[InstrumentId, ...]
    sheet: FinancialSheet
    period_types: tuple[FinancialPeriodType, ...] = ()
    start: date | None = None
    end: date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "instruments", _freeze_tuple(self.instruments, field="instruments")
        )
        object.__setattr__(
            self, "period_types", _freeze_tuple(self.period_types, field="period_types")
        )
        _require_instruments(self.instruments, field="StatementQuery.instruments")
        _require_inclusive_dates(self.start, self.end, start_field="start", end_field="end")


@dataclass(frozen=True, kw_only=True)
class ClassificationQuery:
    kind: ClassificationKind | None = None
    taxonomy: str | None = None
    ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ids", _freeze_tuple(self.ids, field="ids"))
        if self.taxonomy is not None and not self.taxonomy:
            raise ValueError("ClassificationQuery.taxonomy must be None or a non-empty string")


@dataclass(frozen=True, kw_only=True)
class MembershipQuery:
    taxonomy: str | None = None
    classification_id: str | None = None
    kind: ClassificationKind | None = None
    instrument_id: InstrumentId | None = None
    as_of: date | None = None

    def __post_init__(self) -> None:
        if self.taxonomy is not None and not self.taxonomy:
            raise ValueError("MembershipQuery.taxonomy must be None or a non-empty string")
        if self.classification_id is not None and not self.classification_id:
            raise ValueError(
                "MembershipQuery.classification_id must be None or a non-empty string"
            )


@dataclass(frozen=True, kw_only=True)
class NewsQuery:
    instruments: tuple[InstrumentId, ...]
    start: datetime | None = None
    end: datetime | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "instruments", _freeze_tuple(self.instruments, field="instruments")
        )
        _require_instruments(self.instruments, field="NewsQuery.instruments")
        _require_inclusive_datetimes(self.start, self.end, start_field="start", end_field="end")
        if self.limit is not None and self.limit < 0:
            raise ValueError("NewsQuery.limit must be None or >= 0")


@dataclass(frozen=True, kw_only=True)
class EventQuery:
    instruments: tuple[InstrumentId, ...]
    kinds: tuple[EventKind, ...] = ()
    start: datetime | None = None
    end: datetime | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "instruments", _freeze_tuple(self.instruments, field="instruments")
        )
        object.__setattr__(self, "kinds", _freeze_tuple(self.kinds, field="kinds"))
        _require_instruments(self.instruments, field="EventQuery.instruments")
        _require_inclusive_datetimes(self.start, self.end, start_field="start", end_field="end")
        if self.limit is not None and self.limit < 0:
            raise ValueError("EventQuery.limit must be None or >= 0")
