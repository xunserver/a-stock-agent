from __future__ import annotations

import json
import sqlite3

from astock_core.db import MarketDB
from astock_core.financial_statements import extract_statement_items


def test_market_migrations_are_versioned_and_repeatable(tmp_path) -> None:
    path = tmp_path / "legacy-market.db"
    legacy = sqlite3.connect(path)
    legacy.executescript(
        """
        CREATE TABLE stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO stocks VALUES ('000001', '平安银行', '2026-01-01T00:00:00');
        CREATE TABLE trade_calendar (trade_date TEXT PRIMARY KEY);
        INSERT INTO trade_calendar VALUES ('2026-08-26');
        """
    )
    legacy.close()

    with MarketDB(path) as db:
        assert db.get_stock("000001")["name"] == "平安银行"
        assert db.is_trading_day("2026-08-26", market_id="cn_a")
        assert db.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert db.conn.execute(
            "SELECT version FROM _schema_migrations WHERE namespace = 'market'"
        ).fetchone()[0] == 6

    with MarketDB(path) as db:
        assert db.get_stock("000001")["name"] == "平安银行"
        assert db.calendar_coverage(market_id="cn_a")["count"] == 1
        assert db.conn.execute(
            "SELECT version FROM _schema_migrations WHERE namespace = 'market'"
        ).fetchone()[0] == 6


def test_legacy_board_source_migrates_to_eastmoney_taxonomy(tmp_path) -> None:
    path = tmp_path / "legacy-boards.db"
    legacy = sqlite3.connect(path)
    legacy.executescript(
        """
        CREATE TABLE stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO stocks VALUES ('000001', '平安银行', '2026-01-01T00:00:00');
        CREATE TABLE boards (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'em',
            updated_at TEXT NOT NULL
        );
        INSERT INTO boards VALUES ('BK1027', 'industry', '小金属', 'em', '2026-01-01T00:00:00');
        """
    )
    legacy.close()

    with MarketDB(path) as db:
        boards = db.list_boards(kind="industry")
        assert boards[0]["source"] == "eastmoney"


def test_legacy_statement_payload_migrates_to_canonical_read_model(tmp_path) -> None:
    path = tmp_path / "legacy-statements.db"
    legacy = sqlite3.connect(path)
    legacy.executescript(
        """
        CREATE TABLE stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO stocks VALUES ('000001', '平安银行', '2026-01-01T00:00:00');
        CREATE TABLE financial_statements (
            code TEXT NOT NULL,
            report_date TEXT NOT NULL,
            sheet TEXT NOT NULL,
            report_type TEXT,
            notice_date TEXT,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (code, report_date, sheet)
        );
        """
    )
    legacy.execute(
        """
        INSERT INTO financial_statements
        (code, report_date, sheet, report_type, notice_date, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "000001",
            "2026-06-30",
            "profit",
            "2026中报",
            "2026-08-15",
            json.dumps({"OPERATE_INCOME": 100.0, "NETPROFIT": 20.0}),
            "2026-08-15T00:00:00",
        ),
    )
    legacy.commit()
    legacy.close()

    with MarketDB(path) as db:
        stored = db.conn.execute(
            "SELECT payload_json FROM financial_statements WHERE code = '000001'"
        ).fetchone()
        payload = json.loads(stored["payload_json"])
        assert payload["schema"] == "statement_items_v1"
        row = db.get_financial_statement("000001", "2026-06-30", "profit")
        assert row is not None
        assert row["payload"]["operating_revenue"] == 100.0
        assert row["payload"]["net_profit"] == 20.0
        items = extract_statement_items("profit", row["payload"])
        assert items[0]["key"] == "operating_revenue"
        assert items[0]["label"] == "营业收入"
