from __future__ import annotations

from collections.abc import Callable
from typing import Any

from astock_control.adapters.ingest import _run_uv, parse_trailing_json
from astock_control.config import load_settings
from astock_core.paths import REPO_ROOT

ANALYZE_DIR = REPO_ROOT / "tools" / "analyze"

PROVIDER_KEY_ENV = {
    "openai_compatible": "OPENAI_COMPATIBLE_API_KEY",
    "qwen-cn": "DASHSCOPE_CN_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "glm-cn": "ZHIPU_CN_API_KEY",
    "openai": "OPENAI_API_KEY",
    "ollama": None,
}


def analyze_run_argv(command: dict[str, Any]) -> list[str]:
    argv = [
        "uv",
        "--directory",
        str(ANALYZE_DIR),
        "run",
        "python",
        "-m",
        "astock_analyze",
        "--json",
        "run",
        "--code",
        str(command.get("code") or ""),
    ]
    if command.get("date"):
        argv.extend(["--date", str(command["date"])])
    pool = command.get("pool")
    if pool:
        argv.extend(["--pool", str(pool)])
    analysts = command.get("analysts")
    if analysts:
        argv.extend(["--analysts", ",".join(str(item) for item in analysts)])
    return argv


def analyze_child_env(analyze: dict[str, Any]) -> dict[str, str]:
    provider = str(analyze.get("llm_provider") or "")
    extra: dict[str, str] = {
        "TRADINGAGENTS_LLM_PROVIDER": provider,
        "TRADINGAGENTS_DEEP_THINK_LLM": str(analyze.get("deep_think_llm") or ""),
        "TRADINGAGENTS_QUICK_THINK_LLM": str(analyze.get("quick_think_llm") or ""),
        "TRADINGAGENTS_OUTPUT_LANGUAGE": str(analyze.get("output_language") or "Chinese"),
        "TRADINGAGENTS_MAX_DEBATE_ROUNDS": str(analyze.get("max_debate_rounds") or 1),
        "TRADINGAGENTS_MAX_RISK_ROUNDS": str(analyze.get("max_risk_discuss_rounds") or 1),
        "TRADINGAGENTS_CHECKPOINT_ENABLED": "true" if analyze.get("checkpoint_enabled") else "false",
    }
    backend = str(analyze.get("backend_url") or "")
    if backend:
        extra["TRADINGAGENTS_LLM_BACKEND_URL"] = backend
        if provider == "ollama":
            extra["OLLAMA_BASE_URL"] = backend
    temperature = analyze.get("temperature")
    if temperature is not None:
        extra["TRADINGAGENTS_TEMPERATURE"] = str(temperature)
    key_env = PROVIDER_KEY_ENV.get(provider)
    if key_env:
        extra[key_env] = str(analyze.get("api_key") or "")
    return extra


class AnalyzeRunner:
    def run(self, command: dict[str, Any], on_log: Callable[[str], None]) -> dict[str, Any]:
        if command.get("type") != "analyze.run":
            raise ValueError(f"分析执行器不支持命令: {command.get('type')}")
        argv = analyze_run_argv(command)
        on_log("$ " + " ".join(argv))
        settings = load_settings()
        extra = analyze_child_env(settings.get("analyze") or {})
        stdout = _run_uv(argv, on_log, extra_env=extra)
        result = parse_trailing_json(stdout)
        if result is None:
            raise RuntimeError("analyze 没有返回 JSON 结果")
        return result
