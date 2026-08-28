from __future__ import annotations

import json

from fastapi.testclient import TestClient

from astock_control.app import create_app
from astock_control.config import SettingsRunner
from astock_control.engine import DispatchRunner, Engine
from astock_control.queries import handle_query
from astock_core.paths import control_json_path, system_db_path
from tests.test_engine import FakeRunner


def _client() -> TestClient:
    engine = Engine(
        DispatchRunner(
            {
                "quotes.sync": FakeRunner(),
                "settings.update": SettingsRunner(),
            }
        ),
        handle_query,
    )
    return TestClient(create_app(engine))


def test_catalog_lists_modules_and_persists_schema() -> None:
    with _client() as client:
        response = client.post("/api/queries", json={"type": "settings.catalog"})
        assert response.status_code == 200
        body = response.json()
        module_ids = [item["id"] for item in body["modules"]]
        assert module_ids == ["ingest", "analyze", "qlib", "system"]

        ingest = body["modules"][0]
        assert ingest["title"] == "行情采集"
        assert [item["id"] for item in ingest["sections"]] == ["quotes", "indexes", "schedule"]
        quotes = ingest["sections"][0]
        assert quotes["schema"]["properties"]["pool"]["type"] == "string"
        assert quotes["values"]["pool"] == "default"
        assert quotes["values"]["adjust"] == "qfq"
        assert quotes["values"]["history_start"] == "20000101"
        assert quotes["values"]["periods"] == ["daily", "weekly", "monthly"]
        indexes = ingest["sections"][1]
        assert indexes["values"]["hs300_symbol"] == "000300"
        assert indexes["values"]["aliases"]["hs300"] == "000300"

        analyze = next(item for item in body["modules"] if item["id"] == "analyze")
        llm = next(item for item in analyze["sections"] if item["id"] == "llm")
        assert llm["schema"]["properties"]["api_key"]["x-secret"] is True
        assert "api_key" not in llm["values"]
        assert llm["values"]["api_key_set"] is False

        qlib = next(item for item in body["modules"] if item["id"] == "qlib")
        assert [item["id"] for item in qlib["sections"]] == ["data", "workflow"]

        system = next(item for item in body["modules"] if item["id"] == "system")
        paths = system["sections"][0]
        assert paths["read_only"] is True
        assert paths["values"]["system"] == str(system_db_path())


def test_section_get_and_update_roundtrip() -> None:
    with _client() as client:
        saved = client.post(
            "/api/commands",
            json={
                "type": "settings.update",
                "module": "ingest",
                "section": "quotes",
                "values": {"adjust": "hfq", "sleep": 0.5},
            },
        )
        assert saved.status_code == 200
        job = saved.json()
        assert job["status"] == "succeeded"
        assert job["result"]["module"] == "ingest"
        assert job["result"]["section"] == "quotes"
        assert job["result"]["values"]["adjust"] == "hfq"
        assert job["result"]["values"]["sleep"] == 0.5
        assert job["result"]["values"]["pool"] == "default"
        assert "api_key" not in json.dumps(job)

        fetched = client.post(
            "/api/queries",
            json={"type": "settings.get", "module": "ingest", "section": "quotes"},
        )
        assert fetched.status_code == 200
        assert fetched.json()["values"]["adjust"] == "hfq"
        assert fetched.json()["schema"]["properties"]["sleep"]["minimum"] == 0


def test_updating_one_section_does_not_change_another() -> None:
    with _client() as client:
        client.post(
            "/api/commands",
            json={
                "type": "settings.update",
                "module": "analyze",
                "section": "llm",
                "values": {"deep_think_llm": "qwen-plus", "api_key": "sk-secret"},
            },
        )
        client.post(
            "/api/commands",
            json={
                "type": "settings.update",
                "module": "ingest",
                "section": "quotes",
                "values": {"sleep": 0.9},
            },
        )

        llm = client.post(
            "/api/queries",
            json={"type": "settings.get", "module": "analyze", "section": "llm"},
        ).json()
        quotes = client.post(
            "/api/queries",
            json={"type": "settings.get", "module": "ingest", "section": "quotes"},
        ).json()
        schedule = client.post(
            "/api/queries",
            json={"type": "settings.get", "module": "ingest", "section": "schedule"},
        ).json()

        assert llm["values"]["deep_think_llm"] == "qwen-plus"
        assert llm["values"]["api_key_set"] is True
        assert "api_key" not in llm["values"]
        assert quotes["values"]["sleep"] == 0.9
        assert quotes["values"]["adjust"] == "qfq"
        assert schedule["values"]["sync_time"] == "16:30"


def test_section_values_survive_new_http_client() -> None:
    with _client() as client:
        client.post(
            "/api/commands",
            json={
                "type": "settings.update",
                "module": "qlib",
                "section": "workflow",
                "values": {"topk": 20, "benchmark": "SH000001"},
            },
        )

    with _client() as client:
        catalog = client.post("/api/queries", json={"type": "settings.catalog"}).json()
        qlib = next(item for item in catalog["modules"] if item["id"] == "qlib")
        workflow = next(item for item in qlib["sections"] if item["id"] == "workflow")
        assert workflow["values"]["topk"] == 20
        assert workflow["values"]["benchmark"] == "SH000001"
        assert workflow["schema"]["properties"]["topk"]["type"] == "integer"


def test_invalid_section_update_is_rejected_before_queue() -> None:
    with _client() as client:
        bad = client.post(
            "/api/commands",
            json={
                "type": "settings.update",
                "module": "ingest",
                "section": "quotes",
                "values": {"adjust": "nope"},
            },
        )
        assert bad.status_code == 400
        assert "复权" in bad.json()["error"]

        listed = client.get("/api/jobs")
        assert listed.json()["jobs"] == []


def test_read_only_paths_cannot_be_updated() -> None:
    with _client() as client:
        bad = client.post(
            "/api/commands",
            json={
                "type": "settings.update",
                "module": "system",
                "section": "paths",
                "values": {"db": "/tmp/nope.db"},
            },
        )
        assert bad.status_code == 400
        assert "不能修改" in bad.json()["error"]


def test_legacy_settings_get_still_assembles_view() -> None:
    with _client() as client:
        client.post(
            "/api/commands",
            json={
                "type": "settings.update",
                "settings": {"adjust": "hfq", "quotes": {"sleep": 0.5}},
            },
        )
        current = client.post("/api/queries", json={"type": "settings.get"})
        body = current.json()
        assert body["adjust"] == "hfq"
        assert body["quotes"]["sleep"] == 0.5
        assert "api_key" not in body["analyze"]
        assert "db" in body["paths"]
        assert "system" in body["paths"]


def test_migrates_legacy_control_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ASTOCK_CONTROL_CONFIG", str(tmp_path / "legacy.json"))
    monkeypatch.setenv("ASTOCK_SYSTEM_DB", str(tmp_path / "migrated.db"))
    control_json_path().write_text(
        json.dumps(
            {
                "pool": "hs300",
                "adjust": "hfq",
                "quotes": {"sleep": 0.8, "sync_enabled": True, "sync_time": "16:20"},
                "analyze": {
                    "llm_provider": "deepseek",
                    "deep_think_llm": "deepseek-chat",
                    "api_key": "sk-migrated",
                    "analysts": ["market", "news"],
                },
            }
        ),
        encoding="utf-8",
    )

    with _client() as client:
        catalog = client.post("/api/queries", json={"type": "settings.catalog"}).json()
        ingest = next(item for item in catalog["modules"] if item["id"] == "ingest")
        quotes = next(item for item in ingest["sections"] if item["id"] == "quotes")
        schedule = next(item for item in ingest["sections"] if item["id"] == "schedule")
        analyze = next(item for item in catalog["modules"] if item["id"] == "analyze")
        llm = next(item for item in analyze["sections"] if item["id"] == "llm")
        graph = next(item for item in analyze["sections"] if item["id"] == "graph")

        assert quotes["values"]["pool"] == "hs300"
        assert quotes["values"]["adjust"] == "hfq"
        assert quotes["values"]["sleep"] == 0.8
        assert schedule["values"]["sync_enabled"] is True
        assert schedule["values"]["sync_time"] == "16:20"
        assert llm["values"]["llm_provider"] == "deepseek"
        assert llm["values"]["deep_think_llm"] == "deepseek-chat"
        assert llm["values"]["api_key_set"] is True
        assert "api_key" not in llm["values"]
        assert graph["values"]["analysts"] == ["market", "news"]
