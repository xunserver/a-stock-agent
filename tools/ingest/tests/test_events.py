from __future__ import annotations

import pandas as pd

from astock.events import (
    fetch_block_trades,
    fetch_holder_changes,
    fetch_notices,
    fetch_research,
    fetch_stock_events,
)


def test_fetch_notices_maps_and_truncates(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "公告标题": f"公告{i}",
                "公告类型": "财务报告",
                "公告日期": "2026-01-01",
                "网址": f"http://example.com/{i}",
            }
            for i in range(5)
        ]
    )
    monkeypatch.setattr(
        "astock.events._call",
        lambda fn, *args, **kwargs: frame,
    )
    items = fetch_notices("000001", limit=3)
    assert len(items) == 3
    assert items[0]["title"] == "公告0"
    assert items[0]["source"] == "财务报告"
    assert items[0]["url"] == "http://example.com/0"
    assert items[0]["extra"]["notice_type"] == "财务报告"


def test_fetch_research_maps_fields(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "报告名称": "深度报告",
                "机构": "中信证券",
                "东财评级": "买入",
                "日期": "2026-02-01",
                "报告PDF链接": "http://pdf.example.com/a.pdf",
            }
        ]
    )
    monkeypatch.setattr("astock.events._call", lambda fn, *args, **kwargs: frame)
    items = fetch_research("600000", limit=10)
    assert len(items) == 1
    assert items[0]["title"] == "深度报告"
    assert items[0]["summary"] == "中信证券 · 买入"
    assert items[0]["extra"]["rating"] == "买入"


def test_fetch_block_trades_filters_by_code(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "交易日期": "2026-03-01",
                "证券代码": "000001",
                "成交价": 10.5,
                "折溢率": -1.2,
                "成交量": 1000,
                "成交额": 10500,
                "买方营业部": "买方A",
                "卖方营业部": "卖方B",
                "收盘价": 10.6,
                "涨跌幅": 0.5,
            },
            {
                "交易日期": "2026-03-02",
                "证券代码": "600000",
                "成交价": 8.0,
                "折溢率": 2.0,
                "成交量": 2000,
                "成交额": 16000,
                "买方营业部": "买方C",
                "卖方营业部": "卖方D",
                "收盘价": 7.8,
                "涨跌幅": -1.0,
            },
        ]
    )
    monkeypatch.setattr("astock.events._call", lambda fn, *args, **kwargs: frame)
    items = fetch_block_trades("000001", limit=10)
    assert len(items) == 1
    assert items[0]["extra"]["buyer"] == "买方A"
    assert items[0]["extra"]["premium_ratio"] == -1.2


def test_fetch_holder_changes_sse_fields(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "姓名": "张三",
                "职务": "董事",
                "变动数": -1000,
                "本次变动平均价格": 12.3,
                "变动原因": "二级市场买卖",
                "变动日期": "2026-04-01",
                "填报日期": "2026-04-02",
            }
        ]
    )
    monkeypatch.setattr("astock.events._call", lambda fn, *args, **kwargs: frame)
    items = fetch_holder_changes("600000", limit=10)
    assert len(items) == 1
    assert items[0]["title"] == "张三（董事）"
    assert "变动 -1000" in items[0]["summary"]
    assert items[0]["extra"]["reason"] == "二级市场买卖"


def test_fetch_stock_events_dispatches_kind(monkeypatch) -> None:
    monkeypatch.setattr(
        "astock.events.fetch_notices",
        lambda code, limit=None: [{"title": "n", "code": code}],
    )
    items = fetch_stock_events("000001", "notices")
    assert items[0]["title"] == "n"


def test_fetch_stock_events_rejects_unknown_kind() -> None:
    try:
        fetch_stock_events("000001", "nope")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "未知事件类型" in str(exc)
