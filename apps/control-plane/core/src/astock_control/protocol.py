from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from uuid import uuid4

from astock_core.paths import DEFAULT_POOL_ID

COMMAND_TYPES = frozenset(
    {
        "quotes.sync",
        "settings.update",
        "stock.add",
        "stock.remove",
        "pool.create",
        "pool.delete",
        "pool.add",
        "pool.remove",
        "pool.set",
        "analyze.run",
    }
)
QUERY_TYPES = frozenset(
    {
        "status",
        "pool.list",
        "pools.list",
        "stocks.list",
        "settings.get",
        "settings.catalog",
        "analyze.list",
        "analyze.get",
    }
)
ANALYZE_ANALYSTS = frozenset({"market", "social", "news", "fundamentals"})
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
JOB_STATUSES = ("queued", "running", "succeeded", "failed")
IMMEDIATE_COMMANDS = frozenset(
    {"settings.update", "stock.remove", "pool.create", "pool.delete", "pool.remove"}
)
POOL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


class ProtocolError(ValueError):
    """Caller sent a command or query this daemon does not accept."""


class Runner(Protocol):
    def run(self, command: dict[str, Any], on_log: Callable[[str], None]) -> dict[str, Any]:
        """Execute a command. Raise on failure. Return a JSON-able result."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_job_id() -> str:
    return uuid4().hex[:12]


def normalize_codes(raw: Any) -> list[str]:
    if isinstance(raw, str):
        parts = raw.replace("\n", ",").split(",")
    elif isinstance(raw, list):
        parts = [str(item) for item in raw]
    else:
        raise ProtocolError("codes 必须是字符串或数组")
    codes: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = part.strip()
        if not text:
            continue
        if not text.isdigit() or len(text) > 6:
            raise ProtocolError(f"无效股票代码: {text}")
        code = text.zfill(6)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    if not codes:
        raise ProtocolError("codes 不能为空")
    return codes


def code_to_ticker(code: str) -> str:
    if code.startswith(("6", "9", "5")):
        return f"{code}.SS"
    return f"{code}.SZ"


def normalize_date(raw: Any) -> str:
    text = str(raw or "").strip()
    if not DATE_RE.match(text):
        raise ProtocolError("日期必须是 YYYY-MM-DD")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ProtocolError("日期必须是 YYYY-MM-DD") from exc
    return text


def normalize_analysts(raw: Any) -> list[str]:
    if isinstance(raw, str):
        parts = [item.strip() for item in raw.split(",") if item.strip()]
    elif isinstance(raw, list):
        parts = [str(item).strip() for item in raw if str(item).strip()]
    else:
        raise ProtocolError("analysts 必须是字符串或数组")
    if not parts:
        raise ProtocolError("分析师列表不能为空")
    analysts: list[str] = []
    for name in parts:
        if name not in ANALYZE_ANALYSTS:
            raise ProtocolError(f"未知分析师: {name}")
        if name not in analysts:
            analysts.append(name)
    return analysts


def normalize_pool_id(raw: Any, *, required: bool = False, default: str = DEFAULT_POOL_ID) -> str:
    pool = str(raw or "").strip()
    if not pool:
        if required:
            raise ProtocolError("需要股票池 id")
        pool = default
    if not POOL_ID_RE.match(pool):
        raise ProtocolError("池 id 只能是字母、数字、下划线和短横线，最长 32 位")
    return pool


def normalize_command(raw: dict[str, Any], *, default_pool: str = DEFAULT_POOL_ID) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProtocolError("命令必须是 JSON 对象")
    typ = raw.get("type")
    if typ not in COMMAND_TYPES:
        raise ProtocolError(f"未知命令: {typ}")
    if typ == "settings.update":
        module = str(raw.get("module") or "").strip()
        section = str(raw.get("section") or "").strip()
        if module or section:
            if not module or not section:
                raise ProtocolError("settings.update 需要 module 和 section")
            values = raw.get("values")
            if not isinstance(values, dict):
                raise ProtocolError("values 必须是对象")
            return {"type": typ, "module": module, "section": section, "values": values}
        patch = raw.get("settings")
        if not isinstance(patch, dict):
            patch = {key: value for key, value in raw.items() if key != "type"}
        return {"type": typ, "settings": patch}
    if typ == "pool.create":
        pool = normalize_pool_id(raw.get("pool"), required=True)
        name = str(raw.get("name") or pool).strip() or pool
        return {"type": typ, "pool": pool, "name": name}
    if typ == "pool.delete":
        return {"type": typ, "pool": normalize_pool_id(raw.get("pool"), required=True)}
    if typ == "stock.add":
        has_index = bool(str(raw.get("index") or "").strip())
        has_codes = raw.get("codes") not in (None, "", [])
        if has_index == has_codes:
            raise ProtocolError("stock.add 需要恰好一个：index 或 codes")
        if has_index:
            return {"type": typ, "index": str(raw["index"]).strip()}
        return {"type": typ, "codes": normalize_codes(raw.get("codes"))}
    if typ == "stock.remove":
        return {"type": typ, "codes": normalize_codes(raw.get("codes"))}

    command: dict[str, Any] = {
        "type": typ,
        "pool": normalize_pool_id(raw.get("pool"), default=default_pool),
    }
    if typ == "quotes.sync":
        if raw.get("sleep") is not None:
            command["sleep"] = float(raw["sleep"])
        if raw.get("adjust") is not None:
            command["adjust"] = str(raw["adjust"])
        if raw.get("limit") is not None:
            command["limit"] = int(raw["limit"])
        return command
    if typ == "pool.add":
        has_index = bool(str(raw.get("index") or "").strip())
        has_codes = raw.get("codes") not in (None, "", [])
        if has_index == has_codes:
            raise ProtocolError("pool.add 需要恰好一个：index 或 codes")
        if has_index:
            command["index"] = str(raw["index"]).strip()
        else:
            command["codes"] = normalize_codes(raw.get("codes"))
        return command
    if typ == "pool.set":
        index = str(raw.get("index") or "").strip()
        if not index:
            raise ProtocolError("pool.set 需要 index")
        command["index"] = index
        return command
    if typ == "pool.remove":
        command["codes"] = normalize_codes(raw.get("codes"))
        return command
    if typ == "analyze.run":
        if raw.get("code") in (None, ""):
            raise ProtocolError("analyze.run 需要 code")
        codes = normalize_codes(raw.get("code"))
        if len(codes) != 1:
            raise ProtocolError("analyze.run 需要恰好一只股票")
        code = codes[0]
        command["code"] = code
        command["ticker"] = code_to_ticker(code)
        if raw.get("date") not in (None, ""):
            command["date"] = normalize_date(raw.get("date"))
        if raw.get("analysts") is not None:
            command["analysts"] = normalize_analysts(raw.get("analysts"))
        return command
    return command


def normalize_query(raw: dict[str, Any], *, default_pool: str = DEFAULT_POOL_ID) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProtocolError("查询必须是 JSON 对象")
    typ = raw.get("type")
    if typ not in QUERY_TYPES:
        raise ProtocolError(f"未知查询: {typ}")
    if typ in {"settings.catalog", "pools.list", "stocks.list"}:
        return {"type": typ}
    if typ == "settings.get":
        module = str(raw.get("module") or "").strip()
        section = str(raw.get("section") or "").strip()
        if module or section:
            if not module or not section:
                raise ProtocolError("settings.get 需要 module 和 section")
            return {"type": typ, "module": module, "section": section}
        return {"type": typ}
    if typ == "analyze.list":
        query: dict[str, Any] = {"type": typ}
        if raw.get("pool") not in (None, ""):
            query["pool"] = normalize_pool_id(raw.get("pool"), default=default_pool)
        if raw.get("code") not in (None, ""):
            codes = normalize_codes(raw.get("code"))
            if len(codes) != 1:
                raise ProtocolError("analyze.list 的 code 只能是一只股票")
            query["code"] = codes[0]
        return query
    if typ == "analyze.get":
        if raw.get("code") in (None, ""):
            raise ProtocolError("analyze.get 需要 code")
        codes = normalize_codes(raw.get("code"))
        if len(codes) != 1:
            raise ProtocolError("analyze.get 需要恰好一只股票")
        if raw.get("date") in (None, ""):
            raise ProtocolError("analyze.get 需要 date")
        query = {
            "type": typ,
            "code": codes[0],
            "date": normalize_date(raw.get("date")),
        }
        run_id = str(raw.get("run_id") or "").strip()
        if run_id:
            query["run_id"] = run_id
        return query
    query = {
        "type": typ,
        "pool": normalize_pool_id(raw.get("pool"), default=default_pool),
    }
    if typ == "pool.list":
        query["include_removed"] = bool(raw.get("include_removed", False))
    return query


@dataclass
class Job:
    id: str
    type: str
    status: str
    command: dict[str, Any]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    log: list[str] = field(default_factory=list)

    def to_dict(self, *, include_log: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "command": self.command,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
            "log_count": len(self.log),
        }
        if include_log:
            payload["log"] = list(self.log)
        return payload
