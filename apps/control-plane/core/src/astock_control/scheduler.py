from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any

from astock_core.automation import AutomationStore
from astock_core.paths import REPO_ROOT

from astock_control.automations import (
    AutomationManager,
    CalendarUnavailable,
    calculate_next_run,
)
from astock_control.protocol import ProtocolError

DEFAULT_TICK_SECONDS = 15.0
CALENDAR_REFRESH_SECONDS = 24 * 60 * 60


class Scheduler:
    """Turn persistent due automation occurrences into Engine jobs exactly once."""

    def __init__(
        self,
        engine: Any,
        store: AutomationStore,
        *,
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> None:
        self.engine = engine
        self.store = store
        self.manager = AutomationManager(store, engine)
        self.tick_seconds = tick_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_calendar_attempt: datetime | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self.manager.seed_legacy_quotes()
        self._thread = threading.Thread(
            target=self._run,
            name="astock-automation-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def tick(self, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        now_text = current.astimezone(timezone.utc).isoformat(timespec="seconds")
        for automation in self.store.list_due_automations(now_text):
            scheduled_for = str(automation["next_run_at"])
            should_run = automation.get("misfire_policy") != "skip"
            if should_run:
                try:
                    self.engine.submit(
                        dict(automation["command"]),
                        trigger="scheduled",
                        automation_id=str(automation["id"]),
                        scheduled_for=scheduled_for,
                    )
                except ProtocolError as exc:
                    if "计划时刻已经提交" not in str(exc):
                        self.store.update_automation(
                            str(automation["id"]),
                            {"calendar_status": f"提交失败：{exc}"},
                        )
                        continue
            self._advance(automation, current, scheduled_for if should_run else None)

    def refresh_calendar(self) -> bool:
        """Refresh the A-share calendar using the vendored AkShare environment."""
        self._last_calendar_attempt = datetime.now(timezone.utc)
        script = (
            "import json, akshare as ak;"
            "df=ak.tool_trade_date_hist_sina();"
            "print(json.dumps([str(x) for x in df['trade_date'].tolist()]))"
        )
        try:
            completed = subprocess.run(
                [
                    "uv",
                    "--directory",
                    str(REPO_ROOT / "tools" / "ingest"),
                    "run",
                    "python",
                    "-c",
                    script,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            dates = json.loads(completed.stdout.strip().splitlines()[-1])
            if not isinstance(dates, list) or not dates:
                raise ValueError("交易日历为空")
            self.store.replace_calendar([str(item) for item in dates], source="akshare.sina")
            self._restore_trading_schedules()
            return True
        except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            return False

    def _run(self) -> None:
        self.refresh_calendar()
        while not self._stop.wait(self.tick_seconds):
            self.tick()
            now = datetime.now(timezone.utc)
            if (
                self._last_calendar_attempt is None
                or (now - self._last_calendar_attempt).total_seconds()
                >= CALENDAR_REFRESH_SECONDS
            ):
                self.refresh_calendar()

    def _advance(
        self,
        automation: dict[str, Any],
        current: datetime,
        last_run_at: str | None,
    ) -> None:
        try:
            next_run = calculate_next_run(
                automation,
                after=current,
                store=self.store,
            )
            status = "ok"
        except CalendarUnavailable as exc:
            next_run = None
            status = str(exc)
        patch: dict[str, Any] = {
            "next_run_at": next_run,
            "calendar_status": status,
        }
        if last_run_at is not None:
            patch["last_run_at"] = last_run_at
        self.store.update_automation(str(automation["id"]), patch)

    def _restore_trading_schedules(self) -> None:
        now = datetime.now(timezone.utc)
        for automation in self.store.list_automations():
            if (
                automation["enabled"]
                and automation["schedule_kind"] == "trading_day"
                and automation["next_run_at"] is None
            ):
                self._advance(automation, now, None)
