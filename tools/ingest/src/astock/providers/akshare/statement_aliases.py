"""Eastmoney F10 statement field aliases owned by the AKShare Adapter.

Canonical codes and display metadata live in ``astock_core.market_data.line_items``.
This table is the only production place that names source field identifiers.
"""

from __future__ import annotations

from astock_core.financial_statements import (
    LEGACY_SOURCE_ALIASES,
    LEGACY_UNSUPPORTED_KEYS,
    companion_base,
    companion_kind,
    is_companion_key,
    source_key_to_canonical,
    statement_label,
    statement_unit,
)
from astock_core.market_data.enums import StatementUnit
from astock_core.market_data.line_items import LINE_ITEMS
from astock_core.market_data.models import StatementItem

# Live Adapter copy of the stored-payload reconstruction table. A contract test
# requires these dicts to stay equal so ingest and legacy reads cannot drift.
SOURCE_KEY_ALIASES = dict(LEGACY_SOURCE_ALIASES)
UNSUPPORTED_SOURCE_KEYS = dict(LEGACY_UNSUPPORTED_KEYS)


def canonical_code(source_key: str) -> str | None:
    return source_key_to_canonical(source_key)


def items_from_source_row(row: dict[str, object]) -> tuple[StatementItem, ...]:
    values: dict[str, float | str] = {}
    yoy: dict[str, float] = {}
    qoq: dict[str, float] = {}
    for key, raw in row.items():
        if raw is None:
            continue
        name = str(key)
        kind = companion_kind(name)
        base = companion_base(name)
        if kind and base:
            code = canonical_code(base)
            number = _finite_float(raw)
            if code and number is not None:
                if kind == "yoy" and code not in yoy:
                    yoy[code] = number
                elif kind == "qoq" and code not in qoq:
                    qoq[code] = number
            continue
        code = canonical_code(name)
        if not code:
            continue
        parsed = _item_value(raw)
        if parsed is None or code in values:
            continue
        values[code] = parsed
    items: list[StatementItem] = []
    for code, value in values.items():
        spec = LINE_ITEMS.get(code)
        unit = spec.unit if spec is not None else statement_unit(code)
        if isinstance(value, str):
            unit = StatementUnit.TEXT
        items.append(
            StatementItem(
                code=code,
                label=spec.label if spec is not None else statement_label(code),
                value=value,
                unit=unit,
                yoy_pct=yoy.get(code),
                qoq_pct=qoq.get(code),
            )
        )
    return tuple(items)


def _finite_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _item_value(value: object) -> float | str | None:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        number = float(value)
        return None if number != number else number
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return text
    return None if number != number else number


__all__ = [
    "SOURCE_KEY_ALIASES",
    "UNSUPPORTED_SOURCE_KEYS",
    "canonical_code",
    "companion_base",
    "companion_kind",
    "is_companion_key",
    "items_from_source_row",
]
