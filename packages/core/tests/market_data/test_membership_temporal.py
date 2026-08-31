from __future__ import annotations

from datetime import date

import pytest

from astock_core.market_data import (
    CSINDEX_TAXONOMY,
    Membership,
    MembershipQuery,
    UnsupportedQuery,
    from_legacy_symbol,
    is_historically_safe,
    historically_safe_memberships,
    memberships_effective_on,
    reject_undated_as_of_query,
    validate_membership_dataset,
)


def _membership(*, effective_from: date | None = None) -> Membership:
    return Membership(
        classification_id="000300",
        taxonomy=CSINDEX_TAXONOMY,
        instrument_id=from_legacy_symbol("600519"),
        effective_from=effective_from,
    )


def test_undated_membership_is_not_historically_safe() -> None:
    current = _membership()
    dated = _membership(effective_from=date(2024, 1, 1))
    assert is_historically_safe(current) is False
    assert is_historically_safe(dated) is True
    assert historically_safe_memberships((current, dated)) == (dated,)


def test_validate_membership_dataset_rejects_undated_as_of() -> None:
    from astock_core.market_data import Dataset
    from datetime import datetime, timezone

    dataset = Dataset(
        items=(_membership(),),
        source="memory",
        fetched_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )
    query = MembershipQuery(
        taxonomy=CSINDEX_TAXONOMY,
        classification_id="000300",
        as_of=date(2024, 6, 30),
    )
    with pytest.raises(UnsupportedQuery):
        validate_membership_dataset(dataset, query)


def test_memberships_effective_on_filters_dated_rows() -> None:
    rows = (
        _membership(effective_from=date(2024, 1, 1)),
        Membership(
            classification_id="000300",
            taxonomy=CSINDEX_TAXONOMY,
            instrument_id=from_legacy_symbol("000001"),
            effective_from=date(2025, 1, 1),
            effective_to=date(2025, 12, 31),
        ),
    )
    assert memberships_effective_on(rows, date(2024, 6, 30)) == (rows[0],)
    with pytest.raises(UnsupportedQuery):
        reject_undated_as_of_query(
            MembershipQuery(taxonomy=CSINDEX_TAXONOMY, as_of=date(2024, 6, 30)),
            (_membership(), *rows),
        )


def test_membership_validation_handles_mixed_dated_and_current_rows() -> None:
    from astock_core.market_data import Dataset
    from datetime import datetime, timezone

    current = _membership()
    dated = _membership(effective_from=date(2024, 1, 1))
    dataset = Dataset(
        items=(current, dated),
        source="memory",
        fetched_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )
    validate_membership_dataset(
        dataset,
        MembershipQuery(taxonomy=CSINDEX_TAXONOMY, classification_id="000300"),
    )
