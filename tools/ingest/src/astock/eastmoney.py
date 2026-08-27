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


def stock_daily(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
    timeout: float = 20,
) -> pd.DataFrame:
    market = "1" if symbol.startswith("6") else "0"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": PERIOD["daily"],
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
        "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
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
    name = data.get("f58")
    return {
        "code": str(data.get("f57") or symbol).zfill(6),
        "name": str(name).strip() if name else symbol,
        "industry": data.get("f127") or None,
        "list_date": list_date,
        "total_shares": _maybe_float(data.get("f84")),
        "float_shares": _maybe_float(data.get("f85")),
        "total_mv": _maybe_float(data.get("f116")),
        "float_mv": _maybe_float(data.get("f117")),
        "latest_price": _maybe_float(data.get("f43")),
    }


def _maybe_float(value: object) -> float | None:
    if value in (None, "", "-", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
