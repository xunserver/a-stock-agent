"""东方财富行情：用 curl_cffi 模拟浏览器，避免本机 requests 被断开。"""

from __future__ import annotations

import pandas as pd
from curl_cffi import requests as creq

KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
ADJUST = {"qfq": "1", "hfq": "2", "": "0"}
PERIOD = {"daily": "101", "weekly": "102", "monthly": "103"}
INDEX_MARKET = {"sz": "0", "sh": "1", "csi": "2", "bj": "0"}


def _get(url: str, params: dict, timeout: float = 20):
    response = creq.get(url, params=params, timeout=timeout, impersonate="chrome")
    response.raise_for_status()
    return response


def stock_kline(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
    period: str = "daily",
    timeout: float = 20,
) -> pd.DataFrame:
    if period not in PERIOD:
        raise ValueError(f"不支持的 K 线周期: {period}")
    market = "1" if symbol.startswith("6") else "0"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": PERIOD[period],
        "fqt": ADJUST[adjust],
        "secid": f"{market}.{symbol}",
        "beg": start_date,
        "end": end_date,
    }
    payload = _get(KLINE_URL, params, timeout=timeout).json()
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    if not klines:
        return pd.DataFrame()
    rows = [item.split(",") for item in klines]
    frame = pd.DataFrame(rows)
    frame = frame.iloc[:, :11]
    frame.columns = [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "涨跌幅",
        "涨跌额",
        "换手率",
    ]
    frame["股票代码"] = symbol
    for col in ("开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["日期"] = pd.to_datetime(frame["日期"], errors="coerce").dt.date
    return frame[
        [
            "日期",
            "股票代码",
            "开盘",
            "收盘",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "振幅",
            "涨跌幅",
            "涨跌额",
            "换手率",
        ]
    ]


def stock_daily(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
    timeout: float = 20,
) -> pd.DataFrame:
    return stock_kline(
        symbol,
        start_date,
        end_date,
        adjust=adjust,
        period="daily",
        timeout=timeout,
    )


def index_daily(symbol: str, start_date: str, end_date: str, timeout: float = 20) -> pd.DataFrame:
    if symbol.startswith("sz"):
        secid = f"{INDEX_MARKET['sz']}.{symbol[2:]}"
    elif symbol.startswith("sh"):
        secid = f"{INDEX_MARKET['sh']}.{symbol[2:]}"
    elif symbol.startswith("csi"):
        secid = f"{INDEX_MARKET['csi']}.{symbol[3:]}"
    elif symbol.startswith("bj"):
        secid = f"{INDEX_MARKET['bj']}.{symbol[2:]}"
    else:
        return pd.DataFrame()
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "klt": "101",
        "fqt": "0",
        "beg": start_date,
        "end": end_date,
    }
    payload = _get(KLINE_URL, params, timeout=timeout).json()
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    if not klines:
        return pd.DataFrame()
    frame = pd.DataFrame([item.split(",") for item in klines])
    frame = frame.iloc[:, :7]
    frame.columns = ["date", "open", "close", "high", "low", "volume", "amount"]
    for col in ("open", "close", "high", "low", "volume", "amount"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def stock_profile(symbol: str, timeout: float = 20) -> dict:
    market = "1" if symbol.startswith("6") else "0"
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": ",".join(
            [
                "f43",
                "f44",
                "f45",
                "f46",
                "f47",
                "f48",
                "f49",
                "f50",
                "f51",
                "f52",
                "f55",
                "f57",
                "f58",
                "f60",
                "f71",
                "f84",
                "f85",
                "f92",
                "f116",
                "f117",
                "f127",
                "f128",
                "f161",
                "f162",
                "f163",
                "f167",
                "f168",
                "f173",
                "f183",
                "f184",
                "f185",
                "f186",
                "f187",
                "f188",
                "f189",
            ]
        ),
        "secid": f"{market}.{symbol}",
    }
    payload = _get(
        "https://push2.eastmoney.com/api/qt/stock/get",
        params,
        timeout=timeout,
    ).json()
    data = payload.get("data") or {}
    if not data:
        raise RuntimeError(f"个股资料为空 {symbol}")
    list_raw = data.get("f189")
    list_date = None
    if list_raw not in (None, "", "-", "None"):
        digits = str(list_raw).split(".")[0]
        if digits.isdigit() and len(digits) == 8:
            list_date = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    name = _clean_name(data.get("f58"), symbol)
    return {
        "code": str(data.get("f57") or symbol).zfill(6),
        "name": name,
        "industry": _maybe_text(data.get("f127")),
        "region": _maybe_text(data.get("f128")),
        "list_date": list_date,
        "total_shares": _maybe_float(data.get("f84")),
        "float_shares": _maybe_float(data.get("f85")),
        "total_mv": _maybe_float(data.get("f116")),
        "float_mv": _maybe_float(data.get("f117")),
        "latest_price": _maybe_float(data.get("f43")),
        "pre_close": _maybe_float(data.get("f60")),
        "avg_price": _maybe_float(data.get("f71")),
        "high_limit": _maybe_float(data.get("f51")),
        "low_limit": _maybe_float(data.get("f52")),
        "volume_ratio": _maybe_float(data.get("f50")),
        "outer_vol": _maybe_float(data.get("f49")),
        "inner_vol": _maybe_float(data.get("f161")),
        "pe_dyn": _maybe_float(data.get("f162")),
        "pe_static": _maybe_float(data.get("f163")),
        "pb": _maybe_float(data.get("f167")),
        "eps": _maybe_float(data.get("f55")),
        "bps": _maybe_float(data.get("f92")),
        "roe": _maybe_float(data.get("f173")),
        "revenue": _maybe_float(data.get("f183")),
        "revenue_yoy": _maybe_float(data.get("f184")),
        "net_profit_yoy": _maybe_float(data.get("f185")),
        "gross_margin": _maybe_float(data.get("f186")),
        "net_margin": _maybe_float(data.get("f187")),
        "debt_ratio": _maybe_float(data.get("f188")),
    }


def _clean_name(value: object, fallback: str) -> str:
    text = " ".join(str(value).split()) if value not in (None, "", "-", "None") else ""
    return text or fallback


def _maybe_text(value: object) -> str | None:
    if value in (None, "", "-", "None"):
        return None
    text = " ".join(str(value).split())
    return text or None


def _maybe_float(value: object) -> float | None:
    if value in (None, "", "-", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
