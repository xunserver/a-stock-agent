"""Eastmoney Instrument Profile, Quote Snapshot, and Valuation Snapshot Adapter."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from astock_core.market_data import (
    Dataset,
    InstrumentId,
    InstrumentNotFound,
    InstrumentProfile,
    InstrumentQuery,
    InvalidSourcePayload,
    QuoteSnapshot,
    SnapshotQuery,
    UnsupportedQuery,
    ValuationQuery,
    ValuationSnapshot,
    require_optional_finite,
    validate_instrument_profile_dataset,
    validate_quote_snapshot_dataset,
    validate_valuation_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error

SOURCE = "eastmoney"
QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
CN_CURRENCY = "CNY"
CN_TIMEZONE = "Asia/Shanghai"
_SHANGHAI = ZoneInfo(CN_TIMEZONE)

# Quote / profile / valuation fields only. Fundamental field numbers stay out.
_FIELDS = (
    "f43",
    "f49",
    "f50",
    "f51",
    "f52",
    "f57",
    "f58",
    "f60",
    "f71",
    "f84",
    "f85",
    "f86",
    "f116",
    "f117",
    "f127",
    "f128",
    "f161",
    "f162",
    "f163",
    "f167",
    "f189",
)
_EXCHANGE_TO_MARKET = {
    "XSHG": "1",
    "XSHE": "0",
    "BSE": "0",
}

GetJson = Callable[[str, dict[str, str], float], object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]
Pause = Callable[[], None]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _default_get_json(url: str, params: dict[str, str], timeout: float) -> object:
    from astock.eastmoney import _get

    return _get(url, params, timeout=timeout).json()


class EastmoneySnapshotAdapter:
    """Translate Eastmoney ``qt/stock/get`` payloads into three Standard Records.

    One HTTP payload can feed Instrument Profile, Quote Snapshot, and Valuation
    Snapshot methods. Payload mapping stays inside this Adapter. Tests inject
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
        pause: float = 0.0,
    ) -> None:
        self._get_json = get_json or _default_get_json
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock
        self._pause = pause
        self._payloads: dict[InstrumentId, dict[str, object]] = {}

    def fetch_profiles(self, query: InstrumentQuery) -> Dataset[InstrumentProfile]:
        if not query.instruments:
            raise UnsupportedQuery("Eastmoney profile queries require instruments")
        fetched_at = self._clock()
        items, warnings = self._collect(query.instruments)
        profiles = tuple(
            sorted(
                (self._profile_from_payload(instrument_id, payload) for instrument_id, payload in items),
                key=lambda item: item.instrument_id.value,
            )
        )
        dataset = Dataset(
            items=profiles,
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
            warnings=tuple(warnings),
        )
        return validate_instrument_profile_dataset(dataset, query)

    def fetch_snapshots(self, query: SnapshotQuery) -> Dataset[QuoteSnapshot]:
        fetched_at = self._clock()
        items, warnings = self._collect(query.instruments)
        snapshots: list[QuoteSnapshot] = []
        for instrument_id, payload in items:
            snapshot, warning = self._snapshot_from_payload(
                instrument_id, payload, fetched_at=fetched_at
            )
            snapshots.append(snapshot)
            if warning:
                warnings.append(warning)
        snapshots.sort(key=lambda item: (item.instrument_id.value, item.observed_at))
        dataset = Dataset(
            items=tuple(snapshots),
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
            warnings=tuple(dict.fromkeys(warnings)),
        )
        return validate_quote_snapshot_dataset(dataset, query)

    def fetch_valuations(self, query: ValuationQuery) -> Dataset[ValuationSnapshot]:
        fetched_at = self._clock()
        items, warnings = self._collect(query.instruments)
        as_of = query.as_of or fetched_at.astimezone(_SHANGHAI).date()
        snapshots = tuple(
            sorted(
                (
                    self._valuation_from_payload(instrument_id, payload, as_of=as_of)
                    for instrument_id, payload in items
                ),
                key=lambda item: (item.instrument_id.value, item.as_of),
            )
        )
        dataset = Dataset(
            items=snapshots,
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
            warnings=tuple(warnings),
        )
        return validate_valuation_dataset(dataset, query)

    def _collect(
        self,
        instruments: tuple[InstrumentId, ...],
    ) -> tuple[list[tuple[InstrumentId, dict[str, object]]], list[str]]:
        items: list[tuple[InstrumentId, dict[str, object]]] = []
        warnings: list[str] = []
        for instrument_id in instruments:
            payload = self._payload(instrument_id)
            if payload is None:
                continue
            items.append((instrument_id, payload))
        return items, warnings

    def _payload(self, instrument_id: InstrumentId) -> dict[str, object] | None:
        cached = self._payloads.get(instrument_id)
        if cached is not None:
            return cached
        raw = self._fetch(instrument_id)
        data = _payload_data(raw, instrument_id=instrument_id)
        if data is None:
            return None
        self._payloads[instrument_id] = data
        if self._pause:
            self._sleep(self._pause)
        return data

    def _fetch(self, instrument_id: InstrumentId) -> object:
        market = _EXCHANGE_TO_MARKET.get(instrument_id.exchange)
        if market is None:
            raise InvalidSourcePayload(f"unsupported exchange {instrument_id.exchange}")
        params = {
            "fltt": "2",
            "invt": "2",
            "fields": ",".join(_FIELDS),
            "secid": f"{market}.{instrument_id.symbol}",
        }

        def operation() -> object:
            try:
                return self._get_json(QUOTE_URL, params, self._timeout)
            except Exception as exc:
                raise translate_transport_error(exc) from exc

        return call_with_retries(operation, retries=self._retries, sleep=self._sleep)

    def _profile_from_payload(
        self, instrument_id: InstrumentId, payload: dict[str, object]
    ) -> InstrumentProfile:
        name = _required_name(payload.get("f58"), instrument_id)
        return InstrumentProfile(
            instrument_id=instrument_id,
            name=name,
            industry=_optional_text(payload.get("f127")),
            region=_optional_text(payload.get("f128")),
            list_date=_optional_list_date(payload.get("f189")),
            is_st=_name_is_st(name),
        )

    def _snapshot_from_payload(
        self,
        instrument_id: InstrumentId,
        payload: dict[str, object],
        *,
        fetched_at: datetime,
    ) -> tuple[QuoteSnapshot, str | None]:
        observed_at, warning = _observed_at(payload.get("f86"), fetched_at=fetched_at)
        snapshot = QuoteSnapshot(
            instrument_id=instrument_id,
            observed_at=observed_at,
            last_price=_optional_number(payload.get("f43"), field="last_price"),
            pre_close=_optional_number(payload.get("f60"), field="pre_close"),
            average_price=_optional_number(payload.get("f71"), field="average_price"),
            high_limit=_optional_number(payload.get("f51"), field="high_limit"),
            low_limit=_optional_number(payload.get("f52"), field="low_limit"),
            volume_ratio=_optional_number(payload.get("f50"), field="volume_ratio"),
            outer_volume=_optional_number(payload.get("f49"), field="outer_volume"),
            inner_volume=_optional_number(payload.get("f161"), field="inner_volume"),
            is_suspended=False,
            suspend_reason=None,
        )
        return snapshot, warning

    def _valuation_from_payload(
        self,
        instrument_id: InstrumentId,
        payload: dict[str, object],
        *,
        as_of: date,
    ) -> ValuationSnapshot:
        return ValuationSnapshot(
            instrument_id=instrument_id,
            as_of=as_of,
            currency=CN_CURRENCY,
            total_shares=_optional_number(payload.get("f84"), field="total_shares"),
            float_shares=_optional_number(payload.get("f85"), field="float_shares"),
            total_market_cap=_optional_number(payload.get("f116"), field="total_market_cap"),
            float_market_cap=_optional_number(payload.get("f117"), field="float_market_cap"),
            pe_ttm=_optional_number(payload.get("f162"), field="pe_ttm"),
            pe_static=_optional_number(payload.get("f163"), field="pe_static"),
            pb=_optional_number(payload.get("f167"), field="pb"),
        )


def _payload_data(payload: object, *, instrument_id: InstrumentId) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        raise InvalidSourcePayload(
            f"Eastmoney payload must be a JSON object, got {type(payload).__name__}"
        )
    data = payload.get("data")
    if data is None:
        raise InstrumentNotFound(instrument_id.value)
    if not isinstance(data, dict):
        raise InvalidSourcePayload("Eastmoney data must be a JSON object")
    if not data:
        return None
    return data


def _required_name(value: object, instrument_id: InstrumentId) -> str:
    text = _optional_text(value)
    if text is None:
        return instrument_id.symbol
    return text


def _name_is_st(name: str) -> bool:
    return "ST" in name.upper()


def _optional_text(value: object) -> str | None:
    if value in (None, "", "-", "None"):
        return None
    text = " ".join(str(value).split())
    return text or None


def _optional_list_date(value: object) -> date | None:
    if value in (None, "", "-", "None"):
        return None
    digits = str(value).split(".")[0]
    if digits.isdigit() and len(digits) == 8:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-":
        return date.fromisoformat(text[:10])
    return None


def _optional_number(value: object, *, field: str) -> float | None:
    if value in (None, "", "-", "None"):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise InvalidSourcePayload(f"{field} is not numeric: {value!r}") from exc
    if isinstance(value, bool) or not math.isfinite(number):
        raise InvalidSourcePayload(f"{field} must be a finite number, got {value!r}")
    return require_optional_finite(number, field=field)


def _observed_at(value: object, *, fetched_at: datetime) -> tuple[datetime, str | None]:
    if value in (None, "", "-", "None", 0, "0"):
        return fetched_at, "observed_at fell back to fetch time"
    try:
        raw = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fetched_at, "observed_at fell back to fetch time"
    if not math.isfinite(raw) or raw <= 0:
        return fetched_at, "observed_at fell back to fetch time"
    seconds = raw / 1000 if raw > 1_000_000_000_000 else raw
    observed = datetime.fromtimestamp(seconds, tz=_SHANGHAI)
    return observed, None
