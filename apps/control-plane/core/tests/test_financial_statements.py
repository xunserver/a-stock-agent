from __future__ import annotations

import json

from astock_control.protocol import normalize_command
from astock_control.queries import stock_financials_detail_query, stock_get_query
from astock_core.db import MarketDB


def test_stock_sync_with_statements_flag() -> None:
    cmd = normalize_command(
        {
            "type": "stock.sync",
            "codes": ["000001"],
            "with_statements": True,
        }
    )
    assert cmd["with_statements"] is True


def test_stock_financials_detail_query(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行")])
        db.upsert_financial_statements(
            "000001",
            [
                {
                    "report_date": "2026-06-30",
                    "sheet": "profit",
                    "report_type": "2026中报",
                    "notice_date": "2026-08-15",
                    "payload_json": json.dumps(
                        {"OPERATE_INCOME": 100.0, "NETPROFIT": 20.0}
                    ),
                }
            ],
        )
    payload = stock_financials_detail_query(
        "000001",
        sheet="profit",
        report_date="2026-06-30",
    )
    assert payload["report_type"] == "2026中报"
    assert payload["key_items"][0]["label"] == "营业收入"
    assert payload["key_items"][0]["key"] == "operating_revenue"
    assert payload["payload"]["net_profit"] == 20.0
    assert "NETPROFIT" not in payload["payload"]


def test_stock_get_includes_statements_summary(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行")])
        db.upsert_financial_statements(
            "000001",
            [
                {
                    "report_date": "2026-06-30",
                    "sheet": "balance",
                    "payload_json": json.dumps({"TOTAL_ASSETS": 1.0}),
                }
            ],
        )
    payload = stock_get_query("000001")
    assert payload["financial_statements_summary"]["balance"]["count"] == 1
