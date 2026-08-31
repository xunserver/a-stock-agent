from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from astock.events import fetch_stock_events
from astock.providers.akshare.events import AkshareEventAdapter
from astock_core.market_data import (
    BlockTradeEvent,
    HolderChangeEvent,
    NoticeEvent,
    ResearchReportEvent,
    from_legacy_symbol,
)

_fakes_path = Path(__file__).resolve().parent / "providers" / "fakes.py"
_spec = importlib.util.spec_from_file_location("ingest_test_fakes", _fakes_path)
assert _spec and _spec.loader
_fakes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fakes)
InMemoryEventSource = _fakes.InMemoryEventSource


def _aware(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def test_fetch_notices_projects_legacy_extra() -> None:
    instrument = from_legacy_symbol("000001")
    source = InMemoryEventSource(
        (
            NoticeEvent(
                id="notice-0",
                instrument_id=instrument,
                title="公告0",
                published_at=_aware("2026-01-01T00:00:00+08:00"),
                source="财务报告",
                url="http://example.com/0",
                notice_type="财务报告",
            ),
        )
    )
    items = fetch_stock_events("000001", "notices", limit=3, event_source=source)
    assert len(items) == 1
    assert items[0]["extra"]["notice_type"] == "财务报告"


def test_fetch_research_projects_legacy_summary_and_extra() -> None:
    instrument = from_legacy_symbol("600000")
    source = InMemoryEventSource(
        (
            ResearchReportEvent(
                id="research-1",
                instrument_id=instrument,
                title="深度报告",
                published_at=_aware("2026-02-01T00:00:00+08:00"),
                organization="中信证券",
                rating="买入",
                pdf_url="http://pdf.example.com/a.pdf",
                url="http://pdf.example.com/a.pdf",
            ),
        )
    )
    items = fetch_stock_events("600000", "research", limit=10, event_source=source)
    assert items[0]["summary"] == "中信证券 · 买入"
    assert items[0]["extra"]["rating"] == "买入"


def test_fetch_block_trades_projects_legacy_extra() -> None:
    instrument = from_legacy_symbol("000001")
    source = InMemoryEventSource(
        (
            BlockTradeEvent(
                id="block-1",
                instrument_id=instrument,
                title="大宗成交 10.5",
                published_at=_aware("2026-03-01T00:00:00+08:00"),
                buyer="买方A",
                premium_pct=-1.2,
            ),
        )
    )
    items = fetch_stock_events("000001", "block_trades", limit=10, event_source=source)
    assert items[0]["extra"]["buyer"] == "买方A"
    assert items[0]["extra"]["premium_ratio"] == -1.2


def test_fetch_holder_changes_projects_legacy_title_and_extra() -> None:
    instrument = from_legacy_symbol("600000")
    source = InMemoryEventSource(
        (
            HolderChangeEvent(
                id="holder-1",
                instrument_id=instrument,
                title="张三（董事）",
                published_at=_aware("2026-04-01T00:00:00+08:00"),
                person="张三",
                role="董事",
                change_shares=-1000.0,
                average_price=12.3,
                reason="二级市场买卖",
            ),
        )
    )
    items = fetch_stock_events("600000", "holder_changes", limit=10, event_source=source)
    assert items[0]["title"] == "张三（董事）"
    assert "变动 -1000" in items[0]["summary"]
    assert items[0]["extra"]["reason"] == "二级市场买卖"


def test_fetch_stock_events_dispatches_kind_via_adapter() -> None:
    instrument = from_legacy_symbol("000001")
    adapter = AkshareEventAdapter(
        notices=lambda security, begin_date, end_date: [
            {
                "公告标题": "n",
                "公告日期": "2026-01-01",
            }
        ],
    )
    items = fetch_stock_events("000001", "notices", event_source=adapter)
    assert items[0]["title"] == "n"


def test_fetch_stock_events_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="未知事件类型"):
        fetch_stock_events("000001", "nope", event_source=InMemoryEventSource(()))
