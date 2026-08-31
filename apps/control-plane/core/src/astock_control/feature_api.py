from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from astock_core.paths import DEFAULT_POOL_ID
from astock_core.qlib_store import QlibStore

from astock_control.config import get_section_view, settings_catalog_view, settings_view
from astock_control.protocol import EVENTS_DEFAULT_LIMIT, NEWS_DEFAULT_LIMIT, ProtocolError
from astock_control.queries import (
    analyze_get_query,
    analyze_list_query,
    calendar_get_query,
    calendar_markets_query,
    calendar_month_all_query,
    calendar_overview_query,
    pool_list_query,
    pools_list_query,
    qlib_overview_query,
    qlib_run_view,
    status_query,
    stock_events_query,
    stock_financials_detail_query,
    stock_get_query,
    stock_news_query,
    stocks_list_query,
)

router = APIRouter(prefix="/api", tags=["features"])


@router.get("/status")
def get_status(pool: str = DEFAULT_POOL_ID) -> dict[str, Any]:
    return status_query(pool)


@router.get("/pools")
def list_pools() -> dict[str, Any]:
    return pools_list_query()


@router.get("/pools/{pool_id}/members")
def list_pool_members(
    pool_id: str,
    include_removed: bool = False,
) -> dict[str, Any]:
    return pool_list_query(pool_id, include_removed=include_removed)


@router.get("/stocks")
def list_stocks() -> dict[str, Any]:
    return stocks_list_query()


@router.get("/stocks/{code}")
def get_stock(code: str) -> dict[str, Any]:
    return stock_get_query(code)


@router.get("/stocks/{code}/news")
def get_stock_news(
    code: str,
    limit: int = Query(default=NEWS_DEFAULT_LIMIT, ge=1, le=100),
) -> dict[str, Any]:
    return stock_news_query(code, limit=limit)


@router.get("/stocks/{code}/events/{kind}")
def get_stock_events(
    code: str,
    kind: str,
    limit: int = Query(default=EVENTS_DEFAULT_LIMIT, ge=1, le=100),
) -> dict[str, Any]:
    return stock_events_query(code, kind=kind, limit=limit)


@router.get("/stocks/{code}/financial-statements/{sheet}/{report_date}")
def get_financial_statement(
    code: str,
    sheet: str,
    report_date: str,
) -> dict[str, Any]:
    return stock_financials_detail_query(
        code,
        sheet=sheet,
        report_date=report_date,
    )


@router.get("/calendars/markets")
def list_calendar_markets() -> dict[str, Any]:
    return calendar_markets_query()


@router.get("/calendars/overview")
def get_calendar_overview() -> dict[str, Any]:
    return calendar_overview_query()


@router.get("/calendars/month")
def get_all_calendar_months(year: int, month: int) -> dict[str, Any]:
    return calendar_month_all_query(year=year, month=month)


@router.get("/calendars/{market}/{year}/{month}")
def get_calendar_month(market: str, year: int, month: int) -> dict[str, Any]:
    return calendar_get_query(market=market, year=year, month=month)


@router.get("/settings/catalog")
def get_settings_catalog() -> dict[str, Any]:
    return settings_catalog_view()


@router.get("/settings")
def get_settings(
    module: str | None = None,
    section: str | None = None,
) -> dict[str, Any]:
    if module is None and section is None:
        return settings_view()
    if not module or not section:
        raise ProtocolError("module 和 section 必须同时提供")
    return get_section_view(module, section)


@router.get("/qlib/overview")
def get_qlib_overview(pool: str = DEFAULT_POOL_ID) -> dict[str, Any]:
    return qlib_overview_query(pool)


@router.get("/qlib/runs")
def list_qlib_runs(
    pool: str = DEFAULT_POOL_ID,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    return {"pool": pool, "runs": QlibStore().list_runs(pool, limit=limit)}


@router.get("/qlib/runs/{run_id}")
def get_qlib_run(run_id: str) -> dict[str, Any]:
    run = QlibStore().get_run(run_id)
    if run is None:
        raise ProtocolError(f"找不到 Qlib 运行: {run_id}")
    return qlib_run_view(run)


@router.get("/analyses")
def list_analyses(code: str | None = None) -> dict[str, Any]:
    return analyze_list_query(code=code)


@router.get("/analyses/{code}/{date}")
def get_analysis(
    code: str,
    date: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    return analyze_get_query(code=code, date=date, run_id=run_id)
