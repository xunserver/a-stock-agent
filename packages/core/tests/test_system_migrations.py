from __future__ import annotations

import sqlite3

from astock_core.automation import AutomationStore
from astock_core.qlib_store import QlibStore
from astock_core.settings.db import SystemDB


def test_system_namespaces_migrate_independently_and_keep_data(tmp_path) -> None:
    path = tmp_path / "system.db"
    with SystemDB(path) as settings:
        settings.meta_set("test-marker", "kept")

    automations = AutomationStore(path)
    created = automations.create_automation(
        {
            "id": "daily-quotes",
            "name": "行情同步",
            "command": {"type": "quotes.sync", "pool": "default"},
            "schedule_kind": "daily",
            "local_time": "16:10",
            "timezone": "Asia/Shanghai",
        }
    )

    qlib = QlibStore(path)
    qlib.save_workflow(
        "default",
        {
            "config": "workflow.yaml",
            "benchmark": "SH000300",
            "topk": 5,
            "n_drop": 1,
            "account": 1_000_000,
            "data_end": "2026-08-28",
            "test_start": "2026-01-01",
            "learning_rate": 0.05,
        },
    )

    # Reopening every store repeats migration discovery on the same SQLite file.
    with SystemDB(path) as settings:
        assert settings.meta_get("test-marker") == "kept"
    assert AutomationStore(path).get_automation(created["id"])["name"] == "行情同步"
    assert QlibStore(path).get_workflow("default", {})["data_end"] == "2026-08-28"

    connection = sqlite3.connect(path)
    versions = dict(connection.execute("SELECT namespace, version FROM _schema_migrations"))
    connection.close()
    assert versions == {"settings": 1, "automation": 1, "qlib": 2}
