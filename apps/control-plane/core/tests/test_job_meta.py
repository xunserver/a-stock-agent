from __future__ import annotations

import pytest

from astock_control.protocol import (
    DEFAULT_TIMEOUT_IMMEDIATE,
    DEFAULT_TIMEOUT_INDEX,
    DEFAULT_TIMEOUT_LONG,
    ProtocolError,
    build_job_name,
    normalize_command,
    parse_command_submission,
    resolve_job_timeout,
)


def test_parse_command_submission_strips_timeout() -> None:
    payload, background, timeout = parse_command_submission(
        {"type": "quotes.sync", "pool": "default", "background": True, "timeout_seconds": 30}
    )
    assert payload == {"type": "quotes.sync", "pool": "default"}
    assert background is True
    assert timeout == 30


def test_parse_command_submission_rejects_bad_timeout() -> None:
    with pytest.raises(ProtocolError, match="正整数"):
        parse_command_submission({"type": "quotes.sync", "timeout_seconds": True})
    with pytest.raises(ProtocolError, match="正整数"):
        parse_command_submission({"type": "quotes.sync", "timeout_seconds": -1})


def test_resolve_job_timeout_defaults() -> None:
    assert resolve_job_timeout({"type": "quotes.sync"}, requested=None) == DEFAULT_TIMEOUT_LONG
    assert resolve_job_timeout({"type": "analyze.run"}, requested=None) == DEFAULT_TIMEOUT_LONG
    assert (
        resolve_job_timeout({"type": "pool.add", "index": "hs300"}, requested=None)
        == DEFAULT_TIMEOUT_INDEX
    )
    assert (
        resolve_job_timeout({"type": "pool.add", "codes": ["000001"]}, requested=None)
        == DEFAULT_TIMEOUT_IMMEDIATE
    )
    assert resolve_job_timeout({"type": "quotes.sync"}, requested=12) == 12


def test_build_job_name_for_quotes_and_stock() -> None:
    assert (
        build_job_name(normalize_command({"type": "quotes.sync", "pool": "hs"}))
        == "同步行情 · 全部（池 hs）"
    )
    assert (
        build_job_name(normalize_command({"type": "quotes.sync", "codes": "600519,1"}))
        == "同步行情 · 600519, 000001"
    )
    assert (
        build_job_name(
            normalize_command({"type": "quotes.sync", "codes": "1,2,3,4"})
        )
        == "同步行情 · 4 只"
    )
    assert (
        build_job_name(normalize_command({"type": "stock.sync", "codes": ["600519"]}))
        == "同步股票 · 600519"
    )
    assert (
        build_job_name(normalize_command({"type": "boards.sync", "kind": "industry"}))
        == "同步板块 · 行业"
    )
    assert (
        build_job_name(
            normalize_command({"type": "analyze.run", "code": "600519", "date": "2026-08-27"})
        )
        == "运行 AI 分析 · 600519 · 2026-08-27"
    )
