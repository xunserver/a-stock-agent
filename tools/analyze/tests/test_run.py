from __future__ import annotations

import json
from pathlib import Path

import pytest

from astock_analyze.cli import main
from astock_analyze.config import AnalyzeError, AnalyzeSettings, BUILTIN_DEFAULTS, load_settings, validate_run_config
from astock_analyze.run import run_analysis


class FakeGraph:
    def __init__(self, selected_analysts=(), debug=False, config=None):
        self.selected_analysts = selected_analysts
        self.debug = debug
        self.config = config or {}

    def propagate(self, ticker, date):
        return {"ticker": ticker, "date": date}, "Hold"

    def save_reports(self, state, ticker, save_path=None):
        path = Path(save_path)
        path.mkdir(parents=True, exist_ok=True)
        (path / "complete_report.md").write_text("# Hold\n", encoding="utf-8")
        return path


class FakeDB:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def get_stock(self, code):
        return {"code": code, "name": "平安银行"}

    def last_bar_date(self, code, adjust=None):
        return "2026-08-25"

    def pool_membership(self, pool, code):
        if pool == "empty":
            return None
        return {"status": "active", "code": code, "pool_id": pool}


def _ready_file_config(**overrides):
    data = {
        "llm_provider": "openai_compatible",
        "backend_url": "http://127.0.0.1:8000/v1",
        "deep_think_llm": "qwen-plus",
        "quick_think_llm": "qwen-plus",
    }
    data.update(overrides)
    return data


def _settings_with(**overrides) -> AnalyzeSettings:
    data = {
        "llm_provider": BUILTIN_DEFAULTS["llm_provider"],
        "deep_think_llm": "qwen-plus",
        "quick_think_llm": "qwen-plus",
        "backend_url": "http://127.0.0.1:8000/v1",
        "api_key": "",
        "output_language": "Chinese",
        "analysts": ("market", "news", "fundamentals"),
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        "temperature": None,
        "checkpoint_enabled": False,
    }
    data.update(overrides)
    return AnalyzeSettings(**data)


def test_run_fails_before_graph_without_key(monkeypatch, capsys) -> None:
    imported = {"called": False}

    def boom():
        imported["called"] = True
        raise AssertionError("should not import TradingAgentsGraph")

    monkeypatch.setattr(
        "astock_analyze.config.read_control_analyze",
        lambda: {
            "llm_provider": "openai",
            "deep_think_llm": "gpt-4o",
            "quick_think_llm": "gpt-4o-mini",
        },
    )
    monkeypatch.setattr("astock_analyze.run.import_graph", boom)

    code = main(["run", "--code", "000001"])
    err = capsys.readouterr().err
    assert code == 2
    assert imported["called"] is False
    assert "密钥" in err
    assert "OPENAI_API_KEY" in err
    assert "sk-" not in err


def test_default_run_fails_fast_in_chinese(monkeypatch, capsys) -> None:
    imported = {"called": False}

    def boom():
        imported["called"] = True
        raise AssertionError("should not import TradingAgentsGraph")

    monkeypatch.setattr("astock_analyze.run.import_graph", boom)
    code = main(["run", "--code", "000001"])
    err = capsys.readouterr().err
    assert code == 2
    assert imported["called"] is False
    assert err.strip()
    assert any(token in err for token in ("模型", "接口地址", "backend_url"))


def test_illegal_code_fails_before_graph(monkeypatch, capsys) -> None:
    imported = {"called": False}

    def boom():
        imported["called"] = True
        raise AssertionError("should not import TradingAgentsGraph")

    monkeypatch.setattr("astock_analyze.run.import_graph", boom)
    code = main(["run", "--code", "not-a-code"])
    err = capsys.readouterr().err
    assert code == 2
    assert imported["called"] is False
    assert "不合法" in err


def test_openai_compatible_allows_missing_key_but_needs_url() -> None:
    with pytest.raises(AnalyzeError, match="backend_url"):
        validate_run_config(
            _settings_with(
                llm_provider="openai_compatible",
                backend_url="",
                api_key="",
            )
        )


def test_ollama_allows_missing_key() -> None:
    validate_run_config(
        _settings_with(
            llm_provider="ollama",
            backend_url="http://127.0.0.1:11434/v1",
            api_key="",
        )
    )


def test_single_model_fills_both(monkeypatch) -> None:
    monkeypatch.setattr(
        "astock_analyze.config.read_control_analyze",
        lambda: {
            "llm_provider": "ollama",
            "deep_think_llm": "qwen2.5",
        },
    )
    settings = load_settings()
    assert settings.deep_think_llm == "qwen2.5"
    assert settings.quick_think_llm == "qwen2.5"
    assert settings.backend_url == "http://127.0.0.1:11434/v1"


def test_meta_json_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("astock_analyze.run.ANALYZE_DIR", tmp_path)
    monkeypatch.setattr(
        "astock_analyze.config.read_control_analyze",
        lambda: _ready_file_config(),
    )
    monkeypatch.setattr(
        "astock_analyze.run.import_graph",
        lambda: (FakeGraph, {"llm_provider": "openai"}),
    )
    monkeypatch.setattr("astock_analyze.run.MarketDB", FakeDB)

    result = run_analysis(raw_code="000001", date="2026-08-25")
    report_dir = Path(result["report_dir"])
    meta = json.loads((report_dir / "meta.json").read_text(encoding="utf-8"))

    assert result["code"] == "000001"
    assert result["ticker"] == "000001.SZ"
    assert result["date"] == "2026-08-25"
    assert result["decision"] == "Hold"
    assert result["complete_report"] == str(report_dir / "complete_report.md")
    assert meta["code"] == "000001"
    assert meta["ticker"] == "000001.SZ"
    assert meta["name"] == "平安银行"
    assert meta["date"] == "2026-08-25"
    assert meta["run_id"] == result["run_id"]
    assert meta["analysts"] == ["market", "news", "fundamentals"]
    assert meta["created_at"]
    assert meta["status"] == "succeeded"
    assert meta["decision"] == "Hold"
    assert "api_key" not in meta
    assert (report_dir / "complete_report.md").is_file()


def test_pool_membership_rejected(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("astock_analyze.run.ANALYZE_DIR", tmp_path)
    monkeypatch.setattr(
        "astock_analyze.config.read_control_analyze",
        lambda: _ready_file_config(),
    )
    monkeypatch.setattr(
        "astock_analyze.run.import_graph",
        lambda: (FakeGraph, {"llm_provider": "openai"}),
    )
    monkeypatch.setattr("astock_analyze.run.MarketDB", FakeDB)

    code = main(["run", "--code", "000001", "--pool", "empty", "--date", "2026-08-25"])
    err = capsys.readouterr().err
    assert code == 2
    assert "股票池" in err
