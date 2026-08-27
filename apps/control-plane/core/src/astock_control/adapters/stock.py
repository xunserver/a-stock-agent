from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from astock_control.adapters.ingest import IngestRunner
from astock_core.db import MarketDB
from astock_core.paths import DB_PATH


class StockRunner:
    """System stock catalog. Index fills go through ingest."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._ingest = IngestRunner()

    def run(self, command: dict[str, Any], on_log: Callable[[str], None]) -> dict[str, Any]:
        typ = command.get("type")
        if typ == "stock.add":
            if command.get("index"):
                return self._ingest.run(command, on_log)
            codes = [str(code) for code in command.get("codes") or []]
            on_log(f"加入系统 {','.join(codes)}")
            with MarketDB(self._db_path) as db:
                members: list[tuple[str, str]] = []
                for code in codes:
                    row = db.conn.execute(
                        "SELECT name FROM stocks WHERE code = ?",
                        (code,),
                    ).fetchone()
                    members.append((code, row["name"] if row else code))
                return db.add_stocks(members)
        if typ == "stock.remove":
            codes = [str(code) for code in command.get("codes") or []]
            on_log(f"从系统移除 {','.join(codes)}")
            with MarketDB(self._db_path) as db:
                return db.remove_stocks(codes)
        raise ValueError(f"股票执行器不支持命令: {typ}")
