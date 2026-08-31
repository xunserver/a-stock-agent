from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from astock_core.db import MarketDB
from astock_core.paths import (
    ANALYZE_DIR,
    DB_PATH,
    DEFAULT_ADJUST,
    DEFAULT_POOL_ID,
    pool_qlib_dir,
)
from astock_core.session import (
    get_calendar_market,
    get_policy,
    in_trading_hours,
    list_calendar_markets,
    market_now,
    serialize_sessions,
)

from astock_control.adapters.events import fetch_stock_events
from astock_control.adapters.news import fetch_stock_news
from astock_control._analysis_queries import (
    REPORT_LIST_LIMIT,
    REPORT_MD_FILES,
    analyze_get_query as _analyze_get_query,
    analyze_list_query as _analyze_list_query,
)
from astock_control._qlib_queries import (
    qlib_overview_query as _qlib_overview_query,
    qlib_run_view as _qlib_run_view,
)
from astock_control.config import load_settings
from astock_control.protocol import (
    EVENTS_DEFAULT_LIMIT,
    NEWS_DEFAULT_LIMIT,
    ProtocolError,
    code_to_ticker,
)

from astock_core.financial_statements import extract_statement_items


def _qlib_workflow_defaults() -> dict[str, Any]:
    defaults = dict((load_settings().get("qlib") or {}).get("workflow") or {})
    defaults.pop("market", None)
    return defaults


def qlib_run_view(run: dict[str, Any]) -> dict[str, Any]:
    return _qlib_run_view(run, db_path=DB_PATH)


def qlib_overview_query(pool_id: str) -> dict[str, Any]:
    return _qlib_overview_query(
        pool_id,
        db_path=DB_PATH,
        pool_dir=pool_qlib_dir,
        workflow_defaults=_qlib_workflow_defaults,
    )


def pools_list_query() -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        pools = db.list_pools()
        return {"count": len(pools), "pools": pools}


def stocks_list_query() -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        stocks = [_with_ticker(item) for item in db.list_stocks()]
        in_pool = sum(1 for item in stocks if item["pools"])
        return {
            "count": len(stocks),
            "in_pool": in_pool,
            "profile_filled": db.profile_filled_count(),
            "stocks": stocks,
        }


def stock_news_query(code: str, *, limit: int = NEWS_DEFAULT_LIMIT) -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        if db.get_stock(code) is None:
            raise ProtocolError(f"找不到股票: {code}")
    error: str | None = None
    items: list[dict[str, Any]] = []
    try:
        items = fetch_stock_news(code, limit=limit)
    except Exception:
        error = "新闻暂时不可用"
    return {
        "code": code,
        "ticker": code_to_ticker(code),
        "count": len(items),
        "news": items,
        "error": error,
    }


_EVENT_ERROR_LABELS = {
    "notices": "公告暂时不可用",
    "research": "研报暂时不可用",
    "block_trades": "大宗交易暂时不可用",
    "holder_changes": "股东变更暂时不可用",
}


def stock_events_query(
    code: str,
    *,
    kind: str,
    limit: int = EVENTS_DEFAULT_LIMIT,
) -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        if db.get_stock(code) is None:
            raise ProtocolError(f"找不到股票: {code}")
    error: str | None = None
    items: list[dict[str, Any]] = []
    try:
        items = fetch_stock_events(code, kind, limit=limit)
    except Exception:
        error = _EVENT_ERROR_LABELS.get(kind, "事件暂时不可用")
    return {
        "code": code,
        "ticker": code_to_ticker(code),
        "kind": kind,
        "count": len(items),
        "events": items,
        "error": error,
    }


def stock_get_query(code: str) -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        profile = db.get_stock(code)
        if profile is None:
            raise ProtocolError(f"找不到股票: {code}")
        latest = db.latest_bar(code, adjust=DEFAULT_ADJUST)
        payload = dict(profile)
        if (
            not payload.get("latest_price")
            and latest
            and latest.get("close") is not None
        ):
            payload["latest_price"] = latest["close"]
        return {
            "code": code,
            "ticker": code_to_ticker(code),
            "profile": payload,
            "pools": _pools_for_code(db, code),
            "quotes_summary": db.bar_summary(code, adjust=DEFAULT_ADJUST),
            "latest_bar": latest,
            "bars": db.list_bars(code, period="daily", adjust=DEFAULT_ADJUST),
            "bars_weekly": db.list_bars(code, period="weekly", adjust=DEFAULT_ADJUST),
            "bars_yearly": db.list_bars(code, period="yearly", adjust=DEFAULT_ADJUST),
            "financial_reports": db.list_financial_reports(code, limit=12),
            "financial_summary": {
                "count": db.financial_report_count(code),
                "latest_report_date": db.latest_financial_report_date(code),
            },
            "financial_statements_summary": db.financial_statement_summary(code),
        }


def _financial_key_items(sheet: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_statement_items(sheet, payload)


def stock_financials_detail_query(
    code: str,
    *,
    sheet: str,
    report_date: str,
) -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        if db.get_stock(code) is None:
            raise ProtocolError(f"找不到股票: {code}")
        row = db.get_financial_statement(code, report_date, sheet)
        if row is None:
            raise ProtocolError(
                f"找不到报表明细: {code} {sheet} {report_date}"
            )
        payload = row.get("payload") or {}
        return {
            "code": code,
            "ticker": code_to_ticker(code),
            "sheet": sheet,
            "report_date": row.get("report_date"),
            "report_type": row.get("report_type"),
            "notice_date": row.get("notice_date"),
            "key_items": _financial_key_items(sheet, payload),
            "payload": payload,
            "updated_at": row.get("updated_at"),
        }


def _pools_for_code(db: MarketDB, code: str) -> list[dict[str, str]]:
    return db.active_pools_for_code(code)


def _with_ticker(item: dict[str, Any]) -> dict[str, Any]:
    return {**item, "ticker": code_to_ticker(str(item.get("code") or ""))}


def status_query(pool_id: str) -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        plan = db.pool_quote_plan(pool_id)
        trade_date = db.current_trade_date()
        return {
            "db": str(DB_PATH),
            "pool": pool_id,
            "trade_date": trade_date,
            "need_sync": len(plan["full"]) + len(plan["fill"]),
            "need_full": len(plan["full"]),
            "need_fill": len(plan["fill"]),
            "already_current": len(plan["current"]),
            "profile_filled": db.profile_filled_count(pool_id),
            **db.counts(pool_id),
        }


def calendar_markets_query() -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        markets = []
        for item in list_calendar_markets():
            coverage = db.calendar_coverage(market_id=item["id"])
            markets.append(
                {
                    **item,
                    "count": coverage["count"],
                    "first": coverage["first"],
                    "last": coverage["last"],
                }
            )
        return {"count": len(markets), "markets": markets}


def calendar_overview_query() -> dict[str, Any]:
    """顶栏日历弹层：各市场今日是否开市、当前交易日、交易时段。"""
    with MarketDB(DB_PATH) as db:
        markets: list[dict[str, Any]] = []
        for item in list_calendar_markets():
            meta = get_calendar_market(item["id"])
            policy = get_policy(item["id"])
            today = market_now(policy=policy).date().isoformat()
            has_calendar = db.calendar_coverage(market_id=item["id"])["count"] > 0
            today_is_trading = (
                db.is_trading_day(today, market_id=item["id"])
                if has_calendar
                else False
            )
            trade_date = (
                db.current_trade_date(market_id=item["id"]) if has_calendar else None
            )
            markets.append(
                {
                    "id": item["id"],
                    "title": meta.title,
                    "status": meta.status,
                    "timezone": policy.timezone,
                    "today": today,
                    "today_is_trading": today_is_trading,
                    "trade_date": trade_date,
                    "in_session": bool(
                        today_is_trading and in_trading_hours(market_id=item["id"])
                    ),
                    "has_calendar": has_calendar,
                    "sessions": serialize_sessions(meta),
                    "sessions_note": meta.sessions_note,
                }
            )
        return {"markets": markets}


def calendar_month_all_query(*, year: int, month: int) -> dict[str, Any]:
    """月份网格：每天有哪些市场开市，以及各市场常规时段。"""
    if month < 1 or month > 12:
        raise ProtocolError("month 必须在 1–12")
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    today = market_now().date().isoformat()
    with MarketDB(DB_PATH) as db:
        markets: list[dict[str, Any]] = []
        trading_by_date: dict[str, list[str]] = {}
        for item in list_calendar_markets():
            meta = get_calendar_market(item["id"])
            policy = get_policy(item["id"])
            coverage = db.calendar_coverage(market_id=item["id"])
            has_calendar = int(coverage["count"] or 0) > 0
            local_today = market_now(policy=policy).date().isoformat()
            if has_calendar:
                for day in db.calendar_month(year, month, market_id=item["id"])["days"]:
                    if day["is_trading"]:
                        trading_by_date.setdefault(str(day["date"]), []).append(
                            item["id"]
                        )
            markets.append(
                {
                    "id": item["id"],
                    "title": meta.title,
                    "badge": meta.badge or item["id"],
                    "status": meta.status,
                    "timezone": policy.timezone,
                    "today": local_today,
                    "in_session": bool(
                        has_calendar
                        and db.is_trading_day(local_today, market_id=item["id"])
                        and in_trading_hours(market_id=item["id"])
                    ),
                    "has_calendar": has_calendar,
                    "sessions": serialize_sessions(meta),
                    "sessions_note": meta.sessions_note,
                }
            )
        days: list[dict[str, Any]] = []
        cursor = start
        while cursor <= end:
            iso = cursor.isoformat()
            days.append({"date": iso, "markets": trading_by_date.get(iso, [])})
            cursor += timedelta(days=1)
        return {
            "year": year,
            "month": month,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "today": today,
            "days": days,
            "markets": markets,
        }


def calendar_get_query(*, market: str, year: int, month: int) -> dict[str, Any]:
    meta = get_calendar_market(market)
    policy = get_policy(market)
    today = market_now(policy=policy).date().isoformat()
    with MarketDB(DB_PATH) as db:
        payload = db.calendar_month(year, month, market_id=market)
        coverage = db.calendar_coverage(market_id=market)
        trade_date = db.current_trade_date(market_id=market)
        today_trading = db.is_trading_day(today, market_id=market)
        return {
            **payload,
            "title": meta.title,
            "status": meta.status,
            "today": today,
            "today_is_trading": today_trading,
            "trade_date": trade_date,
            "coverage": coverage,
        }


def pool_list_query(pool_id: str, *, include_removed: bool = False) -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        members = db.list_pool_members(pool_id, include_removed=include_removed)
        return {
            "pool": pool_id,
            "count": len(members),
            "members": members,
        }


def analyze_list_query(*, code: str | None = None) -> dict[str, Any]:
    return _analyze_list_query(code=code, analyze_dir=ANALYZE_DIR, db_path=DB_PATH)


def analyze_get_query(
    *, code: str, date: str, run_id: str | None = None
) -> dict[str, Any]:
    return _analyze_get_query(
        code=code,
        date=date,
        run_id=run_id,
        analyze_dir=ANALYZE_DIR,
        db_path=DB_PATH,
    )
