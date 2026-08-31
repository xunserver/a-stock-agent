from __future__ import annotations

from fastapi.testclient import TestClient

from astock_control.app import create_app
from astock_control.engine import JobService


class FakeRunner:
    def run(self, command, on_log, *, timeout=None, cancel_event=None):
        return {"ok": True, "type": command["type"]}


def test_new_http_contract_exposes_feature_routes_and_typed_jobs() -> None:
    engine = JobService(FakeRunner())
    with TestClient(create_app(engine)) as client:
        catalog = client.get("/api/settings/catalog")
        submitted = client.post(
            "/api/jobs",
            json={"type": "boards.sync", "kind": "all"},
        )
        invalid = client.post(
            "/api/jobs",
            json={"type": "boards.sync", "timeout": 0},
        )

    assert catalog.status_code == 200
    assert catalog.json()["modules"]
    assert submitted.status_code == 202
    assert submitted.json()["type"] == "boards.sync"
    assert invalid.status_code == 422


def test_openapi_contains_named_feature_routes() -> None:
    schema = create_app(JobService(FakeRunner())).openapi()
    paths = schema["paths"]
    assert "/api/pools" in paths
    assert "/api/stocks/{code}" in paths
    assert "/api/calendars/{market}/{year}/{month}" in paths
    assert "/api/analyses/{code}/{date}" in paths
    assert "/api/commands" not in paths
    assert "/api/queries" not in paths
    job_schema = paths["/api/jobs"]["post"]["responses"]["202"]["content"]
    assert job_schema["application/json"]["schema"]["$ref"].endswith("/JobResponse")


def test_legacy_generic_endpoints_are_not_found() -> None:
    with TestClient(create_app(JobService(FakeRunner()))) as client:
        assert client.post("/api/commands", json={"type": "quotes.sync"}).status_code == 404
        assert client.post("/api/queries", json={"type": "status"}).status_code == 404
