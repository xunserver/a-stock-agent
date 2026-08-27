from __future__ import annotations

import pytest

from astock_control.adapters.ingest import INGEST_DIR, quotes_sync_argv, stock_command_argv
from astock_control.protocol import ProtocolError, normalize_codes, normalize_command, normalize_query
from astock_control.queries import handle_query
from astock_core.db import MarketDB
from astock_core.paths import DEFAULT_ADJUST


def test_normalize_codes_accepts_ticker_suffix() -> None:
    assert normalize_codes("000001.SZ") == ["000001"]
    assert normalize_codes(["000001.sz", "600519.SS", "830001.BJ"]) == [
        "000001",
        "600519",
        "830001",
    ]
    with pytest.raises(ProtocolError, match="无效股票代码"):
        normalize_codes("000001.US")


def test_quotes_sync_accepts_codes() -> None:
    cmd = normalize_command({"type": "quotes.sync", "codes": "000001.SZ,600519"})
    assert cmd["type"] == "quotes.sync"
    assert cmd["codes"] == ["000001", "600519"]
    assert cmd["pool"] == "default"


def test_quotes_sync_without_codes_stays_pool_wide() -> None:
    cmd = normalize_command({"type": "quotes.sync", "pool": "hs"})
    assert cmd == {"type": "quotes.sync", "pool": "hs"}


def test_boards_sync_normalize_defaults_and_flags() -> None:
    assert normalize_command({"type": "boards.sync"}) == {
        "type": "boards.sync",
        "pool": "default",
        "kind": "all",
    }
    cmd = normalize_command(
        {"type": "boards.sync", "kind": "concept", "sleep": 0.5, "limit": 2}
    )
    assert cmd == {
        "type": "boards.sync",
        "pool": "default",
        "kind": "concept",
        "sleep": 0.5,
        "limit": 2,
    }
    with pytest.raises(ProtocolError, match="kind"):
        normalize_command({"type": "boards.sync", "kind": "sw"})


def test_beijing_and_shanghai_tickers() -> None:
    assert normalize_command({"type": "analyze.run", "code": "830001"})["ticker"] == "830001.BJ"
    assert normalize_command({"type": "analyze.run", "code": "688111"})["ticker"] == "688111.SS"


def test_quotes_sync_argv_includes_codes() -> None:
    argv = quotes_sync_argv({"type": "quotes.sync", "pool": "default", "codes": ["000001", "600519"]})
    assert argv[argv.index("--codes") + 1] == "000001,600519"
    assert "quotes" in argv and "sync" in argv


def test_stock_sync_command() -> None:
    cmd = normalize_command({"type": "stock.sync", "codes": ["000001.SZ", "600519"]})
    assert cmd["codes"] == ["000001", "600519"]
    argv = stock_command_argv(cmd)
    assert argv[-2:] == ["sync", "000001,600519"]
    with pytest.raises(ProtocolError, match="codes"):
        normalize_command({"type": "stock.sync"})


def test_stock_get_query_shape() -> None:
    query = normalize_query({"type": "stock.get", "code": "000001.SZ"})
    assert query == {"type": "stock.get", "code": "000001"}
    with pytest.raises(ProtocolError, match="恰好"):
        normalize_query({"type": "stock.get", "code": "000001,600519"})
    with pytest.raises(ProtocolError, match="需要 code"):
        normalize_query({"type": "stock.get"})


def test_stocks_list_and_get_include_ticker_and_bars(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行")])
        db.upsert_stock_profile(
            "000001",
            name="平安银行",
            industry="银行",
            region="深圳板块",
            list_date="1991-04-03",
            pe_dyn=8.5,
            pb=0.9,
            roe=12.3,
        )
        db.upsert_bars(
            [
                (
                    "000001",
                    "2026-08-25",
                    10.0,
                    10.5,
                    10.8,
                    9.9,
                    1000.0,
                    1.0,
                    8.0,
                    5.0,
                    0.5,
                    1.2,
                    DEFAULT_ADJUST,
                ),
                (
                    "000001",
                    "2026-08-26",
                    10.5,
                    10.2,
                    10.6,
                    10.1,
                    800.0,
                    0.8,
                    4.0,
                    -2.86,
                    -0.3,
                    0.9,
                    DEFAULT_ADJUST,
                ),
            ]
        )

    listed = handle_query({"type": "stocks.list"})
    assert listed["count"] == 1
    stock = listed["stocks"][0]
    assert stock["code"] == "000001"
    assert stock["ticker"] == "000001.SZ"
    assert stock["last_bar"] == "2026-08-26"

    got = handle_query({"type": "stock.get", "code": "000001"})
    assert got["ticker"] == "000001.SZ"
    assert got["profile"]["name"] == "平安银行"
    assert got["profile"]["industry"] == "银行"
    assert got["profile"]["region"] == "深圳板块"
    assert got["profile"]["pe_dyn"] == 8.5
    assert got["profile"]["pb"] == 0.9
    assert got["profile"]["roe"] == 12.3
    assert got["profile"]["latest_price"] == 10.2
    assert got["pools"] == []
    assert got["latest_bar"]["trade_date"] == "2026-08-26"
    assert [bar["trade_date"] for bar in got["bars"]] == ["2026-08-25", "2026-08-26"]
    assert got["quotes_summary"]["bars"] == 2


def test_stock_get_missing_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("astock_control.queries.DB_PATH", tmp_path / "market.db")
    with pytest.raises(ProtocolError, match="找不到股票"):
        handle_query({"type": "stock.get", "code": "000001"})
