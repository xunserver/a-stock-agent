from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from astock_control.app import create_app
from astock_control.config import SettingsRunner
from astock_control.engine import DispatchRunner, Engine
from astock_control.queries import handle_query
from tests.test_engine import FakeRunner, _wait_status


def test_health_and_status_and_sync() -> None:
    runner = FakeRunner(logs=["pulling"], result={"ok": 1})
    engine = Engine(runner, lambda q: {"pool": q["pool"], "need_full": 0} if q["type"] == "status" else {"pool": q["pool"], "count": 0, "members": []})
    with TestClient(create_app(engine)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True

        status = client.post("/api/queries", json={"type": "status"})
        assert status.status_code == 200
        assert status.json()["pool"] == "default"

        listing = client.post("/api/queries", json={"type": "pool.list"})
        assert listing.status_code == 200
        assert listing.json() == {"pool": "default", "count": 0, "members": []}

        unknown = client.post("/api/commands", json={"type": "nope"})
        assert unknown.status_code == 400
        assert "未知命令" in unknown.json()["error"]

        submitted = client.post("/api/commands", json={"type": "quotes.sync", "pool": "default"})
        assert submitted.status_code == 200
        assert submitted.json()["background"] is True
        job_id = submitted.json()["id"]
        _wait_status(engine, job_id, "succeeded")

        job = client.get(f"/api/jobs/{job_id}")
        assert job.status_code == 200
        body = job.json()
        assert body["status"] == "succeeded"
        assert body["background"] is True
        assert body["name"] == "同步行情 · 全部（池 default）"
        assert body["timeout_seconds"] == 7200
        assert body["result"] == {"ok": 1}
        assert "pulling" in body["log"]

        listed = client.get("/api/jobs")
        assert listed.json()["jobs"][0]["id"] == job_id
        assert listed.json()["jobs"][0]["background"] is True
        assert listed.json()["jobs"][0]["name"] == "同步行情 · 全部（池 default）"
        assert "log" not in listed.json()["jobs"][0]

        invalid_background = client.post(
            "/api/commands",
            json={"type": "pool.create", "pool": "hs", "background": True},
        )
        assert invalid_background.status_code == 400
        assert "不支持后台运行" in invalid_background.json()["error"]


def test_settings_get_and_update() -> None:
    engine = Engine(
        DispatchRunner(
            {
                "quotes.sync": FakeRunner(),
                "settings.update": SettingsRunner(),
            }
        ),
        handle_query,
    )
    with TestClient(create_app(engine)) as client:
        current = client.post("/api/queries", json={"type": "settings.get"})
        assert current.status_code == 200
        body = current.json()
        assert body["pool"] == "default"
        assert body["adjust"] == "qfq"
        assert body["quotes"]["sync_time"] == "16:30"
        assert "db" in body["paths"]
        assert "analyze" in body["paths"]
        assert "analyze" in body
        assert "api_key" not in body["analyze"]
        assert body["analyze"]["api_key_set"] is False

        saved = client.post(
            "/api/commands",
            json={
                "type": "settings.update",
                "settings": {
                    "adjust": "hfq",
                    "quotes": {"sync_enabled": True, "sleep": 0.5},
                },
            },
        )
        assert saved.status_code == 200
        job = saved.json()
        assert job["status"] == "succeeded"
        assert job["background"] is False
        assert job["result"]["adjust"] == "hfq"
        assert job["result"]["quotes"]["sync_enabled"] is True
        assert "api_key" not in job["result"]["analyze"]

        again = client.post("/api/queries", json={"type": "settings.get"})
        assert again.json()["adjust"] == "hfq"
        assert again.json()["quotes"]["sleep"] == 0.5

        bad = client.post(
            "/api/commands",
            json={"type": "settings.update", "settings": {"adjust": "nope"}},
        )
        assert bad.status_code == 400
        assert "复权" in bad.json()["error"]


def test_job_events_stream() -> None:
    engine = Engine(FakeRunner(logs=["one", "two"], result={"done": True}), lambda q: {})
    with TestClient(create_app(engine)) as client:
        submitted = client.post("/api/commands", json={"type": "quotes.sync"})
        job_id = submitted.json()["id"]
        with client.stream("GET", f"/api/jobs/{job_id}/events") as response:
            assert response.status_code == 200
            payload = "".join(response.iter_text())
        assert "one" in payload
        assert "two" in payload
        assert "succeeded" in payload


def test_pool_create_list_delete(tmp_path) -> None:
    from astock_control.adapters.pool import PoolRunner
    from astock_core.db import MarketDB

    db_path = tmp_path / "market.db"
    runner = DispatchRunner(
        {
            "quotes.sync": FakeRunner(),
            "pool.create": PoolRunner(db_path),
            "pool.delete": PoolRunner(db_path),
        }
    )

    def query(raw: dict) -> dict:
        if raw["type"] == "pools.list":
            with MarketDB(db_path) as db:
                pools = db.list_pools()
                return {"count": len(pools), "pools": pools}
        return {}

    engine = Engine(runner, query)
    with TestClient(create_app(engine)) as client:
        created = client.post(
            "/api/commands",
            json={"type": "pool.create", "pool": "hs", "name": "沪深样本"},
        )
        assert created.status_code == 200
        assert created.json()["status"] == "succeeded"
        assert created.json()["result"]["pool"] == "hs"

        listed = client.post("/api/queries", json={"type": "pools.list"})
        ids = [item["id"] for item in listed.json()["pools"]]
        assert "default" in ids
        assert "hs" in ids

        duplicate = client.post("/api/commands", json={"type": "pool.create", "pool": "hs"})
        assert duplicate.json()["status"] == "failed"

        deleted = client.post("/api/commands", json={"type": "pool.delete", "pool": "hs"})
        assert deleted.json()["status"] == "succeeded"
        again = client.post("/api/queries", json={"type": "pools.list"})
        assert [item["id"] for item in again.json()["pools"]] == ["default"]

        last = client.post("/api/commands", json={"type": "pool.delete", "pool": "default"})
        assert last.json()["status"] == "failed"
        assert "至少保留一个" in (last.json()["error"] or "")


def test_stock_catalog_gates_pool_membership(tmp_path) -> None:
    from astock_control.adapters.pool import PoolRunner
    from astock_control.adapters.stock import StockRunner
    from astock_core.db import MarketDB

    db_path = tmp_path / "market.db"
    stocks = StockRunner(db_path)
    pools = PoolRunner(db_path)
    runner = DispatchRunner(
        {
            "quotes.sync": FakeRunner(),
            "stock.add": stocks,
            "stock.remove": stocks,
            "pool.add": pools,
            "pool.remove": pools,
        }
    )

    def query(raw: dict) -> dict:
        with MarketDB(db_path) as db:
            if raw["type"] == "stocks.list":
                items = db.list_stocks()
                in_pool = sum(1 for item in items if item["pools"])
                return {"count": len(items), "in_pool": in_pool, "stocks": items}
            if raw["type"] == "pool.list":
                members = db.list_pool_members(raw["pool"])
                return {"pool": raw["pool"], "count": len(members), "members": members}
        return {}

    engine = Engine(runner, query)
    with TestClient(create_app(engine)) as client:
        added = client.post("/api/commands", json={"type": "stock.add", "codes": ["000001"]})
        assert added.json()["status"] == "succeeded"
        assert added.json()["result"]["added"] == 1

        listed = client.post("/api/queries", json={"type": "stocks.list"})
        assert listed.json()["count"] == 1
        assert listed.json()["stocks"][0]["code"] == "000001"
        assert listed.json()["stocks"][0]["pools"] == []

        unknown = client.post(
            "/api/commands",
            json={"type": "pool.add", "pool": "default", "codes": ["600519"]},
        )
        assert unknown.json()["status"] == "failed"
        assert "还不在系统里" in (unknown.json()["error"] or "")

        in_pool = client.post(
            "/api/commands",
            json={"type": "pool.add", "pool": "default", "codes": ["000001"]},
        )
        assert in_pool.json()["status"] == "succeeded"

        listed = client.post("/api/queries", json={"type": "stocks.list"})
        assert listed.json()["in_pool"] == 1
        assert listed.json()["stocks"][0]["pools"][0]["id"] == "default"

        blocked = client.post("/api/commands", json={"type": "stock.remove", "codes": ["000001"]})
        assert blocked.json()["status"] == "failed"
        assert "股票池" in (blocked.json()["error"] or "")

        out = client.post(
            "/api/commands",
            json={"type": "pool.remove", "pool": "default", "codes": ["000001"]},
        )
        assert out.json()["status"] == "succeeded"

        gone = client.post("/api/commands", json={"type": "stock.remove", "codes": ["000001"]})
        assert gone.json()["status"] == "succeeded"
        assert gone.json()["result"]["removed"] == 1

        empty = client.post("/api/queries", json={"type": "stocks.list"})
        assert empty.json()["count"] == 0


def test_cors_allows_web_and_electron_origins() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    with TestClient(create_app(engine)) as client:
        for origin in (
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "null",
        ):
            response = client.get("/api/health", headers={"Origin": origin})
            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") == origin


def test_cancel_job_endpoint() -> None:
    started = threading.Event()
    release = threading.Event()
    engine = Engine(FakeRunner(block=release, started=started), lambda q: {})
    with TestClient(create_app(engine)) as client:
        first = client.post("/api/commands", json={"type": "quotes.sync", "codes": ["000001"]})
        second = client.post("/api/commands", json={"type": "quotes.sync", "codes": ["000002"]})
        assert first.status_code == 200
        assert started.wait(timeout=2)
        cancelled = client.post(f"/api/jobs/{second.json()['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        missing = client.post("/api/jobs/nope/cancel")
        assert missing.status_code == 404
        release.set()
        _wait_status(engine, first.json()["id"], "succeeded")
        again = client.post(f"/api/jobs/{first.json()['id']}/cancel")
        assert again.status_code == 400
        assert "已结束" in again.json()["error"]


def test_duplicate_command_is_rejected() -> None:
    started = threading.Event()
    release = threading.Event()
    engine = Engine(FakeRunner(block=release, started=started), lambda q: {})
    with TestClient(create_app(engine)) as client:
        first = client.post("/api/commands", json={"type": "quotes.sync"})
        assert first.status_code == 200
        assert started.wait(timeout=2)
        duplicate = client.post("/api/commands", json={"type": "quotes.sync"})
        assert duplicate.status_code == 400
        assert first.json()["id"] in duplicate.json()["error"]
        release.set()
        _wait_status(engine, first.json()["id"], "succeeded")
