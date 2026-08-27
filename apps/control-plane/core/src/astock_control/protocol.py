from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event
from typing import Any, Callable, Protocol
from uuid import uuid4

from astock_core.paths import DEFAULT_POOL_ID

COMMAND_TYPES = frozenset(
    {
        "quotes.sync",
        "boards.sync",
        "settings.update",
        "stock.add",
        "stock.remove",
        "stock.sync",
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
        "stock.get",
    }
)
ANALYZE_ANALYSTS = frozenset({"market", "social", "news", "fundamentals"})
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CODE_TOKEN_RE = re.compile(r"^(\d{1,6})(?:\.(SS|SZ|BJ))?$", re.IGNORECASE)
JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")
OPEN_JOB_STATUSES = frozenset({"queued", "running"})
TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
IMMEDIATE_COMMANDS = frozenset(
    {"settings.update", "stock.remove", "pool.create", "pool.delete", "pool.remove"}
)
BACKGROUND_COMMANDS = frozenset({"quotes.sync", "boards.sync", "stock.sync", "analyze.run"})
POOL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
JOB_NAME_CODE_LIST_LIMIT = 3
DEFAULT_TIMEOUT_LONG = 7200
DEFAULT_TIMEOUT_INDEX = 3600
DEFAULT_TIMEOUT_IMMEDIATE = 60
COMMAND_TYPE_LABELS = {
    "quotes.sync": "同步行情",
    "boards.sync": "同步板块",
    "stock.sync": "同步股票",
    "stock.add": "加入股票",
    "stock.remove": "移除股票",
    "pool.create": "创建股票池",
    "pool.delete": "删除股票池",
    "pool.add": "添加股票池成员",
    "pool.set": "覆盖股票池成员",
    "pool.remove": "移出股票池成员",
    "analyze.run": "运行分析",
    "settings.update": "更新设置",
}
BOARD_KIND_LABELS = {"all": "全部", "industry": "行业", "concept": "概念"}


class ProtocolError(ValueError):
    """Caller sent a command or query this daemon does not accept."""


class JobCancelled(Exception):
    """Runner stopped because the job was cancelled."""


class Runner(Protocol):
    def run(
        self,
        command: dict[str, Any],
        on_log: Callable[[str], None],
        *,
        timeout: float | None = None,
        cancel_event: Event | None = None,
    ) -> dict[str, Any]:
        """Execute a command. Raise on failure. Return a JSON-able result."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_job_id() -> str:
    return uuid4().hex[:12]


def parse_command_submission(raw: dict[str, Any]) -> tuple[dict[str, Any], bool, int | None]:
    if not isinstance(raw, dict):
        raise ProtocolError("命令必须是 JSON 对象")
    requested = raw.get("background", False)
    if not isinstance(requested, bool):
        raise ProtocolError("background 必须是布尔值")
    timeout_raw = raw.get("timeout_seconds", None)
    timeout_seconds: int | None = None
    if timeout_raw is not None:
        if isinstance(timeout_raw, bool) or not isinstance(timeout_raw, int):
            raise ProtocolError("timeout_seconds 必须是正整数")
        if timeout_raw <= 0:
            raise ProtocolError("timeout_seconds 必须是正整数")
        timeout_seconds = timeout_raw
    payload = {
        key: value
        for key, value in raw.items()
        if key not in {"background", "timeout_seconds"}
    }
    return payload, requested, timeout_seconds


def resolve_job_background(command: dict[str, Any], *, requested: bool) -> bool:
    typ = str(command.get("type") or "")
    immediate = typ in IMMEDIATE_COMMANDS or (
        typ in {"pool.add", "stock.add"} and bool(command.get("codes"))
    )
    if requested and immediate:
        raise ProtocolError("该命令不支持后台运行")
    return typ in BACKGROUND_COMMANDS or requested


def resolve_job_timeout(command: dict[str, Any], *, requested: int | None) -> int:
    if requested is not None:
        return requested
    typ = str(command.get("type") or "")
    if typ in {"quotes.sync", "boards.sync", "stock.sync", "analyze.run"}:
        return DEFAULT_TIMEOUT_LONG
    if typ in {"pool.set"} or (typ in {"pool.add", "stock.add"} and command.get("index")):
        return DEFAULT_TIMEOUT_INDEX
    return DEFAULT_TIMEOUT_IMMEDIATE


def _format_codes_for_name(codes: list[str]) -> str:
    if len(codes) <= JOB_NAME_CODE_LIST_LIMIT:
        return ", ".join(codes)
    return f"{len(codes)} 只"


def build_job_name(command: dict[str, Any]) -> str:
    typ = str(command.get("type") or "")
    label = COMMAND_TYPE_LABELS.get(typ, typ)
    if typ == "quotes.sync":
        codes = [str(code) for code in command.get("codes") or []]
        if codes:
            return f"{label} · {_format_codes_for_name(codes)}"
        pool = str(command.get("pool") or DEFAULT_POOL_ID)
        return f"{label} · 全部（池 {pool}）"
    if typ == "stock.sync":
        codes = [str(code) for code in command.get("codes") or []]
        return f"{label} · {_format_codes_for_name(codes)}"
    if typ == "boards.sync":
        kind = str(command.get("kind") or "all")
        return f"{label} · {BOARD_KIND_LABELS.get(kind, kind)}"
    if typ == "analyze.run":
        code = str(command.get("code") or "")
        date = str(command.get("date") or "").strip()
        if date:
            return f"{label} · {code} · {date}"
        return f"{label} · {code}"
    if typ in {"stock.add", "pool.add"}:
        if command.get("index"):
            pool = str(command.get("pool") or "")
            suffix = f" · 池 {pool}" if pool and typ == "pool.add" else ""
            return f"{label} · 指数 {command['index']}{suffix}"
        codes = [str(code) for code in command.get("codes") or []]
        pool = str(command.get("pool") or "")
        suffix = f" · 池 {pool}" if pool and typ == "pool.add" else ""
        return f"{label} · {_format_codes_for_name(codes)}{suffix}"
    if typ == "pool.set":
        pool = str(command.get("pool") or DEFAULT_POOL_ID)
        return f"{label} · 指数 {command.get('index')} · 池 {pool}"
    if typ in {"stock.remove", "pool.remove"}:
        codes = [str(code) for code in command.get("codes") or []]
        pool = str(command.get("pool") or "")
        suffix = f" · 池 {pool}" if pool and typ == "pool.remove" else ""
        return f"{label} · {_format_codes_for_name(codes)}{suffix}"
    if typ in {"pool.create", "pool.delete"}:
        pool = str(command.get("pool") or "")
        return f"{label} · {pool}"
    if typ == "settings.update":
        module = str(command.get("module") or "").strip()
        section = str(command.get("section") or "").strip()
        if module and section:
            return f"{label} · {module}.{section}"
        return label
    return label


def parse_code_token(raw: str) -> str:
    text = raw.strip().upper()
    match = CODE_TOKEN_RE.fullmatch(text)
    if not match:
        raise ProtocolError(f"无效股票代码: {raw.strip() or raw}")
    return match.group(1).zfill(6)


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
        text = str(part).strip()
        if not text:
            continue
        code = parse_code_token(text)
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
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
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
    if typ == "stock.sync":
        return {
            "type": typ,
            "pool": normalize_pool_id(raw.get("pool"), default=default_pool),
            "codes": normalize_codes(raw.get("codes")),
        }

    command: dict[str, Any] = {
        "type": typ,
        "pool": normalize_pool_id(raw.get("pool"), default=default_pool),
    }
    if typ == "quotes.sync":
        if raw.get("codes") not in (None, "", []):
            command["codes"] = normalize_codes(raw.get("codes"))
        if raw.get("sleep") is not None:
            command["sleep"] = float(raw["sleep"])
        if raw.get("adjust") is not None:
            command["adjust"] = str(raw["adjust"])
        if raw.get("limit") is not None:
            command["limit"] = int(raw["limit"])
        return command
    if typ == "boards.sync":
        kind = str(raw.get("kind") or "all").strip() or "all"
        if kind not in {"all", "industry", "concept"}:
            raise ProtocolError("boards.sync kind 只能是 all / industry / concept")
        command["kind"] = kind
        if raw.get("sleep") is not None:
            command["sleep"] = float(raw["sleep"])
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
    if typ == "stock.get":
        if raw.get("code") in (None, ""):
            raise ProtocolError("stock.get 需要 code")
        codes = normalize_codes(raw.get("code"))
        if len(codes) != 1:
            raise ProtocolError("stock.get 需要恰好一只股票")
        return {"type": typ, "code": codes[0]}
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
    name: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_IMMEDIATE
    background: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    log: list[str] = field(default_factory=list)

    def to_dict(self, *, include_log: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "status": self.status,
            "command": self.command,
            "background": self.background,
            "timeout_seconds": self.timeout_seconds,
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
