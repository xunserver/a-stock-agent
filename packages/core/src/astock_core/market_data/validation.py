"""Reusable validation for Standard Records and Datasets.

Functions return the validated value or raise ``InvalidSourcePayload``.
They never drop invalid records.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Sequence
from datetime import date, datetime
from typing import TypeVar

from astock_core.market_data.dataset import Dataset
from astock_core.market_data.errors import InvalidSourcePayload
from astock_core.market_data.models import (
    Bar,
    FinancialStatement,
    FundamentalPeriod,
    Instrument,
    InstrumentProfile,
    QuoteSnapshot,
    StatementItem,
    TradingDay,
    ValuationSnapshot,
)
from astock_core.market_data.queries import (
    BarQuery,
    CalendarQuery,
    FundamentalQuery,
    InstrumentQuery,
    SnapshotQuery,
    StatementQuery,
    ValuationQuery,
)

T = TypeVar("T")


def require_finite(value: float, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidSourcePayload(f"{field} must be a finite number, got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise InvalidSourcePayload(f"{field} must be a finite number, got {value!r}")
    return number


def require_optional_finite(value: float | None, *, field: str) -> float | None:
    if value is None:
        return None
    return require_finite(value, field=field)


def require_positive(value: float, *, field: str) -> float:
    number = require_finite(value, field=field)
    if number <= 0:
        raise InvalidSourcePayload(f"{field} must be positive, got {number}")
    return number


def require_non_negative(value: float, *, field: str) -> float:
    number = require_finite(value, field=field)
    if number < 0:
        raise InvalidSourcePayload(f"{field} must be >= 0, got {number}")
    return number


def require_aware_datetime(value: datetime, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidSourcePayload(f"{field} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None:
        raise InvalidSourcePayload(f"{field} must be timezone-aware")
    return value


def require_optional_aware_datetime(value: datetime | None, *, field: str) -> datetime | None:
    if value is None:
        return None
    return require_aware_datetime(value, field=field)


def require_inclusive_range(start: date, end: date) -> tuple[date, date]:
    if end < start:
        raise InvalidSourcePayload(f"inclusive range is inverted: end {end} < start {start}")
    return start, end


def reject_vendor_types(value: object, *, field: str = "value") -> None:
    module = type(value).__module__
    if module.startswith("pandas") or module.startswith("akshare") or module.startswith("curl_cffi"):
        raise InvalidSourcePayload(
            f"{field} must not carry a vendor or pandas type, got {type(value).__module__}.{type(value).__name__}"
        )


def validate_unique_natural_keys(
    items: Sequence[T],
    *,
    natural_key: Callable[[T], Hashable],
    label: str,
) -> None:
    seen: dict[Hashable, int] = {}
    for index, item in enumerate(items):
        key = natural_key(item)
        if key in seen:
            raise InvalidSourcePayload(
                f"duplicate {label} natural key {key!r} at indexes {seen[key]} and {index}"
            )
        seen[key] = index


def validate_sorted(
    items: Sequence[T],
    *,
    sort_key: Callable[[T], object],
    label: str,
) -> None:
    previous = None
    for index, item in enumerate(items):
        current = sort_key(item)
        if previous is not None and current < previous:  # type: ignore[operator]
            raise InvalidSourcePayload(
                f"{label} items must be ascending; index {index} is out of order"
            )
        previous = current


def validate_bar(bar: Bar) -> Bar:
    if not isinstance(bar, Bar):
        raise InvalidSourcePayload(f"expected Bar, got {type(bar).__name__}")
    reject_vendor_types(bar, field="bar")
    open_ = require_positive(bar.open, field="open")
    high = require_positive(bar.high, field="high")
    low = require_positive(bar.low, field="low")
    close = require_positive(bar.close, field="close")
    require_non_negative(bar.volume, field="volume")
    require_non_negative(bar.amount, field="amount")
    require_optional_finite(bar.turnover_pct, field="turnover_pct")
    if bar.turnover_pct is not None and bar.turnover_pct < 0:
        raise InvalidSourcePayload(f"turnover_pct must be >= 0, got {bar.turnover_pct}")
    require_optional_finite(bar.adjustment_factor, field="adjustment_factor")
    if high < max(open_, close, low):
        raise InvalidSourcePayload(
            f"high {high} must be >= max(open, close, low)={max(open_, close, low)}"
        )
    if low > min(open_, close, high):
        raise InvalidSourcePayload(
            f"low {low} must be <= min(open, close, high)={min(open_, close, high)}"
        )
    return bar


def validate_bar_query(query: BarQuery) -> BarQuery:
    require_inclusive_range(query.start, query.end)
    if not query.instruments:
        raise InvalidSourcePayload("BarQuery.instruments must contain at least one InstrumentId")
    return query


def _bar_sort_key(bar: Bar) -> tuple[date, str, str, str]:
    return (bar.trade_date, bar.instrument_id.value, bar.interval, bar.adjustment)


def _bar_agrees_with_query(bar: Bar, query: BarQuery) -> None:
    if bar.instrument_id not in query.instruments:
        raise InvalidSourcePayload(
            f"Bar {bar.natural_key!r} instrument is not in the query"
        )
    if bar.trade_date < query.start or bar.trade_date > query.end:
        raise InvalidSourcePayload(
            f"Bar trade_date {bar.trade_date} is outside query range "
            f"{query.start}..{query.end}"
        )
    if bar.interval != query.interval:
        raise InvalidSourcePayload(
            f"Bar interval {bar.interval} does not match query interval {query.interval}"
        )
    if bar.adjustment != query.adjustment:
        raise InvalidSourcePayload(
            f"Bar adjustment {bar.adjustment} does not match query adjustment {query.adjustment}"
        )


def validate_bar_dataset(dataset: Dataset[Bar], query: BarQuery) -> Dataset[Bar]:
    validate_bar_query(query)
    reject_vendor_types(dataset, field="dataset")
    require_aware_datetime(dataset.fetched_at, field="fetched_at")
    for index, item in enumerate(dataset.items):
        try:
            validate_bar(item)
            _bar_agrees_with_query(item, query)
        except InvalidSourcePayload as exc:
            raise InvalidSourcePayload(f"invalid Bar at index {index}: {exc}") from exc
    validate_unique_natural_keys(
        dataset.items, natural_key=lambda bar: bar.natural_key, label="Bar"
    )
    validate_sorted(dataset.items, sort_key=_bar_sort_key, label="Bar")
    return dataset


def validate_calendar_query(query: CalendarQuery) -> CalendarQuery:
    require_inclusive_range(query.start, query.end)
    if not query.market_id:
        raise InvalidSourcePayload("CalendarQuery.market_id must be a non-empty string")
    return query


def _calendar_sort_key(day: TradingDay) -> tuple[date, str]:
    return (day.trade_date, day.market_id)


def validate_calendar_dataset(
    dataset: Dataset[TradingDay], query: CalendarQuery
) -> Dataset[TradingDay]:
    validate_calendar_query(query)
    reject_vendor_types(dataset, field="dataset")
    require_aware_datetime(dataset.fetched_at, field="fetched_at")
    for index, item in enumerate(dataset.items):
        if not isinstance(item, TradingDay):
            raise InvalidSourcePayload(
                f"invalid TradingDay at index {index}: expected TradingDay, got {type(item).__name__}"
            )
        reject_vendor_types(item, field=f"items[{index}]")
        if item.market_id != query.market_id:
            raise InvalidSourcePayload(
                f"invalid TradingDay at index {index}: market_id {item.market_id!r} "
                f"does not match query {query.market_id!r}"
            )
        if item.trade_date < query.start or item.trade_date > query.end:
            raise InvalidSourcePayload(
                f"invalid TradingDay at index {index}: trade_date {item.trade_date} "
                f"is outside query range {query.start}..{query.end}"
            )
    validate_unique_natural_keys(
        dataset.items, natural_key=lambda day: day.natural_key, label="TradingDay"
    )
    validate_sorted(dataset.items, sort_key=_calendar_sort_key, label="TradingDay")
    return dataset


def _instrument_matches_query(instrument: Instrument, query: InstrumentQuery) -> None:
    if query.instruments and instrument.id not in query.instruments:
        raise InvalidSourcePayload(
            f"Instrument {instrument.id.value} is not in the query"
        )
    if query.asset_types and instrument.asset_type not in query.asset_types:
        raise InvalidSourcePayload(
            f"Instrument {instrument.id.value} asset_type {instrument.asset_type} "
            f"is not in the query"
        )
    if query.exchanges and instrument.id.exchange not in query.exchanges:
        raise InvalidSourcePayload(
            f"Instrument {instrument.id.value} exchange {instrument.id.exchange} "
            f"is not in the query"
        )


def validate_instrument_dataset(
    dataset: Dataset[Instrument], query: InstrumentQuery
) -> Dataset[Instrument]:
    reject_vendor_types(dataset, field="dataset")
    require_aware_datetime(dataset.fetched_at, field="fetched_at")
    for index, item in enumerate(dataset.items):
        if not isinstance(item, Instrument):
            raise InvalidSourcePayload(
                f"invalid Instrument at index {index}: expected Instrument, "
                f"got {type(item).__name__}"
            )
        reject_vendor_types(item, field=f"items[{index}]")
        try:
            _instrument_matches_query(item, query)
        except InvalidSourcePayload as exc:
            raise InvalidSourcePayload(f"invalid Instrument at index {index}: {exc}") from exc
    validate_unique_natural_keys(
        dataset.items, natural_key=lambda item: item.natural_key, label="Instrument"
    )
    validate_sorted(
        dataset.items, sort_key=lambda item: item.id.value, label="Instrument"
    )
    return dataset


def validate_instrument_profile_dataset(
    dataset: Dataset[InstrumentProfile], query: InstrumentQuery
) -> Dataset[InstrumentProfile]:
    reject_vendor_types(dataset, field="dataset")
    require_aware_datetime(dataset.fetched_at, field="fetched_at")
    wanted = frozenset(query.instruments)
    for index, item in enumerate(dataset.items):
        if not isinstance(item, InstrumentProfile):
            raise InvalidSourcePayload(
                f"invalid InstrumentProfile at index {index}: expected InstrumentProfile, "
                f"got {type(item).__name__}"
            )
        reject_vendor_types(item, field=f"items[{index}]")
        if wanted and item.instrument_id not in wanted:
            raise InvalidSourcePayload(
                f"invalid InstrumentProfile at index {index}: instrument "
                f"{item.instrument_id.value} is not in the query"
            )
        if query.exchanges and item.instrument_id.exchange not in query.exchanges:
            raise InvalidSourcePayload(
                f"invalid InstrumentProfile at index {index}: exchange "
                f"{item.instrument_id.exchange} is not in the query"
            )
    validate_unique_natural_keys(
        dataset.items, natural_key=lambda item: item.natural_key, label="InstrumentProfile"
    )
    validate_sorted(
        dataset.items,
        sort_key=lambda item: item.instrument_id.value,
        label="InstrumentProfile",
    )
    return dataset


_QUOTE_OPTIONAL_NUMBERS = (
    "last_price",
    "pre_close",
    "average_price",
    "high_limit",
    "low_limit",
    "volume_ratio",
    "outer_volume",
    "inner_volume",
)
_QUOTE_NON_NEGATIVE = frozenset(
    {"volume_ratio", "outer_volume", "inner_volume"}
)


def validate_quote_snapshot(snapshot: QuoteSnapshot) -> QuoteSnapshot:
    if not isinstance(snapshot, QuoteSnapshot):
        raise InvalidSourcePayload(f"expected QuoteSnapshot, got {type(snapshot).__name__}")
    reject_vendor_types(snapshot, field="snapshot")
    require_aware_datetime(snapshot.observed_at, field="observed_at")
    for field in _QUOTE_OPTIONAL_NUMBERS:
        value = require_optional_finite(getattr(snapshot, field), field=field)
        if value is not None and field in _QUOTE_NON_NEGATIVE and value < 0:
            raise InvalidSourcePayload(f"{field} must be >= 0, got {value}")
    return snapshot


def validate_quote_snapshot_dataset(
    dataset: Dataset[QuoteSnapshot], query: SnapshotQuery
) -> Dataset[QuoteSnapshot]:
    reject_vendor_types(dataset, field="dataset")
    require_aware_datetime(dataset.fetched_at, field="fetched_at")
    wanted = frozenset(query.instruments)
    for index, item in enumerate(dataset.items):
        try:
            validate_quote_snapshot(item)
        except InvalidSourcePayload as exc:
            raise InvalidSourcePayload(f"invalid QuoteSnapshot at index {index}: {exc}") from exc
        if item.instrument_id not in wanted:
            raise InvalidSourcePayload(
                f"invalid QuoteSnapshot at index {index}: instrument "
                f"{item.instrument_id.value} is not in the query"
            )
    validate_unique_natural_keys(
        dataset.items, natural_key=lambda item: item.natural_key, label="QuoteSnapshot"
    )
    validate_sorted(
        dataset.items,
        sort_key=lambda item: (item.instrument_id.value, item.observed_at),
        label="QuoteSnapshot",
    )
    return dataset


_VALUATION_OPTIONAL_NUMBERS = (
    "total_shares",
    "float_shares",
    "total_market_cap",
    "float_market_cap",
    "pe_ttm",
    "pe_static",
    "pb",
)
_VALUATION_NON_NEGATIVE = frozenset(
    {"total_shares", "float_shares", "total_market_cap", "float_market_cap"}
)


def validate_valuation_snapshot(snapshot: ValuationSnapshot) -> ValuationSnapshot:
    if not isinstance(snapshot, ValuationSnapshot):
        raise InvalidSourcePayload(
            f"expected ValuationSnapshot, got {type(snapshot).__name__}"
        )
    reject_vendor_types(snapshot, field="snapshot")
    for field in _VALUATION_OPTIONAL_NUMBERS:
        value = require_optional_finite(getattr(snapshot, field), field=field)
        if value is not None and field in _VALUATION_NON_NEGATIVE and value < 0:
            raise InvalidSourcePayload(f"{field} must be >= 0, got {value}")
    return snapshot


def validate_valuation_dataset(
    dataset: Dataset[ValuationSnapshot], query: ValuationQuery
) -> Dataset[ValuationSnapshot]:
    reject_vendor_types(dataset, field="dataset")
    require_aware_datetime(dataset.fetched_at, field="fetched_at")
    wanted = frozenset(query.instruments)
    for index, item in enumerate(dataset.items):
        try:
            validate_valuation_snapshot(item)
        except InvalidSourcePayload as exc:
            raise InvalidSourcePayload(
                f"invalid ValuationSnapshot at index {index}: {exc}"
            ) from exc
        if item.instrument_id not in wanted:
            raise InvalidSourcePayload(
                f"invalid ValuationSnapshot at index {index}: instrument "
                f"{item.instrument_id.value} is not in the query"
            )
        if query.as_of is not None and item.as_of != query.as_of:
            raise InvalidSourcePayload(
                f"invalid ValuationSnapshot at index {index}: as_of {item.as_of} "
                f"does not match query {query.as_of}"
            )
    validate_unique_natural_keys(
        dataset.items, natural_key=lambda item: item.natural_key, label="ValuationSnapshot"
    )
    validate_sorted(
        dataset.items,
        sort_key=lambda item: (item.instrument_id.value, item.as_of),
        label="ValuationSnapshot",
    )
    return dataset


_FUNDAMENTAL_OPTIONAL_NUMBERS = (
    "eps",
    "bps",
    "roe_pct",
    "revenue",
    "revenue_yoy_pct",
    "net_profit",
    "net_profit_yoy_pct",
    "gross_margin_pct",
    "net_margin_pct",
    "debt_ratio_pct",
)


def validate_fundamental_period(period: FundamentalPeriod) -> FundamentalPeriod:
    if not isinstance(period, FundamentalPeriod):
        raise InvalidSourcePayload(f"expected FundamentalPeriod, got {type(period).__name__}")
    reject_vendor_types(period, field="period")
    require_optional_aware_datetime(period.announced_at, field="announced_at")
    for field in _FUNDAMENTAL_OPTIONAL_NUMBERS:
        require_optional_finite(getattr(period, field), field=field)
    return period


def validate_fundamental_dataset(
    dataset: Dataset[FundamentalPeriod], query: FundamentalQuery
) -> Dataset[FundamentalPeriod]:
    reject_vendor_types(dataset, field="dataset")
    require_aware_datetime(dataset.fetched_at, field="fetched_at")
    wanted = frozenset(query.instruments)
    wanted_periods = frozenset(query.period_types)
    for index, item in enumerate(dataset.items):
        try:
            validate_fundamental_period(item)
        except InvalidSourcePayload as exc:
            raise InvalidSourcePayload(
                f"invalid FundamentalPeriod at index {index}: {exc}"
            ) from exc
        if item.instrument_id not in wanted:
            raise InvalidSourcePayload(
                f"invalid FundamentalPeriod at index {index}: instrument "
                f"{item.instrument_id.value} is not in the query"
            )
        if wanted_periods and item.period_type not in wanted_periods:
            raise InvalidSourcePayload(
                f"invalid FundamentalPeriod at index {index}: period_type "
                f"{item.period_type} is not in the query"
            )
        if query.start is not None and item.period_end < query.start:
            raise InvalidSourcePayload(
                f"invalid FundamentalPeriod at index {index}: period_end "
                f"{item.period_end} is before query start {query.start}"
            )
        if query.end is not None and item.period_end > query.end:
            raise InvalidSourcePayload(
                f"invalid FundamentalPeriod at index {index}: period_end "
                f"{item.period_end} is after query end {query.end}"
            )
    validate_unique_natural_keys(
        dataset.items, natural_key=lambda item: item.natural_key, label="FundamentalPeriod"
    )
    validate_sorted(
        dataset.items,
        sort_key=lambda item: (item.instrument_id.value, item.period_end, item.period_type.value),
        label="FundamentalPeriod",
    )
    return dataset


def validate_statement_item(item: StatementItem, *, field: str = "item") -> StatementItem:
    if not isinstance(item, StatementItem):
        raise InvalidSourcePayload(f"expected StatementItem, got {type(item).__name__}")
    reject_vendor_types(item, field=field)
    if isinstance(item.value, (int, float)):
        require_finite(float(item.value), field=f"{field}.value")
    elif not isinstance(item.value, str) or not item.value:
        raise InvalidSourcePayload(f"{field}.value must be a finite number or non-empty string")
    require_optional_finite(item.yoy_pct, field=f"{field}.yoy_pct")
    require_optional_finite(item.qoq_pct, field=f"{field}.qoq_pct")
    return item


def validate_financial_statement(statement: FinancialStatement) -> FinancialStatement:
    if not isinstance(statement, FinancialStatement):
        raise InvalidSourcePayload(
            f"expected FinancialStatement, got {type(statement).__name__}"
        )
    reject_vendor_types(statement, field="statement")
    require_optional_aware_datetime(statement.announced_at, field="announced_at")
    seen: set[str] = set()
    for index, item in enumerate(statement.items):
        validate_statement_item(item, field=f"items[{index}]")
        if item.code in seen:
            raise InvalidSourcePayload(f"duplicate StatementItem code {item.code!r}")
        seen.add(item.code)
    return statement


def validate_statement_dataset(
    dataset: Dataset[FinancialStatement], query: StatementQuery
) -> Dataset[FinancialStatement]:
    reject_vendor_types(dataset, field="dataset")
    require_aware_datetime(dataset.fetched_at, field="fetched_at")
    wanted = frozenset(query.instruments)
    wanted_periods = frozenset(query.period_types)
    for index, item in enumerate(dataset.items):
        try:
            validate_financial_statement(item)
        except InvalidSourcePayload as exc:
            raise InvalidSourcePayload(
                f"invalid FinancialStatement at index {index}: {exc}"
            ) from exc
        if item.instrument_id not in wanted:
            raise InvalidSourcePayload(
                f"invalid FinancialStatement at index {index}: instrument "
                f"{item.instrument_id.value} is not in the query"
            )
        if item.sheet is not query.sheet:
            raise InvalidSourcePayload(
                f"invalid FinancialStatement at index {index}: sheet {item.sheet} "
                f"does not match query {query.sheet}"
            )
        if wanted_periods and item.period_type not in wanted_periods:
            raise InvalidSourcePayload(
                f"invalid FinancialStatement at index {index}: period_type "
                f"{item.period_type} is not in the query"
            )
        if query.start is not None and item.period_end < query.start:
            raise InvalidSourcePayload(
                f"invalid FinancialStatement at index {index}: period_end "
                f"{item.period_end} is before query start {query.start}"
            )
        if query.end is not None and item.period_end > query.end:
            raise InvalidSourcePayload(
                f"invalid FinancialStatement at index {index}: period_end "
                f"{item.period_end} is after query end {query.end}"
            )
    validate_unique_natural_keys(
        dataset.items, natural_key=lambda item: item.natural_key, label="FinancialStatement"
    )
    validate_sorted(
        dataset.items,
        sort_key=lambda item: (
            item.instrument_id.value,
            item.period_end,
            item.period_type.value,
        ),
        label="FinancialStatement",
    )
    return dataset
