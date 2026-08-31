"""Reusable Financial Statement capability contract."""

from __future__ import annotations

from astock_core.market_data import (
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    reject_vendor_types,
    validate_statement_dataset,
)

from astock.providers.protocols import StatementSource


def assert_statement_source_contract(
    source: StatementSource,
    *,
    valid_query,
    empty_query,
    error_cases: tuple[tuple[object, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_statements(valid_query)
    _assert_dataset_seam(first)
    validate_statement_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Statement query must return at least one FinancialStatement")
    for statement in first.items:
        if statement.announced_at is not None and statement.announced_at.tzinfo is None:
            raise AssertionError("FinancialStatement.announced_at must be timezone-aware when present")
        for item in statement.items:
            if item.code != item.code.lower() or " " in item.code:
                raise AssertionError(f"StatementItem.code must be canonical snake_case, got {item.code!r}")
            if item.code.isupper():
                raise AssertionError("source field identifiers must not cross the Statement interface")

    second = source.fetch_statements(valid_query)
    if first.items != second.items:
        raise AssertionError("Statement Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("Statement Dataset source must be stable across calls")

    empty = source.fetch_statements(empty_query)
    _assert_dataset_seam(empty)
    validate_statement_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Statement query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Statement Dataset must set complete=True")

    for query, error_type in error_cases:
        try:
            source.fetch_statements(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"StatementSource should raise {error_type.__name__}, "
                f"got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(
                f"StatementSource should raise {error_type.__name__} for {query}"
            )

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(
            f"StatementSource must return Dataset, got {type(dataset).__name__}"
        )
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
