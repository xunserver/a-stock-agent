from __future__ import annotations

import json

import pandas as pd

from astock.financial import (
    em_symbol,
    extract_key_items,
    fetch_financial_statement_sheet,
    normalize_statement_row,
    sync_financial_statements,
)
from astock_core.db import MarketDB


def test_em_symbol() -> None:
    assert em_symbol("000001") == "SZ000001"
    assert em_symbol("600519") == "SH600519"
    assert em_symbol("920001") == "BJ920001"


def test_normalize_statement_row() -> None:
    row = normalize_statement_row(
        {
            "SECUCODE": "000001.SZ",
            "SECURITY_CODE": "000001",
            "REPORT_DATE": "2026-06-30 00:00:00",
            "REPORT_DATE_NAME": "2026中报",
            "NOTICE_DATE": "2026-08-15",
            "OPERATE_INCOME": 100.0,
            "TOTAL_PROFIT": 20.0,
        },
        sheet="profit",
    )
    assert row is not None
    assert row["report_date"] == "2026-06-30"
    assert row["sheet"] == "profit"
    payload = json.loads(row["payload_json"])
    assert payload["OPERATE_INCOME"] == 100.0
    assert "SECUCODE" not in payload


def test_extract_key_items() -> None:
    items = extract_key_items(
        "profit",
        {"OPERATE_INCOME": 100.0, "NETPROFIT": 20.0},
    )
    assert items[0]["label"] == "营业收入"
    assert items[0]["value"] == 100.0


def test_fetch_financial_statement_sheet(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2026-06-30 00:00:00",
                "REPORT_DATE_NAME": "2026中报",
                "NOTICE_DATE": "2026-08-15",
                "OPERATE_INCOME": 100.0,
            },
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "REPORT_DATE_NAME": "2025年报",
                "OPERATE_INCOME": 80.0,
            },
        ]
    )

    def fake_call(fn, *args, **kwargs):
        return frame

    monkeypatch.setattr("astock.financial._call", fake_call)
    rows = fetch_financial_statement_sheet("000001", "profit")
    assert len(rows) == 2
    assert rows[0]["report_date"] == "2026-06-30"


def test_sync_financial_statements(monkeypatch, tmp_path) -> None:
    def fake_fetch(code: str, sheet: str):
        return [
            {
                "report_date": "2026-06-30",
                "sheet": sheet,
                "report_type": "2026中报",
                "payload_json": json.dumps({"OPERATE_INCOME": 1.0}),
            }
        ]

    monkeypatch.setattr(
        "astock.financial.fetch_financial_statement_sheet",
        fake_fetch,
    )
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        result = sync_financial_statements(db, ["000001"], sheets=("profit",))
        assert result["statement_stocks"] == 1
        assert result["statement_rows"] == 1
        row = db.get_financial_statement("000001", "2026-06-30", "profit")
        assert row is not None
        assert row["payload"]["OPERATE_INCOME"] == 1.0


def test_financial_statements_db_roundtrip(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        db.upsert_financial_statements(
            "000001",
            [
                {
                    "report_date": "2026-06-30",
                    "sheet": "profit",
                    "report_type": "2026中报",
                    "payload_json": {"OPERATE_INCOME": 100.0},
                }
            ],
        )
        summary = db.financial_statement_summary("000001")
        assert summary["profit"]["count"] == 1
        assert summary["profit"]["latest_report_date"] == "2026-06-30"
        dates = db.list_financial_statement_dates("000001", "profit")
        assert dates == ["2026-06-30"]
