from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from astock_core.db import MarketDB
from astock_core.paths import DEFAULT_ADJUST
from astock_core.qlib_store import QlibStore
from astock_control.protocol import ProtocolError


def qlib_run_view(run: dict[str, Any], *, db_path: Path) -> dict[str, Any]:
    result = dict(run)
    candidates = list(run.get("candidates") or [])
    if not candidates:
        return result
    as_of = str(run.get("as_of") or "")
    codes = [str(item["code"]) for item in candidates]
    with MarketDB(db_path) as db:
        names = db.stock_names()
        next_trade_date = db.next_bar_date(as_of) if as_of else None
        returns = (
            db.pct_changes_on_date(codes, next_trade_date, adjust=DEFAULT_ADJUST)
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


def qlib_overview_query(
    pool_id: str,
    *,
    db_path: Path,
    pool_dir: Callable[[str], Path],
    workflow_defaults: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    with MarketDB(db_path) as db:
        pool = next((item for item in db.list_pools() if item["id"] == pool_id), None)
    if pool is None:
        raise ProtocolError(f"找不到股票池: {pool_id}")
    store = QlibStore()
    latest = store.latest_run(pool_id)
    return {
        "pool": pool,
        "workflow": store.get_workflow(pool_id, workflow_defaults()),
        "data": _qlib_data_status(pool_id, pool_dir),
        "latest_run": qlib_run_view(latest, db_path=db_path) if latest else None,
    }


def _qlib_data_status(
    pool_id: str, pool_dir: Callable[[str], Path]
) -> dict[str, Any]:
    store = QlibStore()
    stored = store.get_pool_data(pool_id)
    root = pool_dir(pool_id)
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
