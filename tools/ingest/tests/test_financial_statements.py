from __future__ import annotations

from datetime import date, datetime, timezone

from astock.financial import sync_financial_statements
from astock.providers.akshare.statements import f10_symbol
from astock_core.db import MarketDB
from astock_core.financial_statements import extract_statement_items
from astock_core.market_data import (
    Dataset,
    FinancialPeriodType,
    FinancialSheet,
    FinancialStatement,
    StatementItem,
    StatementQuery,
    StatementUnit,
    from_legacy_symbol,
)


FETCHED_AT = datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


def test_f10_symbol() -> None:
    assert f10_symbol(from_legacy_symbol("000001")) == "SZ000001"
    assert f10_symbol(from_legacy_symbol("600519")) == "SH600519"
    assert f10_symbol(from_legacy_symbol("920001")) == "BJ920001"


def _statement(**overrides) -> FinancialStatement:
    values = dict(
        instrument_id=from_legacy_symbol("000001"),
        sheet=FinancialSheet.PROFIT,
        period_end=date(2026, 6, 30),
        period_type=FinancialPeriodType.H1,
        currency="CNY",
        items=(
            StatementItem(
                code="operating_revenue",
                label="营业收入",
                value=100.0,
                unit=StatementUnit.CNY,
                yoy_pct=1.2,
            ),
        ),
        announced_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return FinancialStatement(**values)


def test_sync_financial_statements(tmp_path) -> None:
    class _Source:
        def fetch_statements(self, query: StatementQuery):
            return Dataset(items=(_statement(),), source="memory", fetched_at=FETCHED_AT)

    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        result = sync_financial_statements(
            db, ["000001"], sheets=("profit",), statement_source=_Source()
        )
        assert result["statement_stocks"] == 1
        assert result["statement_rows"] == 1
        row = db.get_financial_statement("000001", "2026-06-30", "profit")
        assert row is not None
        assert row["payload"]["operating_revenue"] == 100.0
        assert "OPERATE_INCOME" not in row["payload"]


def test_financial_statements_db_roundtrip(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        db.upsert_standard_statements((_statement(),))
        summary = db.financial_statement_summary("000001")
        assert summary["profit"]["count"] == 1
        assert summary["profit"]["latest_report_date"] == "2026-06-30"
        dates = db.list_financial_statement_dates("000001", "profit")
        assert dates == ["2026-06-30"]


def test_legacy_payload_read_model_uses_canonical_codes() -> None:
    items = extract_statement_items(
        "profit",
        {"OPERATE_INCOME": 100.0, "NETPROFIT": 20.0},
    )
    keys = [item["key"] for item in items]
    assert keys[0] == "operating_revenue"
    assert "OPERATE_INCOME" not in keys
    operate = next(item for item in items if item["key"] == "operating_revenue")
    assert operate["label"] == "营业收入"
    assert operate["value"] == 100.0
    net = next(item for item in items if item["key"] == "net_profit")
    assert net["value"] == 20.0
