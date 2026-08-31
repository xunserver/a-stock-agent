from __future__ import annotations

import pytest

from astock_core.market_data import (
    EVENT_ITEM_KEYS,
    NEWS_ITEM_KEYS,
    BlockTradeEvent,
    EventKind,
    HolderChangeEvent,
    NoticeEvent,
    ResearchReportEvent,
    from_legacy_symbol,
    market_event_extra,
    market_event_to_legacy_dict,
    news_item_to_legacy_dict,
    validate_legacy_event_items,
    validate_legacy_news_items,
)
from datetime import datetime, timezone


def _aware(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def test_news_item_keys_are_locked() -> None:
    assert NEWS_ITEM_KEYS == frozenset(
        {"title", "summary", "published_at", "source", "url"}
    )


def test_event_item_keys_are_locked() -> None:
    assert EVENT_ITEM_KEYS == frozenset(
        {"title", "summary", "published_at", "source", "url", "extra"}
    )


def test_news_projection_matches_http_shape() -> None:
    from astock_core.market_data import NewsItem

    item = NewsItem(
        id="n1",
        instrument_id=from_legacy_symbol("000001"),
        title="标题",
        published_at=_aware("2026-08-27T10:00:00+08:00"),
        publisher="来源",
        summary="摘要",
        url="http://example.com",
    )
    projected = news_item_to_legacy_dict(item)
    assert validate_legacy_news_items([projected]) == [projected]


def test_event_projection_covers_all_variants() -> None:
    instrument = from_legacy_symbol("000001")
    header = dict(
        instrument_id=instrument,
        published_at=_aware("2026-01-01T00:00:00+08:00"),
    )
    variants = (
        NoticeEvent(id="1", title="公告", source="类型", notice_type="类型", **header),
        ResearchReportEvent(
            id="2",
            title="研报",
            organization="机构",
            rating="买入",
            **header,
        ),
        BlockTradeEvent(
            id="3",
            title="大宗",
            deal_price=10.0,
            premium_pct=1.0,
            volume=100.0,
            amount=1000.0,
            buyer="A",
            seller="B",
            close_price=9.8,
            pct_change=0.5,
            **header,
        ),
        HolderChangeEvent(
            id="4",
            title="张三",
            person="张三",
            role="董事",
            change_shares=-100.0,
            average_price=9.5,
            reason="买卖",
            **header,
        ),
    )
    for event in variants:
        projected = market_event_to_legacy_dict(event)
        assert "title" in projected
        extra = market_event_extra(event)
        if extra:
            assert projected.get("extra") == extra
        assert validate_legacy_event_items([projected]) == [projected]


def test_validate_legacy_news_items_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="unknown keys"):
        validate_legacy_news_items([{"title": "x", "unexpected": "y"}])


def test_legacy_items_require_the_five_compatibility_keys() -> None:
    with pytest.raises(ValueError, match="missing keys"):
        validate_legacy_news_items([{"title": "x"}])
    with pytest.raises(ValueError, match="missing keys"):
        validate_legacy_event_items([{"title": "x"}])
