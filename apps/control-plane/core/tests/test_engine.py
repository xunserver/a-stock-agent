from __future__ import annotations

import threading
import time

import pytest

from astock_control.engine import Engine
from astock_control.protocol import ProtocolError


class FakeRunner:
    def __init__(
        self,
        *,
        result: dict | None = None,
        logs: list[str] | None = None,
        error: Exception | None = None,
        block: threading.Event | None = None,
        started: threading.Event | None = None,
    ) -> None:
        self.result = result or {"ok": True}
        self.logs = logs or []
        self.error = error
        self.block = block
        self.started = started
        self.calls: list[dict] = []

    def run(self, command: dict, on_log) -> dict:
        self.calls.append(command)
        if self.started is not None:
            self.started.set()
        for line in self.logs:
            on_log(line)
        if self.block is not None:
            self.block.wait(timeout=5)
        if self.error is not None:
            raise self.error
        return dict(self.result)


def _wait_status(engine: Engine, job_id: str, *statuses: str, timeout: float = 2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = engine.get_job(job_id)
        assert job is not None
        if job.status in statuses:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} still {engine.get_job(job_id).status}, want {statuses}")


def test_query_passes_through() -> None:
    engine = Engine(FakeRunner(), lambda q: {"echo": q["pool"]})
    assert engine.query({"type": "status", "pool": "hs300"}) == {"echo": "hs300"}


def test_pool_list_query_is_accepted() -> None:
    engine = Engine(
        FakeRunner(),
        lambda q: {"type": q["type"], "include_removed": q.get("include_removed", False)},
    )
    assert engine.query({"type": "pool.list", "include_removed": True}) == {
        "type": "pool.list",
        "include_removed": True,
    }


def test_unknown_command_rejected() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    with pytest.raises(ProtocolError, match="未知命令"):
        engine.submit({"type": "nope"})


def test_pool_add_needs_index_or_codes() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    with pytest.raises(ProtocolError, match="恰好一个"):
        engine.submit({"type": "pool.add"})
    with pytest.raises(ProtocolError, match="恰好一个"):
        engine.submit({"type": "pool.add", "index": "hs300", "codes": ["000001"]})


def test_pool_add_normalizes_codes() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    engine.start()
    try:
        job = engine.submit({"type": "pool.add", "pool": "hs", "codes": "1, 600519"})
        done = _wait_status(engine, job.id, "succeeded")
        assert done.command["codes"] == ["000001", "600519"]
    finally:
        engine.stop()


def test_stock_add_needs_index_or_codes() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    with pytest.raises(ProtocolError, match="恰好一个"):
        engine.submit({"type": "stock.add"})
    with pytest.raises(ProtocolError, match="恰好一个"):
        engine.submit({"type": "stock.add", "index": "hs300", "codes": ["000001"]})


def test_stock_add_normalizes_codes() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    engine.start()
    try:
        job = engine.submit({"type": "stock.add", "codes": "1, 600519"})
        done = _wait_status(engine, job.id, "succeeded")
        assert done.status == "succeeded"
        assert done.command["codes"] == ["000001", "600519"]
        assert "pool" not in done.command
    finally:
        engine.stop()


def test_stocks_list_query_is_accepted() -> None:
    engine = Engine(FakeRunner(), lambda q: {"type": q["type"]})
    assert engine.query({"type": "stocks.list"}) == {"type": "stocks.list"}


def test_submit_runs_and_keeps_logs() -> None:
    engine = Engine(FakeRunner(logs=["a", "b"], result={"rows": 3}), lambda q: {})
    engine.start()
    try:
        job = engine.submit({"type": "quotes.sync", "pool": "default"})
        done = _wait_status(engine, job.id, "succeeded")
        assert done.log == ["a", "b"]
        assert done.result == {"rows": 3}
        assert done.command["pool"] == "default"
    finally:
        engine.stop()


def test_runner_failure_marks_job_failed() -> None:
    engine = Engine(FakeRunner(error=RuntimeError("boom")), lambda q: {})
    engine.start()
    try:
        job = engine.submit({"type": "quotes.sync"})
        done = _wait_status(engine, job.id, "failed")
        assert done.error == "boom"
    finally:
        engine.stop()


def test_jobs_run_serially() -> None:
    started = threading.Event()
    release = threading.Event()
    engine = Engine(FakeRunner(block=release, started=started), lambda q: {})
    engine.start()
    try:
        first = engine.submit({"type": "quotes.sync"})
        second = engine.submit({"type": "quotes.sync"})
        assert started.wait(timeout=2)
        assert engine.get_job(first.id).status == "running"
        assert engine.get_job(second.id).status == "queued"
        release.set()
        _wait_status(engine, second.id, "succeeded")
        assert engine.get_job(first.id).status == "succeeded"
    finally:
        release.set()
        engine.stop()
