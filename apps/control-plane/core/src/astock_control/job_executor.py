from __future__ import annotations

import queue
import threading
from collections.abc import Callable


class JobExecutor:
    """Own the single-worker lifecycle; JobService owns job state transitions."""

    def __init__(self, execute: Callable[[str], None], *, join_seconds: float) -> None:
        self._execute = execute
        self._join_seconds = join_seconds
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="astock-control-worker",
            daemon=True,
        )
        self._thread.start()

    def submit(self, job_id: str) -> None:
        self._queue.put(job_id)

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=self._join_seconds)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            job_id = self._queue.get()
            if job_id is None or self._stop.is_set():
                continue
            self._execute(job_id)
