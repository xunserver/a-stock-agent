"""Versioned compatibility DTO shapes for news and events.

The ingest CLI and control-plane subprocess seam exchange these dict projections
derived from Standard Records. Keys and optional fields are stable for HTTP/UI.
"""

from __future__ import annotations

from typing import Any, TypedDict


class LegacyNewsItem(TypedDict, total=False):
    title: str
    summary: str
    published_at: str
    source: str
    url: str


class LegacyEventItem(TypedDict, total=False):
    title: str
    summary: str
    published_at: str
    source: str
    url: str
    extra: dict[str, Any]


NEWS_ITEM_KEYS = frozenset({"title", "summary", "published_at", "source", "url"})
EVENT_ITEM_KEYS = frozenset({"title", "summary", "published_at", "source", "url", "extra"})
_BASE_ITEM_KEYS = frozenset({"title", "summary", "published_at", "source", "url"})


def validate_legacy_news_items(items: object) -> list[dict[str, str]]:
    """Validate a news compatibility payload crossing the ingest subprocess seam."""
    if not isinstance(items, list):
        raise ValueError("news items must be a list")
    validated: list[dict[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"news item at index {index} must be a mapping")
        unknown = set(item.keys()) - NEWS_ITEM_KEYS
        if unknown:
            raise ValueError(
                f"news item at index {index} has unknown keys: {sorted(unknown)}"
            )
        missing = _BASE_ITEM_KEYS - set(item.keys())
        if missing:
            raise ValueError(
                f"news item at index {index} is missing keys: {sorted(missing)}"
            )
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"news item at index {index} requires non-empty title")
        row: dict[str, str] = {"title": title}
        for key in ("summary", "published_at", "source", "url"):
            value = item.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                raise ValueError(
                    f"news item at index {index} field {key} must be a string"
                )
            row[key] = value
        validated.append(row)
    return validated


def validate_legacy_event_items(items: object) -> list[dict[str, Any]]:
    """Validate an events compatibility payload crossing the ingest subprocess seam."""
    if not isinstance(items, list):
        raise ValueError("events items must be a list")
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"event item at index {index} must be a mapping")
        unknown = set(item.keys()) - EVENT_ITEM_KEYS
        if unknown:
            raise ValueError(
                f"event item at index {index} has unknown keys: {sorted(unknown)}"
            )
        missing = _BASE_ITEM_KEYS - set(item.keys())
        if missing:
            raise ValueError(
                f"event item at index {index} is missing keys: {sorted(missing)}"
            )
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"event item at index {index} requires non-empty title")
        row: dict[str, Any] = {"title": title}
        for key in ("summary", "published_at", "source", "url"):
            value = item.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                raise ValueError(
                    f"event item at index {index} field {key} must be a string"
                )
            row[key] = value
        extra = item.get("extra")
        if extra is not None:
            if not isinstance(extra, dict):
                raise ValueError(f"event item at index {index} extra must be a mapping")
            row["extra"] = extra
        validated.append(row)
    return validated
