from __future__ import annotations

import pandas as pd

from astock.news import fetch_stock_news, format_stock_news


def test_fetch_stock_news_maps_eastmoney_columns(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "关键词": "000001",
                "新闻标题": "平安银行发布公告",
                "新闻内容": "摘要一行",
                "发布时间": "2026-08-27 10:00:00",
                "文章来源": "证券时报",
                "新闻链接": "http://finance.eastmoney.com/a/xxx.html",
            },
            {
                "关键词": "000001",
                "新闻标题": "",
                "新闻内容": "应被丢掉",
                "发布时间": "2026-08-27 09:00:00",
                "文章来源": "上海证券报",
                "新闻链接": "http://finance.eastmoney.com/a/yyy.html",
            },
        ]
    )
    monkeypatch.setattr("astock.news._call", lambda fn, *args, **kwargs: frame)
    items = fetch_stock_news("1", limit=10)
    assert items == [
        {
            "title": "平安银行发布公告",
            "summary": "摘要一行",
            "published_at": "2026-08-27 10:00:00",
            "source": "证券时报",
            "url": "http://finance.eastmoney.com/a/xxx.html",
        }
    ]


def test_fetch_stock_news_strips_tags_and_honors_limit(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
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
    )
    monkeypatch.setattr("astock.news._call", lambda fn, *args, **kwargs: frame)
    items = fetch_stock_news("000001", limit=1)
    assert len(items) == 1
    assert items[0]["title"] == "标题甲"


def test_fetch_stock_news_empty_frame(monkeypatch) -> None:
    monkeypatch.setattr("astock.news._call", lambda fn, *args, **kwargs: pd.DataFrame())
    assert fetch_stock_news("000001") == []


def test_format_stock_news_empty() -> None:
    assert format_stock_news({"code": "000001", "news": []}) == "000001  暂无新闻"
