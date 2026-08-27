"""Analyze settings: CLI > env > system DB `analyze.*` > built-in defaults."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from astock_core.paths import DATA_DIR, REPO_ROOT

VENDOR_DIR = REPO_ROOT / "vendor" / "tradingagents"
CONTROL_JSON = DATA_DIR / "control.json"
OLLAMA_DEFAULT_URL = "http://127.0.0.1:11434/v1"

ALLOWED_ANALYSTS = ("market", "social", "news", "fundamentals")
ALLOWED_PROVIDERS = (
    "openai_compatible",
    "qwen-cn",
    "deepseek",
    "glm-cn",
    "ollama",
    "openai",
)

# Upstream provider → API key env var. ollama has no key.
PROVIDER_KEY_ENV: dict[str, str | None] = {
    "openai_compatible": "OPENAI_COMPATIBLE_API_KEY",
    "qwen-cn": "DASHSCOPE_CN_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "glm-cn": "ZHIPU_CN_API_KEY",
    "ollama": None,
    "openai": "OPENAI_API_KEY",
}

KEY_OPTIONAL_PROVIDERS = frozenset({"ollama", "openai_compatible"})

_ENV_OVERRIDES = {
    "TRADINGAGENTS_LLM_PROVIDER": "llm_provider",
    "TRADINGAGENTS_DEEP_THINK_LLM": "deep_think_llm",
    "TRADINGAGENTS_QUICK_THINK_LLM": "quick_think_llm",
    "TRADINGAGENTS_LLM_BACKEND_URL": "backend_url",
    "TRADINGAGENTS_OUTPUT_LANGUAGE": "output_language",
    "TRADINGAGENTS_MAX_DEBATE_ROUNDS": "max_debate_rounds",
    "TRADINGAGENTS_MAX_RISK_ROUNDS": "max_risk_discuss_rounds",
    "TRADINGAGENTS_CHECKPOINT_ENABLED": "checkpoint_enabled",
    "TRADINGAGENTS_TEMPERATURE": "temperature",
}

_BOOL_TRUE = ("true", "1", "yes", "on")
_BOOL_FALSE = ("false", "0", "no", "off")

BUILTIN_DEFAULTS: dict[str, Any] = {
    "llm_provider": "openai_compatible",
    "output_language": "Chinese",
    "analysts": ["market", "news", "fundamentals"],
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "checkpoint_enabled": False,
    "deep_think_llm": "",
    "quick_think_llm": "",
    "backend_url": "",
    "api_key": "",
    "temperature": None,
}

_SETTING_KEYS = frozenset(BUILTIN_DEFAULTS)


class AnalyzeError(Exception):
    """User-facing failure. ``exit_code`` 2 is fail-fast (before the graph)."""

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class AnalyzeSettings:
    llm_provider: str
    deep_think_llm: str
    quick_think_llm: str
    backend_url: str
    api_key: str
    output_language: str
    analysts: tuple[str, ...]
    max_debate_rounds: int
    max_risk_discuss_rounds: int
    temperature: float | None
    checkpoint_enabled: bool

    @property
    def api_key_env(self) -> str | None:
        return PROVIDER_KEY_ENV.get(self.llm_provider)

    @property
    def api_key_set(self) -> bool:
        return bool(self.api_key)


def read_control_analyze() -> dict[str, Any]:
    """Read analyze settings from the system DB, with control.json as fallback."""
    try:
        from astock_core.settings import load_analyze_values

        return load_analyze_values()
    except Exception:
        pass
    path = CONTROL_JSON
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    analyze = payload.get("analyze")
    return dict(analyze) if isinstance(analyze, dict) else {}


def parse_analysts(raw: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        items = [part.strip().lower() for part in raw.split(",") if part.strip()]
    else:
        items = [str(part).strip().lower() for part in raw if str(part).strip()]
    if not items:
        raise AnalyzeError("分析师列表不能为空")
    unknown = [name for name in items if name not in ALLOWED_ANALYSTS]
    if unknown:
        raise AnalyzeError(
            f"未知分析师: {', '.join(unknown)}。"
            f"可选: {', '.join(ALLOWED_ANALYSTS)}"
        )
    return items


def load_settings(*, analysts: list[str] | tuple[str, ...] | None = None) -> AnalyzeSettings:
    """Resolve settings. Priority: CLI > env > control.json > built-in."""
    data = dict(BUILTIN_DEFAULTS)
    _merge_overlay(data, read_control_analyze())
    _merge_env(data)
    if analysts is not None:
        data["analysts"] = parse_analysts(analysts)

    data["llm_provider"] = str(data.get("llm_provider") or "").strip().lower()
    data["deep_think_llm"] = str(data.get("deep_think_llm") or "").strip()
    data["quick_think_llm"] = str(data.get("quick_think_llm") or "").strip()
    data["backend_url"] = str(data.get("backend_url") or "").strip()
    data["output_language"] = str(data.get("output_language") or "Chinese").strip()
    data["api_key"] = str(data.get("api_key") or "")
    data["max_debate_rounds"] = _as_int(data.get("max_debate_rounds"), 1)
    data["max_risk_discuss_rounds"] = _as_int(data.get("max_risk_discuss_rounds"), 1)
    data["checkpoint_enabled"] = _as_bool(data.get("checkpoint_enabled"), False)
    data["temperature"] = _as_optional_float(data.get("temperature"))
    data["analysts"] = parse_analysts(data.get("analysts") or BUILTIN_DEFAULTS["analysts"])

    env_name = PROVIDER_KEY_ENV.get(data["llm_provider"])
    if env_name:
        env_key = os.environ.get(env_name, "")
        if env_key:
            data["api_key"] = env_key

    if data["deep_think_llm"] and not data["quick_think_llm"]:
        data["quick_think_llm"] = data["deep_think_llm"]
    elif data["quick_think_llm"] and not data["deep_think_llm"]:
        data["deep_think_llm"] = data["quick_think_llm"]

    if data["llm_provider"] == "ollama" and not data["backend_url"]:
        data["backend_url"] = OLLAMA_DEFAULT_URL

    return AnalyzeSettings(
        llm_provider=data["llm_provider"],
        deep_think_llm=data["deep_think_llm"],
        quick_think_llm=data["quick_think_llm"],
        backend_url=data["backend_url"],
        api_key=data["api_key"],
        output_language=data["output_language"],
        analysts=tuple(data["analysts"]),
        max_debate_rounds=data["max_debate_rounds"],
        max_risk_discuss_rounds=data["max_risk_discuss_rounds"],
        temperature=data["temperature"],
        checkpoint_enabled=data["checkpoint_enabled"],
    )


def validate_run_config(settings: AnalyzeSettings) -> None:
    """Fail fast before importing TradingAgentsGraph."""
    if not VENDOR_DIR.is_dir():
        raise AnalyzeError(f"找不到上游源码目录: {VENDOR_DIR}")

    provider = settings.llm_provider
    if provider not in PROVIDER_KEY_ENV:
        raise AnalyzeError(
            f"不支持的 LLM 提供商: {provider}。"
            f"可选: {', '.join(ALLOWED_PROVIDERS)}"
        )

    env_name = settings.api_key_env
    if env_name and provider not in KEY_OPTIONAL_PROVIDERS and not settings.api_key:
        raise AnalyzeError(
            f"未配置 API 密钥。请在系统设置中填写，或设置环境变量 {env_name}。"
        )

    if provider == "openai_compatible" and not settings.backend_url:
        raise AnalyzeError(
            "openai_compatible 必须填写接口地址 backend_url"
            "（或环境变量 TRADINGAGENTS_LLM_BACKEND_URL）。"
        )

    if not settings.deep_think_llm and not settings.quick_think_llm:
        raise AnalyzeError(
            "请填写深度思考模型 deep_think_llm 或快速模型 quick_think_llm"
            "（只填一个则两个都用它）。"
        )

    if not settings.analysts:
        raise AnalyzeError("分析师列表不能为空")


def apply_api_key_env(settings: AnalyzeSettings) -> None:
    """Write the resolved key into the provider env var for the upstream client."""
    env_name = settings.api_key_env
    if env_name and settings.api_key:
        os.environ[env_name] = settings.api_key


def redact_secret(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "******")
    return text


def _merge_overlay(data: dict[str, Any], overlay: dict[str, Any]) -> None:
    for key, value in overlay.items():
        if key not in _SETTING_KEYS:
            continue
        if key == "temperature":
            data[key] = value
            continue
        if key == "checkpoint_enabled":
            data[key] = value
            continue
        if value is None or value == "":
            continue
        data[key] = value


def _merge_env(data: dict[str, Any]) -> None:
    for env_var, key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        if key in {"max_debate_rounds", "max_risk_discuss_rounds"}:
            data[key] = _as_int(raw, data[key])
        elif key == "checkpoint_enabled":
            data[key] = _as_bool(raw, data[key])
        elif key == "temperature":
            data[key] = _as_optional_float(raw)
        else:
            data[key] = raw


def _as_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AnalyzeError(f"无法解析整数: {value}") from exc


def _as_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    text = str(value).strip().lower()
    if text in _BOOL_TRUE:
        return True
    if text in _BOOL_FALSE:
        return False
    raise AnalyzeError(f"无法解析布尔值: {value}")


def _as_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise AnalyzeError(f"无法解析温度: {value}") from exc

