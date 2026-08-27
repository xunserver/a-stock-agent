from __future__ import annotations

from datetime import date

import pandas as pd

from astock.profile import (
    as_list_date,
    derive_profile,
    item_map,
    limit_ratio,
    load_profiles,
    map_bid_ask,
    map_financial_indicator,
    map_individual_info,
    map_spot,
    map_value,
    map_yjbb,
    map_zcfz,
    merge_profile,
    report_date_candidates,
    rows_by_code,
    secucode,
)


def test_secucode_market_suffix() -> None:
    assert secucode("000408") == "000408.SZ"
    assert secucode("600519") == "600519.SH"
    assert secucode("688111") == "688111.SH"
    assert secucode("830001") == "830001.BJ"
    assert secucode("920001") == "920001.BJ"


def test_report_dates_are_recent_quarters() -> None:
    dates = report_date_candidates(date(2026, 8, 26))
    assert dates[0] == "20260630"
    assert "20260331" in dates
    assert "20251231" in dates


def test_spot_and_yjbb_map_missing_ui_fields() -> None:
    spot = map_spot(
        {
            "名称": "藏格矿业",
            "最新价": 79.29,
            "昨收": 75.72,
            "量比": 1.8,
            "市盈率-动态": 22.1,
            "市净率": 4.3,
            "总市值": 1.2e11,
            "流通市值": 8e10,
        }
    )
    yjbb = map_yjbb(
        {
            "股票简称": "藏格矿业",
            "所处行业": "化学原料",
            "每股收益": 2.15,
            "每股净资产": 18.4,
            "净资产收益率": 12.3,
            "营业总收入-营业总收入": 1.1e10,
            "营业总收入-同比增长": 8.5,
            "净利润-净利润": 2.2e9,
            "净利润-同比增长": 15.0,
            "销售毛利率": 42.0,
        }
    )
    zcfz = map_zcfz({"资产负债率": 28.6})
    merged = merge_profile(yjbb, zcfz, spot)
    assert merged["pre_close"] == 75.72
    assert merged["volume_ratio"] == 1.8
    assert merged["pe_dyn"] == 22.1
    assert merged["pb"] == 4.3
    assert merged["eps"] == 2.15
    assert merged["roe"] == 12.3
    assert merged["revenue"] == 1.1e10
    assert merged["debt_ratio"] == 28.6
    assert merged["industry"] == "化学原料"


def test_bid_ask_and_info_map_quote_capital() -> None:
    bid = map_bid_ask(
        {
            "最新": 79.29,
            "均价": 78.5,
            "昨收": 75.72,
            "涨停": 83.29,
            "跌停": 68.15,
            "量比": 1.8,
            "外盘": 213400,
            "内盘": 180000,
        }
    )
    info = map_individual_info(
        {
            "股票简称": "藏格矿业",
            "行业": "化学原料",
            "上市时间": 19960715.0,
            "总股本": 1.5e9,
            "流通股": 1.1e9,
            "总市值": 1.2e11,
            "流通市值": 8e10,
            "最新": 79.29,
        }
    )
    assert bid["avg_price"] == 78.5
    assert bid["high_limit"] == 83.29
    assert bid["outer_vol"] == 213400
    assert info["list_date"] == "1996-07-15"
    assert info["total_shares"] == 1.5e9


def test_financial_indicator_and_value_map() -> None:
    financial = map_financial_indicator(
        {
            "EPSJB": 2.15,
            "BPS": 18.4,
            "ROEJQ": 12.3,
            "TOTALOPERATEREVE": 1.1e10,
            "TOTALOPERATEREVETZ": 8.5,
            "PARENTNETPROFIT": 2.2e9,
            "PARENTNETPROFITTZ": 15.0,
            "XSMLL": 42.0,
            "XSJLL": 20.0,
            "ZCFZL": 28.6,
        }
    )
    value = map_value(
        {
            "当日收盘价": 79.29,
            "总市值": 1.2e11,
            "流通市值": 8e10,
            "总股本": 1.5e9,
            "流通股本": 1.1e9,
            "PE(TTM)": 22.1,
            "PE(静)": 36.9,
            "市净率": 4.3,
        }
    )
    assert financial["net_margin"] == 20.0
    assert financial["debt_ratio"] == 28.6
    assert value["pe_static"] == 36.9


def test_derive_fills_pe_pb_margin_limits_and_shares() -> None:
    derived = derive_profile(
        {
            "latest_price": 10.0,
            "pre_close": 10.0,
            "eps": 2.0,
            "bps": 5.0,
            "revenue": 100.0,
            "net_profit": 20.0,
            "total_mv": 1000.0,
            "float_mv": 800.0,
        },
        "000001",
    )
    assert derived["pe_static"] == 5.0
    assert derived["pb"] == 2.0
    assert derived["net_margin"] == 20.0
    assert derived["total_shares"] == 100.0
    assert derived["high_limit"] == 11.0
    assert derived["low_limit"] == 9.0
    assert limit_ratio("300001") == 0.20
    assert limit_ratio("000001", is_st=True) == 0.05


def test_merge_skips_empty_and_keeps_later() -> None:
    merged = merge_profile(
        {"pe_dyn": 10.0, "industry": "旧"},
        {"pe_dyn": None, "industry": "新", "pb": 2.0},
    )
    assert merged["pe_dyn"] == 10.0
    assert merged["industry"] == "新"
    assert merged["pb"] == 2.0


def test_list_date_and_frame_helpers() -> None:
    assert as_list_date("19910403") == "1991-04-03"
    assert as_list_date(19910403.0) == "1991-04-03"
    frame = pd.DataFrame([{"代码": "408", "昨收": 10.0}, {"代码": "000408", "昨收": 11.0}])
    rows = rows_by_code(frame)
    assert rows["000408"]["昨收"] == 11.0
    items = item_map(pd.DataFrame([{"item": "均价", "value": 8.5}]))
    assert items["均价"] == 8.5


def test_load_profiles_single_code_merges_akshare(monkeypatch) -> None:
    monkeypatch.setattr("astock.profile.time.sleep", lambda _s: None)
    monkeypatch.setattr(
        "astock.profile.fetch_quote_profile",
        lambda _code: {
            "name": "平安银行",
            "industry": "银行",
            "list_date": "1991-04-03",
            "latest_price": 10.5,
            "pre_close": 10.0,
            "avg_price": 10.2,
            "high_limit": 11.0,
            "low_limit": 9.0,
            "volume_ratio": 1.2,
            "outer_vol": 1000,
            "inner_vol": 800,
            "total_shares": 1.9e10,
            "float_shares": 1.9e10,
            "total_mv": 2e11,
            "float_mv": 2e11,
        },
    )
    monkeypatch.setattr(
        "astock.profile.fetch_financial_row",
        lambda _code: {
            "EPSJB": 2.0,
            "BPS": 15.0,
            "ROEJQ": 11.0,
            "TOTALOPERATEREVE": 1e11,
            "TOTALOPERATEREVETZ": 5.0,
            "PARENTNETPROFIT": 2e10,
            "PARENTNETPROFITTZ": 8.0,
            "XSMLL": 40.0,
            "XSJLL": 20.0,
            "ZCFZL": 90.0,
        },
    )
    monkeypatch.setattr(
        "astock.profile.fetch_value_row",
        lambda _code: {"PE(TTM)": 5.2, "PE(静)": 5.0, "市净率": 0.7},
    )
    got = load_profiles(["000001"], sleep=0)
    profile = got["000001"]
    assert profile["name"] == "平安银行"
    assert profile["pre_close"] == 10.0
    assert profile["avg_price"] == 10.2
    assert profile["high_limit"] == 11.0
    assert profile["pe_static"] == 5.0
    assert profile["roe"] == 11.0
    assert profile["net_margin"] == 20.0
    assert profile["debt_ratio"] == 90.0
    assert profile["list_date"] == "1991-04-03"
