from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import pandas as pd

from astock.config import (
    default_adjust,
    default_years,
    history_start,
    hs300_index_code,
    hs300_symbol,
    major_indexes,
    quote_periods,
    request_retries,
    request_sleep_seconds,
)
from astock import eastmoney
from astock_core.db import INGEST_KINDS, MarketDB, _ymd
from astock_core.paths import DATA_DIR
from astock_core.session import MARKET_CN_A

logger = logging.getLogger(__name__)


def _today_yyyymmdd() -> str:
    return date.today().strftime("%Y%m%d")


def _next_day_yyyymmdd(iso_date: str) -> str:
    dt = date.fromisoformat(iso_date) + timedelta(days=1)
    return dt.strftime("%Y%m%d")


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
) -> int:
    import akshare as ak

    if not force and db.calendar_synced_today(market_id=market_id):
        logger.info("交易日历今日已同步，跳过")
        return 0

    logger.info("拉取交易日历")
    frame = _call(ak.tool_trade_date_hist_sina)
    dates = frame["trade_date"].tolist()
    n = db.replace_calendar(dates, market_id=market_id)
    db.mark_calendar_synced(market_id=market_id, rows=n)
    logger.info("交易日历写入 %s 条", n)
    return n


def ingest_stocks(db: MarketDB) -> int:
    import akshare as ak

    logger.info("拉取沪深京 A 股列表（东财快照）")
    frame = _call(ak.stock_zh_a_spot_em)
    stocks = [
        (str(code).zfill(6), str(name))
        for code, name in zip(frame["代码"], frame["名称"], strict=True)
        if str(code).strip()
    ]
    n = db.replace_stocks(stocks)
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


def fetch_hs300_members() -> list[tuple[str, str]]:
    import akshare as ak

    logger.info("拉取沪深300成分股")
    try:
        frame = _call(ak.index_stock_cons_csindex, symbol=hs300_symbol())
        members = [
            (str(code).zfill(6), str(name))
            for code, name in zip(frame["成分券代码"], frame["成分券名称"], strict=True)
        ]
        logger.info("中证官网成分股 %s 只", len(members))
        return members
    except Exception as exc:
        logger.warning("中证官网失败，改用新浪：%s", exc)

    frame = _call(ak.index_stock_cons_sina, symbol=hs300_symbol())
    code_col = "code" if "code" in frame.columns else frame.columns[0]
    name_col = "name" if "name" in frame.columns else frame.columns[1]
    members = [
        (str(code).replace("sh", "").replace("sz", "").zfill(6), str(name))
        for code, name in zip(frame[code_col], frame[name_col], strict=True)
    ]
    logger.info("新浪成分股 %s 只", len(members))
    return members


def ingest_hs300_members(db: MarketDB) -> int:
    members = fetch_hs300_members()
    db.replace_stocks(members)
    n = db.replace_universe("hs300", members)
    logger.info("沪深300成分写入 %s 只", n)
    return n


def ingest_indexes(
    db: MarketDB,
    *,
    indexes: tuple[tuple[str, str], ...] | None = None,
    start_date: str | None = None,
) -> int:
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
        frame = _call(eastmoney.index_daily, code, start, end)
        rows = []
        for item in frame.itertuples(index=False):
            rows.append(
                (
                    code,
                    name,
                    _ymd(item.date),
                    float(item.open) if pd.notna(item.open) else None,
                    float(item.close) if pd.notna(item.close) else None,
                    float(item.high) if pd.notna(item.high) else None,
                    float(item.low) if pd.notna(item.low) else None,
                    float(item.volume) if pd.notna(item.volume) else None,
                    float(item.amount) if pd.notna(item.amount) else None,
                )
            )
        written = db.upsert_index_bars(rows)
        last_date = rows[-1][2] if rows else last
        status = "ok" if rows else "empty"
        db.mark_ingest(
            code,
            "index",
            status,
            adjust="",
            last_trade_date=last_date,
            rows=written,
        )
        total += written
        time.sleep(request_sleep_seconds())
    logger.info("指数日线写入 %s 条", total)
    return total


def _bars_from_frame(code: str, frame: pd.DataFrame, adjust: str) -> list[tuple]:
    rows: list[tuple] = []
    for item in frame.itertuples(index=False):
        rows.append(
            (
                code,
                _ymd(getattr(item, "日期")),
                _num(getattr(item, "开盘")),
                _num(getattr(item, "收盘")),
                _num(getattr(item, "最高")),
                _num(getattr(item, "最低")),
                _num(getattr(item, "成交量")),
                _num(getattr(item, "成交额")),
                _num(getattr(item, "振幅")),
                _num(getattr(item, "涨跌幅")),
                _num(getattr(item, "涨跌额")),
                _num(getattr(item, "换手率")),
                adjust,
            )
        )
    return rows


def _num(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_stock_bars(
    code: str,
    start: str,
    end: str,
    adjust: str,
    period: str = "daily",
) -> pd.DataFrame:
    if period not in INGEST_KINDS:
        raise ValueError(f"不支持的 K 线周期: {period}")
    try:
        return eastmoney.stock_kline(code, start, end, adjust=adjust, period=period)
    except Exception as exc:
        logger.warning("东财%s线失败 %s，改用 AKShare：%s", period, code, exc)

    import akshare as ak

    if period == "daily":
        try:
            frame = ak.stock_zh_a_hist_tx(
                symbol=code,
                start_date=start,
                end_date=end,
                adjust=adjust,
            )
            if frame is not None and not frame.empty:
                renamed = frame.rename(
                    columns={
                        "date": "日期",
                        "open": "开盘",
                        "close": "收盘",
                        "high": "最高",
                        "low": "最低",
                        "volume": "成交量",
                        "amount": "成交额",
                    }
                )
                renamed["股票代码"] = code
                renamed["振幅"] = None
                renamed["涨跌幅"] = None
                renamed["涨跌额"] = None
                renamed["换手率"] = renamed["turnover"] if "turnover" in renamed.columns else None
                return renamed
        except Exception as exc:
            logger.warning("腾讯日线失败 %s，改用新浪：%s", code, exc)

        prefix = "sh" if code.startswith("6") else "sz"
        frame = ak.stock_zh_a_daily(symbol=f"{prefix}{code}", adjust=adjust)
        if frame is None or frame.empty:
            return pd.DataFrame()
        renamed = frame.rename(
            columns={
                "date": "日期",
                "open": "开盘",
                "close": "收盘",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "amount": "成交额",
            }
        )
        start_iso = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
        end_iso = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
        dates = pd.to_datetime(renamed["日期"], errors="coerce")
        renamed = renamed[(dates >= start_iso) & (dates <= end_iso)]
        renamed["股票代码"] = code
        renamed["振幅"] = None
        renamed["涨跌幅"] = None
        renamed["涨跌额"] = None
        renamed["换手率"] = renamed["turnover"] if "turnover" in renamed.columns else None
        return renamed

    frame = ak.stock_zh_a_hist(
        symbol=code,
        period=period,
        start_date=start,
        end_date=end,
        adjust=adjust,
    )
    if frame is None or frame.empty:
        return pd.DataFrame()
    return frame


def ingest_bars(
    db: MarketDB,
    *,
    codes: list[str] | None = None,
    limit: int | None = None,
    adjust: str | None = None,
    sleep: float | None = None,
    start_date: str | None = None,
    period: str = "daily",
) -> dict[str, int]:
    periods = quote_periods()
    if period not in INGEST_KINDS:
        raise ValueError(f"不支持的 K 线周期: {period}")
    if period not in periods:
        raise ValueError(f"设置未启用的 K 线周期: {period}")
    ingest_kind = INGEST_KINDS[period]
    universe = codes if codes is not None else db.stock_codes()
    if limit is not None:
        universe = universe[:limit]
    last_cal = db.current_trade_date()
    end = _today_yyyymmdd()
    resolved_adjust = default_adjust() if adjust is None else adjust
    resolved_sleep = request_sleep_seconds() if sleep is None else sleep
    history = start_date or history_start()
    stats = {"ok": 0, "skip": 0, "empty": 0, "error": 0, "rows": 0}
    total = len(universe)
    logger.info(
        "开始逐只拉取%s线：%s 只，复权=%s，起点=%s，截止交易日=%s",
        {"daily": "日", "weekly": "周", "monthly": "月"}.get(period, period),
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
            frame = _call(_fetch_stock_bars, code, start, end, resolved_adjust, period)
            rows = (
                _bars_from_frame(code, frame, resolved_adjust)
                if frame is not None and not frame.empty
                else []
            )
            written = db.upsert_bars(rows, period=period)
            last_date = rows[-1][1] if rows else last
            status = "ok" if rows else "empty"
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
) -> dict[str, int]:
    resolved_years = default_years() if years is None else years
    start_date = _years_start(resolved_years)
    index_code = hs300_index_code()
    result = {
        "calendar": ingest_calendar(db),
        "hs300_members": ingest_hs300_members(db),
        "indexes": ingest_indexes(
            db,
            indexes=((index_code, "沪深300"),),
            start_date=start_date,
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
) -> dict[str, int]:
    result = {
        "calendar": ingest_calendar(db),
        "stocks": ingest_stocks(db),
        "indexes": ingest_indexes(db),
    }
    if not skip_bars:
        result.update(ingest_bars(db, codes=codes, limit=limit))
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
