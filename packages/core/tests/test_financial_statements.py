from __future__ import annotations

from astock_core.financial_statements import extract_statement_items, statement_label


def test_statement_label_known_key() -> None:
    assert statement_label("OPERATE_INCOME") == "营业收入"
    assert statement_label("TOTAL_ASSETS") == "资产总计"


def test_extract_statement_items_includes_template_fields_with_nulls() -> None:
    items = extract_statement_items(
        "profit",
        {
            "OPERATE_INCOME": 100.0,
            "TOTAL_OPERATE_INCOME_YOY": 1.2,
        },
    )
    keys = [item["key"] for item in items]
    assert "OPERATE_INCOME" in keys
    assert keys.index("OPERATE_INCOME") < keys.index("TOTAL_OPERATE_INCOME_YOY")
    operate = next(item for item in items if item["key"] == "OPERATE_INCOME")
    assert operate["label"] == "营业收入"
    assert operate["value"] == 100.0
    assert len(items) >= 190


def test_extract_statement_items_appends_unknown_payload_fields() -> None:
    items = extract_statement_items(
        "profit",
        {
            "OPERATE_INCOME": 100.0,
            "CUSTOM_EXTRA_FIELD": 9.9,
        },
    )
    keys = [item["key"] for item in items]
    assert "CUSTOM_EXTRA_FIELD" in keys
    extra = next(item for item in items if item["key"] == "CUSTOM_EXTRA_FIELD")
    assert extra["value"] == 9.9
