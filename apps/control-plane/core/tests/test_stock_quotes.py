from __future__ import annotations

import pytest

from astock_control.adapters.events import events_argv
from astock_control.adapters.ingest import INGEST_DIR, quotes_sync_argv, stock_command_argv
from astock_control.adapters.news import news_argv
from astock_control.protocol import ProtocolError, normalize_codes, normalize_command
from astock_control.queries import (
    pool_list_query,
    status_query,
    stock_events_query,
    stock_get_query,
    stock_news_query,
    stocks_list_query,
)
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

    listed = stocks_list_query()
    assert listed["count"] == 1
    stock = listed["stocks"][0]
    assert stock["code"] == "000001"
    assert stock["ticker"] == "000001.SZ"
    assert stock["last_bar"] == "2026-08-26"

    got = stock_get_query("000001")
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


def test_stock_get_includes_financial_reports(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行")])
        db.upsert_financial_reports(
            "000001",
            [
                {
                    "report_date": "2026-06-30",
                    "report_type": "2026中报",
                    "roe": 5.22,
                    "revenue": 100.0,
                }
            ],
        )

    got = stock_get_query("000001")
    assert got["financial_summary"]["count"] == 1
    assert got["financial_summary"]["latest_report_date"] == "2026-06-30"
    assert got["financial_reports"][0]["report_type"] == "2026中报"


def test_stock_get_missing_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("astock_control.queries.DB_PATH", tmp_path / "market.db")
    with pytest.raises(ProtocolError, match="找不到股票"):
        stock_get_query("000001")


def test_stock_news_argv() -> None:
    argv = news_argv("000001", limit=10)
    assert argv[-6:] == ["stock", "news", "000001", "--limit", "10", "--json"]
    assert str(INGEST_DIR) in argv


def test_stock_events_argv() -> None:
    argv = events_argv("600000", "research", limit=15)
    assert argv[-8:] == [
        "stock",
        "events",
        "600000",
        "--kind",
        "research",
        "--limit",
        "15",
        "--json",
    ]
    assert str(INGEST_DIR) in argv


def test_stock_news_query_returns_items(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    monkeypatch.setattr(
        "astock_control.queries.fetch_stock_news",
        lambda code, limit=20: [
            {
                "title": "平安银行公告",
                "summary": "摘要",
                "published_at": "2026-08-27 10:00:00",
                "source": "证券时报",
                "url": "http://finance.eastmoney.com/a/xxx.html",
            }
        ],
    )
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行")])
    got = stock_news_query("000001")
    assert got["ticker"] == "000001.SZ"
    assert got["count"] == 1
    assert got["error"] is None
    assert got["news"][0]["title"] == "平安银行公告"


def test_stock_news_fetch_failure_degrades(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    def boom(_code: str, limit: int = 20) -> list:
        raise RuntimeError("boom")

    monkeypatch.setattr("astock_control.queries.fetch_stock_news", boom)
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行")])
    got = stock_news_query("000001")
    assert got["news"] == []
    assert got["count"] == 0
    assert got["error"] == "新闻暂时不可用"


def test_stock_news_missing_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("astock_control.queries.DB_PATH", tmp_path / "market.db")
    with pytest.raises(ProtocolError, match="找不到股票"):
        stock_news_query("000001")


def test_stock_events_query_returns_items(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    monkeypatch.setattr(
        "astock_control.queries.fetch_stock_events",
        lambda code, kind, limit=50: [
            {
                "title": "半年报",
                "summary": "",
                "published_at": "2026-08-01",
                "source": "财务报告",
                "url": "http://example.com/notice",
            }
        ],
    )
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行")])
    got = stock_events_query("000001", kind="notices", limit=20)
    assert got["ticker"] == "000001.SZ"
    assert got["kind"] == "notices"
    assert got["count"] == 1
    assert got["error"] is None
    assert got["events"][0]["title"] == "半年报"


def test_stock_events_fetch_failure_degrades(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)

    def boom(_code: str, _kind: str, limit: int = 50) -> list:
        raise RuntimeError("boom")

    monkeypatch.setattr("astock_control.queries.fetch_stock_events", boom)
    with MarketDB(db_path) as db:
        db.add_stocks([("600000", "浦发银行")])
    got = stock_events_query("600000", kind="holder_changes", limit=20)
    assert got["events"] == []
    assert got["count"] == 0
    assert got["error"] == "股东变更暂时不可用"


def test_stock_events_missing_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("astock_control.queries.DB_PATH", tmp_path / "market.db")
    with pytest.raises(ProtocolError, match="找不到股票"):
        stock_events_query("000001", kind="notices", limit=10)


def _bar(code: str, trade_date: str) -> tuple:
    return (
        code,
        trade_date,
        10.0,
        10.0,
        10.0,
        10.0,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        DEFAULT_ADJUST,
    )


def test_status_and_members_need_sync(tmp_path, monkeypatch) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    # 固定在交易日 8 点后，as_of = 2026-08-28
    frozen = datetime(2026, 8, 28, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    monkeypatch.setattr(
        "astock_core.session.market_now",
        lambda now=None, *, policy=None: frozen if now is None else (
            now if now.tzinfo else now.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        ),
    )

    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    with MarketDB(db_path) as db:
        db.replace_calendar(["2026-08-26", "2026-08-28"])
        db.add_stocks(
            [("000001", "平安银行"), ("000002", "万科A"), ("600519", "贵州茅台")]
        )
        db.add_pool_members(
            "default",
            [("000001", "平安银行"), ("000002", "万科A"), ("600519", "贵州茅台")],
        )
        db.upsert_bars([_bar("000001", "2026-08-26"), _bar("600519", "2026-08-28")])

    status = status_query("default")
    assert status["trade_date"] == "2026-08-28"
    assert status["need_sync"] == 2
    assert status["need_full"] == 1
    assert status["need_fill"] == 1
    assert status["already_current"] == 1

    listed = pool_list_query("default")
    by_code = {item["code"]: item for item in listed["members"]}
    assert by_code["000002"]["quote_plan"] == "full"
    assert by_code["000002"]["needs_sync"] is True
    assert by_code["000001"]["quote_plan"] == "fill"
    assert by_code["000001"]["needs_sync"] is True
    assert by_code["600519"]["quote_plan"] == "current"
    assert by_code["600519"]["needs_sync"] is False


def test_status_before_session_open_uses_prior_trade_date(tmp_path, monkeypatch) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    frozen = datetime(2026, 8, 28, 7, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    monkeypatch.setattr(
        "astock_core.session.market_now",
        lambda now=None, *, policy=None: frozen if now is None else (
            now if now.tzinfo else now.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        ),
    )

    db_path = tmp_path / "market.db"
    monkeypatch.setattr("astock_control.queries.DB_PATH", db_path)
    with MarketDB(db_path) as db:
        db.replace_calendar(["2026-08-26", "2026-08-28"])
        db.add_stocks([("000001", "平安银行"), ("600519", "贵州茅台")])
        db.add_pool_members(
            "default",
            [("000001", "平安银行"), ("600519", "贵州茅台")],
        )
        db.upsert_bars([_bar("000001", "2026-08-26"), _bar("600519", "2026-08-26")])

    status = status_query("default")
    assert status["trade_date"] == "2026-08-26"
    assert status["need_sync"] == 0
    assert status["already_current"] == 2
