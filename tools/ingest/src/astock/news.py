"""Stock news use case: request-time fetch via NewsSource."""

from __future__ import annotations

from typing import Any

from astock.providers.protocols import NewsSource
from astock.providers.registry import resolve_capability
from astock_core.market_data import (
    NewsQuery,
    from_legacy_symbol,
    news_item_to_legacy_dict,
)

NEWS_MAX_LIMIT = 50
NEWS_DEFAULT_LIMIT = 20


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return NEWS_DEFAULT_LIMIT
    return max(1, min(int(limit), NEWS_MAX_LIMIT))


def fetch_stock_news(
    code: str,
    *,
    limit: int | None = None,
    news_source: NewsSource | None = None,
) -> list[dict[str, str]]:
    source = news_source or resolve_capability("news")
    instrument = from_legacy_symbol(str(code).strip().zfill(6))
    cap = _clamp_limit(limit)
    dataset = source.fetch_news(NewsQuery(instruments=(instrument,), limit=cap))
    return [news_item_to_legacy_dict(item) for item in reversed(dataset.items)]


def format_stock_news(payload: dict[str, Any]) -> str:
    code = str(payload.get("code") or "")
    items = payload.get("news") or []
    if not items:
        return f"{code}  暂无新闻"
    lines = [f"{code}  {len(items)} 条", ""]
    for item in items:
        if not isinstance(item, dict):
            continue
        meta = "  ".join(
            part
            for part in (str(item.get("published_at") or ""), str(item.get("source") or ""))
            if part
        )
        title = str(item.get("title") or "")
        lines.append(f"{meta}  {title}".strip())
        summary = str(item.get("summary") or "")
        if summary:
            lines.append(f"  {summary}")
        url = str(item.get("url") or "")
        if url:
            lines.append(f"  {url}")
        lines.append("")
    return "\n".join(lines).rstrip()
