"""AKShare Calendar Adapter: Sina trade-date history to TradingDay records."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from astock_core.market_data import (
    CalendarQuery,
    Dataset,
    InvalidSourcePayload,
    TradingDay,
    UnsupportedQuery,
    validate_calendar_dataset,
)
from astock_core.session import MARKET_CN_A

from astock.providers._support import call_with_retries, translate_transport_error
from astock.providers.akshare._tables import as_date, lookup_column, records_from_source_table

SOURCE = "akshare"
_SUPPORTED_MARKETS = frozenset({MARKET_CN_A})
_DATE_COLUMNS = ("trade_date", "交易日", "date", "日期")

TradeDateHist = Callable[[], object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _default_trade_date_hist() -> object:
    import akshare as ak

    return ak.tool_trade_date_hist_sina()


class AkshareCalendarAdapter:
    """Wrap ``tool_trade_date_hist_sina`` behind CalendarSource."""

    def __init__(
        self,
        *,
        trade_date_hist: TradeDateHist | None = None,
        timeout: float = 20.0,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._trade_date_hist = trade_date_hist or _default_trade_date_hist
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock

    def fetch_calendar(self, query: CalendarQuery) -> Dataset[TradingDay]:
        if query.market_id not in _SUPPORTED_MARKETS:
            raise UnsupportedQuery(f"AKShare calendar does not support market {query.market_id}")
        payload = self._call_source()
        records = records_from_source_table(payload)
        days: list[TradingDay] = []
        seen: set[tuple[str, object]] = set()
        for index, record in enumerate(records):
            if not any(name in record for name in _DATE_COLUMNS):
                raise InvalidSourcePayload("AKShare calendar is missing a trade_date column")
            trade_date = as_date(lookup_column(record, _DATE_COLUMNS), field=f"trade_date[{index}]")
            if trade_date < query.start or trade_date > query.end:
                continue
            day = TradingDay(
                market_id=query.market_id,
                trade_date=trade_date,
                is_open=True,
            )
            if day.natural_key in seen:
                raise InvalidSourcePayload(f"duplicate TradingDay natural key {day.natural_key!r}")
            seen.add(day.natural_key)
            days.append(day)
        days.sort(key=lambda item: (item.trade_date, item.market_id))
        dataset = Dataset(
            items=tuple(days),
            source=SOURCE,
            fetched_at=self._clock(),
            coverage_start=query.start,
            coverage_end=query.end,
            complete=True,
        )
        return validate_calendar_dataset(dataset, query)

    def _call_source(self) -> object:
        def operation() -> object:
            try:
                return self._trade_date_hist()
            except Exception as exc:
                raise translate_transport_error(exc) from exc

        return call_with_retries(operation, retries=self._retries, sleep=self._sleep)
