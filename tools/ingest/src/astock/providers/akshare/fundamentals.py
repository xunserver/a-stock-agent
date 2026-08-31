"""AKShare Fundamental Period Adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from astock_core.market_data import (
    Dataset,
    FinancialPeriodType,
    FundamentalPeriod,
    FundamentalQuery,
    InstrumentId,
    InvalidSourcePayload,
    MarketDataError,
    period_type_from_end,
    to_legacy_symbol,
    validate_fundamental_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error
from astock.providers.akshare._tables import (
    as_optional_date,
    as_optional_float,
    lookup_column,
    records_from_source_table,
)
from astock.providers.eastmoney.snapshots import CN_CURRENCY, CN_TIMEZONE

SOURCE = "akshare"
_SHANGHAI = ZoneInfo(CN_TIMEZONE)
BATCH_MIN_INSTRUMENTS = 8
SUMMARY_REPORT_PERIODS = 12
_CODE_COLUMNS = ("股票代码", "代码", "SECURITY_CODE")

Indicator = Callable[..., object]
BatchTable = Callable[..., object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]
Today = Callable[[], date]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time as time_mod

    time_mod.sleep(seconds)


def _default_today() -> date:
    return datetime.now(_SHANGHAI).date()


def _default_indicator(symbol: str, indicator: str) -> object:
    import akshare as ak

    return ak.stock_financial_analysis_indicator_em(symbol=symbol, indicator=indicator)


def _default_yjbb(date: str) -> object:
    import akshare as ak

    return ak.stock_yjbb_em(date=date)


def _default_zcfz(date: str) -> object:
    import akshare as ak

    return ak.stock_zcfz_em(date=date)


def _default_lrb(date: str) -> object:
    import akshare as ak

    return ak.stock_lrb_em(date=date)


def indicator_symbol(instrument_id: InstrumentId) -> str:
    code = to_legacy_symbol(instrument_id)
    suffix = {"XSHG": "SH", "BSE": "BJ"}.get(instrument_id.exchange, "SZ")
    return f"{code}.{suffix}"


def summary_period_ends(today: date, *, periods: int) -> list[date]:
    quarters: list[date] = []
    for year in range(today.year, today.year - 25, -1):
        quarters.extend(
            [date(year, 3, 31), date(year, 6, 30), date(year, 9, 30), date(year, 12, 31)]
        )
    passed = sorted((item for item in quarters if item <= today), reverse=True)
    return passed[:periods]


class AkshareFundamentalAdapter:
    """Translate AKShare yjbb/zcfz/lrb and indicator payloads into Fundamental Periods."""

    def __init__(
        self,
        *,
        indicator: Indicator | None = None,
        yjbb: BatchTable | None = None,
        zcfz: BatchTable | None = None,
        lrb: BatchTable | None = None,
        batch_min_instruments: int = BATCH_MIN_INSTRUMENTS,
        periods: int = SUMMARY_REPORT_PERIODS,
        timeout: float = 20.0,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
        today: Today | None = None,
    ) -> None:
        self._indicator = indicator or _default_indicator
        self._yjbb = yjbb or _default_yjbb
        self._zcfz = zcfz or _default_zcfz
        self._lrb = lrb or _default_lrb
        self._batch_min_instruments = batch_min_instruments
        self._periods = periods
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock
        self._today = today or _default_today

    def fetch_fundamentals(self, query: FundamentalQuery) -> Dataset[FundamentalPeriod]:
        if len(query.instruments) >= self._batch_min_instruments:
            periods, warnings = self._fetch_batch(query)
        else:
            periods, warnings = self._fetch_each(query)
        periods = _filter_query(periods, query)
        periods.sort(key=lambda item: (item.instrument_id.value, item.period_end, item.period_type.value))
        coverage = _coverage(query)
        dataset = Dataset(
            items=tuple(periods),
            source=SOURCE,
            fetched_at=self._clock(),
            coverage_start=coverage[0],
            coverage_end=coverage[1],
            complete=True,
            warnings=tuple(warnings),
        )
        return validate_fundamental_dataset(dataset, query)

    def _fetch_each(
        self, query: FundamentalQuery
    ) -> tuple[list[FundamentalPeriod], list[str]]:
        periods: list[FundamentalPeriod] = []
        warnings: list[str] = []
        for instrument_id in query.instruments:
            rows = records_from_source_table(
                self._call(lambda symbol=indicator_symbol(instrument_id): self._indicator(symbol, "按报告期"))
            )
            resolved: dict[tuple, FundamentalPeriod] = {}
            for index, row in enumerate(rows):
                period = _period_from_indicator(instrument_id, row, index=index)
                if period is None:
                    continue
                _store_resolved(resolved, period, warnings)
            periods.extend(resolved.values())
        return periods, warnings

    def _fetch_batch(
        self, query: FundamentalQuery
    ) -> tuple[list[FundamentalPeriod], list[str]]:
        wanted = {to_legacy_symbol(item): item for item in query.instruments}
        today = self._today()
        ends = summary_period_ends(today, periods=self._periods)
        if query.start is not None:
            ends = [item for item in ends if item >= query.start]
        if query.end is not None:
            ends = [item for item in ends if item <= query.end]
        resolved: dict[tuple, FundamentalPeriod] = {}
        warnings: list[str] = []
        for period_end in ends:
            stamp = period_end.strftime("%Y%m%d")
            yjbb = _rows_by_code(self._records(lambda date=stamp: self._yjbb(date)))
            zcfz = _rows_by_code(self._records(lambda date=stamp: self._zcfz(date)))
            lrb = _rows_by_code(self._records(lambda date=stamp: self._lrb(date)))
            for code, instrument_id in wanted.items():
                period = _period_from_batch(
                    instrument_id,
                    period_end,
                    yjbb.get(code),
                    zcfz.get(code),
                    lrb.get(code),
                )
                if period is None:
                    continue
                _store_resolved(resolved, period, warnings)
        return list(resolved.values()), warnings

    def _call(self, operation: Callable[[], object]) -> object:
        def wrapped() -> object:
            try:
                return operation()
            except Exception as exc:
                raise translate_transport_error(exc) from exc

        return call_with_retries(wrapped, retries=self._retries, sleep=self._sleep)

    def _records(self, operation: Callable[[], object]) -> list[dict[str, object]]:
        try:
            return records_from_source_table(self._call(operation))
        except MarketDataError:
            return []


def _coverage(query: FundamentalQuery) -> tuple[date | None, date | None]:
    return (query.start, query.end)


def _filter_query(
    periods: list[FundamentalPeriod], query: FundamentalQuery
) -> list[FundamentalPeriod]:
    wanted_types = frozenset(query.period_types)
    out: list[FundamentalPeriod] = []
    for period in periods:
        if wanted_types and period.period_type not in wanted_types:
            continue
        if query.start is not None and period.period_end < query.start:
            continue
        if query.end is not None and period.period_end > query.end:
            continue
        out.append(period)
    return out


def _store_resolved(
    resolved: dict[tuple, FundamentalPeriod],
    period: FundamentalPeriod,
    warnings: list[str],
) -> None:
    key = period.natural_key
    existing = resolved.get(key)
    if existing is None:
        resolved[key] = period
        return
    winner = _prefer_restated(existing, period)
    if winner is not existing:
        warnings.append(
            f"restated Fundamental Period {period.instrument_id.value} "
            f"{period.period_end.isoformat()} kept later announcement"
        )
    resolved[key] = winner


def _prefer_restated(first: FundamentalPeriod, second: FundamentalPeriod) -> FundamentalPeriod:
    if first.announced_at is None:
        return second
    if second.announced_at is None:
        return first
    return second if second.announced_at >= first.announced_at else first


def _period_from_indicator(
    instrument_id: InstrumentId, row: dict[str, object], *, index: int
) -> FundamentalPeriod | None:
    period_end = as_optional_date(
        lookup_column(row, ("REPORT_DATE", "report_date")),
        field=f"REPORT_DATE[{index}]",
    )
    if period_end is None:
        return None
    try:
        period_type = period_type_from_end(period_end)
    except InvalidSourcePayload:
        return None
    announced = _announced_at(
        lookup_column(row, ("NOTICE_DATE", "notice_date")),
        field=f"NOTICE_DATE[{index}]",
    )
    return FundamentalPeriod(
        instrument_id=instrument_id,
        period_end=period_end,
        period_type=period_type,
        currency=CN_CURRENCY,
        announced_at=announced,
        eps=_pct_or_amount(row, ("EPSJB",)),
        bps=_pct_or_amount(row, ("BPS",)),
        roe_pct=_pct_or_amount(row, ("ROEJQ",)),
        revenue=_pct_or_amount(row, ("TOTALOPERATEREVE",)),
        revenue_yoy_pct=_pct_or_amount(row, ("TOTALOPERATEREVETZ",)),
        net_profit=_pct_or_amount(row, ("PARENTNETPROFIT",)),
        net_profit_yoy_pct=_pct_or_amount(row, ("PARENTNETPROFITTZ",)),
        gross_margin_pct=_pct_or_amount(row, ("XSMLL",)),
        net_margin_pct=_pct_or_amount(row, ("XSJLL",)),
        debt_ratio_pct=_pct_or_amount(row, ("ZCFZL",)),
    )


def _period_from_batch(
    instrument_id: InstrumentId,
    period_end: date,
    yjbb: dict[str, object] | None,
    zcfz: dict[str, object] | None,
    lrb: dict[str, object] | None,
) -> FundamentalPeriod | None:
    if not yjbb and not zcfz and not lrb:
        return None
    yjbb = yjbb or {}
    zcfz = zcfz or {}
    lrb = lrb or {}
    revenue = _pct_or_amount(yjbb, ("营业总收入-营业总收入",)) or _pct_or_amount(lrb, ("营业总收入",))
    net_profit = _pct_or_amount(yjbb, ("净利润-净利润",)) or _pct_or_amount(lrb, ("净利润",))
    net_margin = _pct_or_amount(lrb, ("销售净利率",))
    if net_margin is None and revenue and net_profit is not None and revenue != 0:
        net_margin = net_profit / revenue * 100
    announced = (
        _announced_at(zcfz.get("公告日期"), field="公告日期")
        or _announced_at(lrb.get("公告日期"), field="公告日期")
        or _announced_at(yjbb.get("最新公告日期"), field="最新公告日期")
    )
    has_value = any(
        value is not None
        for value in (
            _pct_or_amount(yjbb, ("每股收益",)),
            _pct_or_amount(yjbb, ("每股净资产",)),
            _pct_or_amount(yjbb, ("净资产收益率",)),
            revenue,
            net_profit,
            _pct_or_amount(zcfz, ("资产负债率",)),
            _pct_or_amount(yjbb, ("销售毛利率",)),
            net_margin,
        )
    )
    if not has_value:
        return None
    return FundamentalPeriod(
        instrument_id=instrument_id,
        period_end=period_end,
        period_type=period_type_from_end(period_end),
        currency=CN_CURRENCY,
        announced_at=announced,
        eps=_pct_or_amount(yjbb, ("每股收益",)),
        bps=_pct_or_amount(yjbb, ("每股净资产",)),
        roe_pct=_pct_or_amount(yjbb, ("净资产收益率",)),
        revenue=revenue,
        revenue_yoy_pct=_pct_or_amount(yjbb, ("营业总收入-同比增长",))
        or _pct_or_amount(lrb, ("营业总收入同比",)),
        net_profit=net_profit,
        net_profit_yoy_pct=_pct_or_amount(yjbb, ("净利润-同比增长",))
        or _pct_or_amount(lrb, ("净利润同比",)),
        gross_margin_pct=_pct_or_amount(yjbb, ("销售毛利率",)),
        net_margin_pct=net_margin,
        debt_ratio_pct=_pct_or_amount(zcfz, ("资产负债率",)),
    )


def _announced_at(value: object, *, field: str) -> datetime | None:
    day = as_optional_date(value, field=field)
    if day is None:
        return None
    return datetime.combine(day, time.min, tzinfo=_SHANGHAI)


def _pct_or_amount(row: dict[str, object], names: tuple[str, ...]) -> float | None:
    value = lookup_column(row, names)
    if value in (None, ""):
        return None
    try:
        return as_optional_float(value, field=names[0])
    except InvalidSourcePayload:
        return None


def _rows_by_code(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for record in records:
        raw = lookup_column(record, _CODE_COLUMNS)
        if raw is None:
            continue
        digits = "".join(ch for ch in str(raw) if ch.isdigit())
        if len(digits) < 6:
            continue
        out[digits[-6:]] = record
    return out
