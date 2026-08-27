from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_control_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ASTOCK_CONTROL_CONFIG", str(tmp_path / "control.json"))
    monkeypatch.setenv("ASTOCK_SYSTEM_DB", str(tmp_path / "system.db"))
