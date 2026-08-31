"""Stock event use case: request-time fetch via EventSource."""

from __future__ import annotations

from typing import Any

from astock.providers.protocols import EventSource
from astock.providers.registry import resolve_capability
from astock_core.market_data import (
    EventKind,
    EventQuery,
    from_legacy_symbol,
    market_event_to_legacy_dict,
)

EVENT_KINDS = frozenset({"notices", "research", "block_trades", "holder_changes"})
EVENTS_DEFAULT_LIMIT = 50
EVENTS_MAX_LIMIT = 50
RESEARCH_DEFAULT_LIMIT = 20

_CLI_TO_EVENT_KIND: dict[str, EventKind] = {
    "notices": EventKind.NOTICE,
    "research": EventKind.RESEARCH_REPORT,
    "block_trades": EventKind.BLOCK_TRADE,
    "holder_changes": EventKind.HOLDER_CHANGE,
}


def _clamp_limit(limit: int | None, *, default: int) -> int:
    if limit is None:
        return default
    return max(1, min(int(limit), EVENTS_MAX_LIMIT))


def fetch_stock_events(
    code: str,
    kind: str,
    *,
    limit: int | None = None,
    event_source: EventSource | None = None,
) -> list[dict[str, Any]]:
    key = str(kind).strip()
    event_kind = _CLI_TO_EVENT_KIND.get(key)
    if event_kind is None:
        raise ValueError(f"未知事件类型: {kind}")
    source = event_source or resolve_capability("events")
    instrument = from_legacy_symbol(str(code).strip().zfill(6))
    default = RESEARCH_DEFAULT_LIMIT if key == "research" else EVENTS_DEFAULT_LIMIT
    cap = _clamp_limit(limit, default=default)
    dataset = source.fetch_events(
        EventQuery(instruments=(instrument,), kinds=(event_kind,), limit=cap)
    )
    return [market_event_to_legacy_dict(item) for item in reversed(dataset.items)]


def format_stock_events(payload: dict[str, Any]) -> str:
    code = str(payload.get("code") or "")
    kind = str(payload.get("kind") or "")
    items = payload.get("events") or []
    if not items:
        return f"{code}  {kind}  暂无数据"
    lines = [f"{code}  {kind}  {len(items)} 条", ""]
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
