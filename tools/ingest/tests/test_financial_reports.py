from __future__ import annotations

import pandas as pd
import pytest

from astock.profile import (
    fetch_financial_reports,
    fetch_financial_summaries_batch,
    map_batch_report_rows,
    map_financial_report_row,
    report_type_from_yyyymmdd,
    sync_financial_summaries_batch,
)
from astock_core.db import MarketDB


def test_map_financial_report_row() -> None:
    row = map_financial_report_row(
        {
            "REPORT_DATE": "2026-06-30 00:00:00",
            "REPORT_DATE_NAME": "2026中报",
            "NOTICE_DATE": "2026-08-15 00:00:00",
            "EPSJB": 1.24,
            "ROEJQ": 5.22,
            "TOTALOPERATEREVE": 70617000000.0,
            "TOTALOPERATEREVETZ": 1.77,
            "PARENTNETPROFIT": 25696000000.0,
            "PARENTNETPROFITTZ": 3.32,
            "XSMLL": 40.0,
            "XSJLL": 36.38,
            "ZCFZL": 90.9,
        }
    )
    assert row["report_date"] == "2026-06-30"
    assert row["report_type"] == "2026中报"
    assert row["notice_date"] == "2026-08-15"
    assert row["roe"] == 5.22
    assert row["revenue"] == 70617000000.0


def test_fetch_financial_reports_maps_and_sorts(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "REPORT_DATE": "2025-12-31 00:00:00",
                "REPORT_DATE_NAME": "2025年报",
                "NOTICE_DATE": "2026-03-01 00:00:00",
                "EPSJB": 2.0,
                "ROEJQ": 10.0,
                "TOTALOPERATEREVE": 100.0,
                "TOTALOPERATEREVETZ": 5.0,
                "PARENTNETPROFIT": 20.0,
                "PARENTNETPROFITTZ": 8.0,
                "XSMLL": 30.0,
                "XSJLL": 15.0,
                "ZCFZL": 50.0,
            },
            {
                "REPORT_DATE": "2026-06-30 00:00:00",
                "REPORT_DATE_NAME": "2026中报",
                "NOTICE_DATE": "2026-08-15 00:00:00",
                "EPSJB": 1.0,
                "ROEJQ": 5.0,
                "TOTALOPERATEREVE": 60.0,
                "TOTALOPERATEREVETZ": 2.0,
                "PARENTNETPROFIT": 12.0,
                "PARENTNETPROFITTZ": 3.0,
                "XSMLL": 28.0,
                "XSJLL": 14.0,
                "ZCFZL": 48.0,
            },
        ]
    )
    monkeypatch.setattr(
        "astock.profile._call",
        lambda fn, *args, **kwargs: frame,
    )
    rows = fetch_financial_reports("000001")
    assert len(rows) == 2
    assert rows[0]["report_date"] == "2026-06-30"
    assert rows[1]["report_date"] == "2025-12-31"


def test_report_type_from_yyyymmdd() -> None:
    assert report_type_from_yyyymmdd("20250630") == "2025中报"
    assert report_type_from_yyyymmdd("20250331") == "2025一季报"
    assert report_type_from_yyyymmdd("20251231") == "2025年报"


def test_map_batch_report_rows_merges_sources() -> None:
    row = map_batch_report_rows(
        {
            "股票简称": "平安银行",
            "所处行业": "银行",
            "每股收益": "1.2",
            "净资产收益率": "10.5",
            "销售毛利率": "40.0",
            "最新公告日期": "2026-08-20",
        },
        {"资产负债率": "91.2", "公告日期": "2026-08-21"},
        {
            "营业总收入": "1000",
            "净利润": "300",
            "营业总收入同比": "5.0",
            "净利润同比": "8.0",
        },
        report_date_yyyymmdd="20250630",
    )
    assert row is not None
    assert row["report_date"] == "2025-06-30"
    assert row["report_type"] == "2025中报"
    assert row["notice_date"] == "2026-08-21"
    assert row["roe"] == 10.5
    assert row["debt_ratio"] == 91.2
    assert row["revenue"] == 1000.0
    assert row["net_profit"] == 300.0
    assert row["net_margin"] == pytest.approx(30.0)


def test_fetch_financial_summaries_batch(monkeypatch) -> None:
    def fake_call(fn, *args, **kwargs):
        name = getattr(fn, "__name__", "")
        date = kwargs.get("date")
        if name == "stock_yjbb_em":
            return pd.DataFrame(
                [
                    {
                        "股票代码": "000001",
                        "股票简称": "平安银行",
                        "每股收益": "1.0",
                        "净资产收益率": "9.0",
                    },
                    {
                        "股票代码": "000002",
                        "股票简称": "万科A",
                        "每股收益": "0.5",
                        "净资产收益率": "4.0",
                    },
                ]
            )
        if name == "stock_zcfz_em":
            return pd.DataFrame(
                [
                    {"股票代码": "000001", "资产负债率": "90.0", "公告日期": "2026-08-01"},
                    {"股票代码": "000002", "资产负债率": "75.0", "公告日期": "2026-08-02"},
                ]
            )
        if name == "stock_lrb_em":
            return pd.DataFrame(
                [
                    {
                        "股票代码": "000001",
                        "营业总收入": "100",
                        "净利润": "20",
                        "营业总收入同比": "1.0",
                        "净利润同比": "2.0",
                    },
                    {
                        "股票代码": "000002",
                        "营业总收入": "200",
                        "净利润": "10",
                        "营业总收入同比": "3.0",
                        "净利润同比": "4.0",
                    },
                ]
            )
        raise AssertionError(f"unexpected call {name} {date}")

    monkeypatch.setattr("astock.profile._call", fake_call)
    out = fetch_financial_summaries_batch(
        ["000001", "000002"],
        periods=1,
        today=__import__("datetime").date(2026, 8, 28),
    )
    assert set(out) == {"000001", "000002"}
    assert len(out["000001"]) == 1
    assert out["000001"][0]["report_date"] == "2026-06-30"
    assert out["000001"][0]["debt_ratio"] == 90.0
    assert out["000001"][0]["net_profit"] == 20.0


def test_sync_financial_summaries_batch(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "astock.profile.fetch_financial_summaries_batch",
        lambda codes, **kwargs: {
            "000001": [
                {
                    "report_date": "2026-06-30",
                    "report_type": "2026中报",
                    "roe": 5.0,
                    "revenue": 1.0,
                }
            ]
        },
    )
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        result = sync_financial_summaries_batch(db, ["000001"])
        assert result == {"financial_stocks": 1, "financial_rows": 1}
        assert db.financial_report_count("000001") == 1


def test_financial_reports_db_roundtrip(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        count = db.upsert_financial_reports(
            "000001",
            [
                {
                    "report_date": "2026-06-30",
                    "report_type": "2026中报",
                    "notice_date": "2026-08-15",
                    "roe": 5.22,
                    "revenue": 1.0,
                    "revenue_yoy": 1.7,
                    "net_profit": 2.0,
                    "net_profit_yoy": 3.3,
                    "gross_margin": 40.0,
                    "debt_ratio": 90.0,
                },
                {
                    "report_date": "2025-12-31",
                    "report_type": "2025年报",
                    "roe": 10.0,
                    "revenue": 2.0,
                },
            ],
        )
        assert count == 2
        assert db.financial_report_count("000001") == 2
        assert db.latest_financial_report_date("000001") == "2026-06-30"
        listed = db.list_financial_reports("000001", limit=1)
        assert len(listed) == 1
        assert listed[0]["report_type"] == "2026中报"
        assert listed[0]["roe"] == 5.22
