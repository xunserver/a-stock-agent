from __future__ import annotations

import logging

from astock.config import default_adjust, history_start, quote_periods, request_sleep_seconds
from astock.ingest import ingest_bars, ingest_calendar
from astock_core.db import INGEST_KINDS, MarketDB
from astock_core.paths import DEFAULT_POOL_ID

logger = logging.getLogger(__name__)

_PERIOD_LABEL = {"daily": "日", "weekly": "周", "monthly": "月"}


def _plan_codes(
    db: MarketDB,
    codes: list[str],
    *,
    adjust: str,
    period: str,
) -> tuple[list[str], list[str], int]:
    last_cal = db.current_trade_date()
    need_full: list[str] = []
    need_fill: list[str] = []
    already = 0
    for code in codes:
        last = db.last_bar_date(code, adjust=adjust, period=period)
        if last is None:
            need_full.append(code)
        elif last_cal and last >= last_cal:
            already += 1
        else:
            need_fill.append(code)
    return need_full, need_fill, already


def sync_quotes(
    db: MarketDB,
    *,
    pool_id: str = DEFAULT_POOL_ID,
    codes: list[str] | None = None,
    adjust: str | None = None,
    sleep: float | None = None,
    limit: int | None = None,
    refresh_calendar: bool = True,
    periods: tuple[str, ...] | None = None,
    start_date: str | None = None,
) -> dict:
    """盘后行情：指定代码或活跃池内，新票拉全历史，其余只补缺口；日/周/月线一并补齐。"""
    calendar = ingest_calendar(db) if refresh_calendar else 0
    if codes is None:
        target_codes = db.active_pool_codes(pool_id)
    else:
        target_codes = list(codes)

    resolved_adjust = default_adjust() if adjust is None else adjust
    resolved_sleep = request_sleep_seconds() if sleep is None else sleep
    resolved_start = start_date or history_start()
    resolved_periods = periods or quote_periods()

    result: dict = {
        "pool": pool_id,
        "calendar": calendar,
        "history_start": resolved_start,
        "periods": list(resolved_periods),
        "ok": 0,
        "error": 0,
        "empty": 0,
    }

    for period in resolved_periods:
        if period not in INGEST_KINDS:
            raise ValueError(f"不支持的 K 线周期: {period}")
        need_full, need_fill, already = _plan_codes(
            db, target_codes, adjust=resolved_adjust, period=period
        )
        full = need_full[:limit] if limit is not None else need_full
        fill = (
            need_fill
            if limit is None
            else need_fill[: max(0, limit - len(full))]
        )
        logger.info(
            "%s线补齐：拉全历史 %s 只，补缺口 %s 只，已最新 %s 只",
            _PERIOD_LABEL.get(period, period),
            len(full),
            len(fill),
            already,
        )
        full_stats = (
            ingest_bars(
                db,
                codes=full,
                adjust=resolved_adjust,
                sleep=resolved_sleep,
                start_date=resolved_start,
                period=period,
            )
            if full
            else {"ok": 0, "skip": 0, "empty": 0, "error": 0, "rows": 0}
        )
        fill_stats = (
            ingest_bars(
                db,
                codes=fill,
                adjust=resolved_adjust,
                sleep=resolved_sleep,
                start_date=resolved_start,
                period=period,
            )
            if fill
            else {"ok": 0, "skip": 0, "empty": 0, "error": 0, "rows": 0}
        )
        rows = full_stats["rows"] + fill_stats["rows"]
        result[f"{period}_need_full"] = len(need_full)
        result[f"{period}_need_fill"] = len(need_fill)
        result[f"{period}_already_current"] = already
        result[f"{period}_rows"] = rows
        result["ok"] += full_stats["ok"] + fill_stats["ok"]
        result["error"] += full_stats["error"] + fill_stats["error"]
        result["empty"] += full_stats["empty"] + fill_stats["empty"]

        # 兼容旧字段：以日线计划为准
        if period == "daily":
            result["need_sync"] = len(need_full) + len(need_fill)
            result["need_full"] = len(need_full)
            result["need_fill"] = len(need_fill)
            result["already_current"] = already
            result["rows"] = rows

    return result
