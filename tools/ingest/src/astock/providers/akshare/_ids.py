"""Stable identity helpers for AKShare news and event Adapters."""

from __future__ import annotations

import hashlib
from datetime import datetime
from collections.abc import Iterable

from astock_core.market_data import InstrumentId


def stable_record_id(
    *,
    source: str,
    instrument_id: InstrumentId,
    published_at: datetime,
    title: str,
    url: str | None,
    source_id: str | None = None,
    identity_parts: Iterable[object] = (),
) -> str:
    if source_id:
        cleaned = str(source_id).strip()
        if cleaned:
            return cleaned
    payload = "|".join(
        (
            source,
            instrument_id.value,
            published_at.isoformat(),
            title,
            url or "",
            *(str(part) for part in identity_parts),
        )
    )
    return hashlib.sha256(payload.encode()).hexdigest()
