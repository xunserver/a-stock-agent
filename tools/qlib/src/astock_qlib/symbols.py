from __future__ import annotations


WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(10)),
    *(f"LPT{i}" for i in range(10)),
}


def to_qlib_symbol(code: str) -> str:
    """把库内代码转成 Qlib 的 SH/SZ/BJ 代码。"""
    raw = str(code).strip()
    lower = raw.lower()
    if lower.startswith(("sh", "sz", "bj")) and len(lower) >= 8:
        return lower[:2].upper() + lower[2:]
    digits = "".join(ch for ch in raw if ch.isdigit()).zfill(6)
    if digits.startswith(("6", "9")):
        return f"SH{digits}"
    if digits.startswith(("0", "1", "2", "3")):
        return f"SZ{digits}"
    if digits.startswith(("4", "8")):
        return f"BJ{digits}"
    raise ValueError(f"无法识别交易所: {code}")


def code_to_fname(symbol: str) -> str:
    """与 Qlib dump_bin 一致：Windows 保留名加前缀。"""
    if str(symbol).upper() in WINDOWS_RESERVED:
        return f"_qlib_{symbol}"
    return symbol
