"""Canonical financial-statement line items.

The registry holds stable snake_case codes plus display metadata only.
Source aliases belong in Adapter mapping tables, not here.

To add a line item:
1. Choose a stable snake_case ``code`` (identity; labels may change).
2. Add a ``LineItemSpec`` below with label, unit, and sheet.
3. If it is a specification minimum, also add the code to
   ``CANONICAL_*_ITEMS`` in ``models.py``.
4. Map source field names in the Adapter alias table.
"""

from __future__ import annotations

from dataclasses import dataclass

from astock_core.market_data.enums import FinancialSheet, StatementUnit
from astock_core.market_data.models import (
    CANONICAL_BALANCE_ITEMS,
    CANONICAL_CASHFLOW_ITEMS,
    CANONICAL_PROFIT_ITEMS,
)


@dataclass(frozen=True, kw_only=True)
class LineItemSpec:
    code: str
    label: str
    unit: StatementUnit
    sheet: FinancialSheet


def _spec(
    code: str,
    label: str,
    sheet: FinancialSheet,
    unit: StatementUnit = StatementUnit.CNY,
) -> LineItemSpec:
    return LineItemSpec(code=code, label=label, unit=unit, sheet=sheet)


_BALANCE_SPECS: tuple[LineItemSpec, ...] = (
    _spec("cash_and_equivalents", "货币资金", FinancialSheet.BALANCE),
    _spec("accounts_receivable", "应收账款", FinancialSheet.BALANCE),
    _spec("inventory", "存货", FinancialSheet.BALANCE),
    _spec("total_current_assets", "流动资产合计", FinancialSheet.BALANCE),
    _spec("total_assets", "总资产", FinancialSheet.BALANCE),
    _spec("total_current_liabilities", "流动负债合计", FinancialSheet.BALANCE),
    _spec("total_liabilities", "总负债", FinancialSheet.BALANCE),
    _spec("total_parent_equity", "归母股东权益", FinancialSheet.BALANCE),
    _spec("total_equity", "股东权益", FinancialSheet.BALANCE),
)
_PROFIT_SPECS: tuple[LineItemSpec, ...] = (
    _spec("total_revenue", "营业总收入", FinancialSheet.PROFIT),
    _spec("operating_revenue", "营业收入", FinancialSheet.PROFIT),
    _spec("operating_profit", "营业利润", FinancialSheet.PROFIT),
    _spec("total_profit", "利润总额", FinancialSheet.PROFIT),
    _spec("net_profit", "净利润", FinancialSheet.PROFIT),
    _spec("parent_net_profit", "归母净利润", FinancialSheet.PROFIT),
    _spec("basic_eps", "基本每股收益", FinancialSheet.PROFIT, StatementUnit.PER_SHARE),
)
_CASHFLOW_SPECS: tuple[LineItemSpec, ...] = (
    _spec("operating_cash_inflow", "经营现金流入", FinancialSheet.CASHFLOW),
    _spec("operating_cash_outflow", "经营现金流出", FinancialSheet.CASHFLOW),
    _spec("net_operating_cashflow", "经营现金流净额", FinancialSheet.CASHFLOW),
    _spec("net_investing_cashflow", "投资现金流净额", FinancialSheet.CASHFLOW),
    _spec("net_financing_cashflow", "筹资现金流净额", FinancialSheet.CASHFLOW),
    _spec("net_change_in_cash", "现金净增加额", FinancialSheet.CASHFLOW),
    _spec("ending_cash", "期末现金", FinancialSheet.CASHFLOW),
)

LINE_ITEM_SPECS: tuple[LineItemSpec, ...] = _BALANCE_SPECS + _PROFIT_SPECS + _CASHFLOW_SPECS
LINE_ITEMS: dict[str, LineItemSpec] = {item.code: item for item in LINE_ITEM_SPECS}

DISPLAY_KEY_ITEMS: dict[FinancialSheet, tuple[str, ...]] = {
    FinancialSheet.BALANCE: ("total_assets", "total_liabilities", "total_equity"),
    FinancialSheet.PROFIT: (
        "operating_revenue",
        "total_profit",
        "parent_net_profit",
        "net_profit",
    ),
    FinancialSheet.CASHFLOW: (
        "net_operating_cashflow",
        "net_investing_cashflow",
        "net_financing_cashflow",
    ),
}


def line_item(code: str) -> LineItemSpec:
    spec = LINE_ITEMS.get(code)
    if spec is None:
        raise KeyError(f"unknown canonical line-item code: {code}")
    return spec


def specs_for_sheet(sheet: FinancialSheet) -> tuple[LineItemSpec, ...]:
    return tuple(item for item in LINE_ITEM_SPECS if item.sheet is sheet)


def display_key_codes(sheet: FinancialSheet) -> tuple[str, ...]:
    return DISPLAY_KEY_ITEMS[sheet]


def _assert_spec_minimums_registered() -> None:
    missing = [
        code
        for code in (
            *CANONICAL_BALANCE_ITEMS,
            *CANONICAL_PROFIT_ITEMS,
            *CANONICAL_CASHFLOW_ITEMS,
        )
        if code not in LINE_ITEMS
    ]
    if missing:
        raise RuntimeError(f"canonical line-item registry missing spec minimums: {missing}")


_assert_spec_minimums_registered()
