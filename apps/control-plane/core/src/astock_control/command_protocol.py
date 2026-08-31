from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from astock_core.paths import DEFAULT_POOL_ID


COMMAND_TYPES = frozenset(
    {
        "quotes.sync", "boards.sync", "settings.update", "stock.add",
        "stock.remove", "stock.sync", "pool.create", "pool.delete",
        "pool.add", "pool.remove", "pool.reorder", "pool.set",
        "analyze.run", "qlib.run", "qlib.dump", "qlib.workflow.update",
    }
)
ANALYZE_ANALYSTS = frozenset({"market", "social", "news", "fundamentals"})
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CODE_TOKEN_RE = re.compile(r"^(\d{1,6})(?:\.(SS|SZ|BJ))?$", re.IGNORECASE)
POOL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


class ProtocolError(ValueError):
    """Caller sent a task payload the control plane does not accept."""


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
    for part in parts:
        text = str(part).strip()
        if not text:
            continue
        code = parse_code_token(text)
        if code not in codes:
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
    allowed = {"config", "benchmark", "topk", "n_drop", "account", "data_end", "test_start", "learning_rate"}
    unknown = set(raw) - allowed
    if unknown:
        raise ProtocolError(f"未知 Qlib workflow 字段: {', '.join(sorted(unknown))}")
    result: dict[str, Any] = {}
    for key in ("config", "benchmark"):
        if key in raw:
            value = str(raw[key] or "").strip()
            if not value:
                raise ProtocolError(f"workflow.{key} 不能为空")
            result[key] = value
    for key, lower, upper in (("topk", 1, 500), ("n_drop", 0, 100)):
        if key not in raw:
            continue
        try:
            value = int(raw[key])
        except (TypeError, ValueError) as exc:
            raise ProtocolError(f"workflow.{key} 必须是整数") from exc
        if isinstance(raw[key], bool) or not lower <= value <= upper:
            raise ProtocolError(f"workflow.{key} 必须在 {lower} 到 {upper} 之间")
        result[key] = value
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


Normalizer = Callable[[dict[str, Any], str], dict[str, Any]]


def _pooled(raw: dict[str, Any], default_pool: str) -> dict[str, Any]:
    return {"type": str(raw["type"]), "pool": normalize_pool_id(raw.get("pool"), default=default_pool)}


def _settings(raw: dict[str, Any], _default_pool: str) -> dict[str, Any]:
    module = str(raw.get("module") or "").strip()
    section = str(raw.get("section") or "").strip()
    if module or section:
        if not module or not section:
            raise ProtocolError("settings.update 需要 module 和 section")
        values = raw.get("values")
        if not isinstance(values, dict):
            raise ProtocolError("values 必须是对象")
        return {"type": "settings.update", "module": module, "section": section, "values": values}
    patch = raw.get("settings")
    if not isinstance(patch, dict):
        patch = {key: value for key, value in raw.items() if key != "type"}
    return {"type": "settings.update", "settings": patch}


def _pool_create(raw: dict[str, Any], _default_pool: str) -> dict[str, Any]:
    pool = normalize_pool_id(raw.get("pool"), required=True)
    return {"type": "pool.create", "pool": pool, "name": str(raw.get("name") or pool).strip() or pool}


def _pool_delete(raw: dict[str, Any], _default_pool: str) -> dict[str, Any]:
    return {"type": "pool.delete", "pool": normalize_pool_id(raw.get("pool"), required=True)}


def _exclusive_index_or_codes(raw: dict[str, Any], default_pool: str) -> dict[str, Any]:
    typ = str(raw["type"])
    has_index = bool(str(raw.get("index") or "").strip())
    has_codes = raw.get("codes") not in (None, "", [])
    if has_index == has_codes:
        raise ProtocolError(f"{typ} 需要恰好一个：index 或 codes")
    command = {"type": typ}
    if typ == "pool.add":
        command["pool"] = normalize_pool_id(raw.get("pool"), default=default_pool)
    if has_index:
        command["index"] = str(raw["index"]).strip()
    else:
        command["codes"] = normalize_codes(raw.get("codes"))
    return command


def _stock_remove(raw: dict[str, Any], _default_pool: str) -> dict[str, Any]:
    return {"type": "stock.remove", "codes": normalize_codes(raw.get("codes"))}


def _stock_sync(raw: dict[str, Any], default_pool: str) -> dict[str, Any]:
    command = {"type": "stock.sync", "pool": normalize_pool_id(raw.get("pool"), default=default_pool), "codes": normalize_codes(raw.get("codes"))}
    if raw.get("with_statements"):
        command["with_statements"] = True
    return command


def _quotes(raw: dict[str, Any], default_pool: str) -> dict[str, Any]:
    command = _pooled(raw, default_pool)
    if raw.get("codes") not in (None, "", []):
        command["codes"] = normalize_codes(raw.get("codes"))
    for key, convert in (("sleep", float), ("adjust", str), ("limit", int)):
        if raw.get(key) is not None:
            command[key] = convert(raw[key])
    if raw.get("history_start") is not None:
        text = str(raw["history_start"]).replace("-", "")[:8]
        if not text.isdigit() or len(text) != 8:
            raise ProtocolError("history_start 必须是 YYYYMMDD")
        command["history_start"] = text
    if raw.get("periods") not in (None, "", []):
        periods_raw = raw["periods"]
        if isinstance(periods_raw, str):
            periods = [item.strip() for item in periods_raw.split(",") if item.strip()]
        elif isinstance(periods_raw, list):
            periods = [str(item).strip() for item in periods_raw if str(item).strip()]
        else:
            raise ProtocolError("periods 必须是字符串或数组")
        if not periods:
            raise ProtocolError("periods 不能为空")
        command["periods"] = periods
    return command


def _boards(raw: dict[str, Any], default_pool: str) -> dict[str, Any]:
    command = _pooled(raw, default_pool)
    kind = str(raw.get("kind") or "all").strip() or "all"
    if kind not in {"all", "industry", "concept"}:
        raise ProtocolError("boards.sync kind 只能是 all / industry / concept")
    command["kind"] = kind
    for key, convert in (("sleep", float), ("limit", int)):
        if raw.get(key) is not None:
            command[key] = convert(raw[key])
    return command


def _pool_index(raw: dict[str, Any], default_pool: str) -> dict[str, Any]:
    command = _pooled(raw, default_pool)
    index = str(raw.get("index") or "").strip()
    if not index:
        raise ProtocolError("pool.set 需要 index")
    command["index"] = index
    return command


def _pool_codes(raw: dict[str, Any], default_pool: str) -> dict[str, Any]:
    command = _pooled(raw, default_pool)
    command["codes"] = normalize_codes(raw.get("codes"))
    return command


def _analyze(raw: dict[str, Any], default_pool: str) -> dict[str, Any]:
    command = _pooled(raw, default_pool)
    if raw.get("code") in (None, ""):
        raise ProtocolError("analyze.run 需要 code")
    codes = normalize_codes(raw.get("code"))
    if len(codes) != 1:
        raise ProtocolError("analyze.run 需要恰好一只股票")
    command.update({"code": codes[0], "ticker": code_to_ticker(codes[0])})
    if raw.get("date") not in (None, ""):
        command["date"] = normalize_date(raw.get("date"))
    if raw.get("analysts") is not None:
        command["analysts"] = normalize_analysts(raw.get("analysts"))
    return command


def _qlib(raw: dict[str, Any], default_pool: str) -> dict[str, Any]:
    command = _pooled(raw, default_pool)
    if raw["type"] != "qlib.dump":
        command["workflow"] = normalize_qlib_workflow(raw.get("workflow"))
    return command


NORMALIZERS: dict[str, Normalizer] = {
    "settings.update": _settings, "pool.create": _pool_create, "pool.delete": _pool_delete,
    "stock.add": _exclusive_index_or_codes, "stock.remove": _stock_remove, "stock.sync": _stock_sync,
    "quotes.sync": _quotes, "boards.sync": _boards, "pool.add": _exclusive_index_or_codes,
    "pool.set": _pool_index, "pool.remove": _pool_codes, "pool.reorder": _pool_codes,
    "analyze.run": _analyze, "qlib.run": _qlib, "qlib.dump": _qlib,
    "qlib.workflow.update": _qlib,
}


def normalize_command(raw: dict[str, Any], *, default_pool: str = DEFAULT_POOL_ID) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProtocolError("命令必须是 JSON 对象")
    typ = raw.get("type")
    normalizer = NORMALIZERS.get(str(typ))
    if normalizer is None:
        raise ProtocolError(f"未知命令: {typ}")
    return normalizer(raw, default_pool)
