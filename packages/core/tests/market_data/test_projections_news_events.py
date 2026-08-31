from __future__ import annotations

from datetime import datetime, timezone

from astock_core.market_data import (
    BlockTradeEvent,
    HolderChangeEvent,
    NoticeEvent,
    ResearchReportEvent,
    from_legacy_symbol,
    market_event_extra,
    market_event_to_legacy_dict,
    news_item_to_legacy_dict,
)


def _aware(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def test_news_item_to_legacy_dict_maps_publisher_to_source() -> None:
    from astock_core.market_data import NewsItem

    news = NewsItem(
        id="n1",
        instrument_id=from_legacy_symbol("000001"),
        title="标题",
        published_at=_aware("2026-08-27T10:00:00+08:00"),
        publisher="证券时报",
    )
    assert news_item_to_legacy_dict(news)["source"] == "证券时报"


def test_market_event_extra_legacy_keys() -> None:
    instrument = from_legacy_symbol("000001")
    header = dict(
        instrument_id=instrument,
        title="t",
        published_at=_aware("2026-01-01T00:00:00+08:00"),
    )
    assert market_event_extra(
        ResearchReportEvent(id="1", organization="机构", rating="买入", **header)
    ) == {"org": "机构", "rating": "买入"}
    block = BlockTradeEvent(
        id="2",
        premium_pct=-1.2,
        pct_change=0.5,
        **header,
    )
    assert market_event_extra(block) == {"premium_ratio": -1.2, "pct_chg": 0.5}
    holder = HolderChangeEvent(
        id="3",
        person="张三",
        change_shares=-100.0,
        **header,
    )
    assert market_event_extra(holder) == {"name": "张三", "change_qty": -100.0}


def test_market_event_to_legacy_dict_builds_summary() -> None:
    event = ResearchReportEvent(
        id="1",
        instrument_id=from_legacy_symbol("600000"),
        title="深度报告",
        published_at=_aware("2026-02-01T00:00:00+08:00"),
        organization="中信证券",
        rating="买入",
    )
    projected = market_event_to_legacy_dict(event)
    assert projected["summary"] == "中信证券 · 买入"
