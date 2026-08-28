from __future__ import annotations

import json

import pytest

from astock_control.config import load_settings, preview_update, settings_view, validate_settings, write_settings
from astock_control.engine import Engine
from astock_control.protocol import ProtocolError
from tests.test_engine import FakeRunner, _wait_status


def test_defaults_when_file_missing() -> None:
    settings = load_settings()
    assert settings["pool"] == "default"
    assert settings["adjust"] == "qfq"
    assert settings["quotes"]["sync_enabled"] is False
    assert settings["quotes"]["sync_time"] == "16:30"
    assert settings["quotes"]["sleep"] == 0.35
    assert settings["quotes"]["history_start"] == "20000101"
    assert settings["quotes"]["periods"] == ["daily", "weekly", "monthly"]
    assert settings["quotes"]["retries"] == 3
    assert settings["quotes"]["default_years"] == 5
    assert settings["indexes"]["hs300_symbol"] == "000300"
    assert settings["indexes"]["aliases"]["hs300"] == "000300"
    assert settings["analyze"]["llm_provider"] == "openai_compatible"
    assert settings["analyze"]["analysts"] == ["market", "news", "fundamentals"]
    assert settings["analyze"]["api_key"] == ""
    assert settings["analyze"]["temperature"] is None


def test_write_and_load_roundtrip() -> None:
    write_settings(
        {
            "pool": "hs300",
            "adjust": "hfq",
            "quotes": {"sync_enabled": True, "sleep": 0.5, "sync_time": "16:20"},
        }
    )
    loaded = load_settings()
    assert loaded["pool"] == "hs300"
    assert loaded["adjust"] == "hfq"
    assert loaded["quotes"]["sync_enabled"] is True
    assert loaded["quotes"]["sleep"] == 0.5
    assert loaded["quotes"]["sync_time"] == "16:20"
    assert loaded["quotes"]["timezone"] == "Asia/Shanghai"


def test_preview_rejects_bad_adjust() -> None:
    with pytest.raises(ValueError, match="复权"):
        preview_update({"adjust": "bad"})


def test_preview_rejects_nan_sleep() -> None:
    with pytest.raises(ValueError, match="请求间隔"):
        preview_update({"quotes": {"sleep": float("nan")}})


def test_quotes_sync_inherits_saved_defaults() -> None:
    write_settings(
        {
            "adjust": "hfq",
            "quotes": {"sleep": 0.9, "history_start": "20000101"},
        }
    )
    runner = FakeRunner()
    engine = Engine(runner, lambda q: {})
    engine.start()
    try:
        job = engine.submit({"type": "quotes.sync"})
        _wait_status(engine, job.id, "succeeded")
        assert runner.calls[0]["sleep"] == 0.9
        assert runner.calls[0]["adjust"] == "hfq"
        assert runner.calls[0]["pool"] == "default"
        assert runner.calls[0]["history_start"] == "20000101"
        assert runner.calls[0]["periods"] == ["daily", "weekly", "monthly"]
    finally:
        engine.stop()


def test_settings_update_runs_immediately() -> None:
    runner = FakeRunner(result={"pool": "default", "adjust": "qfq"})
    engine = Engine(runner, lambda q: {})
    job = engine.submit({"type": "settings.update", "settings": {"adjust": ""}})
    assert job.status == "succeeded"
    assert runner.calls[0]["type"] == "settings.update"
    assert runner.calls[0]["settings"]["adjust"] == ""


def test_settings_update_rejects_before_queue() -> None:
    engine = Engine(FakeRunner(), lambda q: {})
    with pytest.raises(ProtocolError, match="复权"):
        engine.submit({"type": "settings.update", "settings": {"adjust": "xx"}})
    assert engine.list_jobs() == []


def test_write_persists_in_system_db() -> None:
    from astock_core.settings import SystemDB
    from astock_core.paths import system_db_path

    write_settings({"pool": "default"})
    assert system_db_path().is_file()
    with SystemDB() as db:
        quotes = db.get_values("ingest", "quotes")
        assert quotes["pool"] == "default"
        llm = db.get_section("analyze", "llm")
        assert "properties" in llm["schema"]
        assert llm["schema"]["properties"]["api_key"]["x-secret"] is True


def test_validate_accepts_legal_analyze() -> None:
    settings = validate_settings(load_settings())
    assert settings["analyze"]["max_debate_rounds"] == 1
    patched = preview_update(
        {
            "analyze": {
                "llm_provider": "deepseek",
                "analysts": ["market", "social"],
                "max_debate_rounds": 2,
                "max_risk_discuss_rounds": 3,
                "output_language": "English",
                "temperature": 0.2,
            }
        }
    )
    assert patched["analyze"]["llm_provider"] == "deepseek"
    assert patched["analyze"]["analysts"] == ["market", "social"]
    assert patched["analyze"]["temperature"] == 0.2


def test_validate_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="提供商"):
        preview_update({"analyze": {"llm_provider": "not-a-provider"}})


def test_validate_rejects_empty_analysts() -> None:
    with pytest.raises(ValueError, match="分析师"):
        preview_update({"analyze": {"analysts": []}})


def test_validate_rejects_zero_rounds() -> None:
    with pytest.raises(ValueError, match="辩论轮数"):
        preview_update({"analyze": {"max_debate_rounds": 0}})


def test_settings_view_hides_api_key() -> None:
    secret = "sk-test-secret-key-xyz"
    write_settings({"analyze": {"api_key": secret}})
    view = settings_view()
    assert "api_key" not in view["analyze"]
    assert view["analyze"]["api_key_set"] is True
    assert view["analyze"]["api_key_hint"] == "••••"
    assert secret not in json.dumps(view)
    assert load_settings()["analyze"]["api_key"] == secret


def test_omitting_api_key_keeps_secret_in_file() -> None:
    secret = "sk-test-secret-key-xyz"
    write_settings({"analyze": {"api_key": secret}})
    write_settings(preview_update({"analyze": {"deep_think_llm": "qwen-plus"}}))
    loaded = load_settings()
    assert loaded["analyze"]["api_key"] == secret
    assert loaded["analyze"]["deep_think_llm"] == "qwen-plus"


def test_empty_api_key_keeps_secret_in_file() -> None:
    secret = "sk-test-secret-key-xyz"
    write_settings({"analyze": {"api_key": secret}})
    write_settings(preview_update({"analyze": {"api_key": ""}}))
    assert load_settings()["analyze"]["api_key"] == secret


def test_quotes_sleep_does_not_clear_api_key() -> None:
    secret = "sk-test-secret-key-xyz"
    write_settings({"analyze": {"api_key": secret}})
    write_settings(preview_update({"quotes": {"sleep": 0.8}}))
    loaded = load_settings()
    assert loaded["analyze"]["api_key"] == secret
    assert loaded["quotes"]["sleep"] == 0.8


def test_analyze_run_inherits_analysts() -> None:
    write_settings({"analyze": {"analysts": ["market", "news"]}})
    runner = FakeRunner()
    engine = Engine(runner, lambda q: {})
    engine.start()
    try:
        job = engine.submit({"type": "analyze.run", "code": "1"})
        done = _wait_status(engine, job.id, "succeeded")
        assert done.command["code"] == "000001"
        assert done.command["ticker"] == "000001.SZ"
        assert done.command["analysts"] == ["market", "news"]
        assert "api_key" not in done.command
        assert runner.calls[0]["analysts"] == ["market", "news"]
    finally:
        engine.stop()
