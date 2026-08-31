"""Financial Statement synchronization through StatementSource."""

from __future__ import annotations

import logging

from astock.providers.defaults import default_statement_source
from astock.providers.protocols import StatementSource
from astock_core.market_data import FinancialSheet, StatementQuery, from_legacy_symbol

logger = logging.getLogger(__name__)

FINANCIAL_SHEETS = ("balance", "profit", "cashflow")
SHEET_INGEST_KIND = {
    "balance": "financial_balance",
    "profit": "financial_profit",
    "cashflow": "financial_cashflow",
}


def sync_financial_statements(
    db,
    codes: list[str],
    *,
    sheets: tuple[str, ...] = FINANCIAL_SHEETS,
    statement_source: StatementSource | None = None,
) -> dict[str, int]:
    source = statement_source or default_statement_source()
    stocks = 0
    rows = 0
    errors = 0
    for code in codes:
        normalized = code.strip().zfill(6)
        if not normalized:
            continue
        instrument_id = from_legacy_symbol(normalized)
        code_ok = False
        for sheet in sheets:
            kind = SHEET_INGEST_KIND[sheet]
            try:
                dataset = source.fetch_statements(
                    StatementQuery(
                        instruments=(instrument_id,),
                        sheet=FinancialSheet(sheet),
                    )
                )
                if dataset.items:
                    inserted = db.upsert_standard_statements(dataset.items)
                    rows += inserted
                    code_ok = True
                    latest = max(item.period_end for item in dataset.items).isoformat()
                    db.mark_ingest(
                        normalized,
                        kind,
                        "ok",
                        last_trade_date=latest,
                        rows=0,
                    )
                else:
                    db.mark_ingest(normalized, kind, "empty", rows=0)
            except Exception as exc:
                errors += 1
                logger.warning("报表明细失败 %s %s: %s", normalized, sheet, exc)
                db.mark_ingest(
                    normalized,
                    kind,
                    "error",
                    error=str(exc),
                    rows=0,
                )
        if code_ok:
            stocks += 1
    return {
        "statement_stocks": stocks,
        "statement_rows": rows,
        "statement_errors": errors,
    }
