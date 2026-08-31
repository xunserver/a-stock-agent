"""AKShare Instrument Profile, Quote Snapshot, and Valuation Snapshot Adapter."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from astock_core.market_data import (
    Dataset,
    InstrumentId,
    InstrumentProfile,
    InstrumentQuery,
    InvalidSourcePayload,
    QuoteSnapshot,
    SnapshotQuery,
    ValuationQuery,
    ValuationSnapshot,
    from_legacy_symbol,
    require_optional_finite,
    to_legacy_symbol,
    validate_instrument_profile_dataset,
    validate_quote_snapshot_dataset,
    validate_valuation_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error
from astock.providers.akshare._tables import lookup_column, records_from_source_table
from astock.providers.eastmoney.snapshots import CN_CURRENCY, CN_TIMEZONE

SOURCE = "akshare"
_SHANGHAI = ZoneInfo(CN_TIMEZONE)
_CODE_COLUMNS = ("代码", "股票代码", "code")
_NAME_COLUMNS = ("名称", "股票简称", "name")
_ST_CODE_COLUMNS = ("代码", "code")

Spot = Callable[..., object]
ItemTable = Callable[..., object]
ValueTable = Callable[..., object]
StTable = Callable[..., object]
TfpTable = Callable[..., object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _default_spot() -> object:
    import akshare as ak

    return ak.stock_zh_a_spot_em()


def _default_bid_ask(symbol: str) -> object:
    import akshare as ak

    return ak.stock_bid_ask_em(symbol=symbol)


def _default_individual(symbol: str) -> object:
    import akshare as ak

    return ak.stock_individual_info_em(symbol=symbol)


def _default_value(symbol: str) -> object:
    import akshare as ak

    return ak.stock_value_em(symbol=symbol)


def _default_st() -> object:
    import akshare as ak

    return ak.stock_zh_a_st_em()


def _default_tfp(trade_date: str) -> object:
    import akshare as ak

    return ak.stock_tfp_em(date=trade_date)


class AkshareSnapshotAdapter:
    """Translate AKShare spot, bid-ask, info, value, ST, and TFP tables.

    Source payload merging stays inside this Adapter. pandas objects never
    leave the capability methods. Tests inject callables.
    """

    def __init__(
        self,
        *,
        spot: Spot | None = None,
        bid_ask: ItemTable | None = None,
        individual: ItemTable | None = None,
        value: ValueTable | None = None,
        st_list: StTable | None = None,
        tfp: TfpTable | None = None,
        timeout: float = 20.0,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
        pause: float = 0.0,
    ) -> None:
        self._spot = spot or _default_spot
        self._bid_ask = bid_ask or _default_bid_ask
        self._individual = individual or _default_individual
        self._value = value or _default_value
        self._st_list = st_list or _default_st
        self._tfp = tfp or _default_tfp
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock
        self._pause = pause
        self._spot_by_code: dict[str, dict[str, object]] | None = None
        self._st_codes: set[str] | None = None
        self._suspend_map: dict[str, str] | None = None

    def st_codes(self) -> set[str]:
        return self._load_st_codes()

    def suspend_reasons(self, as_of) -> dict[str, str]:
        return self._load_suspend_map(as_of)

    def fetch_profiles(self, query: InstrumentQuery) -> Dataset[InstrumentProfile]:
        fetched_at = self._clock()
        st_codes = self._load_st_codes()
        items: list[InstrumentProfile] = []
        for instrument_id in _requested_ids(query):
            code = to_legacy_symbol(instrument_id)
            info = self._item_map(self._call(lambda: self._individual(code)))
            spot = self._spot_row(code)
            if not info and not spot and code not in st_codes:
                continue
            name = (
                _text(info.get("股票简称"))
                or _text(spot.get("名称"))
                or code
            )
            list_date = _list_date(info.get("上市时间"))
            industry = _text(info.get("行业")) or _text(spot.get("所处行业"))
            items.append(
                InstrumentProfile(
                    instrument_id=instrument_id,
                    name=name,
                    industry=industry,
                    region=None,
                    list_date=list_date,
                    is_st=code in st_codes or "ST" in name.upper(),
                )
            )
            self._maybe_pause()
        items.sort(key=lambda item: item.instrument_id.value)
        dataset = Dataset(
            items=tuple(items),
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
        )
        return validate_instrument_profile_dataset(dataset, query)

    def fetch_snapshots(self, query: SnapshotQuery) -> Dataset[QuoteSnapshot]:
        fetched_at = self._clock()
        suspend_map = self._load_suspend_map(fetched_at.astimezone(_SHANGHAI).date())
        items: list[QuoteSnapshot] = []
        for instrument_id in query.instruments:
            code = to_legacy_symbol(instrument_id)
            bid = self._item_map(self._call(lambda symbol=code: self._bid_ask(symbol)))
            spot = self._spot_row(code)
            if not bid and not spot and code not in suspend_map:
                continue
            reason = suspend_map.get(code)
            items.append(
                QuoteSnapshot(
                    instrument_id=instrument_id,
                    observed_at=fetched_at,
                    last_price=_number(bid.get("最新"), spot.get("最新价"), field="last_price"),
                    pre_close=_number(bid.get("昨收"), spot.get("昨收"), field="pre_close"),
                    average_price=_number(bid.get("均价"), None, field="average_price"),
                    high_limit=_number(bid.get("涨停"), None, field="high_limit"),
                    low_limit=_number(bid.get("跌停"), None, field="low_limit"),
                    volume_ratio=_number(bid.get("量比"), spot.get("量比"), field="volume_ratio"),
                    outer_volume=_number(bid.get("外盘"), None, field="outer_volume"),
                    inner_volume=_number(bid.get("内盘"), None, field="inner_volume"),
                    is_suspended=reason is not None,
                    suspend_reason=reason,
                )
            )
            self._maybe_pause()
        items.sort(key=lambda item: (item.instrument_id.value, item.observed_at))
        dataset = Dataset(
            items=tuple(items),
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
            warnings=("observed_at fell back to fetch time",) if items else (),
        )
        return validate_quote_snapshot_dataset(dataset, query)

    def fetch_valuations(self, query: ValuationQuery) -> Dataset[ValuationSnapshot]:
        fetched_at = self._clock()
        as_of = query.as_of or fetched_at.astimezone(_SHANGHAI).date()
        items: list[ValuationSnapshot] = []
        for instrument_id in query.instruments:
            code = to_legacy_symbol(instrument_id)
            value = self._last_record(self._call(lambda symbol=code: self._value(symbol)))
            info = self._item_map(self._call(lambda symbol=code: self._individual(symbol)))
            spot = self._spot_row(code)
            if not value and not info and not spot:
                continue
            items.append(
                ValuationSnapshot(
                    instrument_id=instrument_id,
                    as_of=as_of,
                    currency=CN_CURRENCY,
                    total_shares=_number(
                        value.get("总股本"), info.get("总股本"), field="total_shares"
                    ),
                    float_shares=_number(
                        value.get("流通股本"), info.get("流通股"), field="float_shares"
                    ),
                    total_market_cap=_number(
                        value.get("总市值"),
                        info.get("总市值"),
                        spot.get("总市值"),
                        field="total_market_cap",
                    ),
                    float_market_cap=_number(
                        value.get("流通市值"),
                        info.get("流通市值"),
                        spot.get("流通市值"),
                        field="float_market_cap",
                    ),
                    pe_ttm=_number(
                        value.get("PE(TTM)"), spot.get("市盈率-动态"), field="pe_ttm"
                    ),
                    pe_static=_number(value.get("PE(静)"), None, field="pe_static"),
                    pb=_number(value.get("市净率"), spot.get("市净率"), field="pb"),
                )
            )
            self._maybe_pause()
        items.sort(key=lambda item: (item.instrument_id.value, item.as_of))
        dataset = Dataset(
            items=tuple(items),
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
        )
        return validate_valuation_dataset(dataset, query)

    def _call(self, operation: Callable[[], object]) -> object:
        def wrapped() -> object:
            try:
                return operation()
            except Exception as exc:
                raise translate_transport_error(exc) from exc

        return call_with_retries(wrapped, retries=self._retries, sleep=self._sleep)

    def _maybe_pause(self) -> None:
        if self._pause:
            self._sleep(self._pause)

    def _spot_rows(self) -> dict[str, dict[str, object]]:
        if self._spot_by_code is None:
            records = records_from_source_table(self._call(self._spot))
            by_code: dict[str, dict[str, object]] = {}
            for record in records:
                code = _code_from(record)
                if code:
                    by_code[code] = record
            self._spot_by_code = by_code
        return self._spot_by_code

    def _spot_row(self, code: str) -> dict[str, object]:
        return self._spot_rows().get(code) or {}

    def _load_st_codes(self) -> set[str]:
        if self._st_codes is None:
            records = records_from_source_table(self._call(self._st_list))
            codes: set[str] = set()
            for record in records:
                code = _code_from(record, columns=_ST_CODE_COLUMNS)
                if code:
                    codes.add(code)
            self._st_codes = codes
        return self._st_codes

    def _load_suspend_map(self, as_of: date) -> dict[str, str]:
        if self._suspend_map is None:
            records = records_from_source_table(
                self._call(lambda: self._tfp(as_of.strftime("%Y%m%d")))
            )
            mapping: dict[str, str] = {}
            for record in records:
                code = _code_from(record)
                if not code:
                    continue
                reason = _text(record.get("停牌原因") or record.get("reason")) or ""
                until = _text(record.get("预计复牌时间") or record.get("unpause_date"))
                note = reason
                if until:
                    note = f"{note} 预计复牌 {until}".strip()
                mapping[code] = note
            self._suspend_map = mapping
        return self._suspend_map

    def _item_map(self, payload: object) -> dict[str, object]:
        records = records_from_source_table(payload)
        if not records:
            return {}
        sample = records[0]
        if "item" in sample:
            value_key = "value" if "value" in sample else next(
                (key for key in sample if key != "item"), "value"
            )
            return {str(row.get("item")): row.get(value_key) for row in records}
        return sample

    def _last_record(self, payload: object) -> dict[str, object]:
        records = records_from_source_table(payload)
        return records[-1] if records else {}


def _requested_ids(query: InstrumentQuery) -> tuple[InstrumentId, ...]:
    if query.instruments:
        return query.instruments
    return ()


def _code_from(
    record: dict[str, object], columns: tuple[str, ...] = _CODE_COLUMNS
) -> str | None:
    raw = lookup_column(record, columns)
    if raw in (None, ""):
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(digits) < 6:
        return None
    try:
        return to_legacy_symbol(from_legacy_symbol(digits[-6:]))
    except ValueError:
        return None


def _text(value: object) -> str | None:
    if value in (None, "", "-", "None"):
        return None
    text = " ".join(str(value).split())
    return text or None


def _list_date(value: object) -> date | None:
    text = _text(value)
    if text is None:
        return None
    if len(text) >= 10 and text[4] == "-":
        return date.fromisoformat(text[:10])
    digits = "".join(ch for ch in text.split(".")[0] if ch.isdigit())
    if len(digits) == 8:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    return None


def _number(*values: object, field: str) -> float | None:
    for value in values:
        if value in (None, "", "-", "None"):
            continue
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise InvalidSourcePayload(f"{field} is not numeric: {value!r}") from exc
        if isinstance(value, bool) or not math.isfinite(number):
            raise InvalidSourcePayload(f"{field} must be a finite number, got {value!r}")
        return require_optional_finite(number, field=field)
    return None
