from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Any

from astock_control.config import load_settings, preview_section, preview_update
from astock_control.protocol import (
    IMMEDIATE_COMMANDS,
    OPEN_JOB_STATUSES,
    TERMINAL_JOB_STATUSES,
    Job,
    JobCancelled,
    ProtocolError,
    Runner,
    build_job_name,
    new_job_id,
    normalize_command,
    normalize_query,
    parse_command_submission,
    resolve_job_background,
    resolve_job_timeout,
    utc_now,
)

LOG_LIMIT = 2000
JOB_LIMIT = 100
STOP_JOIN_SECONDS = 8


class DispatchRunner:
    """Route a command to the runner registered for its type."""

    def __init__(self, mapping: dict[str, Runner]) -> None:
        self._mapping = mapping

    def run(
        self,
        command: dict[str, Any],
        on_log: Callable[[str], None],
        *,
        timeout: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        typ = str(command.get("type") or "")
        runner = self._mapping.get(typ)
        if runner is None:
            raise ValueError(f"没有执行器: {typ}")
        return runner.run(command, on_log, timeout=timeout, cancel_event=cancel_event)


class Engine:
    """Serial job runner. Callers submit commands; one worker executes them."""

    def __init__(
        self,
        runner: Runner,
        query_handler: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        self._runner = runner
        self._query_handler = query_handler
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cancel_events: dict[str, threading.Event] = {}

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, name="astock-control-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        events: list[threading.Event] = []
        with self._cv:
            for job in self._jobs.values():
                if job.status == "queued":
                    self._mark_cancelled_locked(job)
            events = list(self._cancel_events.values())
            self._cv.notify_all()
        for event in events:
            event.set()
        self._stop.set()
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=STOP_JOIN_SECONDS)
            self._thread = None

    def submit(self, raw: dict[str, Any]) -> Job:
        settings = load_settings()
        payload, background_requested, timeout_requested = parse_command_submission(raw)
        command = normalize_command(payload, default_pool=settings["pool"])
        background = resolve_job_background(command, requested=background_requested)
        timeout_seconds = resolve_job_timeout(command, requested=timeout_requested)
        if command["type"] == "quotes.sync":
            command.setdefault("sleep", float(settings["quotes"]["sleep"]))
            command.setdefault("adjust", str(settings["adjust"]))
        elif command["type"] == "analyze.run":
            analyze = settings.get("analyze") or {}
            if "analysts" not in command:
                command["analysts"] = list(analyze.get("analysts") or [])
        elif command["type"] == "settings.update":
            try:
                if command.get("module"):
                    preview_section(
                        str(command["module"]),
                        str(command["section"]),
                        command.get("values") or {},
                    )
                else:
                    command["settings"] = preview_update(command.get("settings") or {})
            except ValueError as exc:
                raise ProtocolError(str(exc)) from exc

        job = Job(
            id=new_job_id(),
            type=command["type"],
            status="queued",
            command=command,
            created_at=utc_now(),
            name=build_job_name(command),
            timeout_seconds=timeout_seconds,
            background=background,
        )
        with self._lock:
            duplicate = self._find_duplicate_locked(command)
            if duplicate is not None:
                raise ProtocolError(f"已有相同任务在排队或运行：{duplicate.id}")
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._trim_jobs_locked()
        if command["type"] in IMMEDIATE_COMMANDS or (
            command["type"] in {"pool.add", "stock.add"} and command.get("codes")
        ):
            self._execute(job.id)
            done = self.get_job(job.id)
            assert done is not None
            return done
        self._queue.put(job.id)
        return job

    def query(self, raw: dict[str, Any]) -> dict[str, Any]:
        settings = load_settings()
        return self._query_handler(normalize_query(raw, default_pool=settings["pool"]))

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return self._copy_job(job)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return [self._copy_job(self._jobs[job_id]) for job_id in reversed(self._order) if job_id in self._jobs]

    def cancel(self, job_id: str) -> Job | None:
        event: threading.Event | None = None
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status in TERMINAL_JOB_STATUSES:
                raise ProtocolError("任务已结束，无法取消")
            if job.status == "queued":
                self._mark_cancelled_locked(job)
                self._cv.notify_all()
                return self._copy_job(job)
            event = self._cancel_events.get(job_id)
            self._cv.notify_all()
            copied = self._copy_job(job)
        if event is not None:
            event.set()
        return copied

    def wait_for_change(self, job_id: str, log_count: int, timeout: float = 0.3) -> Job | None:
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if len(job.log) > log_count or job.status in TERMINAL_JOB_STATUSES:
                return self._copy_job(job)
            self._cv.wait(timeout=timeout)
            job = self._jobs.get(job_id)
            return None if job is None else self._copy_job(job)

    def _worker(self) -> None:
        while not self._stop.is_set():
            job_id = self._queue.get()
            if job_id is None or self._stop.is_set():
                continue
            self._execute(job_id)

    def _execute(self, job_id: str) -> None:
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None or job.status == "cancelled":
                return
            job.status = "running"
            job.started_at = utc_now()
            command = dict(job.command)
            timeout = float(job.timeout_seconds)
            cancel_event = threading.Event()
            if self._stop.is_set():
                cancel_event.set()
            self._cancel_events[job_id] = cancel_event
            self._cv.notify_all()
        try:
            result = self._runner.run(
                command,
                lambda line, _id=job_id: self._append_log(_id, line),
                timeout=timeout,
                cancel_event=cancel_event,
            )
        except JobCancelled:
            with self._cv:
                job = self._jobs.get(job_id)
                if job is not None:
                    self._mark_cancelled_locked(job)
                self._cancel_events.pop(job_id, None)
                self._cv.notify_all()
            return
        except Exception as exc:
            with self._cv:
                job = self._jobs.get(job_id)
                if job is not None:
                    job.status = "failed"
                    job.error = str(exc)
                    job.finished_at = utc_now()
                self._cancel_events.pop(job_id, None)
                self._cv.notify_all()
            return
        with self._cv:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = "succeeded"
                job.result = result
                job.finished_at = utc_now()
            self._cancel_events.pop(job_id, None)
            self._cv.notify_all()

    def _append_log(self, job_id: str, line: str) -> None:
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.log.append(line)
            if len(job.log) > LOG_LIMIT:
                job.log = job.log[-LOG_LIMIT:]
            self._cv.notify_all()

    def _find_duplicate_locked(self, command: dict[str, Any]) -> Job | None:
        for job in self._jobs.values():
            if job.status in OPEN_JOB_STATUSES and job.command == command:
                return job
        return None

    def _trim_jobs_locked(self) -> None:
        while len(self._order) > JOB_LIMIT:
            oldest_terminal: str | None = None
            for job_id in self._order:
                job = self._jobs.get(job_id)
                if job is not None and job.status in TERMINAL_JOB_STATUSES:
                    oldest_terminal = job_id
                    break
            if oldest_terminal is None:
                break
            self._order.remove(oldest_terminal)
            self._jobs.pop(oldest_terminal, None)

    @staticmethod
    def _mark_cancelled_locked(job: Job) -> None:
        job.status = "cancelled"
        job.error = "已取消"
        job.finished_at = utc_now()

    @staticmethod
    def _copy_job(job: Job) -> Job:
        return Job(
            id=job.id,
            type=job.type,
            status=job.status,
            command=dict(job.command),
            created_at=job.created_at,
            name=job.name,
            timeout_seconds=job.timeout_seconds,
            background=job.background,
            started_at=job.started_at,
            finished_at=job.finished_at,
            result=None if job.result is None else dict(job.result),
            error=job.error,
            log=list(job.log),
        )
