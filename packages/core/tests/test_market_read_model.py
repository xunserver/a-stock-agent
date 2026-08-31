from __future__ import annotations

from datetime import date

import pytest
from bar_fixtures import make_test_bar

from astock_core.db import MarketDB
from astock_core.market_data import Adjustment, Bar, BarInterval, InstrumentId


def test_catalog_and_candidate_return_projections(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行"), ("600000", "浦发银行")])
        db.upsert_standard_bars(
            [
                make_test_bar("000001", "2026-08-27", close=10.5),
                make_test_bar("000001", "2026-08-28", close=10.4475),
                make_test_bar("600000", "2026-08-27", close=10.0),
                make_test_bar("600000", "2026-08-28", close=10.08),
            ]
        )

        assert db.stock_names({"000001", "999999"}) == {"000001": "平安银行"}
        assert db.next_bar_date("2026-08-27") == "2026-08-28"
        changes = db.pct_changes_on_date(
            ["000001", "600000", "999999"], "2026-08-28"
        )
        assert changes["000001"] == pytest.approx(-0.5)
        assert changes["600000"] == pytest.approx(0.8)


def _index_bar(code: str, trade_date: str) -> Bar:
    symbol = code[-6:]
    exchange = "XSHG" if code.startswith("sh") or code.startswith("csi") else "XSHE"
    return Bar(
        instrument_id=InstrumentId(country="CN", exchange=exchange, symbol=symbol),
        trade_date=date.fromisoformat(trade_date),
        interval=BarInterval.D1,
        adjustment=Adjustment.RAW,
        open=1.0,
        high=3.0,
        low=0.5,
        close=2.0,
        volume=100.0,
        amount=200.0,
    )


def test_export_projections_are_ordered_and_hide_storage_schema(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.upsert_standard_bars(
            [
                make_test_bar("600000", "2026-08-28"),
                make_test_bar("000001", "2026-08-27"),
            ]
        )
        db.upsert_standard_index_bars(
            [_index_bar("000300", "2026-08-28")],
            code="000300",
            name="沪深300",
        )
        db.upsert_standard_index_bars(
            [_index_bar("000001", "2026-08-27")],
            code="000001",
            name="上证指数",
        )

        bars = db.list_bar_export_rows()
        indexes = db.list_index_bar_export_rows()

    assert [(row["code"], row["date"]) for row in bars] == [
        ("000001", "2026-08-27"),
        ("600000", "2026-08-28"),
    ]
    assert list(bars[0]) == [
        "code",
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
    ]
    assert [(row["code"], row["date"]) for row in indexes] == [
        ("000001", "2026-08-27"),
        ("000300", "2026-08-28"),
    ]
