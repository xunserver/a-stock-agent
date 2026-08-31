"""Instrument identity and A-share exchange inference."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_EXCHANGES = frozenset({"XSHG", "XSHE", "BSE"})
COUNTRY_CN = "CN"

_BSE_FIRST_DIGITS = frozenset({"4", "8"})
_SHANGHAI_FIRST_DIGITS = frozenset({"5", "6", "9"})
_SHENZHEN_FIRST_DIGITS = frozenset({"0", "1", "2", "3"})


class InstrumentIdError(ValueError):
    """Raised when an Instrument identity is malformed or unsupported."""


def _require_six_digit_symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not symbol.isdigit() or len(symbol) != 6:
        raise InstrumentIdError(
            f"A-share symbol must be a six-digit string, got {symbol!r}"
        )
    return symbol


def infer_a_share_exchange(symbol: str) -> str:
    """Infer the v1 MIC exchange from a six-digit A-share symbol.

    Beijing prefixes ``4``, ``8``, and ``92`` are handled explicitly so that
    ``92xxxx`` is not classified as a Shanghai ``9xxxx`` B-share.
    """
    normalized = _require_six_digit_symbol(symbol)
    if normalized.startswith("92") or normalized[0] in _BSE_FIRST_DIGITS:
        return "BSE"
    if normalized[0] in _SHANGHAI_FIRST_DIGITS:
        return "XSHG"
    if normalized[0] in _SHENZHEN_FIRST_DIGITS:
        return "XSHE"
    raise InstrumentIdError(
        f"unsupported A-share symbol prefix for {normalized!r}"
    )


def from_legacy_symbol(symbol: str, *, country: str = COUNTRY_CN) -> InstrumentId:
    """Convert a legacy six-digit symbol to an exchange-qualified InstrumentId."""
    normalized = _require_six_digit_symbol(symbol)
    return InstrumentId(
        country=country,
        exchange=infer_a_share_exchange(normalized),
        symbol=normalized,
    )


def to_legacy_symbol(instrument_id: InstrumentId) -> str:
    """Return the six-digit symbol used by existing persistence and HTTP DTOs."""
    return instrument_id.symbol


@dataclass(frozen=True, order=True)
class InstrumentId:
    country: str
    exchange: str
    symbol: str

    def __post_init__(self) -> None:
        if not self.country or not self.country.isascii() or not self.country.isalpha():
            raise InstrumentIdError(f"invalid country code: {self.country!r}")
        if self.country != self.country.upper():
            raise InstrumentIdError(
                f"country must be uppercase, got {self.country!r}"
            )
        if self.exchange not in SUPPORTED_EXCHANGES:
            raise InstrumentIdError(
                f"unsupported exchange {self.exchange!r}; "
                f"v1 supports {sorted(SUPPORTED_EXCHANGES)}"
            )
        _require_six_digit_symbol(self.symbol)

    @property
    def value(self) -> str:
        return f"{self.country}.{self.exchange}.{self.symbol}"

    @classmethod
    def parse(cls, value: str) -> InstrumentId:
        if not isinstance(value, str) or not value:
            raise InstrumentIdError(f"InstrumentId value must be a non-empty string, got {value!r}")
        parts = value.split(".")
        if len(parts) != 3:
            raise InstrumentIdError(
                f"InstrumentId must be '{{country}}.{{exchange}}.{{symbol}}', got {value!r}"
            )
        country, exchange, symbol = parts
        return cls(country=country, exchange=exchange, symbol=symbol)
