from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from astock_core._market_schema import migrate_market
from astock_core._sqlite import connect
from astock_core.paths import DATA_DIR, DB_PATH

if TYPE_CHECKING:
    from astock_core.db import MarketDB

_POOL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")

BAR_TABLES = {
    "daily": "bars_daily",
    "weekly": "bars_weekly",
    "monthly": "bars_monthly",
}
INGEST_KINDS = {
    "daily": "stock",
    "weekly": "stock_weekly",
    "monthly": "stock_monthly",
}


def _quote_sync_fields(last_bar: str | None, last_cal: str | None) -> dict[str, object]:
    if last_bar is None:
        plan = "full"
    elif last_cal and last_bar >= last_cal:
        plan = "current"
    else:
        plan = "fill"
    return {"quote_plan": plan, "needs_sync": plan != "current"}


def _preview_codes(codes: list[str], limit: int = 12) -> str:
    if len(codes) <= limit:
        return ", ".join(codes)
    return f"{', '.join(codes[:limit])} 等 {len(codes)} 只"


def _ymd(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


class _MarketBase:
    """Shared SQLite connection lifecycle for the MarketDB domain mixins."""

    conn: sqlite3.Connection

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = connect(self.path)
        migrate_market(self.conn)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> MarketDB:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
