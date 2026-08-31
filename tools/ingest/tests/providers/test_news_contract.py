from __future__ import annotations

from datetime import datetime, timezone

import pytest

from astock.providers.akshare.news import AkshareNewsAdapter
from astock_core.market_data import InvalidSourcePayload, NewsItem, NewsQuery, from_legacy_symbol

from .contracts import assert_news_source_contract
from .fakes import InMemoryNewsSource, ping_an


def _aware(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def test_in_memory_news_contract() -> None:
    instrument = ping_an()
    item = NewsItem(
        id="news-1",
        instrument_id=instrument,
        title="平安银行发布公告",
        published_at=_aware("2026-08-27T10:00:00+00:00"),
        publisher="证券时报",
        summary="摘要一行",
        url="http://finance.eastmoney.com/a/xxx.html",
    )
    source = InMemoryNewsSource((item,))
    assert_news_source_contract(
        source,
        valid_query=NewsQuery(instruments=(instrument,), limit=10),
        empty_query=NewsQuery(instruments=(from_legacy_symbol("600519"),), limit=10),
    )


def test_akshare_news_fixture_contract() -> None:
    instrument = ping_an()
    source = AkshareNewsAdapter(
        stock_news=lambda symbol: [
            {
                "新闻标题": "平安银行发布公告",
                "新闻内容": "摘要一行",
                "发布时间": "2026-08-27 10:00:00",
                "文章来源": "证券时报",
                "新闻链接": "http://finance.eastmoney.com/a/xxx.html",
            }
        ],
        clock=lambda: _aware("2026-08-31T09:30:00+00:00"),
    )
    assert_news_source_contract(
        source,
        valid_query=NewsQuery(instruments=(instrument,), limit=10),
        empty_query=NewsQuery(instruments=(instrument,), limit=0),
    )


def test_akshare_news_rejects_missing_time_and_duplicates() -> None:
    instrument = ping_an()
    missing = AkshareNewsAdapter(
        stock_news=lambda symbol: [{"新闻标题": "无时间"}],
    )
    duplicate = AkshareNewsAdapter(
        stock_news=lambda symbol: [
            {
                "新闻标题": "重复",
                "发布时间": "2026-08-27",
                "新闻链接": "http://a.example/1",
            },
            {
                "新闻标题": "重复",
                "发布时间": "2026-08-27",
                "新闻链接": "http://a.example/1",
            },
        ],
    )
    query = NewsQuery(instruments=(instrument,), limit=10)
    with pytest.raises(InvalidSourcePayload, match="missing"):
        missing.fetch_news(query)
    with pytest.raises(InvalidSourcePayload, match="duplicate"):
        duplicate.fetch_news(query)
