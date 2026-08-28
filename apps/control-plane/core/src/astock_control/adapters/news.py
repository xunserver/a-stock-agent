from __future__ import annotations

import os
import subprocess
from typing import Any

from astock_control.adapters.ingest import INGEST_DIR, parse_trailing_json
from astock_control.protocol import NEWS_DEFAULT_LIMIT
from astock_core.paths import DEFAULT_POOL_ID

NEWS_TIMEOUT_SECONDS = 25


def news_argv(code: str, *, limit: int = NEWS_DEFAULT_LIMIT) -> list[str]:
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
        "news",
        code,
        "--limit",
        str(limit),
        "--json",
    ]


def fetch_stock_news(code: str, *, limit: int = NEWS_DEFAULT_LIMIT) -> list[dict[str, Any]]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    try:
        completed = subprocess.run(
            news_argv(code, limit=limit),
            capture_output=True,
            text=True,
            timeout=NEWS_TIMEOUT_SECONDS,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("个股新闻拉取超时") from exc
    payload = parse_trailing_json(completed.stdout or "")
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()
        message = detail[-1] if detail else "ingest 退出非零"
        raise RuntimeError(f"个股新闻拉取失败: {message}")
    if not payload:
        raise RuntimeError("个股新闻没有返回 JSON")
    items = payload.get("news")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]
