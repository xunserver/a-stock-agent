"""Financial-statement read models and stored-payload reconstruction.

Live source aliases live in the AKShare Statement Adapter. This module reconstructs
normalized items from stored JSON, including pre-migration Eastmoney-keyed payloads.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from astock_core.market_data.enums import FinancialSheet, StatementUnit
from astock_core.market_data.line_items import (
    LINE_ITEMS,
    display_key_codes,
)
from astock_core.market_data.models import StatementItem

FINANCIAL_SHEETS = ("balance", "profit", "cashflow")
NORMALIZED_STATEMENT_SCHEMA = "statement_items_v1"

# Frozen reconstruction of keys that were stored before Plan 05. Adapter mapping
# tables must cover the same displayed keys; see statement_aliases.py.
LEGACY_SOURCE_ALIASES: dict[str, str] = {
    "MONETARYFUNDS": "cash_and_equivalents",
    "ACCOUNTS_RECE": "accounts_receivable",
    "NOTE_ACCOUNTS_RECE": "accounts_receivable",
    "INVENTORY": "inventory",
    "TOTAL_CURRENT_ASSETS": "total_current_assets",
    "TOTAL_ASSETS": "total_assets",
    "TOTAL_CURRENT_LIAB": "total_current_liabilities",
    "TOTAL_LIABILITIES": "total_liabilities",
    "TOTAL_PARENT_EQUITY": "total_parent_equity",
    "TOTAL_EQUITY": "total_equity",
    "TOTAL_OPERATE_INCOME": "total_revenue",
    "OPERATE_INCOME": "operating_revenue",
    "OPERATE_PROFIT": "operating_profit",
    "TOTAL_PROFIT": "total_profit",
    "NETPROFIT": "net_profit",
    "PARENT_NETPROFIT": "parent_net_profit",
    "BASIC_EPS": "basic_eps",
    "TOTAL_OPERATE_INFLOW": "operating_cash_inflow",
    "TOTAL_OPERATE_OUTFLOW": "operating_cash_outflow",
    "NETCASH_OPERATE": "net_operating_cashflow",
    "NETCASH_INVEST": "net_investing_cashflow",
    "NETCASH_FINANCE": "net_financing_cashflow",
    "CCE_ADD": "net_change_in_cash",
    "END_CCE": "ending_cash",
    "END_CASH": "ending_cash",
}

LEGACY_UNSUPPORTED_KEYS: dict[str, str] = {
    "SECURITY_TYPE_CODE": "security metadata, not a statement line item",
    "SECUCODE": "instrument identity metadata",
    "SECURITY_CODE": "instrument identity metadata",
    "SECURITY_NAME_ABBR": "instrument identity metadata",
    "ORG_CODE": "organization metadata",
    "ORG_TYPE": "organization metadata",
    "REPORT_DATE": "period identity, not a line item",
    "REPORT_TYPE": "period identity, not a line item",
    "REPORT_DATE_NAME": "period identity, not a line item",
    "NOTICE_DATE": "announcement identity, not a line item",
    "UPDATE_DATE": "source housekeeping, not a line item",
    "CURRENCY": "statement currency, not a line item",
    "OSOPINION_TYPE": "audit opinion metadata",
    "LISTING_STATE": "listing metadata",
}

_PERCENT_KEY_SUFFIXES = ("_YOY", "_QOQ", "_MOM", "_TZ", "_RATE", "_yoy", "_qoq", "_mom")
_COMPANION_SUFFIXES = ("_YOY", "_QOQ", "_MOM", "_TZ", "_yoy", "_qoq", "_mom")

# Previously displayed decision-facing keys from extract_statement_items.
PREVIOUS_DISPLAY_KEY_ITEMS: dict[str, tuple[str, ...]] = {
    "profit": ("OPERATE_INCOME", "TOTAL_PROFIT", "PARENT_NETPROFIT", "NETPROFIT"),
    "balance": ("TOTAL_ASSETS", "TOTAL_LIABILITIES", "TOTAL_EQUITY"),
    "cashflow": ("NETCASH_OPERATE", "NETCASH_INVEST", "NETCASH_FINANCE"),
}


@lru_cache(maxsize=1)
def load_statement_labels() -> dict[str, str]:
    text = (
        resources.files(__package__)
        .joinpath("financial_statement_labels.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(text)


@lru_cache(maxsize=1)
def load_statement_templates() -> dict[str, list[dict[str, str]]]:
    text = (
        resources.files(__package__)
        .joinpath("financial_statement_templates.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(text)


def is_companion_key(key: str) -> bool:
    return any(key.endswith(suffix) for suffix in _COMPANION_SUFFIXES)


def companion_base(key: str) -> str | None:
    for suffix in _COMPANION_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return None


def companion_kind(key: str) -> str | None:
    lowered = key.lower()
    if lowered.endswith("_yoy") or lowered.endswith("_tz"):
        return "yoy"
    if lowered.endswith("_qoq") or lowered.endswith("_mom"):
        return "qoq"
    return None


def source_key_to_canonical(key: str) -> str | None:
    """Map a stored or source field name to a canonical line-item code.

    Companion YoY/QoQ keys return ``None``; attach them on the parent item.
    Unsupported metadata keys return ``None``.
    """
    if not key or key in LEGACY_UNSUPPORTED_KEYS or is_companion_key(key):
        return None
    return LEGACY_SOURCE_ALIASES.get(key, key.lower())


def statement_label(code: str) -> str:
    spec = LINE_ITEMS.get(code)
    if spec is not None:
        return spec.label
    labels = load_statement_labels()
    if code in labels:
        return labels[code]
    eastmoney = code.upper()
    if eastmoney in labels:
        return labels[eastmoney]
    alias = next((source for source, target in LEGACY_SOURCE_ALIASES.items() if target == code), None)
    if alias and alias in labels:
        return labels[alias]
    return _humanize_field_key(code)


def statement_unit(code: str) -> StatementUnit:
    spec = LINE_ITEMS.get(code)
    if spec is not None:
        return spec.unit
    if code.endswith("_pct") or code.endswith("_rate"):
        return StatementUnit.PERCENT
    if code.endswith("_eps") or code.endswith("eps"):
        return StatementUnit.PER_SHARE
    return StatementUnit.CNY


def _humanize_field_key(key: str) -> str:
    parts = key.lower().split("_")
    return " ".join(part.capitalize() for part in parts if part)


def _is_percent_code(code: str, label: str) -> bool:
    if statement_unit(code) is StatementUnit.PERCENT:
        return True
    if any(code.endswith(suffix.lower().lstrip("_")) for suffix in ("_pct",)):
        return True
    return "%" in label or "同比" in label or "环比" in label


def _kind_for(code: str, label: str) -> str:
    return "percent" if _is_percent_code(code, label) else "amount"


def item_to_read_model(item: StatementItem) -> dict[str, Any]:
    return {
        "key": item.code,
        "label": item.label,
        "value": item.value,
        "kind": _kind_for(item.code, item.label),
        "yoy": item.yoy_pct,
        "qoq": item.qoq_pct,
    }


def serialize_statement_items(items: tuple[StatementItem, ...]) -> str:
    payload = {
        "schema": NORMALIZED_STATEMENT_SCHEMA,
        "items": [
            {
                "code": item.code,
                "label": item.label,
                "value": item.value,
                "unit": item.unit.value,
                "yoy_pct": item.yoy_pct,
                "qoq_pct": item.qoq_pct,
            }
            for item in items
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def deserialize_statement_items(raw: object) -> tuple[StatementItem, ...]:
    payload = _parse_payload(raw)
    if _is_normalized(payload):
        return _items_from_normalized(payload)
    return _items_from_legacy(payload)


def payload_values_from_items(items: tuple[StatementItem, ...] | list[dict[str, Any]]) -> dict[str, float | str]:
    values: dict[str, float | str] = {}
    for item in items:
        if isinstance(item, StatementItem):
            code, value, yoy, qoq = item.code, item.value, item.yoy_pct, item.qoq_pct
        else:
            code = str(item.get("key") or item.get("code") or "")
            value = item.get("value")
            yoy = item.get("yoy")
            qoq = item.get("qoq")
        if not code or value is None:
            continue
        values[code] = value
        if yoy is not None:
            values[f"{code}_yoy"] = yoy
        if qoq is not None:
            values[f"{code}_qoq"] = qoq
    return values


def extract_statement_items(sheet: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the control-plane/UI read model for one stored statement payload."""
    records = deserialize_statement_items(payload)
    by_code = {item.code: item for item in records}
    seen: set[str] = set()
    items: list[dict[str, Any]] = []

    def append_code(code: str, *, include_missing: bool) -> None:
        if not code or code in seen:
            return
        record = by_code.get(code)
        if record is None and not include_missing:
            return
        seen.add(code)
        label = record.label if record is not None else statement_label(code)
        value: float | str | None = record.value if record is not None else None
        items.append(
            {
                "key": code,
                "label": label,
                "value": value,
                "kind": _kind_for(code, label),
                "yoy": record.yoy_pct if record is not None else None,
                "qoq": record.qoq_pct if record is not None else None,
            }
        )

    try:
        sheet_enum = FinancialSheet(sheet)
    except ValueError:
        sheet_enum = None

    if sheet_enum is not None:
        for code in display_key_codes(sheet_enum):
            append_code(code, include_missing=True)
        for field in load_statement_templates().get(sheet, []):
            canonical = source_key_to_canonical(field["key"])
            if canonical:
                append_code(canonical, include_missing=True)

    remaining = sorted(code for code in by_code if code not in seen)
    for code in remaining:
        append_code(code, include_missing=False)
    return items


def _parse_payload(raw: object) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    if isinstance(raw, dict):
        return raw
    return {}


def _is_normalized(payload: dict[str, Any]) -> bool:
    return payload.get("schema") == NORMALIZED_STATEMENT_SCHEMA and isinstance(
        payload.get("items"), list
    )


def _items_from_normalized(payload: dict[str, Any]) -> tuple[StatementItem, ...]:
    items: list[StatementItem] = []
    for raw in payload["items"]:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("code") or "").strip()
        if not code:
            continue
        value = raw.get("value")
        if value is None:
            continue
        unit_raw = raw.get("unit") or statement_unit(code).value
        try:
            unit = StatementUnit(str(unit_raw))
        except ValueError:
            unit = statement_unit(code)
        items.append(
            StatementItem(
                code=code,
                label=str(raw.get("label") or statement_label(code)),
                value=value if isinstance(value, (int, float, str)) else str(value),
                unit=unit,
                yoy_pct=_optional_float(raw.get("yoy_pct")),
                qoq_pct=_optional_float(raw.get("qoq_pct")),
            )
        )
    return tuple(items)


def _items_from_legacy(payload: dict[str, Any]) -> tuple[StatementItem, ...]:
    values: dict[str, float | str] = {}
    yoy: dict[str, float] = {}
    qoq: dict[str, float] = {}
    for key, raw in payload.items():
        if raw is None:
            continue
        kind = companion_kind(key)
        base = companion_base(key)
        if kind and base:
            canonical = source_key_to_canonical(base)
            number = _optional_float(raw)
            if canonical and number is not None:
                if kind == "yoy":
                    yoy[canonical] = number
                else:
                    qoq[canonical] = number
            continue
        canonical = source_key_to_canonical(str(key))
        if not canonical:
            continue
        parsed = _legacy_value(raw)
        if parsed is None:
            continue
        if canonical not in values:
            values[canonical] = parsed
    items: list[StatementItem] = []
    for code, value in values.items():
        spec = LINE_ITEMS.get(code)
        items.append(
            StatementItem(
                code=code,
                label=spec.label if spec else statement_label(code),
                value=value,
                unit=spec.unit if spec else statement_unit(code),
                yoy_pct=yoy.get(code),
                qoq_pct=qoq.get(code),
            )
        )
    return tuple(items)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _legacy_value(value: object) -> float | str | None:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        number = float(value)
        return None if number != number else number
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    try:
        return float(text)
    except ValueError:
        return text
