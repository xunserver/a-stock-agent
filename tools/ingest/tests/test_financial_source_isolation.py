from __future__ import annotations

from pathlib import Path

FORBIDDEN_FUNCS = (
    "stock_yjbb_em",
    "stock_zcfz_em",
    "stock_lrb_em",
    "stock_financial_analysis_indicator_em",
    "stock_balance_sheet_by_report_em",
    "stock_profit_sheet_by_report_em",
    "stock_cash_flow_sheet_by_report_em",
)
ADAPTER_ROOT = Path(__file__).resolve().parents[2] / "src" / "astock" / "providers"


def test_financial_source_calls_live_only_in_adapters() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "astock"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        if ADAPTER_ROOT in path.parents or path.parent == ADAPTER_ROOT:
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_FUNCS:
            if token in text:
                hits.append(f"{path.relative_to(root)}: {token}")
    assert hits == []
