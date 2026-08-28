from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from astock_core.paths import control_json_path, system_db_path
from astock_core.settings.catalog import SCHEMA_VERSION, find_section, iter_sections, live_paths, settings_catalog
from astock_core.settings.validate import merge_section_patch, secret_fields, validate_against_schema

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS setting_modules (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS setting_sections (
    module_id TEXT NOT NULL,
    id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    schema_json TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    read_only INTEGER NOT NULL DEFAULT 0,
    computed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (module_id, id),
    FOREIGN KEY (module_id) REFERENCES setting_modules(id)
);

CREATE TABLE IF NOT EXISTS setting_values (
    module_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    values_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (module_id, section_id),
    FOREIGN KEY (module_id, section_id)
        REFERENCES setting_sections(module_id, id)
);

CREATE TABLE IF NOT EXISTS system_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SystemDB:
    """SQLite 系统库：设置 schema 与取值。与行情库 market.db 分开。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else system_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._seed_catalog()
        self._migrate_control_json()
        self._refresh_computed()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> SystemDB:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def meta_get(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM system_meta WHERE key = ?",
            (key,),
        ).fetchone()
        return str(row["value"]) if row else None

    def meta_set(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO system_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def list_catalog(self) -> list[dict[str, Any]]:
        modules: list[dict[str, Any]] = []
        rows = self.conn.execute(
            """
            SELECT id, title, description, sort_order
            FROM setting_modules
            ORDER BY sort_order, id
            """
        ).fetchall()
        for row in rows:
            sections = self.conn.execute(
                """
                SELECT
                    id, title, description, sort_order, schema_json,
                    schema_version, read_only, computed, updated_at
                FROM setting_sections
                WHERE module_id = ?
                ORDER BY sort_order, id
                """,
                (row["id"],),
            ).fetchall()
            modules.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "description": row["description"],
                    "sort_order": int(row["sort_order"]),
                    "sections": [
                        {
                            "id": item["id"],
                            "title": item["title"],
                            "description": item["description"],
                            "sort_order": int(item["sort_order"]),
                            "schema": json.loads(item["schema_json"]),
                            "schema_version": int(item["schema_version"]),
                            "read_only": bool(item["read_only"]),
                            "computed": bool(item["computed"]),
                            "updated_at": item["updated_at"],
                        }
                        for item in sections
                    ],
                }
            )
        return modules

    def get_section(self, module_id: str, section_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT
                s.module_id, s.id, s.title, s.description, s.sort_order,
                s.schema_json, s.schema_version, s.read_only, s.computed,
                s.updated_at AS schema_updated_at,
                v.values_json, v.updated_at AS values_updated_at,
                m.title AS module_title
            FROM setting_sections s
            JOIN setting_modules m ON m.id = s.module_id
            LEFT JOIN setting_values v
                ON v.module_id = s.module_id AND v.section_id = s.id
            WHERE s.module_id = ? AND s.id = ?
            """,
            (module_id, section_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"未知设置段: {module_id}.{section_id}")
        schema = json.loads(row["schema_json"])
        values = json.loads(row["values_json"] or "{}")
        if row["computed"]:
            values = live_paths() if section_id == "paths" else values
        return {
            "module": row["module_id"],
            "module_title": row["module_title"],
            "section": row["id"],
            "title": row["title"],
            "description": row["description"],
            "sort_order": int(row["sort_order"]),
            "schema": schema,
            "schema_version": int(row["schema_version"]),
            "read_only": bool(row["read_only"]),
            "computed": bool(row["computed"]),
            "schema_updated_at": row["schema_updated_at"],
            "updated_at": row["values_updated_at"] or row["schema_updated_at"],
            "values": values,
        }

    def get_values(self, module_id: str, section_id: str) -> dict[str, Any]:
        return dict(self.get_section(module_id, section_id)["values"])

    def put_values(
        self,
        module_id: str,
        section_id: str,
        patch: dict[str, Any],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        current = self.get_section(module_id, section_id)
        if current["read_only"]:
            raise ValueError(f"{current['title']}不能修改")
        schema = current["schema"]
        if replace:
            merged = validate_against_schema(schema, {**_defaults_for(module_id, section_id), **patch})
            for key in secret_fields(schema):
                if key not in patch:
                    merged[key] = current["values"].get(key, "")
                elif patch.get(key) in ("", None):
                    merged[key] = current["values"].get(key, "")
                elif patch.get(key) == "__clear__":
                    merged[key] = ""
        else:
            merged = merge_section_patch(schema, current["values"], patch)
        self._write_values(module_id, section_id, merged)
        return self.get_section(module_id, section_id)

    def _write_values(self, module_id: str, section_id: str, values: dict[str, Any]) -> None:
        payload = json.dumps(values, ensure_ascii=False)
        now = _now()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO setting_values (module_id, section_id, values_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(module_id, section_id) DO UPDATE SET
                    values_json = excluded.values_json,
                    updated_at = excluded.updated_at
                """,
                (module_id, section_id, payload, now),
            )

    def _seed_catalog(self) -> None:
        now = _now()
        wanted_modules = {module["id"] for module in settings_catalog()}
        wanted_sections = {(module["id"], section["id"]) for module, section in iter_sections()}
        with self.conn:
            for module, section in iter_sections():
                self.conn.execute(
                    """
                    INSERT INTO setting_modules (id, title, description, sort_order)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        description = excluded.description,
                        sort_order = excluded.sort_order
                    """,
                    (
                        module["id"],
                        module["title"],
                        module["description"],
                        module["sort_order"],
                    ),
                )
                self.conn.execute(
                    """
                    INSERT INTO setting_sections (
                        module_id, id, title, description, sort_order,
                        schema_json, schema_version, read_only, computed, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(module_id, id) DO UPDATE SET
                        title = excluded.title,
                        description = excluded.description,
                        sort_order = excluded.sort_order,
                        schema_json = excluded.schema_json,
                        schema_version = excluded.schema_version,
                        read_only = excluded.read_only,
                        computed = excluded.computed,
                        updated_at = excluded.updated_at
                    """,
                    (
                        module["id"],
                        section["id"],
                        section["title"],
                        section["description"],
                        section["sort_order"],
                        json.dumps(section["schema"], ensure_ascii=False),
                        SCHEMA_VERSION,
                        1 if section["read_only"] else 0,
                        1 if section["computed"] else 0,
                        now,
                    ),
                )
                existing = self.conn.execute(
                    """
                    SELECT values_json FROM setting_values
                    WHERE module_id = ? AND section_id = ?
                    """,
                    (module["id"], section["id"]),
                ).fetchone()
                if existing is None:
                    self.conn.execute(
                        """
                        INSERT INTO setting_values (
                            module_id, section_id, values_json, updated_at
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            module["id"],
                            section["id"],
                            json.dumps(section["defaults"], ensure_ascii=False),
                            now,
                        ),
                    )
                else:
                    current = json.loads(existing["values_json"] or "{}")
                    if not isinstance(current, dict):
                        current = {}
                    defaults = section["defaults"]
                    properties = section["schema"].get("properties") or {}
                    allowed = set(properties)
                    merged = dict(current)
                    changed = False
                    for key, value in defaults.items():
                        if key not in merged:
                            merged[key] = value
                            changed = True
                    if allowed:
                        for key in list(merged):
                            if key not in allowed:
                                del merged[key]
                                changed = True
                    if changed:
                        self.conn.execute(
                            """
                            UPDATE setting_values
                            SET values_json = ?, updated_at = ?
                            WHERE module_id = ? AND section_id = ?
                            """,
                            (
                                json.dumps(merged, ensure_ascii=False),
                                now,
                                module["id"],
                                section["id"],
                            ),
                        )
            stale_sections = [
                (row["module_id"], row["id"])
                for row in self.conn.execute("SELECT module_id, id FROM setting_sections")
                if (row["module_id"], row["id"]) not in wanted_sections
            ]
            for module_id, section_id in stale_sections:
                self.conn.execute(
                    "DELETE FROM setting_values WHERE module_id = ? AND section_id = ?",
                    (module_id, section_id),
                )
                self.conn.execute(
                    "DELETE FROM setting_sections WHERE module_id = ? AND id = ?",
                    (module_id, section_id),
                )
            stale_modules = [
                row["id"]
                for row in self.conn.execute("SELECT id FROM setting_modules")
                if row["id"] not in wanted_modules
            ]
            for module_id in stale_modules:
                self.conn.execute("DELETE FROM setting_modules WHERE id = ?", (module_id,))

    def _refresh_computed(self) -> None:
        now = _now()
        payload = json.dumps(live_paths(), ensure_ascii=False)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO setting_values (module_id, section_id, values_json, updated_at)
                VALUES ('system', 'paths', ?, ?)
                ON CONFLICT(module_id, section_id) DO UPDATE SET
                    values_json = excluded.values_json,
                    updated_at = excluded.updated_at
                """,
                (payload, now),
            )

    def _migrate_control_json(self) -> None:
        if self.meta_get("control_json_migrated") == "1":
            return
        path = control_json_path()
        loaded: dict[str, Any] = {}
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = None
            if isinstance(raw, dict):
                loaded = raw
        if loaded:
            self._apply_legacy_dict(loaded)
        self.meta_set("control_json_migrated", "1")

    def _apply_legacy_dict(self, payload: dict[str, Any]) -> None:
        quotes_patch: dict[str, Any] = {}
        if "pool" in payload:
            quotes_patch["pool"] = payload["pool"]
        if "adjust" in payload:
            quotes_patch["adjust"] = payload["adjust"]
        quotes_in = payload.get("quotes")
        if isinstance(quotes_in, dict):
            if "sleep" in quotes_in:
                quotes_patch["sleep"] = quotes_in["sleep"]
            schedule_patch = {
                key: quotes_in[key]
                for key in ("sync_enabled", "sync_time", "timezone")
                if key in quotes_in
            }
            if schedule_patch:
                self.put_values("ingest", "schedule", schedule_patch)
        if quotes_patch:
            self.put_values("ingest", "quotes", quotes_patch)
        analyze = payload.get("analyze")
        if isinstance(analyze, dict):
            llm_patch = {key: analyze[key] for key in ("llm_provider", "deep_think_llm", "quick_think_llm", "backend_url", "api_key") if key in analyze}
            graph_patch = {
                key: analyze[key]
                for key in ("output_language", "analysts", "max_debate_rounds", "max_risk_discuss_rounds")
                if key in analyze
            }
            runtime_patch = {
                key: analyze[key]
                for key in ("temperature", "checkpoint_enabled")
                if key in analyze
            }
            if llm_patch:
                self.put_values("analyze", "llm", llm_patch)
            if graph_patch:
                self.put_values("analyze", "graph", graph_patch)
            if runtime_patch:
                self.put_values("analyze", "runtime", runtime_patch)


def _defaults_for(module_id: str, section_id: str) -> dict[str, Any]:
    found = find_section(module_id, section_id)
    return dict(found["section"]["defaults"])
