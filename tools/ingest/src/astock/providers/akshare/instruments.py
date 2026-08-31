"""AKShare Instrument catalog Adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from astock_core.market_data import (
    AssetType,
    Dataset,
    Instrument,
    InstrumentId,
    InstrumentQuery,
    InvalidSourcePayload,
    from_legacy_symbol,
    validate_instrument_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error
from astock.providers.akshare._tables import lookup_column, records_from_source_table

SOURCE = "akshare"
CN_CURRENCY = "CNY"
CN_TIMEZONE = "Asia/Shanghai"
_CODE_COLUMNS = ("代码", "code")
_NAME_COLUMNS = ("名称", "name")

Spot = Callable[..., object]
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


class AkshareInstrumentAdapter:
    """Translate AKShare Eastmoney spot tables into Instruments.

    pandas objects never leave ``fetch_instruments``. Tests inject ``spot``.
    """

    def __init__(
        self,
        *,
        spot: Spot | None = None,
        timeout: float = 20.0,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._spot = spot or _default_spot
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock

    def fetch_instruments(self, query: InstrumentQuery) -> Dataset[Instrument]:
        fetched_at = self._clock()
        records = records_from_source_table(self._spot_table())
        items: list[Instrument] = []
        seen: set[InstrumentId] = set()
        for index, record in enumerate(records):
            instrument = _instrument_from_record(record, index=index)
            if instrument is None:
                continue
            if instrument.id in seen:
                raise InvalidSourcePayload(
                    f"duplicate Instrument natural key {instrument.id.value!r}"
                )
            seen.add(instrument.id)
            if not _matches_query(instrument, query):
                continue
            items.append(instrument)
        items.sort(key=lambda item: item.id.value)
        dataset = Dataset(
            items=tuple(items),
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
        )
        return validate_instrument_dataset(dataset, query)

    def _spot_table(self) -> object:
        def operation() -> object:
            try:
                return self._spot()
            except Exception as exc:
                raise translate_transport_error(exc) from exc

        return call_with_retries(operation, retries=self._retries, sleep=self._sleep)


def _instrument_from_record(record: dict[str, object], *, index: int) -> Instrument | None:
    raw_code = lookup_column(record, _CODE_COLUMNS)
    if raw_code in (None, ""):
        raise InvalidSourcePayload(f"spot row {index} is missing a code")
    digits = "".join(ch for ch in str(raw_code) if ch.isdigit())
    if len(digits) < 6:
        raise InvalidSourcePayload(f"spot row {index} has malformed code {raw_code!r}")
    symbol = digits[-6:]
    try:
        instrument_id = from_legacy_symbol(symbol)
    except ValueError as exc:
        raise InvalidSourcePayload(f"spot row {index} has unsupported code {symbol!r}") from exc
    raw_name = lookup_column(record, _NAME_COLUMNS)
    name = " ".join(str(raw_name).split()) if raw_name not in (None, "") else symbol
    if not name:
        name = symbol
    return Instrument(
        id=instrument_id,
        asset_type=AssetType.STOCK,
        name=name,
        currency=CN_CURRENCY,
        timezone=CN_TIMEZONE,
    )


def _matches_query(instrument: Instrument, query: InstrumentQuery) -> bool:
    if query.instruments and instrument.id not in query.instruments:
        return False
    if query.asset_types and instrument.asset_type not in query.asset_types:
        return False
    if query.exchanges and instrument.id.exchange not in query.exchanges:
        return False
    return True
