from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

from astock.news import fetch_stock_news, format_stock_news
from astock_core.market_data import NewsItem, from_legacy_symbol

_fakes_path = Path(__file__).resolve().parent / "providers" / "fakes.py"
_spec = importlib.util.spec_from_file_location("ingest_test_fakes", _fakes_path)
assert _spec and _spec.loader
_fakes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fakes)
InMemoryNewsSource = _fakes.InMemoryNewsSource


def _aware(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def test_fetch_stock_news_projects_legacy_shape() -> None:
    instrument = from_legacy_symbol("000001")
    source = InMemoryNewsSource(
        (
            NewsItem(
                id="news-1",
                instrument_id=instrument,
                title="平安银行发布公告",
                published_at=_aware("2026-08-27T10:00:00+08:00"),
                publisher="证券时报",
                summary="摘要一行",
                url="http://finance.eastmoney.com/a/xxx.html",
            ),
        )
    )
    items = fetch_stock_news("1", limit=10, news_source=source)
    assert items == [
        {
            "title": "平安银行发布公告",
            "summary": "摘要一行",
            "published_at": "2026-08-27 10:00:00",
            "source": "证券时报",
            "url": "http://finance.eastmoney.com/a/xxx.html",
        }
    ]


def test_fetch_stock_news_honors_limit() -> None:
    instrument = from_legacy_symbol("000001")
    rows = tuple(
        NewsItem(
            id=f"news-{index}",
            instrument_id=instrument,
            title=f"标题{index}",
            published_at=_aware(f"2026-08-2{index}T10:00:00+08:00"),
        )
        for index in range(2)
    )
    source = InMemoryNewsSource(rows)
    items = fetch_stock_news("000001", limit=1, news_source=source)
    assert len(items) == 1
    assert items[0]["title"] == "标题1"


def test_fetch_stock_news_presents_latest_first_and_keeps_empty_keys() -> None:
    instrument = from_legacy_symbol("000001")
    source = InMemoryNewsSource(
        (
            NewsItem(
                id="old",
                instrument_id=instrument,
                title="旧",
                published_at=_aware("2026-08-20T10:00:00+08:00"),
            ),
            NewsItem(
                id="new",
                instrument_id=instrument,
                title="新",
                published_at=_aware("2026-08-21T10:00:00+08:00"),
            ),
        )
    )
    items = fetch_stock_news("000001", limit=2, news_source=source)
    assert [item["title"] for item in items] == ["新", "旧"]
    assert set(items[0]) == {"title", "summary", "published_at", "source", "url"}


def test_fetch_stock_news_empty_dataset() -> None:
    source = InMemoryNewsSource(())
    assert fetch_stock_news("000001", news_source=source) == []


def test_format_stock_news_empty() -> None:
    assert format_stock_news({"code": "000001", "news": []}) == "000001  暂无新闻"
