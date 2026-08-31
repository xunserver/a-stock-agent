"""Private schema and migrations for the market-data SQLite namespace."""

from __future__ import annotations

import sqlite3

from astock_core._sqlite import apply_migrations
from astock_core.financial_statements import (
    deserialize_statement_items,
    serialize_statement_items,
)
from astock_core.session import DEFAULT_MARKET


MARKET_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS stocks (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trade_calendar (
    market_id TEXT NOT NULL, trade_date TEXT NOT NULL,
    PRIMARY KEY (market_id, trade_date)
);
CREATE TABLE IF NOT EXISTS bars_daily (
    code TEXT NOT NULL, trade_date TEXT NOT NULL, open REAL, close REAL, high REAL, low REAL,
    volume REAL, amount REAL, amplitude REAL, pct_chg REAL, change_amount REAL, turnover REAL,
    adjust TEXT NOT NULL, PRIMARY KEY (code, trade_date, adjust)
);
CREATE INDEX IF NOT EXISTS idx_bars_daily_date ON bars_daily (trade_date);
CREATE TABLE IF NOT EXISTS bars_weekly (
    code TEXT NOT NULL, trade_date TEXT NOT NULL, open REAL, close REAL, high REAL, low REAL,
    volume REAL, amount REAL, amplitude REAL, pct_chg REAL, change_amount REAL, turnover REAL,
    adjust TEXT NOT NULL, PRIMARY KEY (code, trade_date, adjust)
);
CREATE INDEX IF NOT EXISTS idx_bars_weekly_date ON bars_weekly (trade_date);
CREATE TABLE IF NOT EXISTS bars_monthly (
    code TEXT NOT NULL, trade_date TEXT NOT NULL, open REAL, close REAL, high REAL, low REAL,
    volume REAL, amount REAL, amplitude REAL, pct_chg REAL, change_amount REAL, turnover REAL,
    adjust TEXT NOT NULL, PRIMARY KEY (code, trade_date, adjust)
);
CREATE INDEX IF NOT EXISTS idx_bars_monthly_date ON bars_monthly (trade_date);
CREATE TABLE IF NOT EXISTS index_daily (
    code TEXT NOT NULL, name TEXT NOT NULL, trade_date TEXT NOT NULL, open REAL, close REAL,
    high REAL, low REAL, volume REAL, amount REAL, PRIMARY KEY (code, trade_date)
);
CREATE TABLE IF NOT EXISTS universe_members (
    universe TEXT NOT NULL, code TEXT NOT NULL, name TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (universe, code)
);
CREATE TABLE IF NOT EXISTS ingest_state (
    code TEXT NOT NULL, kind TEXT NOT NULL, adjust TEXT NOT NULL DEFAULT '', last_trade_date TEXT,
    rows INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, error TEXT, updated_at TEXT NOT NULL,
    PRIMARY KEY (code, kind, adjust)
);
CREATE TABLE IF NOT EXISTS pools (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pool_members (
    pool_id TEXT NOT NULL, code TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual', first_added_at TEXT NOT NULL, last_added_at TEXT NOT NULL,
    removed_at TEXT, sort_order INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (pool_id, code)
);
CREATE INDEX IF NOT EXISTS idx_pool_members_status ON pool_members (pool_id, status);
CREATE TABLE IF NOT EXISTS boards (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'eastmoney',
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_boards_kind ON boards (kind);
CREATE TABLE IF NOT EXISTS board_members (
    board_id TEXT NOT NULL, code TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (board_id, code)
);
CREATE INDEX IF NOT EXISTS idx_board_members_code ON board_members (code);
CREATE TABLE IF NOT EXISTS financial_reports (
    code TEXT NOT NULL, report_date TEXT NOT NULL, report_type TEXT, notice_date TEXT, eps REAL,
    bps REAL, roe REAL, revenue REAL, revenue_yoy REAL, net_profit REAL, net_profit_yoy REAL,
    gross_margin REAL, net_margin REAL, debt_ratio REAL, updated_at TEXT NOT NULL,
    PRIMARY KEY (code, report_date)
);
CREATE INDEX IF NOT EXISTS idx_financial_reports_code_date
    ON financial_reports (code, report_date DESC);
CREATE TABLE IF NOT EXISTS financial_statements (
    code TEXT NOT NULL, report_date TEXT NOT NULL, sheet TEXT NOT NULL, report_type TEXT,
    notice_date TEXT, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (code, report_date, sheet)
);
CREATE INDEX IF NOT EXISTS idx_financial_statements_code_sheet_date
    ON financial_statements (code, sheet, report_date DESC);
"""

_STOCK_PROFILE_COLUMNS = (
    ("industry", "TEXT"), ("list_date", "TEXT"), ("total_shares", "REAL"),
    ("float_shares", "REAL"), ("total_mv", "REAL"), ("float_mv", "REAL"),
    ("latest_price", "REAL"), ("is_st", "INTEGER NOT NULL DEFAULT 0"),
    ("is_suspended", "INTEGER NOT NULL DEFAULT 0"), ("suspend_info", "TEXT"),
    ("region", "TEXT"), ("pe_dyn", "REAL"), ("pe_static", "REAL"), ("pb", "REAL"),
    ("volume_ratio", "REAL"), ("high_limit", "REAL"), ("low_limit", "REAL"),
    ("pre_close", "REAL"), ("avg_price", "REAL"), ("outer_vol", "REAL"),
    ("inner_vol", "REAL"), ("eps", "REAL"), ("bps", "REAL"), ("roe", "REAL"),
    ("revenue", "REAL"), ("revenue_yoy", "REAL"), ("net_profit", "REAL"),
    ("net_profit_yoy", "REAL"), ("gross_margin", "REAL"), ("net_margin", "REAL"),
    ("debt_ratio", "REAL"),
)


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(MARKET_SCHEMA)


def _add_stock_profile_columns(connection: sqlite3.Connection) -> None:
    existing = _columns(connection, "stocks")
    for name, declaration in _STOCK_PROFILE_COLUMNS:
        if name not in existing:
            connection.execute(f"ALTER TABLE stocks ADD COLUMN {name} {declaration}")


def _add_trade_calendar_market(connection: sqlite3.Connection) -> None:
    columns = _columns(connection, "trade_calendar")
    if not columns or "market_id" in columns:
        return
    connection.execute(
        "CREATE TABLE trade_calendar__market (market_id TEXT NOT NULL, trade_date TEXT NOT NULL, PRIMARY KEY (market_id, trade_date))"
    )
    connection.execute(
        "INSERT OR IGNORE INTO trade_calendar__market (market_id, trade_date) SELECT ?, trade_date FROM trade_calendar",
        (DEFAULT_MARKET,),
    )
    connection.execute("DROP TABLE trade_calendar")
    connection.execute("ALTER TABLE trade_calendar__market RENAME TO trade_calendar")


def _add_pool_member_sort_order(connection: sqlite3.Connection) -> None:
    columns = _columns(connection, "pool_members")
    if not columns:
        return
    if "sort_order" not in columns:
        connection.execute("ALTER TABLE pool_members ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
        for pool in connection.execute("SELECT DISTINCT pool_id FROM pool_members"):
            rows = connection.execute(
                "SELECT code FROM pool_members WHERE pool_id = ? ORDER BY status, code",
                (pool["pool_id"],),
            ).fetchall()
            for index, row in enumerate(rows):
                connection.execute(
                    "UPDATE pool_members SET sort_order = ? WHERE pool_id = ? AND code = ?",
                    (index, pool["pool_id"], row["code"]),
                )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pool_members_sort ON pool_members (pool_id, status, sort_order)"
    )


def _normalize_statement_payloads(connection: sqlite3.Connection) -> None:
    """Rewrite legacy Eastmoney-keyed statement JSON into normalized items."""
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "financial_statements" not in tables:
        return
    rows = connection.execute(
        """
        SELECT code, report_date, sheet, payload_json
        FROM financial_statements
        """
    ).fetchall()
    for row in rows:
        raw = row["payload_json"] if isinstance(row, sqlite3.Row) else row[3]
        items = deserialize_statement_items(raw)
        normalized = serialize_statement_items(items)
        if normalized == raw:
            continue
        connection.execute(
            """
            UPDATE financial_statements
            SET payload_json = ?
            WHERE code = ? AND report_date = ? AND sheet = ?
            """,
            (
                normalized,
                row["code"] if isinstance(row, sqlite3.Row) else row[0],
                row["report_date"] if isinstance(row, sqlite3.Row) else row[1],
                row["sheet"] if isinstance(row, sqlite3.Row) else row[2],
            ),
        )


def _normalize_board_taxonomy(connection: sqlite3.Connection) -> None:
    """Rewrite legacy Eastmoney board source keys to canonical taxonomy values."""
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "boards" not in tables:
        return
    connection.execute(
        "UPDATE boards SET source = ? WHERE source = ?",
        ("eastmoney", "em"),
    )


def migrate_market(connection: sqlite3.Connection) -> None:
    """Upgrade a market database in place without changing domain data."""
    apply_migrations(
        connection,
        namespace="market",
        migrations=(
            _create_schema,
            _add_stock_profile_columns,
            _add_trade_calendar_market,
            _add_pool_member_sort_order,
            _normalize_statement_payloads,
            _normalize_board_taxonomy,
        ),
    )
