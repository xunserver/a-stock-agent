from __future__ import annotations

import logging

from astock.config import DEFAULT_ADJUST, HISTORY_START, REQUEST_SLEEP_SECONDS
from astock.ingest import ingest_bars, ingest_calendar
from astock_core.db import MarketDB
from astock_core.paths import DEFAULT_POOL_ID

logger = logging.getLogger(__name__)


def sync_quotes(
    db: MarketDB,
    *,
    pool_id: str = DEFAULT_POOL_ID,
    codes: list[str] | None = None,
    adjust: str = DEFAULT_ADJUST,
    sleep: float = REQUEST_SLEEP_SECONDS,
    limit: int | None = None,
    refresh_calendar: bool = True,
) -> dict:
    """盘后行情：指定代码或活跃池内，新票拉全历史，其余只补缺口。"""
    calendar = ingest_calendar(db) if refresh_calendar else 0
    if codes is None:
        plan = db.pool_quote_plan(pool_id, adjust=adjust)
        need_full, need_fill, already = (
            list(plan["full"]),
            list(plan["fill"]),
            len(plan["current"]),
        )
    else:
        last_cal = db.last_calendar_date()
        need_full, need_fill = [], []
        already = 0
        for code in codes:
            last = db.last_bar_date(code, adjust=adjust)
            if last is None:
                need_full.append(code)
            elif last_cal and last >= last_cal:
                already += 1
            else:
                need_fill.append(code)
    full = need_full[:limit] if limit is not None else need_full
    fill = (
        need_fill
        if limit is None
        else need_fill[: max(0, limit - len(full))]
    )
    logger.info(
        "行情补齐：拉全历史 %s 只，补缺口 %s 只，已最新 %s 只",
        len(full),
        len(fill),
        already,
    )
    full_stats = (
        ingest_bars(db, codes=full, adjust=adjust, sleep=sleep, start_date=HISTORY_START)
        if full
        else {"ok": 0, "skip": 0, "empty": 0, "error": 0, "rows": 0}
    )
    fill_stats = (
        ingest_bars(db, codes=fill, adjust=adjust, sleep=sleep, start_date=HISTORY_START)
        if fill
        else {"ok": 0, "skip": 0, "empty": 0, "error": 0, "rows": 0}
    )
    return {
        "pool": pool_id,
        "calendar": calendar,
        "need_full": len(need_full),
        "need_fill": len(need_fill),
        "already_current": already,
        "full_rows": full_stats["rows"],
        "fill_rows": fill_stats["rows"],
        "ok": full_stats["ok"] + fill_stats["ok"],
        "error": full_stats["error"] + fill_stats["error"],
        "empty": full_stats["empty"] + fill_stats["empty"],
    }
