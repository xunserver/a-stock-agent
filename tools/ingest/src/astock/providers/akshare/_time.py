"""Publication-time normalization for AKShare news and event Adapters."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from astock_core.market_data import InvalidSourcePayload

from astock.providers.eastmoney.snapshots import CN_TIMEZONE

_SHANGHAI = ZoneInfo(CN_TIMEZONE)
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
)


def parse_publication_time(
    value: object,
    *,
    field: str,
    warnings: list[str],
    context: str,
) -> datetime:
    if value in (None, ""):
        raise InvalidSourcePayload(f"{field} is missing")
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=_SHANGHAI)
            if value.tzinfo is None
            else value.astimezone(_SHANGHAI)
        )
    if isinstance(value, date):
        warnings.append(
            f"published_at for {context} normalized from date-only {value!s} "
            "to local midnight"
        )
        return datetime.combine(value, time.min, tzinfo=_SHANGHAI)
    text = str(value).strip()
    date_only_text = text.replace("/", "-")
    if len(date_only_text) == 10:
        try:
            day = date.fromisoformat(date_only_text)
        except ValueError:
            pass
        else:
            warnings.append(
                f"published_at for {context} normalized from date-only {text!r} "
                "to local midnight"
            )
            return datetime.combine(day, time.min, tzinfo=_SHANGHAI)
    try:
        parsed_iso = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed_iso = None
    if parsed_iso is not None:
        return (
            parsed_iso.replace(tzinfo=_SHANGHAI)
            if parsed_iso.tzinfo is None
            else parsed_iso.astimezone(_SHANGHAI)
        )
    for fmt in _DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=_SHANGHAI)
        except ValueError:
            continue
    normalized = text.replace("/", "-")
    try:
        day = date.fromisoformat(normalized)
    except ValueError as exc:
        raise InvalidSourcePayload(f"malformed {field}: {value!r}") from exc
    warnings.append(
        f"published_at for {context} normalized from date-only {text!r} to local midnight"
    )
    return datetime.combine(day, time.min, tzinfo=_SHANGHAI)
