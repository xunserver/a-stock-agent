from __future__ import annotations

from datetime import date

from astock.providers.akshare.statement_aliases import (
    SOURCE_KEY_ALIASES,
    UNSUPPORTED_SOURCE_KEYS,
    canonical_code,
)
from astock_core.financial_statements import (
    LEGACY_SOURCE_ALIASES,
    PREVIOUS_DISPLAY_KEY_ITEMS,
)
from astock_core.market_data import (
    CANONICAL_STATEMENT_ITEMS,
    FinancialSheet,
    InvalidSourcePayload,
    StatementQuery,
)

from .contracts import assert_statement_source_contract
from .fakes import InMemoryStatementSource, ping_an
from .fixture_sources import (
    empty_statement_query,
    load_json,
    make_akshare_statement_adapter,
    valid_statement_query,
)


def test_in_memory_and_source_adapter_pass_statement_contract() -> None:
    source_dataset = make_akshare_statement_adapter().fetch_statements(valid_statement_query())
    memory = InMemoryStatementSource(known=(ping_an(),), statements=source_dataset.items)
    assert_statement_source_contract(
        memory,
        valid_query=valid_statement_query(),
        empty_query=empty_statement_query(),
    )
    dataset = assert_statement_source_contract(
        make_akshare_statement_adapter(),
        valid_query=valid_statement_query(),
        empty_query=empty_statement_query(),
    )
    codes = {item.code for statement in dataset.items for item in statement.items}
    assert "operating_revenue" in codes
    assert "OPERATE_INCOME" not in codes
    latest = dataset.items[-1]
    by_code = {item.code: item for item in latest.items}
    assert by_code["operating_revenue"].value == 100.0
    assert by_code["operating_revenue"].yoy_pct == 1.2
    assert by_code["operating_revenue"].qoq_pct == 0.4


def test_balance_and_cashflow_use_canonical_codes() -> None:
    adapter = make_akshare_statement_adapter()
    balance = adapter.fetch_statements(
        StatementQuery(
            instruments=(ping_an(),),
            sheet=FinancialSheet.BALANCE,
            start=date(2026, 1, 1),
            end=date(2026, 12, 31),
        )
    )
    cashflow = adapter.fetch_statements(
        StatementQuery(
            instruments=(ping_an(),),
            sheet=FinancialSheet.CASHFLOW,
            start=date(2026, 1, 1),
            end=date(2026, 12, 31),
        )
    )
    balance_codes = {item.code for item in balance.items[0].items}
    cashflow_codes = {item.code for item in cashflow.items[0].items}
    for code in CANONICAL_STATEMENT_ITEMS[FinancialSheet.BALANCE]:
        assert code in balance_codes
    for code in CANONICAL_STATEMENT_ITEMS[FinancialSheet.CASHFLOW]:
        assert code in cashflow_codes


def test_malformed_mixed_period_raises_typed_error() -> None:
    adapter = make_akshare_statement_adapter(
        profit_rows=load_json("akshare", "statements_mixed_period.json")
    )
    try:
        adapter.fetch_statements(valid_statement_query())
    except InvalidSourcePayload:
        return
    raise AssertionError("mixed-period statement should raise InvalidSourcePayload")


def test_empty_statement_is_successful_dataset() -> None:
    adapter = make_akshare_statement_adapter(profit_rows=[])
    dataset = adapter.fetch_statements(valid_statement_query())
    assert dataset.items == ()
    assert dataset.complete is True


def test_previously_displayed_keys_map_to_canonical_codes() -> None:
    assert SOURCE_KEY_ALIASES == LEGACY_SOURCE_ALIASES
    for sheet, keys in PREVIOUS_DISPLAY_KEY_ITEMS.items():
        for key in keys:
            code = canonical_code(key)
            assert code is not None, f"{sheet} key {key} is unsupported without a reason"
            assert code in CANONICAL_STATEMENT_ITEMS[FinancialSheet(sheet)]
    assert "SECURITY_TYPE_CODE" in UNSUPPORTED_SOURCE_KEYS
