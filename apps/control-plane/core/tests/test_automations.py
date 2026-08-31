from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from astock_control.app import create_app
from astock_control.automations import AutomationManager, calculate_next_run
from astock_control.engine import JobService
from astock_control.protocol import ProtocolError
from astock_control.scheduler import Scheduler
from astock_control.task_registry import TaskDefinition, TaskRegistry
from astock_core.automation import AutomationStore
from astock_core.settings.db import SystemDB


class FakeRunner:
    def run(self, command, on_log, *, timeout=None, cancel_event=None):
        on_log(f"run {command['type']}")
        return {"ok": True}


class FakeCalendar:
    def __init__(self, dates: list[str] | None = None) -> None:
        self.dates = set(dates or [])

    def replace(self, trade_dates: list[str]) -> int:
        self.dates = set(trade_dates)
        return len(self.dates)

    def is_trading_day(self, day: str) -> bool | None:
        if not self.dates:
            return None
        if day < min(self.dates) or day > max(self.dates):
            return None
        return day in self.dates


def _job_service(store: AutomationStore | None = None) -> JobService:
    runner = FakeRunner()
    return JobService(
        TaskRegistry(
            TaskDefinition(task_type, runner)
            for task_type in ("boards.sync", "quotes.sync")
        ),
        repository=store,
    )


def test_schedule_calculation_daily_weekly_and_trading_day() -> None:
    calendar = FakeCalendar(["2026-08-28", "2026-08-31"])
    after = datetime(2026, 8, 28, 7, 0, tzinfo=timezone.utc)
    base = {
        "timezone": "Asia/Shanghai",
        "local_time": "16:10",
        "weekdays": [],
    }
    daily = calculate_next_run(
        {**base, "schedule_kind": "daily"}, after=after, calendar=calendar
    )
    assert daily == "2026-08-28T08:10:00+00:00"

    weekly = calculate_next_run(
        {**base, "schedule_kind": "weekly", "weekdays": [0]},
        after=after,
        calendar=calendar,
    )
    assert weekly == "2026-08-31T08:10:00+00:00"

    trading = calculate_next_run(
        {**base, "schedule_kind": "trading_day"},
        after=after,
        calendar=calendar,
    )
    assert trading == "2026-08-28T08:10:00+00:00"


def test_manager_validates_and_archives_automation() -> None:
    store = AutomationStore()
    manager = AutomationManager(store, _job_service(store))
    item = manager.create(
        {
            "name": "每日板块",
            "command": {"type": "boards.sync", "kind": "industry"},
            "schedule_kind": "daily",
            "local_time": "18:00",
            "timezone": "Asia/Shanghai",
            "enabled": True,
        }
    )
    assert item["next_run_at"]
    assert item["command"]["kind"] == "industry"

    archived = manager.archive(item["id"])
    assert archived is not None
    assert archived["archived"] is True
    assert manager.get(item["id"]) is None

    with pytest.raises(ProtocolError, match="不允许自动调度"):
        manager.create(
            {
                "name": "错误任务",
                "command": {"type": "settings.update", "settings": {}},
                "schedule_kind": "daily",
                "local_time": "18:00",
                "timezone": "Asia/Shanghai",
            }
        )


def test_legacy_schedule_is_seeded_once() -> None:
    with SystemDB() as db:
        db.put_values(
            "ingest",
            "schedule",
            {
                "sync_enabled": True,
                "sync_time": "16:25",
                "timezone": "Asia/Shanghai",
            },
        )
        db.put_values("ingest", "quotes", {"pool": "hs300"})
    store = AutomationStore()
    manager = AutomationManager(store, _job_service(store))
    first = manager.seed_legacy_quotes()
    second = manager.seed_legacy_quotes()
    assert first["id"] == "quotes-after-close"
    assert second["id"] == first["id"]
    assert first["enabled"] is True
    assert first["local_time"] == "16:25"
    assert first["command"]["pool"] == "hs300"
    assert len(store.list_automations()) == 1


def test_scheduler_submits_each_occurrence_once() -> None:
    store = AutomationStore()
    engine = _job_service(store)
    manager = AutomationManager(store, engine)
    item = manager.create(
        {
            "name": "到期任务",
            "command": {"type": "boards.sync", "kind": "all"},
            "schedule_kind": "daily",
            "local_time": "18:00",
            "timezone": "Asia/Shanghai",
            "enabled": False,
        }
    )
    store.update_automation(
        item["id"],
        {
            "enabled": True,
            "next_run_at": "2026-08-28T08:00:00+00:00",
        },
    )
    scheduler = Scheduler(engine, store)
    now = datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc)
    scheduler.tick(now)
    scheduler.tick(now)
    jobs = store.list_jobs(automation_id=item["id"])
    assert len(jobs) == 1
    assert jobs[0]["trigger"] == "scheduled"
    assert jobs[0]["scheduled_for"] == "2026-08-28T08:00:00+00:00"


def test_scheduler_refresh_calendar_invokes_ingest_adapter() -> None:
    store = AutomationStore()
    engine = _job_service(store)
    calls = {"n": 0}

    def fake_sync() -> bool:
        calls["n"] += 1
        return True

    scheduler = Scheduler(engine, store, calendar_sync=fake_sync)
    assert scheduler.refresh_calendar() is True
    assert calls["n"] == 1

    def failing_sync() -> bool:
        raise RuntimeError("ingest failed")

    scheduler = Scheduler(engine, store, calendar_sync=failing_sync)
    assert scheduler.refresh_calendar() is False


def test_job_and_logs_survive_engine_restart() -> None:
    store = AutomationStore()
    first = _job_service(store)
    first.start()
    job = first.submit({"type": "boards.sync"})
    done = first.wait_for_change(job.id, 0, timeout=2)
    while done is not None and done.status not in {"succeeded", "failed"}:
        done = first.wait_for_change(job.id, len(done.log), timeout=2)
    first.stop()

    second = _job_service(store)
    restored = second.get_job(job.id)
    assert restored is not None
    assert restored.status == "succeeded"
    assert restored.log == ["run boards.sync"]


def test_restart_marks_interrupted_job_as_failed() -> None:
    store = AutomationStore()
    first = _job_service(store)
    queued = first.submit({"type": "boards.sync"})

    restarted = _job_service(store)
    restored = restarted.get_job(queued.id)

    assert restored is not None
    assert restored.status == "failed"
    assert restored.error == "core 重启，任务执行状态已中断"


def test_automation_http_crud_and_history() -> None:
    engine = _job_service()
    with TestClient(create_app(engine)) as client:
        created = client.post(
            "/api/automations",
            json={
                "name": "HTTP 自动任务",
                "command": {"type": "boards.sync", "kind": "concept"},
                "schedule_kind": "weekly",
                "weekdays": [0, 4],
                "local_time": "18:30",
                "timezone": "Asia/Shanghai",
                "enabled": True,
            },
        )
        assert created.status_code == 201
        automation = created.json()

        submitted = client.post(f"/api/automations/{automation['id']}/run")
        assert submitted.status_code == 200
        assert submitted.json()["trigger"] == "automation_manual"

        history = client.get(f"/api/automations/{automation['id']}/runs")
        assert history.status_code == 200
        assert history.json()["count"] == 1

        archived = client.delete(f"/api/automations/{automation['id']}")
        assert archived.status_code == 200
        assert archived.json()["archived"] is True
