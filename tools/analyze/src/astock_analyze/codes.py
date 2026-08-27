"""Map A-share codes to Yahoo tickers used by TradingAgents."""

from __future__ import annotations

_SUFFIXES = (".SS", ".SZ", ".BJ")
_SHANGHAI_PREFIXES = frozenset("695")


class CodeError(ValueError):
    """Illegal stock code."""


def parse_a_share(raw: str) -> tuple[str, str]:
    """Return ``(code, yahoo_ticker)``.

    * ``6xxxxx`` / ``9xxxxx`` / ``5xxxxx`` → ``.SS``
    * other 6-digit codes → ``.SZ``
    * already suffixed ``.SS`` / ``.SZ`` / ``.BJ`` is kept as-is
    """
    text = str(raw).strip().upper()
    if not text:
        raise CodeError("股票代码不能为空")

    for suffix in _SUFFIXES:
        if text.endswith(suffix):
            body = text[: -len(suffix)]
            code = _six_digits(body, raw)
            return code, f"{code}{suffix}"

    code = _six_digits(text, raw)
    if code[0] in _SHANGHAI_PREFIXES:
        return code, f"{code}.SS"
    return code, f"{code}.SZ"


def to_yahoo_ticker(raw: str) -> str:
    """Map an A-share code or ticker to a Yahoo symbol."""
    return parse_a_share(raw)[1]


def _six_digits(text: str, original: str) -> str:
    if text.isdigit() and 1 <= len(text) <= 6:
        return text.zfill(6)
    raise CodeError(
        f"股票代码不合法: {original}。需要 6 位数字，或带 .SS/.SZ/.BJ 后缀。"
    )
