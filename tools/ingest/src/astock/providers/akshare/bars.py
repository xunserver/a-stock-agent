"""AKShare Bar Adapter: Tencent, Sina, and Eastmoney-backed tables to Standard Bars."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from astock_core.market_data import (
    Adjustment,
    Bar,
    BarInterval,
    BarQuery,
    Dataset,
    InstrumentId,
    InstrumentNotFound,
    InvalidSourcePayload,
    SourceUnavailable,
    UnsupportedQuery,
    require_non_negative,
    require_positive,
    to_legacy_symbol,
    validate_bar_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error
from astock.providers.akshare._tables import (
    as_date,
    as_optional_float,
    as_required_float,
    has_any_column,
    lookup_column,
    records_from_source_table,
)
from astock.providers.eastmoney.bars import SHARES_PER_LOT, is_index_instrument

SOURCE = "akshare"

_INTERVAL_TO_PERIOD = {
    BarInterval.D1: "daily",
    BarInterval.W1: "weekly",
    BarInterval.M1: "monthly",
}
_ADJUSTMENT_TO_PARAM = {
    Adjustment.RAW: "",
    Adjustment.QFQ: "qfq",
    Adjustment.HFQ: "hfq",
}
_SINA_PREFIX = {"XSHG": "sh", "XSHE": "sz", "BSE": "bj"}

_DATE_COLUMNS = ("日期", "date")
_OPEN_COLUMNS = ("开盘", "open")
_HIGH_COLUMNS = ("最高", "high")
_LOW_COLUMNS = ("最低", "low")
_CLOSE_COLUMNS = ("收盘", "close")
_VOLUME_COLUMNS = ("成交量", "volume")
_AMOUNT_COLUMNS = ("成交额", "amount")
_TURNOVER_COLUMNS = ("换手率", "turnover")

HistTx = Callable[..., object]
Hist = Callable[..., object]
Daily = Callable[..., object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _default_hist_tx(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str,
    timeout: float | None = None,
) -> object:
    import akshare as ak

    return ak.stock_zh_a_hist_tx(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
        timeout=timeout,
    )


def _default_daily(
    symbol: str,
    adjust: str,
    start_date: str | None = None,
    end_date: str | None = None,
    timeout: float | None = None,
) -> object:
    import akshare as ak

    kwargs: dict[str, object] = {"symbol": symbol, "adjust": adjust}
    if start_date is not None:
        kwargs["start_date"] = start_date
    if end_date is not None:
        kwargs["end_date"] = end_date
    return ak.stock_zh_a_daily(**kwargs)


def _default_hist(
    symbol: str,
    period: str,
    start_date: str,
    end_date: str,
    adjust: str,
    timeout: float | None = None,
) -> object:
    import akshare as ak

    return ak.stock_zh_a_hist(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
        timeout=timeout,
    )


class AkshareBarAdapter:
    """Translate AKShare Tencent, Sina, and Eastmoney-backed tables into Standard Bars.

    Daily calls try Tencent then Sina. Weekly and monthly calls use the Eastmoney-backed
    ``stock_zh_a_hist``. All of these remain the ``akshare`` registry source. pandas objects never leave ``fetch_bars``.
    """

    def __init__(
        self,
        *,
        hist_tx: HistTx | None = None,
        daily: Daily | None = None,
        hist: Hist | None = None,
        timeout: float = 20.0,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._hist_tx = hist_tx or _default_hist_tx
        self._daily = daily or _default_daily
        self._hist = hist or _default_hist
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock

    def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
        period = _INTERVAL_TO_PERIOD.get(query.interval)
        adjust = _ADJUSTMENT_TO_PARAM.get(query.adjustment)
        if period is None or adjust is None:
            raise UnsupportedQuery(
                f"AKShare cannot serve interval={query.interval} adjustment={query.adjustment}"
            )
        bars: list[Bar] = []
        for instrument_id in query.instruments:
            if is_index_instrument(instrument_id) and query.interval is not BarInterval.D1:
                raise UnsupportedQuery(
                    f"AKShare index Bars only support daily interval, got {query.interval}"
                )
            bars.extend(self._fetch_instrument(instrument_id, query, period=period, adjust=adjust))
        bars.sort(
            key=lambda bar: (
                bar.trade_date,
                bar.instrument_id.value,
                bar.interval,
                bar.adjustment,
            )
        )
        dataset = Dataset(
            items=tuple(bars),
            source=SOURCE,
            fetched_at=self._clock(),
            coverage_start=query.start,
            coverage_end=query.end,
            complete=True,
        )
        return validate_bar_dataset(dataset, query)

    def _fetch_instrument(
        self,
        instrument_id: InstrumentId,
        query: BarQuery,
        *,
        period: str,
        adjust: str,
    ) -> tuple[Bar, ...]:
        if query.interval is BarInterval.D1:
            return self._fetch_daily(instrument_id, query, adjust=adjust)
        return self._map_table(
            self._call_source(
                lambda: self._hist(
                    to_legacy_symbol(instrument_id),
                    period,
                    query.start.strftime("%Y%m%d"),
                    query.end.strftime("%Y%m%d"),
                    adjust,
                    self._timeout,
                )
            ),
            instrument_id=instrument_id,
            query=query,
            volume_in_lots=True,
            turnover_is_percent=True,
        )

    def _fetch_daily(
        self,
        instrument_id: InstrumentId,
        query: BarQuery,
        *,
        adjust: str,
    ) -> tuple[Bar, ...]:
        symbol = to_legacy_symbol(instrument_id)
        start = query.start.strftime("%Y%m%d")
        end = query.end.strftime("%Y%m%d")
        tx_error: Exception | None = None
        try:
            payload = self._call_source(
                lambda: self._hist_tx(symbol, start, end, adjust, self._timeout)
            )
            bars = self._map_table(
                payload,
                instrument_id=instrument_id,
                query=query,
                volume_in_lots=False,
                turnover_is_percent=False,
            )
            if bars:
                return bars
        except InstrumentNotFound:
            raise
        except SourceUnavailable as exc:
            tx_error = exc
        sina_symbol = f"{_SINA_PREFIX[instrument_id.exchange]}{symbol}"
        try:
            payload = self._call_source(
                lambda: self._daily(sina_symbol, adjust, start, end, self._timeout)
            )
            return self._map_table(
                payload,
                instrument_id=instrument_id,
                query=query,
                volume_in_lots=False,
                turnover_is_percent=False,
            )
        except SourceUnavailable as exc:
            if tx_error is not None:
                raise tx_error from exc
            raise

    def _call_source(self, operation: Callable[[], object]) -> object:
        def wrapped() -> object:
            try:
                return operation()
            except Exception as exc:
                raise translate_transport_error(exc) from exc

        return call_with_retries(wrapped, retries=self._retries, sleep=self._sleep)

    def _map_table(
        self,
        payload: object,
        *,
        instrument_id: InstrumentId,
        query: BarQuery,
        volume_in_lots: bool,
        turnover_is_percent: bool,
    ) -> tuple[Bar, ...]:
        records = records_from_source_table(payload)
        if records and not has_any_column(records, _DATE_COLUMNS):
            raise InvalidSourcePayload("AKShare Bar table is missing a date column")
        bars: list[Bar] = []
        seen: set[tuple] = set()
        for index, record in enumerate(records):
            bar = _bar_from_record(
                record,
                instrument_id=instrument_id,
                query=query,
                volume_in_lots=volume_in_lots,
                turnover_is_percent=turnover_is_percent,
                index=index,
            )
            if bar is None:
                continue
            if bar.natural_key in seen:
                raise InvalidSourcePayload(f"duplicate Bar natural key {bar.natural_key!r}")
            seen.add(bar.natural_key)
            bars.append(bar)
        return tuple(bars)


def _bar_from_record(
    record: dict[str, object],
    *,
    instrument_id: InstrumentId,
    query: BarQuery,
    volume_in_lots: bool,
    turnover_is_percent: bool,
    index: int,
) -> Bar | None:
    trade_date = as_date(lookup_column(record, _DATE_COLUMNS), field=f"trade_date[{index}]")
    if trade_date < query.start or trade_date > query.end:
        return None
    open_ = require_positive(
        as_required_float(lookup_column(record, _OPEN_COLUMNS), field=f"open[{index}]"),
        field=f"open[{index}]",
    )
    high = require_positive(
        as_required_float(lookup_column(record, _HIGH_COLUMNS), field=f"high[{index}]"),
        field=f"high[{index}]",
    )
    low = require_positive(
        as_required_float(lookup_column(record, _LOW_COLUMNS), field=f"low[{index}]"),
        field=f"low[{index}]",
    )
    close = require_positive(
        as_required_float(lookup_column(record, _CLOSE_COLUMNS), field=f"close[{index}]"),
        field=f"close[{index}]",
    )
    volume = require_non_negative(
        as_required_float(lookup_column(record, _VOLUME_COLUMNS), field=f"volume[{index}]"),
        field=f"volume[{index}]",
    )
    amount = require_non_negative(
        as_required_float(lookup_column(record, _AMOUNT_COLUMNS), field=f"amount[{index}]"),
        field=f"amount[{index}]",
    )
    if volume_in_lots:
        volume *= SHARES_PER_LOT
    turnover_raw = as_optional_float(
        lookup_column(record, _TURNOVER_COLUMNS), field=f"turnover_pct[{index}]"
    )
    turnover_pct = None
    if turnover_raw is not None:
        turnover_pct = turnover_raw if turnover_is_percent else turnover_raw * 100.0
        turnover_pct = require_non_negative(turnover_pct, field=f"turnover_pct[{index}]")
    return Bar(
        instrument_id=instrument_id,
        trade_date=trade_date,
        interval=query.interval,
        adjustment=query.adjustment,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
        turnover_pct=turnover_pct,
    )
