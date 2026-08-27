"""把 AKShare 行情快照、估值和财报拼成入库用的个股资料。

日更批量走全市场接口；单票同步走个股接口，避免为一只股票拉全市场报表。
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import pandas as pd

from astock import eastmoney
from astock.config import REQUEST_SLEEP_SECONDS
from astock.ingest import _call

logger = logging.getLogger(__name__)

BATCH_MIN_CODES = 8
REPORT_TRIES = 4

PROFILE_VALUE_KEYS = (
    "industry",
    "list_date",
    "total_shares",
    "float_shares",
    "total_mv",
    "float_mv",
    "latest_price",
    "region",
    "pe_dyn",
    "pe_static",
    "pb",
    "volume_ratio",
    "high_limit",
    "low_limit",
    "pre_close",
    "avg_price",
    "outer_vol",
    "inner_vol",
    "eps",
    "bps",
    "roe",
    "revenue",
    "revenue_yoy",
    "net_profit",
    "net_profit_yoy",
    "gross_margin",
    "net_margin",
    "debt_ratio",
)


def secucode(code: str) -> str:
    """AKShare 东财财务接口用的带后缀代码（上海是 .SH）。"""
    if code.startswith(("6", "5", "9")) and not code.startswith("92"):
        return f"{code}.SH"
    if code.startswith(("4", "8", "92")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def report_date_candidates(today: date | None = None) -> list[str]:
    today = today or date.today()
    quarters: list[date] = []
    for year in (today.year, today.year - 1):
        quarters.extend(
            [
                date(year, 3, 31),
                date(year, 6, 30),
                date(year, 9, 30),
                date(year, 12, 31),
            ]
        )
    passed = [item for item in quarters if item <= today]
    passed.sort(reverse=True)
    return [item.strftime("%Y%m%d") for item in passed[:REPORT_TRIES]]


def as_text(value: object) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    text = " ".join(str(value).split())
    if text in {"", "-", "None", "nan", "NaN"}:
        return None
    return text


def as_float(value: object) -> float | None:
    text = as_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def as_list_date(value: object) -> str | None:
    text = as_text(value)
    if text is None:
        return None
    if len(text) >= 10 and text[4] == "-":
        return text[:10]
    digits = "".join(ch for ch in text.split(".")[0] if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return None


def as_code(value: object) -> str | None:
    text = as_text(value)
    if text is None:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return digits[-6:]
    return None


def merge_profile(*parts: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for part in parts:
        for key, value in part.items():
            if value is None or value == "":
                continue
            out[key] = value
    return out


def map_spot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": as_text(row.get("名称")),
        "latest_price": as_float(row.get("最新价")),
        "pre_close": as_float(row.get("昨收")),
        "volume_ratio": as_float(row.get("量比")),
        "pe_dyn": as_float(row.get("市盈率-动态")),
        "pb": as_float(row.get("市净率")),
        "total_mv": as_float(row.get("总市值")),
        "float_mv": as_float(row.get("流通市值")),
    }


def map_yjbb(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": as_text(row.get("股票简称")),
        "industry": as_text(row.get("所处行业")),
        "eps": as_float(row.get("每股收益")),
        "bps": as_float(row.get("每股净资产")),
        "roe": as_float(row.get("净资产收益率")),
        "revenue": as_float(row.get("营业总收入-营业总收入")),
        "revenue_yoy": as_float(row.get("营业总收入-同比增长")),
        "net_profit": as_float(row.get("净利润-净利润")),
        "net_profit_yoy": as_float(row.get("净利润-同比增长")),
        "gross_margin": as_float(row.get("销售毛利率")),
    }


def map_zcfz(row: dict[str, Any]) -> dict[str, Any]:
    return {"debt_ratio": as_float(row.get("资产负债率"))}


def map_bid_ask(items: dict[str, Any]) -> dict[str, Any]:
    return {
        "latest_price": as_float(items.get("最新")),
        "avg_price": as_float(items.get("均价")),
        "pre_close": as_float(items.get("昨收")),
        "high_limit": as_float(items.get("涨停")),
        "low_limit": as_float(items.get("跌停")),
        "volume_ratio": as_float(items.get("量比")),
        "outer_vol": as_float(items.get("外盘")),
        "inner_vol": as_float(items.get("内盘")),
    }


def map_individual_info(items: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": as_text(items.get("股票简称")),
        "industry": as_text(items.get("行业")),
        "list_date": as_list_date(items.get("上市时间")),
        "total_shares": as_float(items.get("总股本")),
        "float_shares": as_float(items.get("流通股")),
        "total_mv": as_float(items.get("总市值")),
        "float_mv": as_float(items.get("流通市值")),
        "latest_price": as_float(items.get("最新")),
    }


def map_financial_indicator(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "eps": as_float(row.get("EPSJB")),
        "bps": as_float(row.get("BPS")),
        "roe": as_float(row.get("ROEJQ")),
        "revenue": as_float(row.get("TOTALOPERATEREVE")),
        "revenue_yoy": as_float(row.get("TOTALOPERATEREVETZ")),
        "net_profit": as_float(row.get("PARENTNETPROFIT")),
        "net_profit_yoy": as_float(row.get("PARENTNETPROFITTZ")),
        "gross_margin": as_float(row.get("XSMLL")),
        "net_margin": as_float(row.get("XSJLL")),
        "debt_ratio": as_float(row.get("ZCFZL")),
    }


def map_value(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "latest_price": as_float(row.get("当日收盘价")),
        "total_mv": as_float(row.get("总市值")),
        "float_mv": as_float(row.get("流通市值")),
        "total_shares": as_float(row.get("总股本")),
        "float_shares": as_float(row.get("流通股本")),
        "pe_dyn": as_float(row.get("PE(TTM)")),
        "pe_static": as_float(row.get("PE(静)")),
        "pb": as_float(row.get("市净率")),
    }


def limit_ratio(code: str, *, is_st: bool = False) -> float:
    if is_st:
        return 0.05
    if code.startswith(("300", "301", "688")):
        return 0.20
    if code.startswith(("4", "8", "92")):
        return 0.30
    return 0.10


def derive_profile(profile: dict[str, Any], code: str, *, is_st: bool = False) -> dict[str, Any]:
    out = dict(profile)
    price = as_float(out.get("latest_price"))
    pre_close = as_float(out.get("pre_close"))
    eps = as_float(out.get("eps"))
    bps = as_float(out.get("bps"))
    revenue = as_float(out.get("revenue"))
    net_profit = as_float(out.get("net_profit"))
    total_mv = as_float(out.get("total_mv"))
    float_mv = as_float(out.get("float_mv"))
    if out.get("pe_static") is None and price and eps:
        out["pe_static"] = price / eps
    if out.get("pb") is None and price and bps:
        out["pb"] = price / bps
    if out.get("net_margin") is None and revenue:
        out["net_margin"] = net_profit / revenue * 100 if net_profit is not None else None
    if out.get("total_shares") is None and price and total_mv:
        out["total_shares"] = total_mv / price
    if out.get("float_shares") is None and price and float_mv:
        out["float_shares"] = float_mv / price
    ratio = limit_ratio(code, is_st=is_st)
    base = pre_close or price
    if out.get("high_limit") is None and base:
        out["high_limit"] = round(base * (1 + ratio), 2)
    if out.get("low_limit") is None and base:
        out["low_limit"] = round(base * (1 - ratio), 2)
    return out


def rows_by_code(frame: pd.DataFrame | None, code_col: str = "代码") -> dict[str, dict[str, Any]]:
    if frame is None or frame.empty:
        return {}
    column = code_col if code_col in frame.columns else "股票代码"
    out: dict[str, dict[str, Any]] = {}
    for rec in frame.to_dict(orient="records"):
        code = as_code(rec.get(column) or rec.get("代码") or rec.get("股票代码"))
        if code:
            out[code] = rec
    return out


def item_map(frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None or frame.empty or "item" not in frame.columns:
        return {}
    value_col = "value" if "value" in frame.columns else frame.columns[1]
    return {str(row["item"]): row[value_col] for row in frame.to_dict(orient="records")}


def fetch_spot_rows() -> dict[str, dict[str, Any]]:
    import akshare as ak

    logger.info("拉取沪深京 A 股快照（估值/昨收/量比）")
    return rows_by_code(_call(ak.stock_zh_a_spot_em))


def fetch_report_rows(
    fetch,
    dates: list[str],
    *,
    wanted: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for report_date in dates:
        missing = None if wanted is None else wanted - set(out)
        if missing is not None and not missing:
            break
        try:
            frame = _call(fetch, date=report_date)
        except Exception as exc:
            logger.warning("报表 %s 拉取失败：%s", report_date, exc)
            continue
        rows = rows_by_code(frame, "股票代码")
        if not rows:
            continue
        added = 0
        for code, row in rows.items():
            if code in out:
                continue
            if wanted is not None and code not in wanted:
                continue
            out[code] = row
            added += 1
        logger.info("报表 %s 写入 %s 只", report_date, added)
    return out


def fetch_bid_ask_items(code: str) -> dict[str, Any]:
    import akshare as ak

    return item_map(_call(ak.stock_bid_ask_em, symbol=code))


def fetch_individual_items(code: str) -> dict[str, Any]:
    import akshare as ak

    return item_map(_call(ak.stock_individual_info_em, symbol=code))


def fetch_financial_row(code: str) -> dict[str, Any]:
    import akshare as ak

    frame = _call(
        ak.stock_financial_analysis_indicator_em,
        symbol=secucode(code),
        indicator="按报告期",
    )
    if frame is None or frame.empty:
        return {}
    return frame.iloc[0].to_dict()


def fetch_value_row(code: str) -> dict[str, Any]:
    import akshare as ak

    frame = _call(ak.stock_value_em, symbol=code)
    if frame is None or frame.empty:
        return {}
    return frame.iloc[-1].to_dict()


def fetch_quote_profile(code: str) -> dict[str, Any]:
    """个股盘口/股本走 curl_cffi。AKShare 的 push2 封装在本机常被断开。"""
    return eastmoney.stock_profile(code)


def _safe_fetch(label: str, code: str, fn) -> dict[str, Any]:
    try:
        return fn(code) or {}
    except Exception as exc:
        logger.warning("%s 失败 %s: %s", label, code, exc)
        return {}


def _quote_from_akshare(code: str) -> dict[str, Any]:
    return merge_profile(
        map_individual_info(_safe_fetch("个股信息", code, fetch_individual_items)),
        map_bid_ask(_safe_fetch("行情报价", code, fetch_bid_ask_items)),
    )


def _quote_profile(code: str) -> dict[str, Any]:
    quote = _safe_fetch("东财资料", code, fetch_quote_profile)
    if quote.get("pre_close") or quote.get("industry") or quote.get("total_shares"):
        return quote
    return merge_profile(quote, _quote_from_akshare(code))


def load_profiles(
    codes: list[str],
    *,
    sleep: float = REQUEST_SLEEP_SECONDS,
    today: date | None = None,
    st_codes: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """拉取 codes 的资料。大批量用全市场接口，少量用个股接口。"""
    wanted = [code.zfill(6) for code in codes if code.strip()]
    if not wanted:
        return {}
    flags = st_codes or set()
    if len(wanted) >= BATCH_MIN_CODES:
        return _load_batch(wanted, sleep=sleep, today=today, st_codes=flags)
    return _load_each(wanted, sleep=sleep, st_codes=flags)


def _is_st(code: str, profile: dict[str, Any], st_codes: set[str]) -> bool:
    name = str(profile.get("name") or "")
    return code in st_codes or "ST" in name


def _load_batch(
    codes: list[str],
    *,
    sleep: float,
    today: date | None,
    st_codes: set[str],
) -> dict[str, dict[str, Any]]:
    import akshare as ak

    wanted = set(codes)
    dates = report_date_candidates(today)
    spot: dict[str, dict[str, Any]] = {}
    yjbb: dict[str, dict[str, Any]] = {}
    zcfz: dict[str, dict[str, Any]] = {}
    try:
        spot = fetch_spot_rows()
    except Exception as exc:
        logger.warning("A 股快照拉取失败：%s", exc)
    try:
        yjbb = fetch_report_rows(ak.stock_yjbb_em, dates, wanted=wanted)
    except Exception as exc:
        logger.warning("业绩报表拉取失败：%s", exc)
    try:
        zcfz = fetch_report_rows(ak.stock_zcfz_em, dates, wanted=wanted)
    except Exception as exc:
        logger.warning("资产负债表拉取失败：%s", exc)

    out: dict[str, dict[str, Any]] = {}
    for i, code in enumerate(codes, start=1):
        quote = _quote_profile(code)
        profile = merge_profile(
            map_spot(spot.get(code) or {}),
            quote,
            map_yjbb(yjbb.get(code) or {}),
            map_zcfz(zcfz.get(code) or {}),
        )
        out[code] = derive_profile(profile, code, is_st=_is_st(code, profile, st_codes))
        if i == 1 or i % 20 == 0 or i == len(codes):
            logger.info("资料拼装 %s/%s  %s %s", i, len(codes), code, out[code].get("name") or "")
        time.sleep(sleep)
    return out


def _load_each(codes: list[str], *, sleep: float, st_codes: set[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i, code in enumerate(codes, start=1):
        quote = _quote_profile(code)
        financial = _safe_fetch("财务指标", code, fetch_financial_row)
        value = _safe_fetch("估值序列", code, fetch_value_row)
        profile = merge_profile(
            quote,
            map_value(value),
            map_financial_indicator(financial),
        )
        out[code] = derive_profile(profile, code, is_st=_is_st(code, profile, st_codes))
        logger.info("个股资料 %s/%s  %s %s", i, len(codes), code, out[code].get("name") or "")
        time.sleep(sleep)
    return out
