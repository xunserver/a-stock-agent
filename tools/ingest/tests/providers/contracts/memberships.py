"""Reusable Membership capability contract."""

from __future__ import annotations

from astock_core.market_data import (
    Dataset,
    InvalidSourcePayload,
    MarketDataError,
    UnsupportedQuery,
    reject_vendor_types,
    validate_membership_dataset,
)

from astock.providers.protocols import MembershipSource


def assert_membership_source_contract(
    source: MembershipSource,
    *,
    valid_query,
    empty_query,
    undated_as_of_query=None,
    error_cases: tuple[tuple[object, type[MarketDataError]], ...] = (),
) -> Dataset:
    first = source.fetch_memberships(valid_query)
    _assert_dataset_seam(first)
    validate_membership_dataset(first, valid_query)
    if not first.items:
        raise AssertionError("valid Membership query must return at least one Membership")

    second = source.fetch_memberships(valid_query)
    if first.items != second.items:
        raise AssertionError("Membership Dataset items must be deterministic across calls")
    if first.source != second.source:
        raise AssertionError("Membership Dataset source must be stable across calls")

    keys = {item.natural_key for item in first.items}
    if len(keys) != len(first.items):
        raise AssertionError("Membership natural keys must be unique within a Dataset")

    empty = source.fetch_memberships(empty_query)
    _assert_dataset_seam(empty)
    validate_membership_dataset(empty, empty_query)
    if empty.items:
        raise AssertionError("empty Membership query must return a successful empty Dataset")
    if empty.complete is not True:
        raise AssertionError("conclusive empty Membership Dataset must set complete=True")

    if undated_as_of_query is not None:
        try:
            source.fetch_memberships(undated_as_of_query)
        except UnsupportedQuery:
            pass
        except Exception as exc:
            raise AssertionError(
                f"undated as_of Membership query should raise UnsupportedQuery, "
                f"got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(
                "undated as_of Membership query must raise UnsupportedQuery"
            )

    for query, error_type in error_cases:
        try:
            source.fetch_memberships(query)
        except error_type:
            pass
        except Exception as exc:
            raise AssertionError(
                f"MembershipSource should raise {error_type.__name__}, "
                f"got {type(exc).__name__}: {exc}"
            ) from exc
        else:
            raise AssertionError(
                f"MembershipSource should raise {error_type.__name__} for {query}"
            )

    return first


def _assert_dataset_seam(dataset: object) -> None:
    if type(dataset) is not Dataset:
        raise AssertionError(
            f"MembershipSource must return Dataset, got {type(dataset).__name__}"
        )
    reject_vendor_types(dataset, field="dataset")
    if dataset.fetched_at.tzinfo is None:
        raise InvalidSourcePayload("fetched_at must be timezone-aware")
    for index, item in enumerate(dataset.items):
        reject_vendor_types(item, field=f"items[{index}]")
