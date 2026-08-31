"""Persistence and HTTP compatibility projections for Standard Records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from astock_core.market_data.identity import to_legacy_symbol
from astock_core.market_data.models import (
    BlockTradeEvent,
    Classification,
    HolderChangeEvent,
    MarketEvent,
    Membership,
    NewsItem,
    NoticeEvent,
    ResearchReportEvent,
)

CN_TIMEZONE = "Asia/Shanghai"
_SHANGHAI = ZoneInfo(CN_TIMEZONE)


def board_rows_from_classifications(
    classifications: Sequence[Classification],
) -> list[tuple[str, str, str, str]]:
    """Project Classifications into legacy ``boards`` rows."""
    return [
        (item.id, item.kind.value, item.name, item.taxonomy)
        for item in classifications
    ]


def membership_codes(
    memberships: Sequence[Membership],
) -> list[str]:
    """Return legacy six-digit codes for Membership instrument IDs."""
    return [to_legacy_symbol(item.instrument_id) for item in memberships]


def membership_code_name_pairs(
    memberships: Sequence[Membership],
    *,
    names: Mapping[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Project Memberships into legacy ``(code, name)`` pairs."""
    lookup = names or {}
    pairs: list[tuple[str, str]] = []
    for item in memberships:
        code = to_legacy_symbol(item.instrument_id)
        pairs.append((code, lookup.get(code, code)))
    return pairs


def format_legacy_published_at(value: datetime) -> str:
    """Format a timezone-aware publication time for CLI/HTTP consumers."""
    local = value.astimezone(_SHANGHAI)
    if local.hour == 0 and local.minute == 0 and local.second == 0 and local.microsecond == 0:
        return local.date().isoformat()
    return local.strftime("%Y-%m-%d %H:%M:%S")


def news_item_to_legacy_dict(item: NewsItem) -> dict[str, str]:
    """Project a NewsItem into the existing CLI/HTTP news item shape."""
    payload: dict[str, str] = {
        "title": item.title,
        "summary": item.summary or "",
        "published_at": format_legacy_published_at(item.published_at),
        "source": item.publisher or "",
        "url": item.url or "",
    }
    return payload


def market_event_extra(event: MarketEvent) -> dict[str, Any] | None:
    """Build the legacy ``extra`` object deterministically from a typed event."""
    if isinstance(event, NoticeEvent):
        if not event.notice_type:
            return None
        return {"notice_type": event.notice_type}
    if isinstance(event, ResearchReportEvent):
        extra: dict[str, Any] = {}
        if event.organization:
            extra["org"] = event.organization
        if event.rating:
            extra["rating"] = event.rating
        return extra or None
    if isinstance(event, BlockTradeEvent):
        extra = {}
        if event.deal_price is not None:
            extra["deal_price"] = event.deal_price
        if event.premium_pct is not None:
            extra["premium_ratio"] = event.premium_pct
        if event.volume is not None:
            extra["volume"] = event.volume
        if event.amount is not None:
            extra["amount"] = event.amount
        if event.buyer:
            extra["buyer"] = event.buyer
        if event.seller:
            extra["seller"] = event.seller
        if event.close_price is not None:
            extra["close_price"] = event.close_price
        if event.pct_change is not None:
            extra["pct_chg"] = event.pct_change
        return extra or None
    if isinstance(event, HolderChangeEvent):
        extra = {}
        if event.person:
            extra["name"] = event.person
        if event.role:
            extra["role"] = event.role
        if event.change_shares is not None:
            extra["change_qty"] = event.change_shares
        if event.average_price is not None:
            extra["avg_price"] = event.average_price
        if event.reason:
            extra["reason"] = event.reason
        return extra or None
    raise TypeError(f"unsupported MarketEvent type: {type(event).__name__}")


def _legacy_event_summary(event: MarketEvent) -> str:
    if isinstance(event, ResearchReportEvent):
        if event.summary:
            return event.summary
        return " · ".join(
            part for part in (event.organization, event.rating) if part
        )
    if isinstance(event, BlockTradeEvent):
        parts: list[str] = []
        if event.premium_pct is not None:
            parts.append(f"折溢率 {event.premium_pct}%")
        if event.volume is not None:
            parts.append(f"量 {event.volume}")
        if event.amount is not None:
            parts.append(f"额 {event.amount}")
        return " · ".join(parts)
    if isinstance(event, HolderChangeEvent):
        parts = []
        if event.change_shares is not None:
            parts.append(f"变动 {event.change_shares}")
        if event.average_price is not None:
            parts.append(f"均价 {event.average_price}")
        if event.reason:
            parts.append(event.reason)
        return " · ".join(parts)
    if isinstance(event, NoticeEvent):
        return event.summary or ""
    return ""


def market_event_to_legacy_dict(event: MarketEvent) -> dict[str, Any]:
    """Project a typed MarketEvent into the existing CLI/HTTP event item shape."""
    payload: dict[str, Any] = {
        "title": event.title,
        "summary": _legacy_event_summary(event),
        "published_at": format_legacy_published_at(event.published_at),
        "source": event.source or "",
        "url": event.url or "",
    }
    extra = market_event_extra(event)
    if extra:
        payload["extra"] = extra
    return payload
