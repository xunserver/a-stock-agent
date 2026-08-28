"""东财 F10 三大报表明细拉取与入库。"""

from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd

from astock.ingest import _call
from astock.profile import as_list_date, as_text
from astock_core.financial_statements import extract_statement_items

logger = logging.getLogger(__name__)

FINANCIAL_SHEETS = ("balance", "profit", "cashflow")
SHEET_INGEST_KIND = {
    "balance": "financial_balance",
    "profit": "financial_profit",
    "cashflow": "financial_cashflow",
}
STATEMENT_META_KEYS = frozenset(
    {
        "SECUCODE",
        "SECURITY_CODE",
        "SECURITY_NAME_ABBR",
        "ORG_CODE",
        "ORG_TYPE",
        "REPORT_DATE",
        "REPORT_TYPE",
        "REPORT_DATE_NAME",
        "NOTICE_DATE",
        "UPDATE_DATE",
        "CURRENCY",
        "OSOPINION_TYPE",
        "LISTING_STATE",
    }
)

def em_symbol(code: str) -> str:
    normalized = code.strip().zfill(6)
    if normalized.startswith(("6", "5", "9")) and not normalized.startswith("92"):
        return f"SH{normalized}"
    if normalized.startswith(("4", "8", "92")):
        return f"BJ{normalized}"
    return f"SZ{normalized}"


def _json_value(value: object) -> float | str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        if value != value:
            return None
        return value
    text = as_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return text


def normalize_statement_row(raw: dict[str, Any], *, sheet: str) -> dict[str, Any] | None:
    report_date = as_list_date(raw.get("REPORT_DATE"))
    if not report_date:
        return None
    payload: dict[str, float | str] = {}
    for key, value in raw.items():
        if key in STATEMENT_META_KEYS:
            continue
        parsed = _json_value(value)
        if parsed is not None:
            payload[key] = parsed
    if not payload:
        return None
    report_type = as_text(raw.get("REPORT_TYPE")) or as_text(raw.get("REPORT_DATE_NAME"))
    return {
        "report_date": report_date,
        "sheet": sheet,
        "report_type": report_type,
        "notice_date": as_list_date(raw.get("NOTICE_DATE")),
        "payload_json": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    }


def extract_key_items(sheet: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_statement_items(sheet, payload)


def _sheet_fetcher(sheet: str):
    import akshare as ak

    return {
        "balance": ak.stock_balance_sheet_by_report_em,
        "profit": ak.stock_profit_sheet_by_report_em,
        "cashflow": ak.stock_cash_flow_sheet_by_report_em,
    }[sheet]


def fetch_financial_statement_sheet(code: str, sheet: str) -> list[dict[str, Any]]:
    if sheet not in FINANCIAL_SHEETS:
        raise ValueError(f"未知 sheet: {sheet}")
    frame = _call(_sheet_fetcher(sheet), symbol=em_symbol(code))
    if frame is None or frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        mapped = normalize_statement_row(raw, sheet=sheet)
        if mapped:
            rows.append(mapped)
    rows.sort(key=lambda item: str(item.get("report_date") or ""), reverse=True)
    return rows


def fetch_financial_statements(
    code: str,
    *,
    sheets: tuple[str, ...] = FINANCIAL_SHEETS,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sheet in sheets:
        out.extend(fetch_financial_statement_sheet(code, sheet))
    return out


def sync_financial_statements(
    db,
    codes: list[str],
    *,
    sheets: tuple[str, ...] = FINANCIAL_SHEETS,
) -> dict[str, int]:
    stocks = 0
    rows = 0
    errors = 0
    for code in codes:
        normalized = code.strip().zfill(6)
        if not normalized:
            continue
        code_ok = False
        for sheet in sheets:
            kind = SHEET_INGEST_KIND[sheet]
            try:
                sheet_rows = fetch_financial_statement_sheet(normalized, sheet)
                if sheet_rows:
                    inserted = db.upsert_financial_statements(normalized, sheet_rows)
                    rows += inserted
                    code_ok = True
                    latest = str(sheet_rows[0].get("report_date") or "")
                    db.mark_ingest(
                        normalized,
                        kind,
                        "ok",
                        last_trade_date=latest or None,
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
