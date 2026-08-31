from __future__ import annotations

from datetime import datetime

import pytest

from astock.providers.akshare.events import AkshareEventAdapter
from astock_core.market_data import EventKind, EventQuery, InvalidSourcePayload, from_legacy_symbol


def test_akshare_notices_maps_and_truncates() -> None:
    instrument = from_legacy_symbol("000001")
    rows = [
        {
            "公告标题": f"公告{i}",
            "公告类型": "财务报告",
            "公告日期": "2026-01-01",
            "网址": f"http://example.com/{i}",
        }
        for i in range(5)
    ]
    source = AkshareEventAdapter(notices=lambda security, begin_date, end_date: rows)
    dataset = source.fetch_events(
        EventQuery(instruments=(instrument,), kinds=(EventKind.NOTICE,), limit=3)
    )
    assert len(dataset.items) == 3
    assert tuple(item.published_at for item in dataset.items) == tuple(
        sorted(item.published_at for item in dataset.items)
    )
    assert all(item.source == "财务报告" for item in dataset.items)
    assert all(item.url and item.url.startswith("http://example.com/") for item in dataset.items)


def test_akshare_events_rejects_unknown_kind_via_use_case() -> None:
    from astock.events import fetch_stock_events

    with pytest.raises(ValueError, match="未知事件类型"):
        fetch_stock_events("000001", "nope", event_source=AkshareEventAdapter())


def test_block_trade_identity_distinguishes_same_day_rows_and_keeps_base_units() -> None:
    instrument = from_legacy_symbol("000001")
    rows = [
        {
            "交易日期": "2026-03-01",
            "证券代码": "000001",
            "成交价": 10.5,
            "成交量": 1000,
            "成交额": 10500,
            "买方营业部": buyer,
            "卖方营业部": "卖方",
        }
        for buyer in ("买方A", "买方B")
    ]
    source = AkshareEventAdapter(block_trades=lambda start_date, end_date: rows)
    dataset = source.fetch_events(
        EventQuery(instruments=(instrument,), kinds=(EventKind.BLOCK_TRADE,))
    )
    assert len({item.id for item in dataset.items}) == 2
    assert all(item.volume == 1000 for item in dataset.items)
    assert all(item.amount == 10500 for item in dataset.items)


def test_akshare_event_rejects_missing_required_title() -> None:
    instrument = from_legacy_symbol("000001")
    source = AkshareEventAdapter(
        notices=lambda security, begin_date, end_date: [{"公告日期": "2026-01-01"}]
    )
    with pytest.raises(InvalidSourcePayload, match="missing title"):
        source.fetch_events(
            EventQuery(instruments=(instrument,), kinds=(EventKind.NOTICE,))
        )
