"""Ingest 运行时配置：一律从 system.db 读取，默认值只在 settings catalog 播种。"""

from __future__ import annotations

from typing import Any

from astock_core.settings import SystemDB

_QUOTES: dict[str, Any] | None = None
_INDEXES: dict[str, Any] | None = None


def clear_settings_cache() -> None:
    global _QUOTES, _INDEXES
    _QUOTES = None
    _INDEXES = None


def quotes_settings() -> dict[str, Any]:
    global _QUOTES
    if _QUOTES is None:
        with SystemDB() as db:
            _QUOTES = db.get_values("ingest", "quotes")
    return dict(_QUOTES)


def indexes_settings() -> dict[str, Any]:
    global _INDEXES
    if _INDEXES is None:
        with SystemDB() as db:
            _INDEXES = db.get_values("ingest", "indexes")
    return dict(_INDEXES)


def history_start() -> str:
    return str(quotes_settings()["history_start"])


def quote_periods() -> tuple[str, ...]:
    return tuple(str(item) for item in quotes_settings()["periods"])


def request_sleep_seconds() -> float:
    return float(quotes_settings()["sleep"])


def request_retries() -> int:
    return int(quotes_settings()["retries"])


def default_adjust() -> str:
    return str(quotes_settings()["adjust"])


def default_years() -> int:
    return int(quotes_settings()["default_years"])


def hs300_symbol() -> str:
    return str(indexes_settings()["hs300_symbol"])


def hs300_index_code() -> str:
    return str(indexes_settings()["hs300_index_code"])


def major_indexes() -> tuple[tuple[str, str], ...]:
    items = indexes_settings()["major_indexes"]
    return tuple((str(item["code"]), str(item["name"])) for item in items)


def index_aliases() -> dict[str, str]:
    raw = indexes_settings()["aliases"]
    return {str(key): str(value) for key, value in raw.items()}
