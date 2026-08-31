"""Historical-safety helpers for Membership records.

Current-source snapshots may omit effective dates. They describe present state
and must not be treated as historical truth for backtests or as-of queries.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from astock_core.market_data.errors import UnsupportedQuery
from astock_core.market_data.models import Membership
from astock_core.market_data.queries import MembershipQuery


def is_historically_safe(membership: Membership) -> bool:
    """Return whether ``membership`` carries an effective start date."""
    return membership.effective_from is not None


def historically_safe_memberships(
    memberships: Sequence[Membership],
) -> tuple[Membership, ...]:
    """Return only Memberships that are safe for historical or as-of research."""
    return tuple(item for item in memberships if is_historically_safe(item))


def reject_undated_as_of_query(
    query: MembershipQuery,
    memberships: Sequence[Membership],
) -> None:
    """Reject as-of membership queries when only undated snapshots exist."""
    if query.as_of is None:
        return
    if any(not is_historically_safe(item) for item in memberships):
        raise UnsupportedQuery(
            "Membership as_of queries require effective dates; "
            "current snapshots without effective_from are display-only"
        )


def memberships_effective_on(
    memberships: Sequence[Membership],
    as_of: date,
) -> tuple[Membership, ...]:
    """Filter dated memberships to those effective on ``as_of``."""
    selected: list[Membership] = []
    for item in memberships:
        if item.effective_from is None:
            continue
        if item.effective_from > as_of:
            continue
        if item.effective_to is not None and item.effective_to < as_of:
            continue
        selected.append(item)
    return tuple(selected)
