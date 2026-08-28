from __future__ import annotations

import time

from astock_core.db import MarketDB
from astock_core.qlib_store import QlibStore

from astock_control.adapters.qlib import qlib_select_argv
from astock_control.engine import Engine
from astock_control.protocol import ProtocolError, normalize_command, normalize_query
from astock_control.queries import handle_query

WORKFLOW = {
    "config": "workflow_lightgbm_alpha158",
    "benchmark": "SH000300",
    "topk": 2,
    "n_drop": 1,
    "account": 1_000_000,
}


class FakeRunner:
    def __init__(self) -> None:
        self.command = None

    def run(self, command, on_log, *, timeout=None, cancel_event=None):
        self.command = dict(command)
        return {"ok": True}


def test_qlib_protocol_normalizes_dump_command() -> None:
    command = normalize_command({"type": "qlib.dump", "pool": "focus"})
    assert command == {"type": "qlib.dump", "pool": "focus"}


def test_qlib_protocol_normalizes_workflow_extensions() -> None:
    command = normalize_command(
        {
            "type": "qlib.run",
            "pool": "focus",
            "workflow": {
                "data_end": "2026-08-25",
                "test_start": "2026-01-01",
                "learning_rate": 0.05,
            },
        }
    )
    assert command["workflow"] == {
        "data_end": "2026-08-25",
        "test_start": "2026-01-01",
        "learning_rate": 0.05,
    }


def test_qlib_protocol_normalizes_command_and_queries() -> None:
    command = normalize_command(
        {
            "type": "qlib.run",
            "pool": "focus",
            "workflow": {"topk": 5, "n_drop": 1},
        }
    )
    assert command == {
        "type": "qlib.run",
        "pool": "focus",
        "workflow": {"topk": 5, "n_drop": 1},
    }
    assert (
        normalize_query({"type": "qlib.overview", "pool": "focus"})["pool"] == "focus"
    )
    assert normalize_query({"type": "qlib.run.get", "run_id": "run-1"}) == {
        "type": "qlib.run.get",
        "run_id": "run-1",
    }


def test_qlib_protocol_rejects_invalid_workflow() -> None:
    try:
        normalize_command({"type": "qlib.run", "workflow": {"topk": 0}})
    except ProtocolError as exc:
        assert "topk" in str(exc)
    else:
        raise AssertionError("invalid topk was accepted")


def test_engine_uses_job_id_as_qlib_run_id() -> None:
    runner = FakeRunner()
    engine = Engine(runner, lambda query: query)
    engine.start()
    try:
        job = engine.submit({"type": "qlib.run", "pool": "focus"})
        assert job.background is True
        deadline = time.time() + 2
        done = engine.get_job(job.id)
        while done is not None and done.status not in {"succeeded", "failed"}:
            assert time.time() < deadline
            time.sleep(0.01)
            done = engine.get_job(job.id)
        assert done is not None and done.status == "succeeded"
        assert done.command["run_id"] == job.id
        assert runner.command["run_id"] == job.id
    finally:
        engine.stop()


def test_qlib_store_keeps_pool_defaults_and_immutable_runs(tmp_path) -> None:
    store = QlibStore(tmp_path / "system.db")
    defaults = dict(WORKFLOW)
    first = store.save_workflow("first", {**WORKFLOW, "topk": 1})
    second = store.get_workflow("second", defaults)
    assert first["topk"] == 1
    assert second["topk"] == 2
    assert second["updated_at"] is None

    stored = store.record_run(
        {
            "run_id": "run-1",
            "job_id": "run-1",
            "pool": "first",
            "as_of": "2026-08-25",
            "workflow": first,
            "artifact_ref": "/tmp/pred.pkl",
            "universe_size": 2,
            "candidates": [
                {"rank": 1, "code": "000001", "symbol": "SZ000001", "score": 0.8},
                {"rank": 2, "code": "600519", "symbol": "SH600519", "score": 0.7},
            ],
        }
    )
    assert stored["candidate_count"] == 2
    assert [item["code"] for item in stored["candidates"]] == ["000001", "600519"]
    assert store.list_runs("second") == []


def test_qlib_queries_add_stock_names(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    with MarketDB(db_path) as db:
        db.create_pool("focus", "重点池")
        db.add_stocks([("000001", "平安银行")])
        db.add_pool_members("focus", [("000001", "平安银行")], source="manual")
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    qlib_root = tmp_path / "qlib" / "pools" / "focus"
    (qlib_root / "calendars").mkdir(parents=True)
    (qlib_root / "instruments").mkdir()
    (qlib_root / "calendars" / "day.txt").write_text("2026-08-25\n", encoding="utf-8")
    (qlib_root / "instruments" / "focus.txt").write_text(
        "SZ000001\t2026-08-25\t2026-08-25\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "astock_control.queries.pool_qlib_dir",
        lambda pool_id: tmp_path / "qlib" / "pools" / pool_id,
    )

    store = QlibStore()
    store.record_run(
        {
            "run_id": "query-run",
            "pool": "focus",
            "as_of": "2026-08-25",
            "workflow": WORKFLOW,
            "artifact_ref": "/tmp/pred.pkl",
            "universe_size": 1,
            "candidates": [
                {"rank": 1, "code": "000001", "symbol": "SZ000001", "score": 0.8}
            ],
        }
    )
    detail = handle_query({"type": "qlib.run.get", "run_id": "query-run"})
    assert detail["candidates"][0]["name"] == "平安银行"
    overview = handle_query({"type": "qlib.overview", "pool": "focus"})
    assert overview["pool"]["active"] == 1
    assert overview["latest_run"]["run_id"] == "query-run"


def test_qlib_argv_contains_effective_workflow() -> None:
    argv = qlib_select_argv(
        {"pool": "focus", "run_id": "job-1"},
        {**WORKFLOW, "data_end": "2026-08-25", "learning_rate": 0.05},
    )
    assert argv[argv.index("--pool") + 1] == "focus"
    assert argv[argv.index("--run-id") + 1] == "job-1"
    assert argv[argv.index("--topk") + 1] == "2"
    assert argv[argv.index("--data-end") + 1] == "2026-08-25"
    assert argv[argv.index("--learning-rate") + 1] == "0.05"
