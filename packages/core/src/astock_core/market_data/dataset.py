"""Dataset envelope returned by every market-data capability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Generic, TypeVar

T = TypeVar("T")


def _require_tuple(value: object, *, field: str) -> None:
    if type(value) is not tuple:
        raise ValueError(f"Dataset.{field} must be a tuple, got {type(value).__name__}")


@dataclass(frozen=True)
class Dataset(Generic[T]):
    items: tuple[T, ...]
    source: str
    fetched_at: datetime
    coverage_start: date | None = None
    coverage_end: date | None = None
    complete: bool = True
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_tuple(self.items, field="items")
        _require_tuple(self.warnings, field="warnings")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("Dataset.source must be a non-empty registry key")
        if self.source != self.source.strip():
            raise ValueError("Dataset.source must not include surrounding whitespace")
        if self.fetched_at.tzinfo is None:
            raise ValueError("Dataset.fetched_at must be timezone-aware")
        if (
            self.coverage_start is not None
            and self.coverage_end is not None
            and self.coverage_end < self.coverage_start
        ):
            raise ValueError("Dataset coverage_end must be on or after coverage_start")
        for warning in self.warnings:
            if not isinstance(warning, str) or not warning:
                raise ValueError("Dataset.warnings must contain non-empty strings")
