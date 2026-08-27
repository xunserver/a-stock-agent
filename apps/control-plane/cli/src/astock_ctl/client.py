from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8787"


class CoreUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "core 未运行。请先启动：\n"
            "  uv --directory apps/control-plane/core run python -m astock_control\n"
            "或： uv --directory apps/control-plane/cli run python -m astock_ctl serve"
        )


def find_repo_root() -> Path:
    starts = [Path.cwd().resolve(), Path(__file__).resolve()]
    seen: set[Path] = set()
    for start in starts:
        for path in [start, *start.parents]:
            if path in seen:
                continue
            seen.add(path)
            if (path / ".astock-root").is_file():
                return path
    raise RuntimeError("找不到仓库根目录（缺少 .astock-root）")


def base_url() -> str:
    return os.environ.get("ASTOCK_CONTROL_URL", DEFAULT_BASE_URL).rstrip("/")


def request(method: str, path: str, *, payload: dict[str, Any] | None = None) -> Any:
    url = base_url() + path
    try:
        response = httpx.request(method, url, json=payload, timeout=30.0)
    except httpx.ConnectError as exc:
        raise CoreUnavailable() from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"请求 core 失败: {exc}") from exc
    try:
        data = response.json()
    except ValueError:
        data = {"error": response.text or f"HTTP {response.status_code}"}
    if response.status_code >= 400:
        message = None
        if isinstance(data, dict):
            err = data.get("error") or data.get("detail")
            message = err if isinstance(err, str) else None
        raise RuntimeError(message or f"HTTP {response.status_code}")
    return data


def follow_events(job_id: str) -> dict[str, Any]:
    url = base_url() + f"/api/jobs/{job_id}/events"
    final: dict[str, Any] = {}
    try:
        with httpx.stream("GET", url, timeout=None) as response:
            if response.status_code >= 400:
                raise RuntimeError(f"跟踪任务失败: HTTP {response.status_code}")
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                stream = event.get("stream")
                if stream == "log":
                    print(event.get("message") or "", file=sys.stderr)
                elif stream == "status":
                    final = event.get("data") or {"status": event.get("message")}
                    if event.get("message") == "missing":
                        raise RuntimeError(f"找不到任务: {job_id}")
                    break
    except httpx.ConnectError as exc:
        raise CoreUnavailable() from exc
    return final
