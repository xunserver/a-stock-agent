from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from astock_core.db import MarketDB
from astock_core.paths import (
    ANALYZE_DIR,
    DB_PATH,
    DEFAULT_ADJUST,
    DEFAULT_POOL_ID,
    pool_qlib_dir,
)
from astock_core.qlib_store import QlibStore
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
from astock_control.config import (
    get_section_view,
    load_settings,
    settings_catalog_view,
    settings_view,
)
from astock_control.protocol import (
    EVENTS_DEFAULT_LIMIT,
    NEWS_DEFAULT_LIMIT,
    ProtocolError,
    code_to_ticker,
)

from astock_core.financial_statements import extract_statement_items
REPORT_MD_FILES = (
    ("complete_report", "complete_report.md"),
    ("market", "1_analysts/market.md"),
    ("social", "1_analysts/social.md"),
    ("news", "1_analysts/news.md"),
    ("fundamentals", "1_analysts/fundamentals.md"),
    ("bull", "2_research/bull.md"),
    ("bear", "2_research/bear.md"),
    ("manager", "2_research/manager.md"),
    ("trader", "3_trading/trader.md"),
    ("aggressive", "4_risk/aggressive.md"),
    ("conservative", "4_risk/conservative.md"),
    ("neutral", "4_risk/neutral.md"),
    ("portfolio", "5_portfolio/decision.md"),
)


def handle_query(query: dict[str, Any]) -> dict[str, Any]:
    if query["type"] == "settings.catalog":
        return settings_catalog_view()
    if query["type"] == "settings.get":
        if query.get("module"):
            return get_section_view(str(query["module"]), str(query["section"]))
        return settings_view()
    if query["type"] == "pools.list":
        return pools_list_query()
    if query["type"] == "stocks.list":
        return stocks_list_query()
    if query["type"] == "stock.get":
        return stock_get_query(str(query["code"]))
    if query["type"] == "stock.financials.detail":
        return stock_financials_detail_query(
            str(query["code"]),
            sheet=str(query["sheet"]),
            report_date=str(query["report_date"]),
        )
    if query["type"] == "stock.news":
        return stock_news_query(
            str(query["code"]), limit=int(query.get("limit") or NEWS_DEFAULT_LIMIT)
        )
    if query["type"] == "stock.events":
        return stock_events_query(
            str(query["code"]),
            kind=str(query["kind"]),
            limit=int(query.get("limit") or EVENTS_DEFAULT_LIMIT),
        )
    if query["type"] == "calendar.markets":
        return calendar_markets_query()
    if query["type"] == "calendar.overview":
        return calendar_overview_query()
    if query["type"] == "calendar.month":
        return calendar_month_all_query(
            year=int(query["year"]),
            month=int(query["month"]),
        )
    if query["type"] == "calendar.get":
        return calendar_get_query(
            market=str(query["market"]),
            year=int(query["year"]),
            month=int(query["month"]),
        )
    if query["type"] == "analyze.list":
        return analyze_list_query(code=query.get("code"))
    if query["type"] == "analyze.get":
        return analyze_get_query(
            code=str(query["code"]),
            date=str(query["date"]),
            run_id=query.get("run_id"),
        )
    if query["type"] == "qlib.run.get":
        run = QlibStore().get_run(str(query["run_id"]))
        if run is None:
            raise ProtocolError(f"找不到 Qlib 运行: {query['run_id']}")
        return _with_candidate_names(run)
    pool_id = query.get("pool") or DEFAULT_POOL_ID
    if query["type"] == "qlib.overview":
        return qlib_overview_query(pool_id)
    if query["type"] == "qlib.runs":
        return {
            "pool": pool_id,
            "runs": QlibStore().list_runs(pool_id, limit=int(query.get("limit") or 20)),
        }
    if query["type"] == "status":
        return status_query(pool_id)
    if query["type"] == "pool.list":
        return pool_list_query(
            pool_id, include_removed=bool(query.get("include_removed"))
        )
    raise ValueError(f"未知查询: {query['type']}")


def _qlib_workflow_defaults() -> dict[str, Any]:
    defaults = dict((load_settings().get("qlib") or {}).get("workflow") or {})
    defaults.pop("market", None)
    return defaults


def _qlib_data_status(pool_id: str) -> dict[str, Any]:
    store = QlibStore()
    stored = store.get_pool_data(pool_id)
    root = pool_qlib_dir(pool_id)
    calendar_path = root / "calendars" / "day.txt"
    instrument_path = root / "instruments" / f"{pool_id}.txt"
    calendar = (
        [
            line.strip()
            for line in calendar_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if calendar_path.is_file()
        else []
    )
    instruments = (
        [
            line
            for line in instrument_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if instrument_path.is_file()
        else []
    )
    ready = bool(calendar and instruments)
    return {
        "ready": ready,
        "qlib_dir": str(root),
        "calendar_first": calendar[0] if calendar else None,
        "calendar_last": calendar[-1] if calendar else None,
        "pool_members": stored["pool_members"] if stored else len(instruments),
        "symbol_count": stored["symbol_count"] if stored else len(instruments),
        "prepared_at": stored["prepared_at"] if stored else None,
    }


def _next_trading_date(db: MarketDB, after: str) -> str | None:
    row = db.conn.execute(
        """
        SELECT MIN(trade_date) AS trade_date
        FROM bars_daily
        WHERE trade_date > ?
        """,
        (after,),
    ).fetchone()
    if not row or not row["trade_date"]:
        return None
    return str(row["trade_date"])


def _pct_chg_on_date(
    db: MarketDB, codes: list[str], trade_date: str
) -> dict[str, float | None]:
    if not codes:
        return {}
    placeholders = ",".join("?" * len(codes))
    rows = db.conn.execute(
        f"""
        SELECT code, pct_chg
        FROM bars_daily
        WHERE adjust = ? AND trade_date = ? AND code IN ({placeholders})
        """,
        [DEFAULT_ADJUST, trade_date, *codes],
    ).fetchall()
    return {str(row["code"]): row["pct_chg"] for row in rows}


def _with_candidate_names(run: dict[str, Any]) -> dict[str, Any]:
    result = dict(run)
    candidates = list(run.get("candidates") or [])
    if not candidates:
        return result
    as_of = str(run.get("as_of") or "")
    codes = [str(item["code"]) for item in candidates]
    with MarketDB(DB_PATH) as db:
        names = {
            str(row["code"]): str(row["name"] or "")
            for row in db.conn.execute("SELECT code, name FROM stocks").fetchall()
        }
        next_trade_date = _next_trading_date(db, as_of) if as_of else None
        returns = (
            _pct_chg_on_date(db, codes, next_trade_date)
            if next_trade_date
            else {}
        )
    if next_trade_date:
        result["next_trade_date"] = next_trade_date
    result["candidates"] = [
        {
            **item,
            "name": names.get(str(item["code"]), ""),
            "next_day_pct_chg": returns.get(str(item["code"])),
        }
        for item in candidates
    ]
    return result


def qlib_overview_query(pool_id: str) -> dict[str, Any]:
    with MarketDB(DB_PATH) as db:
        pool = next((item for item in db.list_pools() if item["id"] == pool_id), None)
    if pool is None:
        raise ProtocolError(f"找不到股票池: {pool_id}")
    store = QlibStore()
    latest = store.latest_run(pool_id)
    return {
        "pool": pool,
        "workflow": store.get_workflow(pool_id, _qlib_workflow_defaults()),
        "data": _qlib_data_status(pool_id),
        "latest_run": _with_candidate_names(latest) if latest else None,
    }


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
    rows = db.conn.execute(
        """
        SELECT p.id, p.name
        FROM pool_members m
        JOIN pools p ON p.id = m.pool_id
        WHERE m.code = ? AND m.status = 'active'
        ORDER BY p.id
        """,
        (code,),
    ).fetchall()
    return [{"id": row["id"], "name": row["name"]} for row in rows]


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
    reports: list[dict[str, Any]] = []
    root = ANALYZE_DIR / "reports"
    if root.is_dir():
        for meta_path in root.rglob("meta.json"):
            item = _read_meta_summary(meta_path)
            if item is None:
                continue
            if code and item.get("code") != code:
                continue
            reports.append(item)
    reports.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    reports = reports[:REPORT_LIST_LIMIT]
    names = _stock_names(
        {str(item.get("code") or "") for item in reports if item.get("code")}
    )
    for item in reports:
        item["name"] = names.get(str(item.get("code") or ""), "")
    return {"count": len(reports), "reports": reports}


def analyze_get_query(
    *, code: str, date: str, run_id: str | None = None
) -> dict[str, Any]:
    run_dir = _resolve_run_dir(code, date, run_id)
    meta_path = run_dir / "meta.json"
    if not meta_path.is_file():
        raise ValueError(_missing_report_message(code, date, run_id))
    meta = _load_meta(meta_path)
    if meta is None:
        raise ValueError(_missing_report_message(code, date, run_id))
    names = _stock_names({code})
    payload: dict[str, Any] = {
        "code": meta.get("code") or code,
        "ticker": meta.get("ticker") or "",
        "name": names.get(code, ""),
        "date": meta.get("date") or date,
        "run_id": meta.get("run_id") or run_dir.name,
        "analysts": meta.get("analysts")
        if isinstance(meta.get("analysts"), list)
        else [],
        "created_at": meta.get("created_at") or "",
        "status": meta.get("status") or "",
        "decision": meta.get("decision") or "",
        "report_dir": str(run_dir),
    }
    for key, relative in REPORT_MD_FILES:
        path = run_dir / relative
        if path.is_file():
            try:
                payload[key] = path.read_text(encoding="utf-8")
            except OSError:
                continue
    return payload


def _resolve_run_dir(code: str, date: str, run_id: str | None) -> Path:
    day_dir = ANALYZE_DIR / "reports" / code / date
    if run_id:
        return day_dir / run_id
    if not day_dir.is_dir():
        raise ValueError(_missing_report_message(code, date, run_id))
    candidates: list[tuple[str, Path]] = []
    for meta_path in day_dir.glob("*/meta.json"):
        meta = _load_meta(meta_path)
        created = str((meta or {}).get("created_at") or "")
        candidates.append((created, meta_path.parent))
    if not candidates:
        raise ValueError(_missing_report_message(code, date, run_id))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _read_meta_summary(meta_path: Path) -> dict[str, Any] | None:
    meta = _load_meta(meta_path)
    if meta is None:
        return None
    run_dir = meta_path.parent
    code = str(meta.get("code") or _path_code(run_dir) or "")
    date = str(meta.get("date") or _path_date(run_dir) or "")
    run_id = str(meta.get("run_id") or run_dir.name)
    return {
        "code": code,
        "ticker": str(meta.get("ticker") or ""),
        "name": str(meta.get("name") or ""),
        "date": date,
        "run_id": run_id,
        "decision": str(meta.get("decision") or ""),
        "created_at": str(meta.get("created_at") or ""),
        "status": str(meta.get("status") or ""),
        "report_dir": str(run_dir),
    }


def _load_meta(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _path_code(run_dir: Path) -> str:
    try:
        return run_dir.parent.parent.name
    except IndexError:
        return ""


def _path_date(run_dir: Path) -> str:
    try:
        return run_dir.parent.name
    except IndexError:
        return ""


def _stock_names(codes: set[str]) -> dict[str, str]:
    names = {code: "" for code in codes if code}
    if not names or not Path(DB_PATH).is_file():
        return names
    try:
        with MarketDB(DB_PATH) as db:
            for code in list(names):
                row = db.conn.execute(
                    "SELECT name FROM stocks WHERE code = ?", (code,)
                ).fetchone()
                if row and row["name"]:
                    names[code] = str(row["name"])
    except OSError:
        return names
    return names


def _missing_report_message(code: str, date: str, run_id: str | None) -> str:
    if run_id:
        return f"找不到分析报告: {code} {date} {run_id}"
    return f"找不到分析报告: {code} {date}"
