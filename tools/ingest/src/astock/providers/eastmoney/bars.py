"""Eastmoney Bar Adapter: kline payloads to Standard Bars."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, datetime, timezone

from astock_core.market_data import (
    Adjustment,
    Bar,
    BarInterval,
    BarQuery,
    Dataset,
    InstrumentId,
    InstrumentNotFound,
    InvalidSourcePayload,
    UnsupportedQuery,
    require_finite,
    require_non_negative,
    require_positive,
    validate_bar_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error

SOURCE = "eastmoney"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

# Eastmoney stock and index 成交量 is reported in 手 (lots). One A-share lot is 100 shares.
SHARES_PER_LOT = 100

_INTERVAL_TO_KLT = {
    BarInterval.D1: "101",
    BarInterval.W1: "102",
    BarInterval.M1: "103",
}
_ADJUSTMENT_TO_FQT = {
    Adjustment.RAW: "0",
    Adjustment.QFQ: "1",
    Adjustment.HFQ: "2",
}
_EXCHANGE_TO_MARKET = {
    "XSHG": "1",
    "XSHE": "0",
    "BSE": "0",
}

GetJson = Callable[[str, dict[str, str], float], object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _default_get_json(url: str, params: dict[str, str], timeout: float) -> object:
    from astock.providers.eastmoney._transport import get_response

    return get_response(url, params, timeout=timeout).json()


def is_index_instrument(instrument_id: InstrumentId) -> bool:
    """Classify A-share indexes from exchange-qualified identity.

    Shanghai indexes use ``000``/``880`` prefixes; Shenzhen indexes use ``399``;
    Beijing indexes use ``899``. Six-digit stocks such as ``CN.XSHE.000001`` stay stocks.
    """
    symbol = instrument_id.symbol
    if instrument_id.exchange == "XSHG" and symbol.startswith(("000", "880")):
        return True
    if instrument_id.exchange == "XSHE" and symbol.startswith("399"):
        return True
    if instrument_id.exchange == "BSE" and symbol.startswith("899"):
        return True
    return False


class EastmoneyBarAdapter:
    """Translate Eastmoney kline payloads into Standard Bars.

    Transport retries and timeouts are constructor-injected. Tests replace
    ``get_json`` so the default suite never opens a network connection.
    """

    def __init__(
        self,
        *,
        get_json: GetJson | None = None,
        timeout: float = 20.0,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._get_json = get_json or _default_get_json
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock

    def fetch_bars(self, query: BarQuery) -> Dataset[Bar]:
        klt = _INTERVAL_TO_KLT.get(query.interval)
        fqt = _ADJUSTMENT_TO_FQT.get(query.adjustment)
        if klt is None or fqt is None:
            raise UnsupportedQuery(
                f"Eastmoney cannot serve interval={query.interval} adjustment={query.adjustment}"
            )
        bars: list[Bar] = []
        for instrument_id in query.instruments:
            bars.extend(self._fetch_instrument(instrument_id, query, klt=klt, fqt=fqt))
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
        klt: str,
        fqt: str,
    ) -> tuple[Bar, ...]:
        market = _EXCHANGE_TO_MARKET.get(instrument_id.exchange)
        if market is None:
            raise UnsupportedQuery(f"unsupported exchange {instrument_id.exchange}")
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "klt": klt,
            "fqt": fqt,
            "secid": f"{market}.{instrument_id.symbol}",
            "beg": query.start.strftime("%Y%m%d"),
            "end": query.end.strftime("%Y%m%d"),
        }
        payload = self._get_payload(KLINE_URL, params)
        return _bars_from_payload(
            payload,
            instrument_id=instrument_id,
            query=query,
            min_fields=7 if is_index_instrument(instrument_id) else 11,
        )

    def _get_payload(self, url: str, params: dict[str, str]) -> object:
        def operation() -> object:
            try:
                return self._get_json(url, params, self._timeout)
            except Exception as exc:
                raise translate_transport_error(exc) from exc

        return call_with_retries(operation, retries=self._retries, sleep=self._sleep)


def _bars_from_payload(
    payload: object,
    *,
    instrument_id: InstrumentId,
    query: BarQuery,
    min_fields: int,
) -> tuple[Bar, ...]:
    data = _kline_data(payload, instrument_id=instrument_id)
    klines = data.get("klines") or []
    if not isinstance(klines, list):
        raise InvalidSourcePayload("Eastmoney klines must be a list")
    bars: list[Bar] = []
    seen: set[tuple] = set()
    for index, item in enumerate(klines):
        bar = _bar_from_kline(
            item,
            instrument_id=instrument_id,
            query=query,
            min_fields=min_fields,
            index=index,
        )
        if bar is None:
            continue
        if bar.natural_key in seen:
            raise InvalidSourcePayload(f"duplicate Bar natural key {bar.natural_key!r}")
        seen.add(bar.natural_key)
        bars.append(bar)
    return tuple(bars)


def _kline_data(payload: object, *, instrument_id: InstrumentId) -> dict:
    if not isinstance(payload, dict):
        raise InvalidSourcePayload(
            f"Eastmoney payload must be a JSON object, got {type(payload).__name__}"
        )
    data = payload.get("data")
    if data is None:
        raise InstrumentNotFound(instrument_id.value)
    if not isinstance(data, dict):
        raise InvalidSourcePayload("Eastmoney data must be a JSON object")
    return data


def _bar_from_kline(
    item: object,
    *,
    instrument_id: InstrumentId,
    query: BarQuery,
    min_fields: int,
    index: int,
) -> Bar | None:
    if not isinstance(item, str) or not item:
        raise InvalidSourcePayload(f"kline at index {index} must be a non-empty string")
    parts = item.split(",")
    if len(parts) < min_fields:
        raise InvalidSourcePayload(
            f"kline at index {index} has {len(parts)} fields, expected at least {min_fields}"
        )
    trade_date = _parse_trade_date(parts[0], index=index)
    if trade_date < query.start or trade_date > query.end:
        return None
    open_ = _required_price(parts[1], field="open", index=index)
    close = _required_price(parts[2], field="close", index=index)
    high = _required_price(parts[3], field="high", index=index)
    low = _required_price(parts[4], field="low", index=index)
    volume_lots = _required_non_negative(parts[5], field="volume", index=index)
    amount = _required_non_negative(parts[6], field="amount", index=index)
    turnover_pct = None
    if min_fields >= 11:
        turnover_pct = _optional_non_negative(parts[10], field="turnover_pct", index=index)
    return Bar(
        instrument_id=instrument_id,
        trade_date=trade_date,
        interval=query.interval,
        adjustment=query.adjustment,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume_lots * SHARES_PER_LOT,
        amount=amount,
        turnover_pct=turnover_pct,
    )


def _parse_trade_date(value: object, *, index: int) -> date:
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise InvalidSourcePayload(f"malformed trade_date at index {index}: {value!r}") from exc


def _required_price(value: object, *, field: str, index: int) -> float:
    return require_positive(_as_finite(value, field=field, index=index), field=f"{field}[{index}]")


def _required_non_negative(value: object, *, field: str, index: int) -> float:
    return require_non_negative(_as_finite(value, field=field, index=index), field=f"{field}[{index}]")


def _optional_non_negative(value: object, *, field: str, index: int) -> float | None:
    if value in (None, ""):
        return None
    number = require_non_negative(_as_finite(value, field=field, index=index), field=f"{field}[{index}]")
    return number


def _as_finite(value: object, *, field: str, index: int) -> float:
    if value in (None, ""):
        raise InvalidSourcePayload(f"{field}[{index}] is missing")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidSourcePayload(f"{field}[{index}] is not numeric: {value!r}") from exc
    if isinstance(value, bool) or not math.isfinite(number):
        raise InvalidSourcePayload(f"{field}[{index}] must be a finite number, got {value!r}")
    return require_finite(number, field=f"{field}[{index}]")
