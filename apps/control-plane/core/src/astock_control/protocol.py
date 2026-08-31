from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event
from typing import Any, Protocol
from uuid import uuid4

from astock_core.paths import DEFAULT_POOL_ID

from astock_control.command_protocol import (
    COMMAND_TYPES,
    ProtocolError,
    code_to_ticker,
    normalize_analysts,
    normalize_codes,
    normalize_command,
    normalize_date,
    normalize_pool_id,
    normalize_qlib_workflow,
    parse_code_token,
)

NEWS_DEFAULT_LIMIT = 20
EVENTS_DEFAULT_LIMIT = 50
JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")
OPEN_JOB_STATUSES = frozenset({"queued", "running"})
TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
IMMEDIATE_COMMANDS = frozenset(
    {
        "settings.update",
        "stock.remove",
        "pool.create",
        "pool.delete",
        "pool.remove",
        "pool.reorder",
        "qlib.workflow.update",
    }
)
BACKGROUND_COMMANDS = frozenset(
    {"quotes.sync", "boards.sync", "stock.sync", "analyze.run", "qlib.run", "qlib.dump"}
)
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
    "pool.reorder": "调整股票池顺序",
    "analyze.run": "运行 AI 分析",
    "qlib.run": "运行量化选股",
    "qlib.dump": "准备量化数据",
    "qlib.workflow.update": "更新量化选股配置",
    "settings.update": "更新设置",
}
BOARD_KIND_LABELS = {"all": "全部", "industry": "行业", "concept": "概念"}


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


def parse_command_submission(
    raw: dict[str, Any],
) -> tuple[dict[str, Any], bool, int | None]:
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
    if typ in {"quotes.sync", "boards.sync", "stock.sync", "analyze.run", "qlib.run", "qlib.dump"}:
        return DEFAULT_TIMEOUT_LONG
    if typ in {"pool.set"} or (
        typ in {"pool.add", "stock.add"} and command.get("index")
    ):
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
    if typ in {"qlib.run", "qlib.dump", "qlib.workflow.update"}:
        pool = str(command.get("pool") or DEFAULT_POOL_ID)
        return f"{label} · 池 {pool}"
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
    if typ == "pool.reorder":
        pool = str(command.get("pool") or "")
        suffix = f" · 池 {pool}" if pool else ""
        return f"{label}{suffix}"
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
    trigger: str = "manual"
    automation_id: str | None = None
    scheduled_for: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    log: list[str] = field(default_factory=list)
    persisted_log_count: int = 0

    def to_dict(self, *, include_log: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "status": self.status,
            "command": self.command,
            "background": self.background,
            "timeout_seconds": self.timeout_seconds,
            "trigger": self.trigger,
            "automation_id": self.automation_id,
            "scheduled_for": self.scheduled_for,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
            "log_count": max(len(self.log), self.persisted_log_count),
        }
        if include_log:
            payload["log"] = list(self.log)
        return payload
