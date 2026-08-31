"""Taxonomy keys for Classification and Membership identity."""

from __future__ import annotations

EASTMONEY_TAXONOMY = "eastmoney"
CSINDEX_TAXONOMY = "csindex"

DEFAULT_BOARD_TAXONOMY = EASTMONEY_TAXONOMY

_LEGACY_BOARD_SOURCES: dict[str, str] = {
    "em": EASTMONEY_TAXONOMY,
}


def normalize_board_taxonomy(source: str | None) -> str | None:
    """Map legacy board source values to canonical taxonomy keys."""
    if source is None:
        return None
    return _LEGACY_BOARD_SOURCES.get(source, source)


def classification_identity(taxonomy: str, classification_id: str) -> tuple[str, str]:
    """Return the stable Classification natural key."""
    if not taxonomy:
        raise ValueError("taxonomy must be a non-empty string")
    if not classification_id:
        raise ValueError("classification_id must be a non-empty string")
    return (taxonomy, classification_id)
