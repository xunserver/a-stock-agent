"""Index alias resolution and membership orchestration."""

from __future__ import annotations

from astock.config import index_aliases
from astock.providers.protocols import MembershipSource
from astock.providers.registry import resolve_capability
from astock_core.market_data import (
    CSINDEX_TAXONOMY,
    ClassificationKind,
    MembershipQuery,
    membership_code_name_pairs,
    validate_membership_dataset,
)


def resolve_index_symbol(index: str) -> str:
    aliases = index_aliases()
    key = index.strip().lower()
    if key in aliases:
        return aliases[key]
    code = index.strip()
    if code.isdigit():
        return code.zfill(6)
    raise ValueError(f"未知指数：{index}。可用别名：{', '.join(aliases)}")


def _display_names(source: MembershipSource) -> dict[str, str]:
    getter = getattr(source, "display_names", None)
    if callable(getter):
        return getter()
    return {}


def index_member_tuples(
    index: str,
    *,
    membership_source: MembershipSource | None = None,
) -> tuple[str, list[tuple[str, str]]]:
    """Fetch index constituents as legacy ``(code, name)`` pairs."""
    source = membership_source or resolve_capability("memberships")
    symbol = resolve_index_symbol(index)
    query = MembershipQuery(
        taxonomy=CSINDEX_TAXONOMY,
        classification_id=symbol,
        kind=ClassificationKind.INDEX,
    )
    dataset = validate_membership_dataset(source.fetch_memberships(query), query)
    pairs = membership_code_name_pairs(dataset.items, names=_display_names(source))
    return symbol, pairs
