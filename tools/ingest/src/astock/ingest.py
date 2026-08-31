from __future__ import annotations

import logging
import time
from datetime import date, timedelta

from astock.config import (
    default_adjust,
    default_years,
    history_start,
    hs300_index_code,
    major_indexes,
    quote_periods,
    request_retries,
    request_sleep_seconds,
)
from astock.indexes import index_member_tuples
from astock.providers.registry import resolve_capability
from astock.providers.protocols import BarSource, CalendarSource, InstrumentSource, MembershipSource
from astock_core.db import INGEST_KINDS, MarketDB
from astock_core.market_data import (
    Adjustment,
    AssetType,
    BarInterval,
    BarQuery,
    CalendarQuery,
    InstrumentId,
    InstrumentQuery,
    MarketDataError,
    from_legacy_symbol,
)
from astock_core.paths import DATA_DIR
from astock_core.session import MARKET_CN_A

logger = logging.getLogger(__name__)

_PERIOD_TO_INTERVAL = {
    "daily": BarInterval.D1,
    "weekly": BarInterval.W1,
    "monthly": BarInterval.M1,
}
_PERIOD_LABEL = {"daily": "日", "weekly": "周", "monthly": "月"}
_INDEX_PREFIX_EXCHANGE = {
    "sh": "XSHG",
    "sz": "XSHE",
    "bj": "BSE",
    "csi": "XSHG",
}
_CALENDAR_START = date(1990, 1, 1)
_CALENDAR_HORIZON_YEARS = 2


def _today_yyyymmdd() -> str:
    return date.today().strftime("%Y%m%d")


def _next_day_yyyymmdd(iso_date: str) -> str:
    dt = date.fromisoformat(iso_date) + timedelta(days=1)
    return dt.strftime("%Y%m%d")


def _parse_yyyymmdd(text: str) -> date:
    compact = text.replace("-", "")[:8]
    return date(int(compact[:4]), int(compact[4:6]), int(compact[6:8]))


def _adjustment_from_persist(adjust: str) -> Adjustment:
    if adjust in ("", "raw"):
        return Adjustment.RAW
    return Adjustment(adjust)


def instrument_id_for_index_code(code: str) -> InstrumentId | None:
    """Parse a persisted index code such as ``sh000300`` into an InstrumentId."""
    lower = str(code).strip().lower()
    for prefix, exchange in _INDEX_PREFIX_EXCHANGE.items():
        if not lower.startswith(prefix):
            continue
        symbol = lower[len(prefix) :]
        if symbol.isdigit() and 1 <= len(symbol) <= 6:
            return InstrumentId(country="CN", exchange=exchange, symbol=symbol.zfill(6))
        return None
    return None


def _call(fn, *args, retries: int | None = None, **kwargs):
    attempts = request_retries() if retries is None else retries
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # akshare 上游站点不稳定
            last_error = exc
            wait = min(2 ** attempt, 16)
            logger.warning("调用失败 %s/%s: %s，%ss 后重试", attempt, attempts, exc, wait)
            time.sleep(wait)
    assert last_error is not None
    raise last_error


def ingest_calendar(
    db: MarketDB,
    *,
    force: bool = False,
    market_id: str = MARKET_CN_A,
    calendar_source: CalendarSource | None = None,
) -> int:
    if not force and db.calendar_synced_today(market_id=market_id):
        logger.info("交易日历今日已同步，跳过")
        return 0

    source = calendar_source or resolve_capability("calendar")
    today = date.today()
    query = CalendarQuery(
        market_id=market_id,
        start=_CALENDAR_START,
        end=date(today.year + _CALENDAR_HORIZON_YEARS, 12, 31),
    )
    logger.info("拉取交易日历")
    dataset = source.fetch_calendar(query)
    if not any(day.is_open and day.market_id == market_id for day in dataset.items):
        raise ValueError("交易日历为空")
    n = db.upsert_trading_days(dataset.items, market_id=market_id)
    logger.info("交易日历写入 %s 条", n)
    return n


def ingest_stocks(db: MarketDB, *, instrument_source: InstrumentSource | None = None) -> int:
    source = instrument_source or resolve_capability("instruments")
    logger.info("拉取沪深京 A 股列表")
    dataset = source.fetch_instruments(InstrumentQuery(asset_types=(AssetType.STOCK,)))
    n = db.upsert_instruments(dataset.items)
    logger.info("股票列表写入 %s 只", n)
    return n


def _years_start(years: int | None) -> str:
    if not years:
        return history_start()
    today = date.today()
    try:
        start = today.replace(year=today.year - years)
    except ValueError:
        start = today.replace(month=2, day=28, year=today.year - years)
    return start.strftime("%Y%m%d")


def ingest_hs300_members(
    db: MarketDB,
    *,
    membership_source: MembershipSource | None = None,
) -> int:
    _, members = index_member_tuples("hs300", membership_source=membership_source)
    db.replace_stocks(members)
    n = db.replace_universe("hs300", members)
    logger.info("沪深300成分写入 %s 只", n)
    return n


def ingest_indexes(
    db: MarketDB,
    *,
    indexes: tuple[tuple[str, str], ...] | None = None,
    start_date: str | None = None,
    bar_source: BarSource | None = None,
) -> int:
    source = bar_source or resolve_capability("bars")
    total = 0
    end = _today_yyyymmdd()
    begin = start_date or history_start()
    targets = indexes or major_indexes()
    for code, name in targets:
        last = db.last_index_date(code)
        start = _next_day_yyyymmdd(last) if last else begin
        if last and start > end:
            logger.info("指数 %s 已是最新", code)
            continue
        logger.info("拉取指数 %s %s  %s -> %s", code, name, start, end)
        instrument_id = instrument_id_for_index_code(code)
        try:
            if instrument_id is None:
                bars = ()
            else:
                dataset = source.fetch_bars(
                    BarQuery(
                        instruments=(instrument_id,),
                        start=_parse_yyyymmdd(start),
                        end=_parse_yyyymmdd(end),
                        interval=BarInterval.D1,
                        adjustment=Adjustment.RAW,
                    )
                )
                bars = dataset.items
            written = db.upsert_standard_index_bars(bars, code=code, name=name)
            last_date = bars[-1].trade_date.isoformat() if bars else last
            status = "ok" if bars else "empty"
            db.mark_ingest(
                code,
                "index",
                status,
                adjust="",
                last_trade_date=last_date,
                rows=written,
            )
            total += written
        except MarketDataError as exc:
            db.mark_ingest(code, "index", "error", adjust="", error=str(exc)[:500])
            logger.warning("指数 %s 失败: %s", code, exc)
        except Exception as exc:
            db.mark_ingest(code, "index", "error", adjust="", error=str(exc)[:500])
            logger.warning("指数 %s 失败: %s", code, exc)
        time.sleep(request_sleep_seconds())
    logger.info("指数日线写入 %s 条", total)
    return total


def ingest_bars(
    db: MarketDB,
    *,
    codes: list[str] | None = None,
    limit: int | None = None,
    adjust: str | None = None,
    sleep: float | None = None,
    start_date: str | None = None,
    period: str = "daily",
    bar_source: BarSource | None = None,
) -> dict[str, int]:
    periods = quote_periods()
    if period not in INGEST_KINDS:
        raise ValueError(f"不支持的 K 线周期: {period}")
    if period not in periods:
        raise ValueError(f"设置未启用的 K 线周期: {period}")
    interval = _PERIOD_TO_INTERVAL[period]
    ingest_kind = INGEST_KINDS[period]
    universe = codes if codes is not None else db.stock_codes()
    if limit is not None:
        universe = universe[:limit]
    last_cal = db.current_trade_date()
    end = _today_yyyymmdd()
    resolved_adjust = default_adjust() if adjust is None else adjust
    resolved_sleep = request_sleep_seconds() if sleep is None else sleep
    history = start_date or history_start()
    source = bar_source or resolve_capability("bars")
    adjustment = _adjustment_from_persist(resolved_adjust)
    stats = {"ok": 0, "skip": 0, "empty": 0, "error": 0, "rows": 0}
    total = len(universe)
    logger.info(
        "开始逐只拉取%s线：%s 只，复权=%s，起点=%s，截止交易日=%s",
        _PERIOD_LABEL.get(period, period),
        total,
        resolved_adjust,
        history,
        last_cal,
    )

    for i, code in enumerate(universe, start=1):
        last = db.last_bar_date(code, adjust=resolved_adjust, period=period)
        if last and last_cal and last >= last_cal:
            stats["skip"] += 1
            continue
        start = _next_day_yyyymmdd(last) if last else history
        if start < history:
            start = history
        try:
            dataset = source.fetch_bars(
                BarQuery(
                    instruments=(from_legacy_symbol(code),),
                    start=_parse_yyyymmdd(start),
                    end=_parse_yyyymmdd(end),
                    interval=interval,
                    adjustment=adjustment,
                )
            )
            bars = dataset.items
            if dataset.warnings or not dataset.complete:
                logger.warning(
                    "股票 %s %s线 Dataset 不完整 complete=%s warnings=%s",
                    code,
                    period,
                    dataset.complete,
                    dataset.warnings,
                )
            written = db.upsert_standard_bars(bars)
            last_date = bars[-1].trade_date.isoformat() if bars else last
            status = "ok" if bars else "empty"
            db.mark_ingest(
                code,
                ingest_kind,
                status,
                adjust=resolved_adjust,
                last_trade_date=last_date,
                rows=written,
            )
            stats[status] += 1
            stats["rows"] += written
            if i % 20 == 0 or i == total:
                logger.info(
                    "进度 %s/%s  %s 本次 %s 条 累计写入 %s  跳过 %s  空 %s  错 %s",
                    i,
                    total,
                    code,
                    written,
                    stats["rows"],
                    stats["skip"],
                    stats["empty"],
                    stats["error"],
                )
        except MarketDataError as exc:
            db.mark_ingest(
                code, ingest_kind, "error", adjust=resolved_adjust, error=str(exc)[:500]
            )
            stats["error"] += 1
            logger.warning("股票 %s %s线失败: %s", code, period, exc)
        except Exception as exc:
            db.mark_ingest(
                code, ingest_kind, "error", adjust=resolved_adjust, error=str(exc)[:500]
            )
            stats["error"] += 1
            logger.warning("股票 %s %s线失败: %s", code, period, exc)
        time.sleep(resolved_sleep)
    return stats


def ingest_hs300(
    db: MarketDB,
    *,
    years: int | None = None,
    limit: int | None = None,
    sleep: float | None = None,
    adjust: str | None = None,
    bar_source: BarSource | None = None,
    calendar_source: CalendarSource | None = None,
    membership_source: MembershipSource | None = None,
) -> dict[str, int]:
    resolved_years = default_years() if years is None else years
    start_date = _years_start(resolved_years)
    index_code = hs300_index_code()
    resolved_bars = bar_source or resolve_capability("bars")
    resolved_memberships = membership_source or resolve_capability("memberships")
    result = {
        "calendar": ingest_calendar(db, calendar_source=calendar_source),
        "hs300_members": ingest_hs300_members(db, membership_source=resolved_memberships),
        "indexes": ingest_indexes(
            db,
            indexes=((index_code, "沪深300"),),
            start_date=start_date,
            bar_source=resolved_bars,
        ),
    }
    codes = db.universe_codes("hs300")
    result.update(
        ingest_bars(
            db,
            codes=codes,
            limit=limit,
            adjust=adjust,
            sleep=sleep,
            start_date=start_date,
            bar_source=resolved_bars,
        )
    )
    result["start_date"] = start_date
    result["universe"] = "hs300"
    return result


def ingest_all(
    db: MarketDB,
    *,
    codes: list[str] | None = None,
    limit: int | None = None,
    skip_bars: bool = False,
    bar_source: BarSource | None = None,
    calendar_source: CalendarSource | None = None,
    instrument_source: InstrumentSource | None = None,
) -> dict[str, int]:
    resolved_bars = bar_source or resolve_capability("bars")
    result = {
        "calendar": ingest_calendar(db, calendar_source=calendar_source),
        "stocks": ingest_stocks(db, instrument_source=instrument_source),
        "indexes": ingest_indexes(db, bar_source=resolved_bars),
    }
    if not skip_bars:
        result.update(ingest_bars(db, codes=codes, limit=limit, bar_source=resolved_bars))
    return result


def configure_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(DATA_DIR / "ingest.log", encoding="utf-8"),
        ],
    )
