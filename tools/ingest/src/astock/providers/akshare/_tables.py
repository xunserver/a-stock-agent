"""Helpers for turning AKShare DataFrames into plain records."""

from __future__ import annotations

import math
from datetime import date, datetime

from astock_core.market_data import InvalidSourcePayload


def records_from_source_table(payload: object) -> list[dict[str, object]]:
    """Convert an AKShare table to a list of JSON-like dicts.

    pandas missing values become ``None`` before any Standard Record is built.
    """
    if payload is None:
        return []
    if isinstance(payload, list):
        return [_plain_record(item, index=index) for index, item in enumerate(payload)]
    if _is_empty_frame(payload):
        return []
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        try:
            raw_records = to_dict(orient="records")
        except TypeError as exc:
            raise InvalidSourcePayload("AKShare table could not be converted to records") from exc
        if not isinstance(raw_records, list):
            raise InvalidSourcePayload("AKShare table records must be a list")
        return [_plain_record(item, index=index) for index, item in enumerate(raw_records)]
    raise InvalidSourcePayload(
        f"AKShare payload must be a table or list of records, got {type(payload).__name__}"
    )


def lookup_column(record: dict[str, object], names: tuple[str, ...]) -> object:
    for name in names:
        if name in record:
            return record[name]
    return None


def has_any_column(records: list[dict[str, object]], names: tuple[str, ...]) -> bool:
    if not records:
        return False
    sample = records[0]
    return any(name in sample for name in names)


def as_date(value: object, *, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        converted = to_pydatetime()
        if isinstance(converted, datetime):
            return converted.date()
        if isinstance(converted, date):
            return converted
    date_method = getattr(value, "date", None)
    if callable(date_method) and not isinstance(value, date):
        try:
            converted = date_method()
        except (TypeError, ValueError):
            converted = None
        if isinstance(converted, date) and not isinstance(converted, datetime):
            return converted
    if value in (None, ""):
        raise InvalidSourcePayload(f"{field} is missing")
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise InvalidSourcePayload(f"malformed {field}: {value!r}") from exc


def as_optional_date(value: object, *, field: str) -> date | None:
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    if text in {"nan", "none", "nat"}:
        return None
    return as_date(value, field=field)


def as_optional_float(value: object, *, field: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidSourcePayload(f"{field} is not numeric: {value!r}") from exc
    if isinstance(value, bool) or not math.isfinite(number):
        return None
    return number


def as_required_float(value: object, *, field: str) -> float:
    number = as_optional_float(value, field=field)
    if number is None:
        raise InvalidSourcePayload(f"{field} is missing")
    return number


def _is_empty_frame(payload: object) -> bool:
    empty = getattr(payload, "empty", None)
    return empty is True


def _plain_record(item: object, *, index: int) -> dict[str, object]:
    if not isinstance(item, dict):
        raise InvalidSourcePayload(f"record at index {index} must be a mapping")
    return {str(key): _plain_value(value) for key, value in item.items()}


def _plain_value(value: object) -> object:
    if value is None:
        return None
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except (TypeError, ValueError, ImportError):
        pass
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
