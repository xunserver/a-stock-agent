from __future__ import annotations

import pytest

from astock_analyze.codes import CodeError, parse_a_share, to_yahoo_ticker


@pytest.mark.parametrize(
    ("raw", "code", "ticker"),
    [
        ("000001", "000001", "000001.SZ"),
        ("600519", "600519", "600519.SS"),
        ("300750", "300750", "300750.SZ"),
        ("688111", "688111", "688111.SS"),
        ("000001.SZ", "000001", "000001.SZ"),
        ("600519.SS", "600519", "600519.SS"),
        ("000001.BJ", "000001", "000001.BJ"),
        ("501018", "501018", "501018.SS"),
        ("900948", "900948", "900948.SS"),
    ],
)
def test_code_mapping(raw: str, code: str, ticker: str) -> None:
    assert parse_a_share(raw) == (code, ticker)
    assert to_yahoo_ticker(raw) == ticker


def test_lowercase_suffix_kept() -> None:
    assert to_yahoo_ticker("000001.sz") == "000001.SZ"


def test_illegal_code() -> None:
    with pytest.raises(CodeError, match="不合法"):
        to_yahoo_ticker("abc")
    with pytest.raises(CodeError, match="不合法"):
        to_yahoo_ticker("000001.US")
    with pytest.raises(CodeError, match="不能为空"):
        to_yahoo_ticker("  ")
