from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from astock_control.adapters.ingest import IngestRunner
from astock_control.config import load_settings, write_settings
from astock_core.db import MarketDB
from astock_core.paths import DB_PATH, DEFAULT_POOL_ID


class PoolRunner:
    """Named-pool lifecycle and local member edits. Index fills go through ingest."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._ingest = IngestRunner()

    def run(
        self,
        command: dict[str, Any],
        on_log: Callable[[str], None],
        *,
        timeout: float | None = None,
        cancel_event=None,
    ) -> dict[str, Any]:
        typ = command.get("type")
        pool_id = str(command.get("pool") or "")
        if typ == "pool.create":
            name = str(command.get("name") or pool_id)
            on_log(f"创建股票池 {pool_id}")
            with MarketDB(self._db_path) as db:
                return db.create_pool(pool_id, name)
        if typ == "pool.delete":
            on_log(f"删除股票池 {pool_id}")
            with MarketDB(self._db_path) as db:
                result = db.delete_pool(pool_id)
                remaining = db.list_pools()
            settings = load_settings()
            if settings["pool"] == pool_id:
                fallback = remaining[0]["id"] if remaining else DEFAULT_POOL_ID
                write_settings({"pool": fallback})
                result["settings_pool"] = fallback
                on_log(f"默认股票池改到 {fallback}")
            return result
        if typ == "pool.remove":
            codes = [str(code) for code in command.get("codes") or []]
            on_log(f"移出 {','.join(codes)}")
            with MarketDB(self._db_path) as db:
                result = db.remove_pool_members(pool_id, codes)
                result["pool"] = pool_id
                result["active"] = len(db.active_pool_codes(pool_id))
                return result
        if typ == "pool.add":
            if command.get("index"):
                return self._ingest.run(
                    command, on_log, timeout=timeout, cancel_event=cancel_event
                )
            codes = [str(code) for code in command.get("codes") or []]
            on_log(f"加入 {','.join(codes)}")
            with MarketDB(self._db_path) as db:
                members: list[tuple[str, str]] = []
                for code in codes:
                    row = db.conn.execute(
                        "SELECT name FROM stocks WHERE code = ?",
                        (code,),
                    ).fetchone()
                    members.append((code, row["name"] if row else code))
                result = db.add_pool_members(pool_id, members, source="manual")
                result["pool"] = pool_id
                result["active"] = len(db.active_pool_codes(pool_id))
                return result
        raise ValueError(f"股票池执行器不支持命令: {typ}")
