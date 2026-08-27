from __future__ import annotations

import threading
import time

import pytest

from astock_control.engine import Engine
from astock_control.protocol import JobCancelled, ProtocolError


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
        self.timeouts: list[float | None] = []

    def run(self, command: dict, on_log, *, timeout: float | None = None, cancel_event=None) -> dict:
        self.calls.append(command)
        self.timeouts.append(timeout)
        if self.started is not None:
            self.started.set()
        for line in self.logs:
            on_log(line)
        if self.block is not None:
            wait_for = 5.0 if timeout is None else float(timeout)
            deadline = time.time() + wait_for
            while time.time() < deadline:
                if self.block.is_set():
                    break
                if cancel_event is not None and cancel_event.is_set():
                    raise JobCancelled("已取消")
                time.sleep(0.02)
            else:
                if cancel_event is not None and cancel_event.is_set():
                    raise JobCancelled("已取消")
                limit = int(timeout) if timeout is not None else 0
                raise RuntimeError(f"任务超时（{limit}s），已终止子进程")
        if cancel_event is not None and cancel_event.is_set():
            raise JobCancelled("已取消")
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


def test_background_metadata_is_resolved_and_not_forwarded() -> None:
    runner = FakeRunner()
    engine = Engine(runner, lambda q: {})
    engine.start()
    try:
        default_job = engine.submit({"type": "quotes.sync"})
        opted_in = engine.submit({"type": "pool.add", "pool": "default", "index": "hs300", "background": True})
        assert default_job.background is True
        assert opted_in.background is True
        assert "background" not in opted_in.command
        _wait_status(engine, opted_in.id, "succeeded")
        assert all("background" not in command for command in runner.calls)
    finally:
        engine.stop()


def test_background_metadata_rejects_invalid_and_immediate_commands() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    with pytest.raises(ProtocolError, match="布尔值"):
        engine.submit({"type": "quotes.sync", "background": "yes"})
    with pytest.raises(ProtocolError, match="不支持后台运行"):
        engine.submit({"type": "pool.create", "pool": "hs", "background": True})
    with pytest.raises(ProtocolError, match="不支持后台运行"):
        engine.submit({"type": "stock.add", "codes": ["000001"], "background": True})


def test_immediate_job_is_not_background() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    job = engine.submit({"type": "pool.create", "pool": "hs"})
    assert job.background is False
    assert engine.get_job(job.id).background is False


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
        first = engine.submit({"type": "quotes.sync", "codes": ["000001"]})
        second = engine.submit({"type": "quotes.sync", "codes": ["000002"]})
        assert started.wait(timeout=2)
        assert engine.get_job(first.id).status == "running"
        assert engine.get_job(second.id).status == "queued"
        release.set()
        _wait_status(engine, second.id, "succeeded")
        assert engine.get_job(first.id).status == "succeeded"
    finally:
        release.set()
        engine.stop()


def test_submit_sets_name_and_default_timeout() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    engine.start()
    try:
        whole = engine.submit({"type": "quotes.sync", "pool": "hs"})
        assert whole.name == "同步行情 · 全部（池 hs）"
        assert whole.timeout_seconds == 7200
        codes = engine.submit({"type": "quotes.sync", "codes": ["600519", "000001"]})
        assert codes.name == "同步行情 · 600519, 000001"
        many = engine.submit(
            {
                "type": "quotes.sync",
                "codes": ["000001", "000002", "000003", "000004"],
            }
        )
        assert many.name == "同步行情 · 4 只"
        analyze = engine.submit({"type": "analyze.run", "code": "600519", "date": "2026-08-27"})
        assert analyze.name == "运行分析 · 600519 · 2026-08-27"
        assert analyze.timeout_seconds == 7200
        immediate = engine.submit({"type": "pool.create", "pool": "demo"})
        assert immediate.name == "创建股票池 · demo"
        assert immediate.timeout_seconds == 60
    finally:
        engine.stop()


def test_submit_timeout_override_and_expiry() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    with pytest.raises(ProtocolError, match="正整数"):
        engine.submit({"type": "quotes.sync", "timeout_seconds": 0})
    with pytest.raises(ProtocolError, match="正整数"):
        engine.submit({"type": "quotes.sync", "timeout_seconds": 1.5})

    started = threading.Event()
    release = threading.Event()
    runner = FakeRunner(block=release, started=started)
    engine = Engine(runner, lambda q: {})
    engine.start()
    try:
        job = engine.submit({"type": "quotes.sync", "timeout_seconds": 1})
        assert job.timeout_seconds == 1
        assert "timeout_seconds" not in job.command
        assert started.wait(timeout=2)
        done = _wait_status(engine, job.id, "failed", timeout=3.0)
        assert "超时" in (done.error or "")
        assert runner.timeouts == [1.0]
    finally:
        release.set()
        engine.stop()


def test_cancel_queued_job_skips_execution() -> None:
    started = threading.Event()
    release = threading.Event()
    runner = FakeRunner(block=release, started=started)
    engine = Engine(runner, lambda q: {})
    engine.start()
    try:
        first = engine.submit({"type": "quotes.sync", "codes": ["000001"]})
        second = engine.submit({"type": "quotes.sync", "codes": ["000002"]})
        assert started.wait(timeout=2)
        cancelled = engine.cancel(second.id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.error == "已取消"
        release.set()
        _wait_status(engine, first.id, "succeeded")
        assert engine.get_job(second.id).status == "cancelled"
        assert len(runner.calls) == 1
    finally:
        release.set()
        engine.stop()


def test_cancel_running_job_is_cancelled_not_failed() -> None:
    started = threading.Event()
    release = threading.Event()
    engine = Engine(FakeRunner(block=release, started=started), lambda q: {})
    engine.start()
    try:
        job = engine.submit({"type": "quotes.sync"})
        assert started.wait(timeout=2)
        pending = engine.cancel(job.id)
        assert pending is not None
        assert pending.status in {"running", "cancelled"}
        done = _wait_status(engine, job.id, "cancelled")
        assert done.status == "cancelled"
        assert done.error == "已取消"
    finally:
        release.set()
        engine.stop()


def test_cancel_terminal_job_rejected() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    engine.start()
    try:
        job = engine.submit({"type": "quotes.sync"})
        done = _wait_status(engine, job.id, "succeeded")
        with pytest.raises(ProtocolError, match="已结束"):
            engine.cancel(done.id)
        assert engine.cancel("missing") is None
    finally:
        engine.stop()


def test_stop_cancels_queued_and_running() -> None:
    started = threading.Event()
    release = threading.Event()
    engine = Engine(FakeRunner(block=release, started=started), lambda q: {})
    engine.start()
    first = engine.submit({"type": "quotes.sync", "codes": ["000001"]})
    second = engine.submit({"type": "quotes.sync", "codes": ["000002"]})
    assert started.wait(timeout=2)
    engine.stop()
    assert engine.get_job(first.id).status == "cancelled"
    assert engine.get_job(second.id).status == "cancelled"
    release.set()


def test_duplicate_open_command_rejected() -> None:
    started = threading.Event()
    release = threading.Event()
    engine = Engine(FakeRunner(block=release, started=started), lambda q: {})
    engine.start()
    try:
        first = engine.submit({"type": "quotes.sync", "pool": "default"})
        assert started.wait(timeout=2)
        with pytest.raises(ProtocolError, match="已有相同任务"):
            engine.submit({"type": "quotes.sync", "pool": "default"})
        other = engine.submit({"type": "quotes.sync", "codes": ["600519"]})
        assert other.id != first.id
        assert other.status == "queued"
    finally:
        release.set()
        engine.stop()


def test_trim_keeps_open_jobs_and_drops_oldest_terminal() -> None:
    from astock_control.engine import JOB_LIMIT

    engine = Engine(FakeRunner(), lambda q: {})
    engine.start()
    try:
        kept = []
        for index in range(JOB_LIMIT + 5):
            job = engine.submit({"type": "quotes.sync", "codes": [f"{index:06d}"]})
            done = _wait_status(engine, job.id, "succeeded")
            kept.append(done.id)
        listed = engine.list_jobs()
        assert len(listed) == JOB_LIMIT
        listed_ids = {job.id for job in listed}
        assert kept[0] not in listed_ids
        assert kept[-1] in listed_ids
    finally:
        engine.stop()

    started = threading.Event()
    release = threading.Event()
    engine = Engine(FakeRunner(block=release, started=started), lambda q: {})
    engine.start()
    try:
        running = engine.submit({"type": "quotes.sync", "codes": ["000001"]})
        assert started.wait(timeout=2)
        queued = []
        for index in range(JOB_LIMIT):
            queued.append(engine.submit({"type": "quotes.sync", "codes": [f"{index + 2:06d}"]}))
        ids = {job.id for job in engine.list_jobs()}
        assert running.id in ids
        assert {job.id for job in queued} <= ids
        assert len(engine.list_jobs()) == JOB_LIMIT + 1
    finally:
        release.set()
        engine.stop()
