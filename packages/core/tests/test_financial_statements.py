from __future__ import annotations

from astock_core.financial_statements import (
    PREVIOUS_DISPLAY_KEY_ITEMS,
    extract_statement_items,
    source_key_to_canonical,
    statement_label,
)
from astock_core.market_data import CANONICAL_STATEMENT_ITEMS, FinancialSheet


def test_statement_label_known_canonical_code() -> None:
    assert statement_label("operating_revenue") == "营业收入"
    assert statement_label("total_assets") == "总资产"


def test_extract_statement_items_uses_canonical_codes_and_keeps_template_nulls() -> None:
    items = extract_statement_items(
        "profit",
        {
            "OPERATE_INCOME": 100.0,
            "OPERATE_INCOME_YOY": 1.2,
        },
    )
    keys = [item["key"] for item in items]
    assert "operating_revenue" in keys
    assert "OPERATE_INCOME" not in keys
    operate = next(item for item in items if item["key"] == "operating_revenue")
    assert operate["label"] == "营业收入"
    assert operate["value"] == 100.0
    assert operate["yoy"] == 1.2
    assert len(items) >= 50


def test_extract_statement_items_appends_unknown_payload_fields() -> None:
    items = extract_statement_items(
        "profit",
        {
            "OPERATE_INCOME": 100.0,
            "CUSTOM_EXTRA_FIELD": 9.9,
        },
    )
    keys = [item["key"] for item in items]
    assert "custom_extra_field" in keys
    extra = next(item for item in items if item["key"] == "custom_extra_field")
    assert extra["value"] == 9.9


def test_previously_displayed_key_items_map_to_canonical_codes() -> None:
    for sheet, keys in PREVIOUS_DISPLAY_KEY_ITEMS.items():
        for key in keys:
            code = source_key_to_canonical(key)
            assert code is not None
            assert code in CANONICAL_STATEMENT_ITEMS[FinancialSheet(sheet)]


def test_template_line_items_map_or_are_documented_unsupported() -> None:
    from astock_core.financial_statements import (
        LEGACY_UNSUPPORTED_KEYS,
        is_companion_key,
        load_statement_templates,
    )

    unmapped: list[str] = []
    for sheet, fields in load_statement_templates().items():
        for field in fields:
            key = field["key"]
            if is_companion_key(key) or key in LEGACY_UNSUPPORTED_KEYS:
                continue
            if source_key_to_canonical(key) is None:
                unmapped.append(f"{sheet}:{key}")
    assert unmapped == []
