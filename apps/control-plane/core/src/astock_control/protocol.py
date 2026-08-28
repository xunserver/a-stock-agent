from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event
from typing import Any, Protocol
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
        "pool.reorder",
        "pool.set",
        "analyze.run",
        "qlib.run",
        "qlib.dump",
        "qlib.workflow.update",
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
        "stock.news",
        "stock.events",
        "stock.financials.detail",
        "calendar.markets",
        "calendar.get",
        "calendar.overview",
        "qlib.overview",
        "qlib.runs",
        "qlib.run.get",
        "calendar.month",
    }
)
ANALYZE_ANALYSTS = frozenset({"market", "social", "news", "fundamentals"})
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CODE_TOKEN_RE = re.compile(r"^(\d{1,6})(?:\.(SS|SZ|BJ))?$", re.IGNORECASE)
NEWS_DEFAULT_LIMIT = 20
NEWS_MAX_LIMIT = 50
EVENT_KINDS = frozenset({"notices", "research", "block_trades", "holder_changes"})
FINANCIAL_SHEETS = frozenset({"balance", "profit", "cashflow"})
EVENTS_DEFAULT_LIMIT = 50
EVENTS_MAX_LIMIT = 50
RESEARCH_DEFAULT_LIMIT = 20
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
    "pool.reorder": "调整股票池顺序",
    "analyze.run": "运行 AI 分析",
    "qlib.run": "运行量化选股",
    "qlib.dump": "准备量化数据",
    "qlib.workflow.update": "更新量化选股配置",
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


def _normalize_news_limit(raw: Any) -> int:
    if raw in (None, ""):
        return NEWS_DEFAULT_LIMIT
    try:
        limit = int(raw)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("stock.news limit 必须是正整数") from exc
    if isinstance(raw, bool) or limit < 1:
        raise ProtocolError("stock.news limit 必须是正整数")
    return min(limit, NEWS_MAX_LIMIT)


def _normalize_events_kind(raw: Any) -> str:
    kind = str(raw or "").strip()
    if kind not in EVENT_KINDS:
        raise ProtocolError(
            "stock.events kind 必须是 notices / research / block_trades / holder_changes"
        )
    return kind


def _normalize_events_limit(raw: Any, *, kind: str) -> int:
    default = RESEARCH_DEFAULT_LIMIT if kind == "research" else EVENTS_DEFAULT_LIMIT
    if raw in (None, ""):
        return default
    try:
        limit = int(raw)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("stock.events limit 必须是正整数") from exc
    if isinstance(raw, bool) or limit < 1:
        raise ProtocolError("stock.events limit 必须是正整数")
    return min(limit, EVENTS_MAX_LIMIT)


def _normalize_financial_sheet(raw: Any) -> str:
    sheet = str(raw or "profit").strip() or "profit"
    if sheet not in FINANCIAL_SHEETS:
        raise ProtocolError("stock.financials.detail sheet 必须是 balance / profit / cashflow")
    return sheet


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


def normalize_calendar_market(raw: Any) -> str:
    from astock_core.session import DEFAULT_MARKET, get_calendar_market

    text = str(raw or DEFAULT_MARKET).strip() or DEFAULT_MARKET
    try:
        return get_calendar_market(text).market_id
    except ValueError as exc:
        raise ProtocolError(f"未知市场: {text}") from exc


def normalize_calendar_month(year_raw: Any, month_raw: Any) -> tuple[int, int]:
    try:
        year = int(year_raw)
        month = int(month_raw)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("year / month 必须是整数") from exc
    if year < 1990 or year > 2100:
        raise ProtocolError("year 超出范围")
    if month < 1 or month > 12:
        raise ProtocolError("month 必须在 1–12")
    return year, month


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


def normalize_pool_id(
    raw: Any, *, required: bool = False, default: str = DEFAULT_POOL_ID
) -> str:
    pool = str(raw or "").strip()
    if not pool:
        if required:
            raise ProtocolError("需要股票池 id")
        pool = default
    if not POOL_ID_RE.match(pool):
        raise ProtocolError("池 id 只能是字母、数字、下划线和短横线，最长 32 位")
    return pool


def normalize_qlib_workflow(raw: Any) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise ProtocolError("workflow 必须是对象")
    unknown = set(raw) - {
        "config",
        "benchmark",
        "topk",
        "n_drop",
        "account",
        "data_end",
        "test_start",
        "learning_rate",
    }
    if unknown:
        raise ProtocolError(f"未知 Qlib workflow 字段: {', '.join(sorted(unknown))}")
    result: dict[str, Any] = {}
    for key in ("config", "benchmark"):
        if key in raw:
            value = str(raw[key] or "").strip()
            if not value:
                raise ProtocolError(f"workflow.{key} 不能为空")
            result[key] = value
    if "topk" in raw:
        try:
            topk = int(raw["topk"])
        except (TypeError, ValueError) as exc:
            raise ProtocolError("workflow.topk 必须是整数") from exc
        if isinstance(raw["topk"], bool) or not 1 <= topk <= 500:
            raise ProtocolError("workflow.topk 必须在 1 到 500 之间")
        result["topk"] = topk
    if "n_drop" in raw:
        try:
            n_drop = int(raw["n_drop"])
        except (TypeError, ValueError) as exc:
            raise ProtocolError("workflow.n_drop 必须是整数") from exc
        if isinstance(raw["n_drop"], bool) or not 0 <= n_drop <= 100:
            raise ProtocolError("workflow.n_drop 必须在 0 到 100 之间")
        result["n_drop"] = n_drop
    if "account" in raw:
        try:
            account = float(raw["account"])
        except (TypeError, ValueError) as exc:
            raise ProtocolError("workflow.account 必须是数字") from exc
        if isinstance(raw["account"], bool) or account <= 0:
            raise ProtocolError("workflow.account 必须大于 0")
        result["account"] = account
    for key in ("data_end", "test_start"):
        if key in raw:
            value = str(raw[key] or "").strip()
            if value and not DATE_RE.match(value):
                raise ProtocolError(f"workflow.{key} 必须是 YYYY-MM-DD")
            result[key] = value or None
    if "learning_rate" in raw:
        raw_rate = raw["learning_rate"]
        if raw_rate in (None, ""):
            result["learning_rate"] = None
        else:
            try:
                rate = float(raw_rate)
            except (TypeError, ValueError) as exc:
                raise ProtocolError("workflow.learning_rate 必须是数字") from exc
            if isinstance(raw_rate, bool) or rate <= 0:
                raise ProtocolError("workflow.learning_rate 必须大于 0")
            result["learning_rate"] = rate
    return result


def normalize_command(
    raw: dict[str, Any], *, default_pool: str = DEFAULT_POOL_ID
) -> dict[str, Any]:
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
        command = {
            "type": typ,
            "pool": normalize_pool_id(raw.get("pool"), default=default_pool),
            "codes": normalize_codes(raw.get("codes")),
        }
        if raw.get("with_statements"):
            command["with_statements"] = True
        return command

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
        if raw.get("history_start") is not None:
            text = str(raw["history_start"]).replace("-", "")[:8]
            if not text.isdigit() or len(text) != 8:
                raise ProtocolError("history_start 必须是 YYYYMMDD")
            command["history_start"] = text
        if raw.get("periods") not in (None, "", []):
            if isinstance(raw["periods"], str):
                periods = [
                    item.strip() for item in raw["periods"].split(",") if item.strip()
                ]
            elif isinstance(raw["periods"], list):
                periods = [
                    str(item).strip() for item in raw["periods"] if str(item).strip()
                ]
            else:
                raise ProtocolError("periods 必须是字符串或数组")
            if not periods:
                raise ProtocolError("periods 不能为空")
            command["periods"] = periods
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
    if typ == "pool.reorder":
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
    if typ in {"qlib.run", "qlib.dump", "qlib.workflow.update"}:
        if typ != "qlib.dump":
            command["workflow"] = normalize_qlib_workflow(raw.get("workflow"))
        return command
    return command


def normalize_query(
    raw: dict[str, Any], *, default_pool: str = DEFAULT_POOL_ID
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProtocolError("查询必须是 JSON 对象")
    typ = raw.get("type")
    if typ not in QUERY_TYPES:
        raise ProtocolError(f"未知查询: {typ}")
    if typ in {
        "settings.catalog",
        "pools.list",
        "stocks.list",
        "calendar.markets",
        "calendar.overview",
        "calendar.month",
    }:
        if typ == "calendar.month":
            if raw.get("year") in (None, "") or raw.get("month") in (None, ""):
                from astock_core.session import market_now

                today = market_now().date()
                return {"type": typ, "year": today.year, "month": today.month}
            year, month = normalize_calendar_month(raw.get("year"), raw.get("month"))
            return {"type": typ, "year": year, "month": month}
        return {"type": typ}
    if typ == "calendar.get":
        year, month = normalize_calendar_month(raw.get("year"), raw.get("month"))
        return {
            "type": typ,
            "market": normalize_calendar_market(raw.get("market")),
            "year": year,
            "month": month,
        }
    if typ in {"stock.get", "stock.news", "stock.events", "stock.financials.detail"}:
        if raw.get("code") in (None, ""):
            raise ProtocolError(f"{typ} 需要 code")
        codes = normalize_codes(raw.get("code"))
        if len(codes) != 1:
            raise ProtocolError(f"{typ} 需要恰好一只股票")
        payload: dict[str, Any] = {"type": typ, "code": codes[0]}
        if typ == "stock.news":
            payload["limit"] = _normalize_news_limit(raw.get("limit"))
        if typ == "stock.events":
            kind = _normalize_events_kind(raw.get("kind"))
            payload["kind"] = kind
            payload["limit"] = _normalize_events_limit(raw.get("limit"), kind=kind)
        if typ == "stock.financials.detail":
            if raw.get("report_date") in (None, ""):
                raise ProtocolError("stock.financials.detail 需要 report_date")
            payload["sheet"] = _normalize_financial_sheet(raw.get("sheet"))
            payload["report_date"] = normalize_date(raw.get("report_date"))
        return payload
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
    if typ == "qlib.run.get":
        run_id = str(raw.get("run_id") or "").strip()
        if not run_id:
            raise ProtocolError("qlib.run.get 需要 run_id")
        return {"type": typ, "run_id": run_id}
    query = {
        "type": typ,
        "pool": normalize_pool_id(raw.get("pool"), default=default_pool),
    }
    if typ == "pool.list":
        query["include_removed"] = bool(raw.get("include_removed", False))
    if typ == "qlib.runs":
        try:
            query["limit"] = max(1, min(int(raw.get("limit") or 20), 100))
        except (TypeError, ValueError) as exc:
            raise ProtocolError("qlib.runs limit 必须是正整数") from exc
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
