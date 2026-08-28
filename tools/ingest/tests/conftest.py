from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_system_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ASTOCK_SYSTEM_DB", str(tmp_path / "system.db"))
    from astock.config import clear_settings_cache

    clear_settings_cache()
    yield
    clear_settings_cache()
