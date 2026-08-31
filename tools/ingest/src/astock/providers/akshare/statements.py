"""AKShare Financial Statement Adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from astock_core.market_data import (
    Dataset,
    FinancialSheet,
    FinancialStatement,
    InstrumentId,
    InvalidSourcePayload,
    StatementQuery,
    period_type_from_end,
    to_legacy_symbol,
    validate_statement_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error
from astock.providers.akshare._tables import (
    as_optional_date,
    lookup_column,
    records_from_source_table,
)
from astock.providers.akshare.statement_aliases import items_from_source_row
from astock.providers.eastmoney.snapshots import CN_CURRENCY, CN_TIMEZONE

SOURCE = "akshare"
_SHANGHAI = ZoneInfo(CN_TIMEZONE)
_META_KEYS = frozenset(
    {
        "SECUCODE",
        "SECURITY_CODE",
        "SECURITY_NAME_ABBR",
        "ORG_CODE",
        "ORG_TYPE",
        "REPORT_DATE",
        "REPORT_TYPE",
        "REPORT_DATE_NAME",
        "NOTICE_DATE",
        "UPDATE_DATE",
        "CURRENCY",
        "OSOPINION_TYPE",
        "LISTING_STATE",
        "SECURITY_TYPE_CODE",
    }
)

SheetTable = Callable[..., object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time as time_mod

    time_mod.sleep(seconds)


def _default_balance(symbol: str) -> object:
    import akshare as ak

    return ak.stock_balance_sheet_by_report_em(symbol=symbol)


def _default_profit(symbol: str) -> object:
    import akshare as ak

    return ak.stock_profit_sheet_by_report_em(symbol=symbol)


def _default_cashflow(symbol: str) -> object:
    import akshare as ak

    return ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)


def f10_symbol(instrument_id: InstrumentId) -> str:
    code = to_legacy_symbol(instrument_id)
    prefix = {"XSHG": "SH", "BSE": "BJ"}.get(instrument_id.exchange, "SZ")
    return f"{prefix}{code}"


class AkshareStatementAdapter:
    """Translate AKShare F10 three-statement payloads into Financial Statements."""

    def __init__(
        self,
        *,
        balance: SheetTable | None = None,
        profit: SheetTable | None = None,
        cashflow: SheetTable | None = None,
        timeout: float = 20.0,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._fetchers = {
            FinancialSheet.BALANCE: balance or _default_balance,
            FinancialSheet.PROFIT: profit or _default_profit,
            FinancialSheet.CASHFLOW: cashflow or _default_cashflow,
        }
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock

    def fetch_statements(self, query: StatementQuery) -> Dataset[FinancialStatement]:
        statements: list[FinancialStatement] = []
        warnings: list[str] = []
        fetcher = self._fetchers[query.sheet]
        for instrument_id in query.instruments:
            rows = records_from_source_table(
                self._call(lambda symbol=f10_symbol(instrument_id): fetcher(symbol))
            )
            resolved: dict[tuple, FinancialStatement] = {}
            seen_ends: set[date] = set()
            for index, row in enumerate(rows):
                statement = _statement_from_row(
                    instrument_id, query.sheet, row, index=index
                )
                if statement is None:
                    continue
                seen_ends.add(statement.period_end)
                key = statement.natural_key
                existing = resolved.get(key)
                if existing is None:
                    resolved[key] = statement
                    continue
                winner = _prefer_restated(existing, statement)
                if winner is not existing:
                    warnings.append(
                        f"restated Financial Statement {instrument_id.value} "
                        f"{statement.sheet.value} {statement.period_end.isoformat()} "
                        "kept later announcement"
                    )
                resolved[key] = winner
            statements.extend(resolved.values())
        statements = _filter_query(statements, query)
        statements.sort(
            key=lambda item: (item.instrument_id.value, item.period_end, item.period_type.value)
        )
        dataset = Dataset(
            items=tuple(statements),
            source=SOURCE,
            fetched_at=self._clock(),
            coverage_start=query.start,
            coverage_end=query.end,
            complete=True,
            warnings=tuple(warnings),
        )
        return validate_statement_dataset(dataset, query)

    def _call(self, operation: Callable[[], object]) -> object:
        def wrapped() -> object:
            try:
                return operation()
            except Exception as exc:
                raise translate_transport_error(exc) from exc

        return call_with_retries(wrapped, retries=self._retries, sleep=self._sleep)


def _filter_query(
    statements: list[FinancialStatement], query: StatementQuery
) -> list[FinancialStatement]:
    wanted_types = frozenset(query.period_types)
    out: list[FinancialStatement] = []
    for statement in statements:
        if wanted_types and statement.period_type not in wanted_types:
            continue
        if query.start is not None and statement.period_end < query.start:
            continue
        if query.end is not None and statement.period_end > query.end:
            continue
        out.append(statement)
    return out


def _prefer_restated(
    first: FinancialStatement, second: FinancialStatement
) -> FinancialStatement:
    if first.announced_at is None:
        return second
    if second.announced_at is None:
        return first
    return second if second.announced_at >= first.announced_at else first


def _statement_from_row(
    instrument_id: InstrumentId,
    sheet: FinancialSheet,
    row: dict[str, object],
    *,
    index: int,
) -> FinancialStatement | None:
    period_end = as_optional_date(
        lookup_column(row, ("REPORT_DATE", "report_date")),
        field=f"REPORT_DATE[{index}]",
    )
    if period_end is None:
        raise InvalidSourcePayload(f"statement row {index} is missing REPORT_DATE")
    try:
        period_type = period_type_from_end(period_end)
    except InvalidSourcePayload as exc:
        raise InvalidSourcePayload(
            f"malformed mixed-period statement row {index}: {exc}"
        ) from exc
    announced = _announced_at(
        lookup_column(row, ("NOTICE_DATE", "notice_date")),
        field=f"NOTICE_DATE[{index}]",
    )
    currency = str(lookup_column(row, ("CURRENCY",)) or CN_CURRENCY).strip() or CN_CURRENCY
    if currency.upper() in {"CNY", "人民币", "RMB"}:
        currency = CN_CURRENCY
    payload = {key: value for key, value in row.items() if key not in _META_KEYS}
    items = items_from_source_row(payload)
    if not items:
        return None
    return FinancialStatement(
        instrument_id=instrument_id,
        sheet=sheet,
        period_end=period_end,
        period_type=period_type,
        currency=currency,
        items=items,
        announced_at=announced,
        source_payload=None,
    )


def _announced_at(value: object, *, field: str) -> datetime | None:
    day = as_optional_date(value, field=field)
    if day is None:
        return None
    return datetime.combine(day, time.min, tzinfo=_SHANGHAI)
