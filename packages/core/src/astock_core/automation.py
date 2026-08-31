from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from astock_core._sqlite import apply_migrations, connect
from astock_core.paths import system_db_path


AUTOMATION_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS automations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    command_json TEXT NOT NULL,
    schedule_kind TEXT NOT NULL CHECK (schedule_kind IN ('daily', 'weekly', 'trading_day')),
    local_time TEXT NOT NULL,
    timezone TEXT NOT NULL,
    weekdays_json TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    archived INTEGER NOT NULL DEFAULT 0,
    misfire_policy TEXT NOT NULL DEFAULT 'run_once' CHECK (misfire_policy IN ('run_once', 'skip')),
    next_run_at TEXT,
    last_run_at TEXT,
    calendar_status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_automations_due
ON automations(enabled, archived, next_run_at);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    command_json TEXT NOT NULL,
    background INTEGER NOT NULL,
    timeout_seconds INTEGER NOT NULL,
    trigger_kind TEXT NOT NULL DEFAULT 'manual',
    automation_id TEXT,
    scheduled_for TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    result_json TEXT,
    error TEXT,
    log_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (automation_id) REFERENCES automations(id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_automation_created
ON jobs(automation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_scheduled_once
ON jobs(automation_id, scheduled_for)
WHERE automation_id IS NOT NULL AND scheduled_for IS NOT NULL AND trigger_kind = 'scheduled';

CREATE TABLE IF NOT EXISTS job_logs (
    job_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    line TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (job_id, seq),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trading_calendar (
    trade_date TEXT PRIMARY KEY,
    is_open INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL,
    refreshed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automation_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _create_automation_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(AUTOMATION_SCHEMA)


def _migrate_automation(conn: sqlite3.Connection) -> None:
    apply_migrations(
        conn,
        namespace="automation",
        migrations=(_create_automation_schema,),
    )


class AutomationStore:
    """Persistent automation definitions, executions, logs and calendar cache."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else system_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            _migrate_automation(conn)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.path)

    def create_automation(self, values: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        automation_id = str(values.get("id") or uuid4().hex[:12])
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO automations (
                    id, name, description, command_json, schedule_kind,
                    local_time, timezone, weekdays_json, enabled, archived,
                    misfire_policy, next_run_at, last_run_at, calendar_status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    automation_id,
                    values["name"],
                    values.get("description", ""),
                    _dump(values["command"]),
                    values["schedule_kind"],
                    values["local_time"],
                    values["timezone"],
                    _dump(values.get("weekdays", [])),
                    int(bool(values.get("enabled", True))),
                    int(bool(values.get("archived", False))),
                    values.get("misfire_policy", "run_once"),
                    values.get("next_run_at"),
                    values.get("last_run_at"),
                    values.get("calendar_status"),
                    now,
                    now,
                ),
            )
        result = self.get_automation(automation_id, include_archived=True)
        assert result is not None
        return result

    def update_automation(self, automation_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_automation(automation_id, include_archived=True)
        if current is None:
            return None
        merged = {**current, **values, "id": automation_id}
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE automations SET
                    name = ?, description = ?, command_json = ?,
                    schedule_kind = ?, local_time = ?, timezone = ?,
                    weekdays_json = ?, enabled = ?, archived = ?,
                    misfire_policy = ?, next_run_at = ?, last_run_at = ?,
                    calendar_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    merged["name"],
                    merged.get("description", ""),
                    _dump(merged["command"]),
                    merged["schedule_kind"],
                    merged["local_time"],
                    merged["timezone"],
                    _dump(merged.get("weekdays", [])),
                    int(bool(merged.get("enabled", True))),
                    int(bool(merged.get("archived", False))),
                    merged.get("misfire_policy", "run_once"),
                    merged.get("next_run_at"),
                    merged.get("last_run_at"),
                    merged.get("calendar_status"),
                    utc_now(),
                    automation_id,
                ),
            )
        return self.get_automation(automation_id, include_archived=True)

    def get_automation(
        self, automation_id: str, *, include_archived: bool = False
    ) -> dict[str, Any] | None:
        sql = "SELECT * FROM automations WHERE id = ?"
        params: list[Any] = [automation_id]
        if not include_archived:
            sql += " AND archived = 0"
        with closing(self._connect()) as conn:
            row = conn.execute(sql, params).fetchone()
        return _automation_row(row) if row else None

    def list_automations(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        sql = """
            SELECT a.*,
                   j.status AS last_status,
                   j.id AS last_job_id,
                   j.finished_at AS last_finished_at
            FROM automations a
            LEFT JOIN jobs j ON j.id = (
                SELECT j2.id FROM jobs j2
                WHERE j2.automation_id = a.id
                ORDER BY j2.created_at DESC LIMIT 1
            )
        """
        if not include_archived:
            sql += " WHERE a.archived = 0"
        sql += " ORDER BY a.created_at, a.id"
        with closing(self._connect()) as conn:
            rows = conn.execute(sql).fetchall()
        return [_automation_row(row) for row in rows]

    def list_due_automations(self, now: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT * FROM automations
                WHERE enabled = 1 AND archived = 0
                  AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at, id
                """,
                (now,),
            ).fetchall()
        return [_automation_row(row) for row in rows]

    def record_job(self, job: dict[str, Any]) -> bool:
        """Insert a job. False means its scheduled occurrence already exists."""
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        id, type, name, status, command_json, background,
                        timeout_seconds, trigger_kind, automation_id,
                        scheduled_for, created_at, started_at, finished_at,
                        result_json, error, log_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job["id"],
                        job["type"],
                        job.get("name", ""),
                        job["status"],
                        _dump(job["command"]),
                        int(bool(job.get("background", False))),
                        int(job.get("timeout_seconds", 60)),
                        job.get("trigger", "manual"),
                        job.get("automation_id"),
                        job.get("scheduled_for"),
                        job["created_at"],
                        job.get("started_at"),
                        job.get("finished_at"),
                        _dump_nullable(job.get("result")),
                        job.get("error"),
                        int(job.get("log_count", 0)),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def recover_open_jobs(self) -> int:
        """Close jobs left open by a previous core process."""
        now = utc_now()
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = 'failed', error = 'core 重启，任务执行状态已中断',
                    finished_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (now,),
            )
            return int(cursor.rowcount)

    def update_job(self, job: dict[str, Any]) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE jobs SET status = ?, started_at = ?, finished_at = ?,
                    result_json = ?, error = ?, log_count = ?
                WHERE id = ?
                """,
                (
                    job["status"],
                    job.get("started_at"),
                    job.get("finished_at"),
                    _dump_nullable(job.get("result")),
                    job.get("error"),
                    int(job.get("log_count", 0)),
                    job["id"],
                ),
            )

    def append_job_log(self, job_id: str, seq: int, line: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO job_logs(job_id, seq, line, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, seq, line, utc_now()),
            )
            conn.execute(
                "UPDATE jobs SET log_count = MAX(log_count, ?) WHERE id = ?",
                (seq + 1, job_id),
            )

    def get_job(self, job_id: str, *, include_log: bool = True) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            result = _job_row(row)
            if include_log:
                result["log"] = [
                    str(item["line"])
                    for item in conn.execute(
                        "SELECT line FROM job_logs WHERE job_id = ? ORDER BY seq",
                        (job_id,),
                    ).fetchall()
                ]
        return result

    def list_jobs(
        self,
        *,
        automation_id: str | None = None,
        date: str | None = None,
        trigger: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if automation_id:
            where.append("automation_id = ?")
            params.append(automation_id)
        if date:
            where.append("substr(created_at, 1, 10) = ?")
            params.append(date)
        if trigger:
            where.append("trigger_kind = ?")
            params.append(trigger)
        sql = "SELECT * FROM jobs"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += """
            ORDER BY
                CASE WHEN status IN ('queued', 'running') THEN 0 ELSE 1 END,
                created_at DESC, rowid DESC
            LIMIT ? OFFSET ?
        """
        params.extend((max(1, min(limit, 500)), max(0, offset)))
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_job_row(row) for row in rows]

    def count_jobs(
        self,
        *,
        automation_id: str | None = None,
        date: str | None = None,
        trigger: str | None = None,
    ) -> int:
        where: list[str] = []
        params: list[Any] = []
        if automation_id:
            where.append("automation_id = ?")
            params.append(automation_id)
        if date:
            where.append("substr(created_at, 1, 10) = ?")
            params.append(date)
        if trigger:
            where.append("trigger_kind = ?")
            params.append(trigger)
        sql = "SELECT COUNT(*) FROM jobs"
        if where:
            sql += " WHERE " + " AND ".join(where)
        with closing(self._connect()) as conn:
            return int(conn.execute(sql, params).fetchone()[0])

def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _dump_nullable(value: Any) -> str | None:
    return None if value is None else _dump(value)


def _load(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _automation_row(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "description": str(row["description"]),
        "command": _load(row["command_json"], {}),
        "schedule_kind": str(row["schedule_kind"]),
        "local_time": str(row["local_time"]),
        "timezone": str(row["timezone"]),
        "weekdays": _load(row["weekdays_json"], []),
        "enabled": bool(row["enabled"]),
        "archived": bool(row["archived"]),
        "misfire_policy": str(row["misfire_policy"]),
        "next_run_at": row["next_run_at"],
        "last_run_at": row["last_run_at"],
        "calendar_status": row["calendar_status"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "last_status": row["last_status"] if "last_status" in keys else None,
        "last_job_id": row["last_job_id"] if "last_job_id" in keys else None,
        "last_finished_at": row["last_finished_at"] if "last_finished_at" in keys else None,
    }


def _job_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "type": str(row["type"]),
        "name": str(row["name"]),
        "status": str(row["status"]),
        "command": _load(row["command_json"], {}),
        "background": bool(row["background"]),
        "timeout_seconds": int(row["timeout_seconds"]),
        "trigger": str(row["trigger_kind"]),
        "automation_id": row["automation_id"],
        "scheduled_for": row["scheduled_for"],
        "created_at": str(row["created_at"]),
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "result": _load(row["result_json"], None),
        "error": row["error"],
        "log_count": int(row["log_count"]),
    }
