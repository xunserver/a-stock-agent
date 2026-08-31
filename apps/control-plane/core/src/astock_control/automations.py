from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astock_core.automation import AutomationStore
from astock_core.calendar_store import MarketCalendar, TradingCalendar
from astock_core.settings.db import SystemDB

from astock_control.config import load_settings
from astock_control.protocol import (
    BACKGROUND_COMMANDS,
    COMMAND_TYPE_LABELS,
    ProtocolError,
    normalize_command,
)

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
SCHEDULE_KINDS = frozenset({"daily", "weekly", "trading_day"})
MISFIRE_POLICIES = frozenset({"run_once", "skip"})
LEGACY_QUOTES_AUTOMATION_ID = "quotes-after-close"

AUTOMATION_COMMAND_CATALOG: list[dict[str, Any]] = [
    {
        "type": "quotes.sync",
        "label": "同步行情",
        "description": "按股票池或指定代码补齐日、周、月行情。",
        "fields": [
            {"name": "pool", "label": "股票池", "kind": "text", "default": "default"},
            {"name": "codes", "label": "股票代码", "kind": "text", "optional": True},
        ],
    },
    {
        "type": "boards.sync",
        "label": "同步板块",
        "description": "同步行业板块和概念板块。",
        "fields": [
            {
                "name": "kind",
                "label": "板块类型",
                "kind": "select",
                "default": "all",
                "options": [
                    {"value": "all", "label": "全部"},
                    {"value": "industry", "label": "行业"},
                    {"value": "concept", "label": "概念"},
                ],
            }
        ],
    },
    {
        "type": "stock.sync",
        "label": "同步股票资料",
        "description": "同步指定股票的基础资料。",
        "fields": [
            {"name": "pool", "label": "股票池", "kind": "text", "default": "default"},
            {"name": "codes", "label": "股票代码", "kind": "text"},
        ],
    },
    {
        "type": "analyze.run",
        "label": "运行 AI 分析",
        "description": "定时运行单只股票分析。",
        "fields": [
            {"name": "pool", "label": "股票池", "kind": "text", "default": "default"},
            {"name": "code", "label": "股票代码", "kind": "text"},
        ],
    },
    {
        "type": "qlib.run",
        "label": "运行量化选股",
        "description": "使用股票池保存的默认 workflow 刷新候选结果。",
        "fields": [
            {"name": "pool", "label": "股票池", "kind": "text", "default": "default"},
        ],
    },
]


class CalendarUnavailable(ValueError):
    pass


def calculate_next_run(
    automation: dict[str, Any],
    *,
    after: datetime | None = None,
    calendar: TradingCalendar,
) -> str:
    current = after or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    zone = _zone(str(automation["timezone"]))
    local_now = current.astimezone(zone)
    run_time = _time(str(automation["local_time"]))
    kind = str(automation["schedule_kind"])
    weekdays = {int(item) for item in automation.get("weekdays") or []}

    for offset in range(370):
        day = local_now.date() + timedelta(days=offset)
        candidate = datetime.combine(day, run_time, tzinfo=zone)
        if candidate <= local_now:
            continue
        if kind == "weekly" and day.weekday() not in weekdays:
            continue
        if kind == "trading_day":
            trading = calendar.is_trading_day(day.isoformat())
            if trading is None:
                raise CalendarUnavailable(f"交易日历尚未覆盖 {day.isoformat()}")
            if not trading:
                continue
        return candidate.astimezone(timezone.utc).isoformat(timespec="seconds")
    raise CalendarUnavailable("无法在未来一年内计算下一次执行时间")


class AutomationManager:
    def __init__(
        self,
        store: AutomationStore,
        engine: Any,
        calendar: TradingCalendar | None = None,
    ) -> None:
        self.store = store
        self.engine = engine
        self.calendar = calendar or MarketCalendar()

    def catalog(self) -> dict[str, Any]:
        return {"commands": AUTOMATION_COMMAND_CATALOG}

    def list(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        return self.store.list_automations(include_archived=include_archived)

    def get(
        self, automation_id: str, *, include_archived: bool = False
    ) -> dict[str, Any] | None:
        return self.store.get_automation(
            automation_id, include_archived=include_archived
        )

    def create(self, raw: dict[str, Any]) -> dict[str, Any]:
        values = self._normalize(raw)
        values["next_run_at"], values["calendar_status"] = self._next(values)
        return self.store.create_automation(values)

    def update(
        self, automation_id: str, patch: dict[str, Any]
    ) -> dict[str, Any] | None:
        current = self.store.get_automation(automation_id, include_archived=True)
        if current is None:
            return None
        values = self._normalize({**current, **patch})
        values["archived"] = bool(current["archived"])
        values["last_run_at"] = current.get("last_run_at")
        values["next_run_at"], values["calendar_status"] = self._next(values)
        return self.store.update_automation(automation_id, values)

    def archive(self, automation_id: str) -> dict[str, Any] | None:
        return self.store.update_automation(
            automation_id,
            {"archived": True, "enabled": False, "next_run_at": None},
        )

    def run_now(self, automation_id: str):
        automation = self.store.get_automation(automation_id)
        if automation is None:
            return None
        return self.engine.submit(
            dict(automation["command"]),
            trigger="automation_manual",
            automation_id=automation_id,
        )

    def seed_legacy_quotes(self) -> dict[str, Any]:
        existing = self.store.get_automation(
            LEGACY_QUOTES_AUTOMATION_ID, include_archived=True
        )
        if existing is not None:
            return existing
        try:
            with SystemDB() as db:
                schedule = db.get_values("ingest", "schedule")
                quotes = db.get_values("ingest", "quotes")
        except (KeyError, ValueError):
            schedule = {
                "sync_enabled": False,
                "sync_time": "16:10",
                "timezone": "Asia/Shanghai",
            }
            quotes = {"pool": "default"}
        return self.create(
            {
                "id": LEGACY_QUOTES_AUTOMATION_ID,
                "name": "盘后行情同步",
                "description": "每个 A 股交易日收盘后同步股票池行情。",
                "command": {
                    "type": "quotes.sync",
                    "pool": quotes.get("pool", "default"),
                },
                "schedule_kind": "trading_day",
                "local_time": schedule.get("sync_time", "16:10"),
                "timezone": schedule.get("timezone", "Asia/Shanghai"),
                "enabled": bool(schedule.get("sync_enabled", False)),
                "misfire_policy": "run_once",
            }
        )

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ProtocolError("自动任务必须是对象")
        name = str(raw.get("name") or "").strip()
        if not name:
            raise ProtocolError("自动任务名称不能为空")
        command_raw = raw.get("command")
        if not isinstance(command_raw, dict):
            raise ProtocolError("自动任务 command 必须是对象")
        typ = str(command_raw.get("type") or "")
        if typ not in BACKGROUND_COMMANDS:
            raise ProtocolError("该命令不允许自动调度")
        settings = load_settings()
        command = normalize_command(command_raw, default_pool=settings["pool"])
        kind = str(raw.get("schedule_kind") or "")
        if kind not in SCHEDULE_KINDS:
            raise ProtocolError("schedule_kind 必须是 daily / weekly / trading_day")
        local_time = str(raw.get("local_time") or "")
        _time(local_time)
        timezone_name = str(raw.get("timezone") or "")
        _zone(timezone_name)
        weekdays_raw = raw.get("weekdays") or []
        if not isinstance(weekdays_raw, list):
            raise ProtocolError("weekdays 必须是数组")
        weekdays = sorted({int(item) for item in weekdays_raw})
        if any(item < 0 or item > 6 for item in weekdays):
            raise ProtocolError("weekdays 只能包含 0 到 6")
        if kind == "weekly" and not weekdays:
            raise ProtocolError("每周任务至少选择一天")
        policy = str(raw.get("misfire_policy") or "run_once")
        if policy not in MISFIRE_POLICIES:
            raise ProtocolError("misfire_policy 必须是 run_once 或 skip")
        return {
            "id": raw.get("id"),
            "name": name,
            "description": str(raw.get("description") or "").strip(),
            "command": command,
            "schedule_kind": kind,
            "local_time": local_time,
            "timezone": timezone_name,
            "weekdays": weekdays,
            "enabled": bool(raw.get("enabled", True)),
            "misfire_policy": policy,
        }

    def _next(self, values: dict[str, Any]) -> tuple[str | None, str | None]:
        if not values.get("enabled"):
            return None, None
        try:
            return calculate_next_run(values, calendar=self.calendar), "ok"
        except CalendarUnavailable as exc:
            return None, str(exc)


def _time(value: str) -> time:
    match = TIME_RE.fullmatch(value)
    if not match:
        raise ProtocolError("执行时刻必须是 HH:MM")
    return time(hour=int(match.group(1)), minute=int(match.group(2)))


def _zone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ProtocolError(f"未知时区: {value}") from exc


def automation_label(automation: dict[str, Any]) -> str:
    typ = str((automation.get("command") or {}).get("type") or "")
    return COMMAND_TYPE_LABELS.get(typ, typ)
