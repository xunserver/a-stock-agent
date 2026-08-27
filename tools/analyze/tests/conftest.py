from __future__ import annotations

import os

import pytest

_LLM_ENV = (
    "OPENAI_API_KEY",
    "OPENAI_COMPATIBLE_API_KEY",
    "DASHSCOPE_CN_API_KEY",
    "DASHSCOPE_API_KEY",
    "DEEPSEEK_API_KEY",
    "ZHIPU_CN_API_KEY",
    "ZHIPU_API_KEY",
    "TRADINGAGENTS_LLM_PROVIDER",
    "TRADINGAGENTS_DEEP_THINK_LLM",
    "TRADINGAGENTS_QUICK_THINK_LLM",
    "TRADINGAGENTS_LLM_BACKEND_URL",
    "TRADINGAGENTS_OUTPUT_LANGUAGE",
    "TRADINGAGENTS_MAX_DEBATE_ROUNDS",
    "TRADINGAGENTS_MAX_RISK_ROUNDS",
    "TRADINGAGENTS_CHECKPOINT_ENABLED",
    "TRADINGAGENTS_TEMPERATURE",
)


@pytest.fixture(autouse=True)
def isolate_analyze_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests off the developer's LLM keys and control.json."""
    for name in _LLM_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("astock_analyze.config.read_control_analyze", lambda: {})
    for name in list(os.environ):
        if name.endswith("_API_KEY"):
            monkeypatch.delenv(name, raising=False)
