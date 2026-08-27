from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Any

from astock_control.config import load_settings, preview_section, preview_update
from astock_control.protocol import (
    IMMEDIATE_COMMANDS,
    Job,
    ProtocolError,
    Runner,
    new_job_id,
    normalize_command,
    normalize_query,
    utc_now,
)

LOG_LIMIT = 2000
JOB_LIMIT = 100


class DispatchRunner:
    """Route a command to the runner registered for its type."""

    def __init__(self, mapping: dict[str, Runner]) -> None:
        self._mapping = mapping

    def run(self, command: dict[str, Any], on_log: Callable[[str], None]) -> dict[str, Any]:
        typ = str(command.get("type") or "")
        runner = self._mapping.get(typ)
        if runner is None:
            raise ValueError(f"没有执行器: {typ}")
        return runner.run(command, on_log)


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

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, name="astock-control-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def submit(self, raw: dict[str, Any]) -> Job:
        settings = load_settings()
        command = normalize_command(raw, default_pool=settings["pool"])
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
        )
        with self._lock:
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

    def wait_for_change(self, job_id: str, log_count: int, timeout: float = 0.3) -> Job | None:
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if len(job.log) > log_count or job.status in {"succeeded", "failed"}:
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
            if job is None:
                return
            job.status = "running"
            job.started_at = utc_now()
            command = dict(job.command)
            self._cv.notify_all()
        try:
            result = self._runner.run(command, lambda line, _id=job_id: self._append_log(_id, line))
        except Exception as exc:
            with self._cv:
                job = self._jobs.get(job_id)
                if job is not None:
                    job.status = "failed"
                    job.error = str(exc)
                    job.finished_at = utc_now()
                self._cv.notify_all()
            return
        with self._cv:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = "succeeded"
                job.result = result
                job.finished_at = utc_now()
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

    def _trim_jobs_locked(self) -> None:
        while len(self._order) > JOB_LIMIT:
            old_id = self._order.pop(0)
            old = self._jobs.get(old_id)
            if old is not None and old.status in {"queued", "running"}:
                self._order.insert(0, old_id)
                break
            self._jobs.pop(old_id, None)

    @staticmethod
    def _copy_job(job: Job) -> Job:
        return Job(
            id=job.id,
            type=job.type,
            status=job.status,
            command=dict(job.command),
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            result=None if job.result is None else dict(job.result),
            error=job.error,
            log=list(job.log),
        )
