from __future__ import annotations

import json
from pathlib import Path

import pytest

from astock_control.adapters.analyze import ANALYZE_DIR, analyze_child_env, analyze_run_argv
from astock_control.protocol import ProtocolError, normalize_command, normalize_query
from astock_control.queries import handle_query
from astock_core.db import MarketDB
from astock_core.paths import REPO_ROOT


def test_analyze_run_pads_code_and_maps_ticker() -> None:
    cmd = normalize_command({"type": "analyze.run", "code": "1"})
    assert cmd["code"] == "000001"
    assert cmd["ticker"] == "000001.SZ"
    assert cmd["pool"] == "default"
    assert "analysts" not in cmd
    assert "api_key" not in cmd

    shanghai = normalize_command({"type": "analyze.run", "code": "600519"})
    assert shanghai["ticker"] == "600519.SS"
    gem = normalize_command({"type": "analyze.run", "code": "688111"})
    assert gem["ticker"] == "688111.SS"
    chi = normalize_command({"type": "analyze.run", "code": "300750"})
    assert chi["ticker"] == "300750.SZ"


def test_analyze_run_rejects_invalid_code() -> None:
    with pytest.raises(ProtocolError, match="无效股票代码"):
        normalize_command({"type": "analyze.run", "code": "abc"})


def test_analyze_run_rejects_unknown_analyst() -> None:
    with pytest.raises(ProtocolError, match="分析师"):
        normalize_command(
            {"type": "analyze.run", "code": "000001", "analysts": ["market", "foo"]}
        )


def test_analyze_run_rejects_empty_analysts() -> None:
    with pytest.raises(ProtocolError, match="分析师"):
        normalize_command({"type": "analyze.run", "code": "000001", "analysts": []})


def test_analyze_run_rejects_multiple_codes() -> None:
    with pytest.raises(ProtocolError, match="恰好"):
        normalize_command({"type": "analyze.run", "code": "000001,600519"})


def test_analyze_list_and_get_queries_normalize() -> None:
    listed = normalize_query({"type": "analyze.list", "code": "1"})
    assert listed == {"type": "analyze.list", "code": "000001"}
    got = normalize_query(
        {"type": "analyze.get", "code": "000001", "date": "2026-08-25", "run_id": "abc"}
    )
    assert got["date"] == "2026-08-25"
    assert got["run_id"] == "abc"


def test_analyze_argv_has_no_secret() -> None:
    secret = "sk-SHOULD-NOT-APPEAR"
    argv = analyze_run_argv(
        {
            "type": "analyze.run",
            "code": "000001",
            "date": "2026-08-25",
            "pool": "default",
            "analysts": ["market", "news", "fundamentals"],
            "api_key": secret,
        }
    )
    directory = argv[argv.index("--directory") + 1]
    assert Path(directory) == ANALYZE_DIR
    assert ANALYZE_DIR == REPO_ROOT / "tools" / "analyze"
    assert "--json" in argv
    assert argv[argv.index("--code") + 1] == "000001"
    assert argv[argv.index("--date") + 1] == "2026-08-25"
    assert argv[argv.index("--analysts") + 1] == "market,news,fundamentals"
    assert secret not in " ".join(argv)


def test_analyze_env_puts_key_in_env_not_argv() -> None:
    env = analyze_child_env(
        {
            "llm_provider": "openai_compatible",
            "api_key": "sk-secret",
            "backend_url": "http://127.0.0.1:8000/v1",
            "deep_think_llm": "qwen-plus",
            "quick_think_llm": "qwen-turbo",
            "output_language": "Chinese",
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "checkpoint_enabled": False,
        }
    )
    assert env["OPENAI_COMPATIBLE_API_KEY"] == "sk-secret"
    assert env["TRADINGAGENTS_LLM_BACKEND_URL"] == "http://127.0.0.1:8000/v1"
    assert env["TRADINGAGENTS_LLM_PROVIDER"] == "openai_compatible"
    assert env["TRADINGAGENTS_DEEP_THINK_LLM"] == "qwen-plus"

    ollama = analyze_child_env(
        {
            "llm_provider": "ollama",
            "api_key": "sk-secret",
            "backend_url": "http://127.0.0.1:11434/v1",
        }
    )
    assert "OPENAI_COMPATIBLE_API_KEY" not in ollama
    assert ollama["OLLAMA_BASE_URL"] == "http://127.0.0.1:11434/v1"
    assert ollama["TRADINGAGENTS_LLM_BACKEND_URL"] == "http://127.0.0.1:11434/v1"


def _write_report(
    root: Path,
    *,
    code: str,
    date: str,
    run_id: str,
    created_at: str,
    decision: str = "Hold",
    extra_md: dict[str, str] | None = None,
) -> Path:
    run_dir = root / "reports" / code / date / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "code": code,
        "ticker": f"{code}.SZ",
        "date": date,
        "run_id": run_id,
        "analysts": ["market", "news"],
        "created_at": created_at,
        "status": "succeeded",
        "decision": decision,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if extra_md:
        for relative, text in extra_md.items():
            path = run_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    return run_dir


def test_analyze_list_and_get(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行")])
    monkeypatch.setattr("astock_control.queries.ANALYZE_DIR", tmp_path)
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)

    older = _write_report(
        tmp_path,
        code="000001",
        date="2026-08-24",
        run_id="oldrun",
        created_at="2026-08-24T10:00:00+00:00",
        decision="Buy",
    )
    newer = _write_report(
        tmp_path,
        code="000001",
        date="2026-08-25",
        run_id="newrun",
        created_at="2026-08-25T15:01:00+00:00",
        extra_md={
            "complete_report.md": "全文",
            "1_analysts/market.md": "技术面",
            "5_portfolio/decision.md": "组合建议",
        },
    )
    _write_report(
        tmp_path,
        code="600519",
        date="2026-08-25",
        run_id="other",
        created_at="2026-08-25T12:00:00+00:00",
        decision="Sell",
    )

    listed = handle_query({"type": "analyze.list"})
    assert listed["count"] == 3
    assert [item["run_id"] for item in listed["reports"]] == ["newrun", "other", "oldrun"]
    first = listed["reports"][0]
    assert first["code"] == "000001"
    assert first["name"] == "平安银行"
    assert first["decision"] == "Hold"
    assert first["report_dir"] == str(newer)
    assert "complete_report" not in first

    filtered = handle_query({"type": "analyze.list", "code": "000001"})
    assert filtered["count"] == 2
    assert all(item["code"] == "000001" for item in filtered["reports"])

    got = handle_query({"type": "analyze.get", "code": "000001", "date": "2026-08-25"})
    assert got["run_id"] == "newrun"
    assert got["name"] == "平安银行"
    assert got["complete_report"] == "全文"
    assert got["market"] == "技术面"
    assert got["portfolio"] == "组合建议"
    assert "news" not in got
    assert got["report_dir"] == str(newer)

    specific = handle_query(
        {"type": "analyze.get", "code": "000001", "date": "2026-08-24", "run_id": "oldrun"}
    )
    assert specific["run_id"] == "oldrun"
    assert specific["decision"] == "Buy"
    assert "complete_report" not in specific
    assert specific["report_dir"] == str(older)


def test_analyze_get_missing_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("astock_control.queries.ANALYZE_DIR", tmp_path)
    monkeypatch.setattr("astock_control.queries.DB_PATH", tmp_path / "missing.db")
    with pytest.raises(ValueError, match="找不到分析报告"):
        handle_query({"type": "analyze.get", "code": "000001", "date": "2026-08-25"})
