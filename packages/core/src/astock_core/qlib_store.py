from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astock_core._sqlite import apply_migrations, connect
from astock_core.paths import system_db_path

QLIB_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS qlib_pool_workflows (
    pool_id TEXT PRIMARY KEY,
    config TEXT NOT NULL,
    benchmark TEXT NOT NULL,
    topk INTEGER NOT NULL,
    n_drop INTEGER NOT NULL,
    account REAL NOT NULL,
    data_end TEXT,
    test_start TEXT,
    learning_rate REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qlib_pool_data (
    pool_id TEXT PRIMARY KEY,
    qlib_dir TEXT NOT NULL,
    benchmark TEXT NOT NULL,
    pool_members INTEGER NOT NULL,
    symbol_count INTEGER NOT NULL,
    calendar_last TEXT,
    prepared_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qlib_candidate_runs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    pool_id TEXT NOT NULL,
    as_of TEXT NOT NULL,
    config_snapshot_json TEXT NOT NULL,
    artifact_ref TEXT NOT NULL,
    universe_size INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_qlib_runs_pool_created
ON qlib_candidate_runs(pool_id, created_at DESC);

CREATE TABLE IF NOT EXISTS qlib_candidates (
    run_id TEXT NOT NULL,
    code TEXT NOT NULL,
    symbol TEXT NOT NULL,
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    PRIMARY KEY (run_id, code),
    FOREIGN KEY (run_id) REFERENCES qlib_candidate_runs(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_qlib_candidates_run_rank
ON qlib_candidates(run_id, rank);
"""

WORKFLOW_FIELDS = (
    "config",
    "benchmark",
    "topk",
    "n_drop",
    "account",
    "data_end",
    "test_start",
    "learning_rate",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _create_qlib_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(QLIB_SCHEMA)


def _add_workflow_fields(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(qlib_pool_workflows)").fetchall()
    }
    for name, ddl in (
        ("data_end", "ALTER TABLE qlib_pool_workflows ADD COLUMN data_end TEXT"),
        ("test_start", "ALTER TABLE qlib_pool_workflows ADD COLUMN test_start TEXT"),
        (
            "learning_rate",
            "ALTER TABLE qlib_pool_workflows ADD COLUMN learning_rate REAL",
        ),
    ):
        if name not in columns:
            conn.execute(ddl)


def _migrate_qlib(conn: sqlite3.Connection) -> None:
    apply_migrations(
        conn,
        namespace="qlib",
        migrations=(_create_qlib_schema, _add_workflow_fields),
    )


class QlibStore:
    """Persistent per-pool workflow defaults and immutable candidate results."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else system_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            _migrate_qlib(conn)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.path)

    def get_workflow(self, pool_id: str, defaults: dict[str, Any]) -> dict[str, Any]:
        effective = {field: defaults.get(field) for field in WORKFLOW_FIELDS}
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM qlib_pool_workflows WHERE pool_id = ?",
                (pool_id,),
            ).fetchone()
        if row is not None:
            for field in WORKFLOW_FIELDS:
                if row[field] is not None:
                    effective[field] = row[field]
            effective["updated_at"] = row["updated_at"]
        else:
            effective["updated_at"] = None
        effective["pool"] = pool_id
        return effective

    def save_workflow(self, pool_id: str, values: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO qlib_pool_workflows (
                    pool_id, config, benchmark, topk, n_drop, account,
                    data_end, test_start, learning_rate, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pool_id) DO UPDATE SET
                    config = excluded.config,
                    benchmark = excluded.benchmark,
                    topk = excluded.topk,
                    n_drop = excluded.n_drop,
                    account = excluded.account,
                    data_end = excluded.data_end,
                    test_start = excluded.test_start,
                    learning_rate = excluded.learning_rate,
                    updated_at = excluded.updated_at
                """,
                (
                    pool_id,
                    values["config"],
                    values["benchmark"],
                    int(values["topk"]),
                    int(values["n_drop"]),
                    float(values["account"]),
                    values.get("data_end"),
                    values.get("test_start"),
                    values.get("learning_rate"),
                    now,
                ),
            )
        return self.get_workflow(pool_id, values)

    def save_pool_data(self, pool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        prepared_at = str(payload.get("prepared_at") or utc_now())
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO qlib_pool_data (
                    pool_id, qlib_dir, benchmark, pool_members, symbol_count,
                    calendar_last, prepared_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pool_id) DO UPDATE SET
                    qlib_dir = excluded.qlib_dir,
                    benchmark = excluded.benchmark,
                    pool_members = excluded.pool_members,
                    symbol_count = excluded.symbol_count,
                    calendar_last = excluded.calendar_last,
                    prepared_at = excluded.prepared_at
                """,
                (
                    pool_id,
                    str(payload["qlib_dir"]),
                    str(payload.get("benchmark") or ""),
                    int(payload.get("pool_members") or payload.get("pool_instruments") or 0),
                    int(payload.get("symbols") or payload.get("features") or 0),
                    payload.get("calendar_last"),
                    prepared_at,
                ),
            )
        row = self.get_pool_data(pool_id)
        assert row is not None
        return row

    def get_pool_data(self, pool_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM qlib_pool_data WHERE pool_id = ?",
                (pool_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "pool": row["pool_id"],
            "qlib_dir": row["qlib_dir"],
            "benchmark": row["benchmark"],
            "pool_members": int(row["pool_members"]),
            "symbol_count": int(row["symbol_count"]),
            "calendar_last": row["calendar_last"],
            "prepared_at": row["prepared_at"],
            "ready": True,
        }

    def record_run(self, result: dict[str, Any]) -> dict[str, Any]:
        run_id = str(result["run_id"])
        candidates = list(result.get("candidates") or result.get("top") or [])
        created_at = str(result.get("created_at") or utc_now())
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO qlib_candidate_runs (
                    id, job_id, pool_id, as_of, config_snapshot_json,
                    artifact_ref, universe_size, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    str(result.get("job_id") or run_id),
                    str(result["pool"]),
                    str(result["as_of"]),
                    json.dumps(result["workflow"], ensure_ascii=False),
                    str(result["artifact_ref"]),
                    int(result["universe_size"]),
                    created_at,
                ),
            )
            conn.executemany(
                """
                INSERT INTO qlib_candidates (run_id, code, symbol, rank, score)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        str(item["code"]),
                        str(item["symbol"]),
                        int(item["rank"]),
                        float(item["score"]),
                    )
                    for item in candidates
                ],
            )
        stored = self.get_run(run_id)
        assert stored is not None
        return stored

    def list_runs(self, pool_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT r.*, COUNT(c.code) AS candidate_count
                FROM qlib_candidate_runs r
                LEFT JOIN qlib_candidates c ON c.run_id = r.id
                WHERE r.pool_id = ?
                GROUP BY r.id
                ORDER BY r.created_at DESC, r.id DESC
                LIMIT ?
                """,
                (pool_id, max(1, min(int(limit), 100))),
            ).fetchall()
        return [self._run_row(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT r.*, COUNT(c.code) AS candidate_count
                FROM qlib_candidate_runs r
                LEFT JOIN qlib_candidates c ON c.run_id = r.id
                WHERE r.id = ?
                GROUP BY r.id
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            candidates = conn.execute(
                """
                SELECT code, symbol, rank, score
                FROM qlib_candidates
                WHERE run_id = ?
                ORDER BY rank
                """,
                (run_id,),
            ).fetchall()
        result = self._run_row(row)
        result["candidates"] = [dict(item) for item in candidates]
        return result

    def latest_run(self, pool_id: str) -> dict[str, Any] | None:
        runs = self.list_runs(pool_id, limit=1)
        return self.get_run(str(runs[0]["id"])) if runs else None

    @staticmethod
    def _run_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "run_id": row["id"],
            "job_id": row["job_id"],
            "pool": row["pool_id"],
            "as_of": row["as_of"],
            "workflow": json.loads(row["config_snapshot_json"]),
            "artifact_ref": row["artifact_ref"],
            "universe_size": int(row["universe_size"]),
            "candidate_count": int(row["candidate_count"]),
            "created_at": row["created_at"],
        }
