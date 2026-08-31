from __future__ import annotations

from datetime import datetime, timezone

import pytest

from astock.providers.akshare.news import AkshareNewsAdapter
from astock_core.market_data import InvalidSourcePayload, NewsQuery, from_legacy_symbol


def _aware(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def test_akshare_news_strips_tags_and_honors_limit() -> None:
    instrument = from_legacy_symbol("000001")
    rows = [
        {
            "新闻标题": "<em>标题甲</em>",
            "新闻内容": "甲",
            "发布时间": "2026-08-27",
            "文章来源": "来源甲",
            "新闻链接": "http://a.example/1",
        },
        {
            "新闻标题": "标题乙",
            "新闻内容": "乙",
            "发布时间": "2026-08-26",
            "文章来源": "来源乙",
            "新闻链接": "http://a.example/2",
        },
    ]
    source = AkshareNewsAdapter(stock_news=lambda symbol: rows)
    dataset = source.fetch_news(NewsQuery(instruments=(instrument,), limit=1))
    assert len(dataset.items) == 1
    assert dataset.items[0].title == "标题甲"
    assert any("date-only" in warning for warning in dataset.warnings)


def test_akshare_news_empty_payload() -> None:
    instrument = from_legacy_symbol("000001")
    source = AkshareNewsAdapter(stock_news=lambda symbol: [])
    dataset = source.fetch_news(NewsQuery(instruments=(instrument,), limit=10))
    assert dataset.items == ()
    assert dataset.complete is True


def test_akshare_news_filters_range_and_preserves_iso_offset() -> None:
    instrument = from_legacy_symbol("000001")
    source = AkshareNewsAdapter(
        stock_news=lambda symbol: [
            {"新闻标题": "旧", "发布时间": "2026-08-20T10:00:00+08:00"},
            {"新闻标题": "新", "发布时间": "2026-08-27T10:00:00+08:00"},
        ]
    )
    dataset = source.fetch_news(
        NewsQuery(
            instruments=(instrument,),
            start=datetime.fromisoformat("2026-08-25T00:00:00+08:00"),
        )
    )
    assert [item.title for item in dataset.items] == ["新"]
    assert dataset.items[0].published_at.isoformat() == "2026-08-27T10:00:00+08:00"
    assert not dataset.warnings


def test_akshare_news_rejects_missing_title() -> None:
    instrument = from_legacy_symbol("000001")
    source = AkshareNewsAdapter(stock_news=lambda symbol: [{"发布时间": "2026-08-27"}])
    with pytest.raises(InvalidSourcePayload, match="missing title"):
        source.fetch_news(NewsQuery(instruments=(instrument,)))
