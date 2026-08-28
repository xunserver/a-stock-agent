from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

FINANCIAL_SHEETS = ("balance", "profit", "cashflow")

STATEMENT_KEY_ITEMS: dict[str, list[tuple[str, str]]] = {
    "profit": [
        ("OPERATE_INCOME", "营业收入"),
        ("TOTAL_PROFIT", "利润总额"),
        ("PARENT_NETPROFIT", "归母净利润"),
        ("NETPROFIT", "净利润"),
    ],
    "balance": [
        ("TOTAL_ASSETS", "总资产"),
        ("TOTAL_LIABILITIES", "总负债"),
        ("TOTAL_EQUITY", "股东权益"),
    ],
    "cashflow": [
        ("NETCASH_OPERATE", "经营现金流净额"),
        ("NETCASH_INVEST", "投资现金流净额"),
        ("NETCASH_FINANCE", "筹资现金流净额"),
    ],
}

PAYLOAD_SKIP_KEYS = frozenset(
    {
        "SECURITY_TYPE_CODE",
    }
)

_PERCENT_KEY_SUFFIXES = ("_YOY", "_QOQ", "_MOM", "_TZ", "_RATE")


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


def statement_label(key: str) -> str:
    labels = load_statement_labels()
    if key in labels:
        return labels[key]
    for items in STATEMENT_KEY_ITEMS.values():
        for item_key, item_label in items:
            if item_key == key:
                return item_label
    return _humanize_field_key(key)


def _humanize_field_key(key: str) -> str:
    parts = key.lower().split("_")
    return " ".join(part.capitalize() for part in parts if part)


def _companion_base(key: str) -> str | None:
    for suffix in _PERCENT_KEY_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return None


def _is_percent_field(key: str, label: str) -> bool:
    if any(key.endswith(suffix) for suffix in _PERCENT_KEY_SUFFIXES):
        return True
    return "%" in label or "同比" in label or "环比" in label


def extract_statement_items(
    sheet: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    labels = load_statement_labels()
    templates = load_statement_templates().get(sheet, [])
    seen: set[str] = set()
    items: list[dict[str, Any]] = []

    def append_item(key: str, label: str, value: Any) -> None:
        if key in seen or key in PAYLOAD_SKIP_KEYS:
            return
        if _companion_base(key) is not None:
            return
        seen.add(key)
        yoy = payload.get(f"{key}_YOY")
        qoq = payload.get(f"{key}_QOQ")
        if qoq is None:
            qoq = payload.get(f"{key}_MOM")
        items.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "kind": "percent" if _is_percent_field(key, label) else "amount",
                "yoy": yoy,
                "qoq": qoq,
            }
        )

    for field in templates:
        key = field["key"]
        label = labels.get(key) or field.get("label") or statement_label(key)
        append_item(key, label, payload.get(key))

    remaining = sorted(
        (key for key in payload if key not in seen and key not in PAYLOAD_SKIP_KEYS),
        key=lambda key: labels.get(key, key),
    )
    for key in remaining:
        value = payload.get(key)
        if value is None:
            continue
        append_item(key, labels.get(key) or statement_label(key), value)

    return items
