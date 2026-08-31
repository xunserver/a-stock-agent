from __future__ import annotations

import os
import subprocess
from typing import Any

from astock_control.adapters.ingest import INGEST_DIR, parse_trailing_json
from astock_control.protocol import EVENTS_DEFAULT_LIMIT
from astock_core.market_data import validate_legacy_event_items
from astock_core.paths import DEFAULT_POOL_ID

EVENTS_TIMEOUT_SECONDS = 60


def events_argv(
    code: str,
    kind: str,
    *,
    limit: int = EVENTS_DEFAULT_LIMIT,
) -> list[str]:
    return [
        "uv",
        "--directory",
        str(INGEST_DIR),
        "run",
        "python",
        "-m",
        "astock",
        "--json",
        "--pool",
        DEFAULT_POOL_ID,
        "stock",
        "events",
        code,
        "--kind",
        kind,
        "--limit",
        str(limit),
        "--json",
    ]


def fetch_stock_events(
    code: str,
    kind: str,
    *,
    limit: int = EVENTS_DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Fetch events via ingest subprocess.

    The subprocess returns a versioned compatibility DTO produced from typed
    MarketEvent records at the ingest CLI edge. Successful empty results return
    ``[]`` with exit code 0; source failures exit non-zero and raise here.
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    try:
        completed = subprocess.run(
            events_argv(code, kind, limit=limit),
            capture_output=True,
            text=True,
            timeout=EVENTS_TIMEOUT_SECONDS,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("个股事件拉取超时") from exc
    payload = parse_trailing_json(completed.stdout or "")
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()
        message = detail[-1] if detail else "ingest 退出非零"
        raise RuntimeError(f"个股事件拉取失败: {message}")
    if not payload:
        raise RuntimeError("个股事件没有返回 JSON")
    try:
        return validate_legacy_event_items(payload.get("events", []))
    except ValueError as exc:
        raise RuntimeError(f"个股事件 JSON 无效: {exc}") from exc
