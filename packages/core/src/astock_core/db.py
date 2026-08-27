from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from astock_core.paths import DATA_DIR, DB_PATH, DEFAULT_ADJUST, DEFAULT_POOL_ID

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

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stocks (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_calendar (
    trade_date TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS bars_daily (
    code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    close REAL,
    high REAL,
    low REAL,
    volume REAL,
    amount REAL,
    amplitude REAL,
    pct_chg REAL,
    change_amount REAL,
    turnover REAL,
    adjust TEXT NOT NULL,
    PRIMARY KEY (code, trade_date, adjust)
);

CREATE INDEX IF NOT EXISTS idx_bars_daily_date
    ON bars_daily (trade_date);

CREATE TABLE IF NOT EXISTS bars_weekly (
    code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    close REAL,
    high REAL,
    low REAL,
    volume REAL,
    amount REAL,
    amplitude REAL,
    pct_chg REAL,
    change_amount REAL,
    turnover REAL,
    adjust TEXT NOT NULL,
    PRIMARY KEY (code, trade_date, adjust)
);

CREATE INDEX IF NOT EXISTS idx_bars_weekly_date
    ON bars_weekly (trade_date);

CREATE TABLE IF NOT EXISTS bars_monthly (
    code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    close REAL,
    high REAL,
    low REAL,
    volume REAL,
    amount REAL,
    amplitude REAL,
    pct_chg REAL,
    change_amount REAL,
    turnover REAL,
    adjust TEXT NOT NULL,
    PRIMARY KEY (code, trade_date, adjust)
);

CREATE INDEX IF NOT EXISTS idx_bars_monthly_date
    ON bars_monthly (trade_date);

CREATE TABLE IF NOT EXISTS index_daily (
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    close REAL,
    high REAL,
    low REAL,
    volume REAL,
    amount REAL,
    PRIMARY KEY (code, trade_date)
);

CREATE TABLE IF NOT EXISTS universe_members (
    universe TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (universe, code)
);

CREATE TABLE IF NOT EXISTS ingest_state (
    code TEXT NOT NULL,
    kind TEXT NOT NULL,
    adjust TEXT NOT NULL DEFAULT '',
    last_trade_date TEXT,
    rows INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    error TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (code, kind, adjust)
);

CREATE TABLE IF NOT EXISTS pools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pool_members (
    pool_id TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    first_added_at TEXT NOT NULL,
    last_added_at TEXT NOT NULL,
    removed_at TEXT,
    PRIMARY KEY (pool_id, code)
);

CREATE INDEX IF NOT EXISTS idx_pool_members_status
    ON pool_members (pool_id, status);

CREATE TABLE IF NOT EXISTS boards (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'em',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_boards_kind
    ON boards (kind);

CREATE TABLE IF NOT EXISTS board_members (
    board_id TEXT NOT NULL,
    code TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (board_id, code)
);

CREATE INDEX IF NOT EXISTS idx_board_members_code
    ON board_members (code);
"""


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


class MarketDB:
    """SQLite 行情库：日历、股票列表、日/周/月线、采集进度。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate_stock_profile_columns()
        self.ensure_pool(DEFAULT_POOL_ID, "默认股票池")
        self._migrate_universe_into_default_pool()

    def close(self) -> None:
        self.conn.close()

    def _migrate_stock_profile_columns(self) -> None:
        existing = {
            row[1] for row in self.conn.execute("PRAGMA table_info(stocks)")
        }
        columns = [
            ("industry", "TEXT"),
            ("list_date", "TEXT"),
            ("total_shares", "REAL"),
            ("float_shares", "REAL"),
            ("total_mv", "REAL"),
            ("float_mv", "REAL"),
            ("latest_price", "REAL"),
            ("is_st", "INTEGER NOT NULL DEFAULT 0"),
            ("is_suspended", "INTEGER NOT NULL DEFAULT 0"),
            ("suspend_info", "TEXT"),
            ("region", "TEXT"),
            ("pe_dyn", "REAL"),
            ("pe_static", "REAL"),
            ("pb", "REAL"),
            ("volume_ratio", "REAL"),
            ("high_limit", "REAL"),
            ("low_limit", "REAL"),
            ("pre_close", "REAL"),
            ("avg_price", "REAL"),
            ("outer_vol", "REAL"),
            ("inner_vol", "REAL"),
            ("eps", "REAL"),
            ("bps", "REAL"),
            ("roe", "REAL"),
            ("revenue", "REAL"),
            ("revenue_yoy", "REAL"),
            ("net_profit", "REAL"),
            ("net_profit_yoy", "REAL"),
            ("gross_margin", "REAL"),
            ("net_margin", "REAL"),
            ("debt_ratio", "REAL"),
        ]
        with self.conn:
            for name, decl in columns:
                if name not in existing:
                    self.conn.execute(f"ALTER TABLE stocks ADD COLUMN {name} {decl}")

    def upsert_stock_profile(self, code: str, *, name: str, **fields: object) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        allowed = {
            "industry",
            "list_date",
            "total_shares",
            "float_shares",
            "total_mv",
            "float_mv",
            "latest_price",
            "is_st",
            "is_suspended",
            "suspend_info",
            "region",
            "pe_dyn",
            "pe_static",
            "pb",
            "volume_ratio",
            "high_limit",
            "low_limit",
            "pre_close",
            "avg_price",
            "outer_vol",
            "inner_vol",
            "eps",
            "bps",
            "roe",
            "revenue",
            "revenue_yoy",
            "net_profit",
            "net_profit_yoy",
            "gross_margin",
            "net_margin",
            "debt_ratio",
        }
        data = {key: fields[key] for key in allowed if key in fields}
        assignments = ", ".join(f"{key} = excluded.{key}" for key in ("name", *data))
        columns = ["code", "name", *data, "updated_at"]
        values = [code, name, *data.values(), now]
        placeholders = ", ".join("?" * len(columns))
        with self.conn:
            self.conn.execute(
                f"""
                INSERT INTO stocks ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(code) DO UPDATE SET
                    {assignments},
                    updated_at = excluded.updated_at
                """,
                values,
            )

    def get_stock(self, code: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM stocks WHERE code = ?",
            (code,),
        ).fetchone()
        return dict(row) if row else None

    def pool_membership(self, pool_id: str, code: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT * FROM pool_members
            WHERE pool_id = ? AND code = ?
            """,
            (pool_id, code),
        ).fetchone()
        return dict(row) if row else None

    def latest_bar(self, code: str, adjust: str = DEFAULT_ADJUST) -> dict | None:
        row = self.conn.execute(
            """
            SELECT * FROM bars_daily
            WHERE code = ? AND adjust = ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (code, adjust),
        ).fetchone()
        return dict(row) if row else None

    def list_daily_bars(
        self,
        code: str,
        *,
        adjust: str = DEFAULT_ADJUST,
        limit: int | None = None,
    ) -> list[dict]:
        return self.list_bars(code, period="daily", adjust=adjust, limit=limit)

    def list_bars(
        self,
        code: str,
        *,
        period: str = "daily",
        adjust: str = DEFAULT_ADJUST,
        limit: int | None = None,
    ) -> list[dict]:
        if period == "yearly":
            return self.list_yearly_bars(code, adjust=adjust, limit=limit)
        table = BAR_TABLES.get(period)
        if table is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        sql = f"""
            SELECT trade_date, open, close, high, low, volume, amount,
                   pct_chg, turnover, amplitude, change_amount
            FROM {table}
            WHERE code = ? AND adjust = ?
            ORDER BY trade_date DESC
        """
        params: list = [code, adjust]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in reversed(rows)]

    def list_yearly_bars(
        self,
        code: str,
        *,
        adjust: str = DEFAULT_ADJUST,
        limit: int | None = None,
    ) -> list[dict]:
        """年 K：优先用月线聚合，没有月线再用日线。"""
        source = self.list_bars(code, period="monthly", adjust=adjust)
        if not source:
            source = self.list_bars(code, period="daily", adjust=adjust)
        if not source:
            return []

        grouped: dict[str, list[dict]] = {}
        for bar in source:
            year = str(bar.get("trade_date") or "")[:4]
            if len(year) != 4:
                continue
            grouped.setdefault(year, []).append(bar)

        yearly: list[dict] = []
        prev_close: float | None = None
        for year in sorted(grouped):
            rows = grouped[year]
            first = rows[0]
            last = rows[-1]
            opens = [row["open"] for row in rows if row.get("open") is not None]
            highs = [row["high"] for row in rows if row.get("high") is not None]
            lows = [row["low"] for row in rows if row.get("low") is not None]
            close = last.get("close")
            open_ = opens[0] if opens else first.get("open")
            high = max(highs) if highs else None
            low = min(lows) if lows else None
            volume = sum(float(row["volume"]) for row in rows if row.get("volume") is not None) or None
            amount = sum(float(row["amount"]) for row in rows if row.get("amount") is not None) or None
            change_amount = None
            pct_chg = None
            if close is not None and prev_close not in (None, 0):
                change_amount = float(close) - float(prev_close)
                pct_chg = change_amount / float(prev_close) * 100
            amplitude = None
            if high is not None and low is not None and prev_close not in (None, 0):
                amplitude = (float(high) - float(low)) / float(prev_close) * 100
            yearly.append(
                {
                    "trade_date": last.get("trade_date"),
                    "open": open_,
                    "close": close,
                    "high": high,
                    "low": low,
                    "volume": volume,
                    "amount": amount,
                    "pct_chg": pct_chg,
                    "turnover": None,
                    "amplitude": amplitude,
                    "change_amount": change_amount,
                }
            )
            if close is not None:
                prev_close = float(close)

        if limit is not None:
            return yearly[-limit:]
        return yearly

    def bar_summary(self, code: str, adjust: str = DEFAULT_ADJUST) -> dict:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS n, MIN(trade_date) AS first, MAX(trade_date) AS last
            FROM bars_daily
            WHERE code = ? AND adjust = ?
            """,
            (code, adjust),
        ).fetchone()
        first = row["first"]
        last = row["last"]
        last_cal = self.last_calendar_date()
        missing = 0
        if first and last_cal:
            missing = int(
                self.conn.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM trade_calendar c
                    WHERE c.trade_date >= ?
                      AND c.trade_date <= ?
                      AND NOT EXISTS (
                        SELECT 1 FROM bars_daily b
                        WHERE b.code = ? AND b.adjust = ? AND b.trade_date = c.trade_date
                      )
                    """,
                    (first, last_cal, code, adjust),
                ).fetchone()["n"]
            )
        return {
            "adjust": adjust,
            "bars": int(row["n"] or 0),
            "first": first,
            "last": last,
            "calendar_as_of": last_cal,
            "missing_sessions": missing,
        }

    def profile_filled_count(self, pool_id: str | None = None) -> int:
        if pool_id is None:
            row = self.conn.execute(
                """
                SELECT COUNT(*) AS n FROM stocks
                WHERE industry IS NOT NULL AND industry != ''
                """
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM pool_members m
                JOIN stocks s ON s.code = m.code
                WHERE m.pool_id = ? AND m.status = 'active'
                  AND s.industry IS NOT NULL AND s.industry != ''
                """,
                (pool_id,),
            ).fetchone()
        return int(row["n"] or 0)

    def __enter__(self) -> MarketDB:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def replace_calendar(self, dates: list[date | str]) -> int:
        rows = [(_ymd(item),) for item in dates]
        with self.conn:
            self.conn.execute("DELETE FROM trade_calendar")
            self.conn.executemany(
                "INSERT OR IGNORE INTO trade_calendar (trade_date) VALUES (?)",
                rows,
            )
        return len(rows)

    def last_calendar_date(self, as_of: date | None = None) -> str | None:
        today = (as_of or date.today()).isoformat()
        row = self.conn.execute(
            "SELECT MAX(trade_date) AS d FROM trade_calendar WHERE trade_date <= ?",
            (today,),
        ).fetchone()
        return row["d"] if row and row["d"] else None

    def replace_stocks(self, stocks: list[tuple[str, str]]) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        payload = [(code, name, now) for code, name in stocks]
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO stocks (code, name, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return len(payload)

    def stock_codes(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT code FROM stocks ORDER BY code"
        ).fetchall()
        return [row["code"] for row in rows]

    def upsert_boards(self, rows: list[tuple[str, str, str, str]]) -> int:
        """rows: (id, kind, name, source)."""
        if not rows:
            return 0
        now = datetime.now().isoformat(timespec="seconds")
        payload = [(board_id, kind, name, source, now) for board_id, kind, name, source in rows]
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO boards (id, kind, name, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kind = excluded.kind,
                    name = excluded.name,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return len(payload)

    def replace_board_members(self, board_id: str, codes: list[str]) -> int:
        """按板块替换成员；只保留已在 stocks 表中的代码。"""
        now = datetime.now().isoformat(timespec="seconds")
        unique = sorted({str(code).zfill(6) for code in codes if str(code).strip()})
        if unique:
            placeholders = ",".join("?" for _ in unique)
            allowed = {
                row["code"]
                for row in self.conn.execute(
                    f"SELECT code FROM stocks WHERE code IN ({placeholders})",
                    unique,
                ).fetchall()
            }
            unique = sorted(code for code in unique if code in allowed)
        with self.conn:
            self.conn.execute("DELETE FROM board_members WHERE board_id = ?", (board_id,))
            if unique:
                self.conn.executemany(
                    """
                    INSERT INTO board_members (board_id, code, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    [(board_id, code, now) for code in unique],
                )
        return len(unique)

    def list_boards(self, *, kind: str | None = None, source: str | None = "em") -> list[dict]:
        clauses: list[str] = []
        params: list[str] = []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if source:
            clauses.append("source = ?")
            params.append(source)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"""
            SELECT id, kind, name, source, updated_at
            FROM boards
            {where}
            ORDER BY kind, name
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def boards_for_code(self, code: str, *, source: str | None = "em") -> list[dict]:
        params: list[str] = [code.zfill(6)]
        source_clause = ""
        if source:
            source_clause = "AND b.source = ?"
            params.append(source)
        rows = self.conn.execute(
            f"""
            SELECT b.id, b.kind, b.name, b.source, b.updated_at
            FROM board_members m
            JOIN boards b ON b.id = m.board_id
            WHERE m.code = ? {source_clause}
            ORDER BY b.kind, b.name
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def list_stocks(self, *, adjust: str = DEFAULT_ADJUST) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT
                s.code,
                s.name,
                s.industry,
                s.is_st,
                s.is_suspended,
                (
                    SELECT MAX(b.trade_date)
                    FROM bars_daily b
                    WHERE b.code = s.code AND b.adjust = ?
                ) AS last_bar
            FROM stocks s
            ORDER BY s.code
            """,
            (adjust,),
        ).fetchall()
        pool_rows = self.conn.execute(
            """
            SELECT m.code, p.id, p.name
            FROM pool_members m
            JOIN pools p ON p.id = m.pool_id
            WHERE m.status = 'active'
            ORDER BY p.id
            """
        ).fetchall()
        pools_by_code: dict[str, list[dict]] = {}
        for row in pool_rows:
            pools_by_code.setdefault(row["code"], []).append(
                {"id": row["id"], "name": row["name"]}
            )
        return [
            {
                "code": row["code"],
                "name": row["name"],
                "industry": row["industry"],
                "is_st": int(row["is_st"] or 0),
                "is_suspended": int(row["is_suspended"] or 0),
                "last_bar": row["last_bar"],
                "pools": pools_by_code.get(row["code"], []),
            }
            for row in rows
        ]

    def add_stocks(self, stocks: list[tuple[str, str]]) -> dict[str, int]:
        catalog = set(self.stock_codes())
        added = 0
        unchanged = 0
        seen: set[str] = set()
        unique: list[tuple[str, str]] = []
        for code, name in stocks:
            if code in seen:
                continue
            seen.add(code)
            unique.append((code, name))
            if code in catalog:
                unchanged += 1
            else:
                added += 1
        if unique:
            self.replace_stocks(unique)
        return {"added": added, "unchanged": unchanged, "count": len(self.stock_codes())}

    def active_pools_for_code(self, code: str) -> list[dict]:
        rows = self.conn.execute(
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

    def remove_stocks(self, codes: list[str]) -> dict:
        catalog = set(self.stock_codes())
        missing = [code for code in codes if code not in catalog]
        present = [code for code in codes if code in catalog]
        blocked: list[tuple[str, list[dict]]] = []
        removable: list[str] = []
        for code in present:
            pools = self.active_pools_for_code(code)
            if pools:
                blocked.append((code, pools))
            else:
                removable.append(code)
        if blocked:
            parts = []
            for code, pools in blocked:
                names = "、".join(str(pool["name"] or pool["id"]) for pool in pools)
                parts.append(f"{code}（{names}）")
            raise ValueError(f"这些股票还在股票池里，不能从系统移除: {'; '.join(parts)}")
        if not removable:
            raise ValueError(f"找不到股票: {_preview_codes(missing)}")
        with self.conn:
            for code in removable:
                self.conn.execute("DELETE FROM pool_members WHERE code = ?", (code,))
                self.conn.execute("DELETE FROM stocks WHERE code = ?", (code,))
        return {"removed": len(removable), "missing": len(missing), "codes": removable}

    def replace_universe(self, universe: str, members: list[tuple[str, str]]) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        payload = [(universe, code, name, now) for code, name in members]
        with self.conn:
            self.conn.execute(
                "DELETE FROM universe_members WHERE universe = ?",
                (universe,),
            )
            self.conn.executemany(
                """
                INSERT INTO universe_members (universe, code, name, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                payload,
            )
        return len(payload)

    def universe_codes(self, universe: str) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT code FROM universe_members
            WHERE universe = ?
            ORDER BY code
            """,
            (universe,),
        ).fetchall()
        return [row["code"] for row in rows]

    def universe_size(self, universe: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM universe_members WHERE universe = ?",
            (universe,),
        ).fetchone()
        return int(row["n"])

    def ensure_pool(self, pool_id: str = DEFAULT_POOL_ID, name: str = "默认股票池") -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO pools (id, name, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (pool_id, name, now),
            )

    def list_pools(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT
                p.id,
                p.name,
                p.created_at,
                COALESCE(SUM(CASE WHEN m.status = 'active' THEN 1 ELSE 0 END), 0) AS active,
                COALESCE(SUM(CASE WHEN m.status = 'removed' THEN 1 ELSE 0 END), 0) AS removed
            FROM pools p
            LEFT JOIN pool_members m ON m.pool_id = p.id
            GROUP BY p.id
            ORDER BY CASE WHEN p.id = ? THEN 0 ELSE 1 END, p.created_at, p.id
            """,
            (DEFAULT_POOL_ID,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "active": int(row["active"]),
                "removed": int(row["removed"]),
            }
            for row in rows
        ]

    def create_pool(self, pool_id: str, name: str = "") -> dict:
        pool_id = str(pool_id).strip()
        name = str(name).strip() or pool_id
        if not _POOL_ID_RE.match(pool_id):
            raise ValueError("池 id 只能是字母、数字、下划线和短横线，最长 32 位")
        existing = self.conn.execute(
            "SELECT id FROM pools WHERE id = ?",
            (pool_id,),
        ).fetchone()
        if existing is not None:
            raise ValueError(f"股票池已存在: {pool_id}")
        self.ensure_pool(pool_id, name)
        return {"pool": pool_id, "name": name, "created": True}

    def delete_pool(self, pool_id: str) -> dict:
        existing = self.conn.execute(
            "SELECT id FROM pools WHERE id = ?",
            (pool_id,),
        ).fetchone()
        if existing is None:
            raise ValueError(f"找不到股票池: {pool_id}")
        total = int(self.conn.execute("SELECT COUNT(*) AS n FROM pools").fetchone()["n"])
        if total <= 1:
            raise ValueError("至少保留一个股票池")
        members = int(
            self.conn.execute(
                "SELECT COUNT(*) AS n FROM pool_members WHERE pool_id = ?",
                (pool_id,),
            ).fetchone()["n"]
        )
        with self.conn:
            self.conn.execute("DELETE FROM pool_members WHERE pool_id = ?", (pool_id,))
            self.conn.execute("DELETE FROM pools WHERE id = ?", (pool_id,))
        return {"pool": pool_id, "deleted": True, "members_cleared": members}

    def _migrate_universe_into_default_pool(self) -> None:
        existing = self.conn.execute(
            "SELECT COUNT(*) AS n FROM pool_members WHERE pool_id = ?",
            (DEFAULT_POOL_ID,),
        ).fetchone()
        if existing and int(existing["n"]) > 0:
            return
        rows = self.conn.execute(
            """
            SELECT code, name FROM universe_members
            WHERE universe = 'hs300'
            ORDER BY code
            """
        ).fetchall()
        if not rows:
            return
        members = [(row["code"], row["name"]) for row in rows]
        self.replace_stocks(members)
        self.add_pool_members(DEFAULT_POOL_ID, members, source="index:000300")

    def add_pool_members(
        self,
        pool_id: str,
        members: list[tuple[str, str]],
        *,
        source: str = "manual",
    ) -> dict[str, int]:
        self.ensure_pool(pool_id)
        if members:
            catalog = set(self.stock_codes())
            missing = [code for code, _ in members if code not in catalog]
            if missing:
                raise ValueError(
                    "这些股票还不在系统里，请先在股票管理中加入: "
                    f"{_preview_codes(missing)}"
                )
        now = datetime.now().isoformat(timespec="seconds")
        added = 0
        reactivated = 0
        unchanged = 0
        with self.conn:
            for code, name in members:
                row = self.conn.execute(
                    """
                    SELECT status FROM pool_members
                    WHERE pool_id = ? AND code = ?
                    """,
                    (pool_id, code),
                ).fetchone()
                if row is None:
                    self.conn.execute(
                        """
                        INSERT INTO pool_members (
                            pool_id, code, name, status, source,
                            first_added_at, last_added_at, removed_at
                        ) VALUES (?, ?, ?, 'active', ?, ?, ?, NULL)
                        """,
                        (pool_id, code, name, source, now, now),
                    )
                    added += 1
                elif row["status"] == "removed":
                    self.conn.execute(
                        """
                        UPDATE pool_members
                        SET name = ?, status = 'active', source = ?,
                            last_added_at = ?, removed_at = NULL
                        WHERE pool_id = ? AND code = ?
                        """,
                        (name, source, now, pool_id, code),
                    )
                    reactivated += 1
                else:
                    self.conn.execute(
                        """
                        UPDATE pool_members
                        SET name = ?, source = ?
                        WHERE pool_id = ? AND code = ?
                        """,
                        (name, source, pool_id, code),
                    )
                    unchanged += 1
        return {"added": added, "reactivated": reactivated, "unchanged": unchanged}

    def remove_pool_members(self, pool_id: str, codes: list[str]) -> dict[str, int]:
        now = datetime.now().isoformat(timespec="seconds")
        removed = 0
        missing = 0
        already = 0
        with self.conn:
            for code in codes:
                row = self.conn.execute(
                    """
                    SELECT status FROM pool_members
                    WHERE pool_id = ? AND code = ?
                    """,
                    (pool_id, code),
                ).fetchone()
                if row is None:
                    missing += 1
                    continue
                if row["status"] == "removed":
                    already += 1
                    continue
                self.conn.execute(
                    """
                    UPDATE pool_members
                    SET status = 'removed', removed_at = ?
                    WHERE pool_id = ? AND code = ?
                    """,
                    (now, pool_id, code),
                )
                removed += 1
        return {"removed": removed, "already_removed": already, "missing": missing}

    def set_pool_members(
        self,
        pool_id: str,
        members: list[tuple[str, str]],
        *,
        source: str,
    ) -> dict[str, int]:
        wanted = {code for code, _ in members}
        result = self.add_pool_members(pool_id, members, source=source)
        extra = [
            code
            for code in self.active_pool_codes(pool_id)
            if code not in wanted
        ]
        removed = self.remove_pool_members(pool_id, extra)
        result["removed"] = removed["removed"]
        return result

    def active_pool_codes(self, pool_id: str = DEFAULT_POOL_ID) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT code FROM pool_members
            WHERE pool_id = ? AND status = 'active'
            ORDER BY code
            """,
            (pool_id,),
        ).fetchall()
        return [row["code"] for row in rows]

    def list_pool_members(
        self,
        pool_id: str = DEFAULT_POOL_ID,
        *,
        include_removed: bool = False,
        adjust: str = DEFAULT_ADJUST,
    ) -> list[dict]:
        sql = """
            SELECT
                m.code,
                m.name,
                m.status,
                m.source,
                m.first_added_at,
                m.last_added_at,
                m.removed_at,
                (
                    SELECT MAX(b.trade_date)
                    FROM bars_daily b
                    WHERE b.code = m.code AND b.adjust = ?
                ) AS last_bar
            FROM pool_members m
            WHERE m.pool_id = ?
        """
        params: list = [adjust, pool_id]
        if not include_removed:
            sql += " AND m.status = 'active'"
        sql += " ORDER BY m.status, m.code"
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def pool_quote_plan(
        self,
        pool_id: str = DEFAULT_POOL_ID,
        *,
        adjust: str = DEFAULT_ADJUST,
    ) -> dict[str, list[str]]:
        last_cal = self.last_calendar_date()
        full: list[str] = []
        fill: list[str] = []
        current: list[str] = []
        for code in self.active_pool_codes(pool_id):
            last = self.last_bar_date(code, adjust=adjust)
            if last is None:
                full.append(code)
            elif last_cal and last >= last_cal:
                current.append(code)
            else:
                fill.append(code)
        return {"full": full, "fill": fill, "current": current}

    def last_bar_date(
        self,
        code: str,
        adjust: str = DEFAULT_ADJUST,
        period: str = "daily",
    ) -> str | None:
        table = BAR_TABLES.get(period)
        if table is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        row = self.conn.execute(
            f"""
            SELECT MAX(trade_date) AS d
            FROM {table}
            WHERE code = ? AND adjust = ?
            """,
            (code, adjust),
        ).fetchone()
        return row["d"] if row and row["d"] else None

    def last_index_date(self, code: str) -> str | None:
        row = self.conn.execute(
            "SELECT MAX(trade_date) AS d FROM index_daily WHERE code = ?",
            (code,),
        ).fetchone()
        return row["d"] if row and row["d"] else None

    def upsert_bars(self, rows: list[tuple], *, period: str = "daily") -> int:
        if not rows:
            return 0
        table = BAR_TABLES.get(period)
        if table is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        with self.conn:
            self.conn.executemany(
                f"""
                INSERT INTO {table} (
                    code, trade_date, open, close, high, low,
                    volume, amount, amplitude, pct_chg, change_amount,
                    turnover, adjust
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, trade_date, adjust) DO UPDATE SET
                    open = excluded.open,
                    close = excluded.close,
                    high = excluded.high,
                    low = excluded.low,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    amplitude = excluded.amplitude,
                    pct_chg = excluded.pct_chg,
                    change_amount = excluded.change_amount,
                    turnover = excluded.turnover
                """,
                rows,
            )
        return len(rows)

    def upsert_index_bars(self, rows: list[tuple]) -> int:
        if not rows:
            return 0
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO index_daily (
                    code, name, trade_date, open, close, high, low, volume, amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, trade_date) DO UPDATE SET
                    name = excluded.name,
                    open = excluded.open,
                    close = excluded.close,
                    high = excluded.high,
                    low = excluded.low,
                    volume = excluded.volume,
                    amount = excluded.amount
                """,
                rows,
            )
        return len(rows)

    def mark_ingest(
        self,
        code: str,
        kind: str,
        status: str,
        *,
        adjust: str = DEFAULT_ADJUST,
        last_trade_date: str | None = None,
        rows: int = 0,
        error: str | None = None,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO ingest_state (
                    code, kind, adjust, last_trade_date, rows, status, error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, kind, adjust) DO UPDATE SET
                    last_trade_date = excluded.last_trade_date,
                    rows = ingest_state.rows + excluded.rows,
                    status = excluded.status,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (code, kind, adjust, last_trade_date, rows, status, error, now),
            )

    def counts(self, pool_id: str = DEFAULT_POOL_ID) -> dict[str, int]:
        tables = (
            "stocks",
            "trade_calendar",
            "bars_daily",
            "bars_weekly",
            "bars_monthly",
            "index_daily",
            "universe_members",
            "pool_members",
            "boards",
            "board_members",
        )
        out: dict[str, int] = {}
        for table in tables:
            row = self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            out[table] = int(row["n"])
        row = self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'removed' THEN 1 ELSE 0 END) AS removed
            FROM pool_members
            WHERE pool_id = ?
            """,
            (pool_id,),
        ).fetchone()
        out["pool_active"] = int(row["active"] or 0)
        out["pool_removed"] = int(row["removed"] or 0)
        row = self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error,
                SUM(CASE WHEN status = 'empty' THEN 1 ELSE 0 END) AS empty
            FROM ingest_state
            WHERE kind = 'stock'
            """
        ).fetchone()
        out["ingest_ok"] = int(row["ok"] or 0)
        out["ingest_error"] = int(row["error"] or 0)
        out["ingest_empty"] = int(row["empty"] or 0)
        return out


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
