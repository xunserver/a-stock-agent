from __future__ import annotations

from datetime import datetime, timezone

import pytest

from astock.providers.akshare.events import AkshareEventAdapter
from astock_core.market_data import (
    BlockTradeEvent,
    EventKind,
    EventQuery,
    HolderChangeEvent,
    InvalidSourcePayload,
    NoticeEvent,
    ResearchReportEvent,
    SourceUnavailable,
    from_legacy_symbol,
)

from .contracts import assert_event_source_contract
from .fakes import InMemoryEventSource, ping_an


def _aware(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def test_in_memory_event_contract() -> None:
    instrument = ping_an()
    event = NoticeEvent(
        id="notice-1",
        instrument_id=instrument,
        title="公告0",
        published_at=_aware("2026-01-01T00:00:00+00:00"),
        source="财务报告",
        url="http://example.com/0",
        notice_type="财务报告",
    )
    source = InMemoryEventSource((event,))
    assert_event_source_contract(
        source,
        valid_query=EventQuery(instruments=(instrument,), kinds=(EventKind.NOTICE,), limit=10),
        empty_query=EventQuery(
            instruments=(from_legacy_symbol("600519"),),
            kinds=(EventKind.NOTICE,),
            limit=10,
        ),
    )


def test_akshare_notice_fixture_contract() -> None:
    instrument = ping_an()
    source = AkshareEventAdapter(
        notices=lambda security, begin_date, end_date: [
            {
                "公告标题": "公告0",
                "公告类型": "财务报告",
                "公告日期": "2026-01-01",
                "网址": "http://example.com/0",
            }
        ],
        clock=lambda: _aware("2026-08-31T09:30:00+00:00"),
        today=lambda: datetime(2026, 8, 31).date(),
    )
    assert_event_source_contract(
        source,
        valid_query=EventQuery(instruments=(instrument,), kinds=(EventKind.NOTICE,), limit=10),
        empty_query=EventQuery(instruments=(instrument,), kinds=(EventKind.NOTICE,), limit=0),
    )


def test_akshare_research_maps_typed_variant() -> None:
    instrument = from_legacy_symbol("600000")
    source = AkshareEventAdapter(
        research=lambda symbol: [
            {
                "报告名称": "深度报告",
                "机构": "中信证券",
                "东财评级": "买入",
                "日期": "2026-02-01",
                "报告PDF链接": "http://pdf.example.com/a.pdf",
            }
        ],
    )
    dataset = source.fetch_events(
        EventQuery(instruments=(instrument,), kinds=(EventKind.RESEARCH_REPORT,), limit=10)
    )
    event = dataset.items[0]
    assert isinstance(event, ResearchReportEvent)
    assert event.organization == "中信证券"
    assert event.rating == "买入"


def test_akshare_block_trade_filters_by_code() -> None:
    instrument = ping_an()
    source = AkshareEventAdapter(
        block_trades=lambda start_date, end_date: [
            {
                "交易日期": "2026-03-01",
                "证券代码": "000001",
                "成交价": 10.5,
                "折溢率": -1.2,
                "成交量": 1000.0,
                "成交额": 10500.0,
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
                "成交量": 2000.0,
                "成交额": 16000.0,
                "买方营业部": "买方C",
                "卖方营业部": "卖方D",
                "收盘价": 7.8,
                "涨跌幅": -1.0,
            },
        ],
        today=lambda: datetime(2026, 8, 31).date(),
    )
    dataset = source.fetch_events(
        EventQuery(instruments=(instrument,), kinds=(EventKind.BLOCK_TRADE,), limit=10)
    )
    assert len(dataset.items) == 1
    event = dataset.items[0]
    assert isinstance(event, BlockTradeEvent)
    assert event.buyer == "买方A"
    assert event.premium_pct == -1.2
    assert event.volume == 1000.0
    assert event.amount == 10500.0


def test_akshare_holder_change_sse_fields() -> None:
    instrument = from_legacy_symbol("600000")
    source = AkshareEventAdapter(
        holder_sse=lambda symbol: [
            {
                "姓名": "张三",
                "职务": "董事",
                "变动数": -1000.0,
                "本次变动平均价格": 12.3,
                "变动原因": "二级市场买卖",
                "变动日期": "2026-04-01",
                "填报日期": "2026-04-02",
            }
        ],
    )
    dataset = source.fetch_events(
        EventQuery(instruments=(instrument,), kinds=(EventKind.HOLDER_CHANGE,), limit=10)
    )
    event = dataset.items[0]
    assert isinstance(event, HolderChangeEvent)
    assert event.person == "张三"
    assert event.title == "张三（董事）"
    assert event.change_shares == -1000.0


def test_akshare_events_rejects_malformed_and_source_failure() -> None:
    instrument = ping_an()
    malformed = AkshareEventAdapter(
        notices=lambda security, begin_date, end_date: [{"公告标题": "缺日期"}],
    )
    failing = AkshareEventAdapter(
        notices=lambda security, begin_date, end_date: (_ for _ in ()).throw(
            TimeoutError("upstream down")
        ),
    )
    query = EventQuery(instruments=(instrument,), kinds=(EventKind.NOTICE,), limit=10)
    with pytest.raises(InvalidSourcePayload, match="missing"):
        malformed.fetch_events(query)
    with pytest.raises(SourceUnavailable):
        failing.fetch_events(query)
