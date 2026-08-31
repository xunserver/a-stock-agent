"""Fixture loaders and fixture-backed Adapter factories for contract tests."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from astock.providers.akshare.bars import AkshareBarAdapter
from astock.providers.akshare.calendar import AkshareCalendarAdapter
from astock.providers.akshare.fundamentals import AkshareFundamentalAdapter
from astock.providers.akshare.instruments import AkshareInstrumentAdapter
from astock.providers.akshare.snapshots import AkshareSnapshotAdapter
from astock.providers.akshare.statements import AkshareStatementAdapter
from astock.providers.eastmoney.bars import EastmoneyBarAdapter
from astock.providers.eastmoney.snapshots import EastmoneySnapshotAdapter
from astock_core.market_data import (
    Adjustment,
    AssetType,
    BarInterval,
    BarQuery,
    CalendarQuery,
    FinancialSheet,
    FundamentalQuery,
    InstrumentId,
    InstrumentNotFound,
    InstrumentQuery,
    SnapshotQuery,
    StatementQuery,
    ValuationQuery,
    from_legacy_symbol,
)

from .fakes import maotai, ping_an

FIXTURES = Path(__file__).parent / "fixtures"
FIXED_NOW = datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


def load_json(*parts: str) -> object:
    return json.loads(FIXTURES.joinpath(*parts).read_text(encoding="utf-8"))


def hs300() -> InstrumentId:
    return InstrumentId(country="CN", exchange="XSHG", symbol="000300")


def valid_bar_query() -> BarQuery:
    return BarQuery(
        instruments=(maotai(),),
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=BarInterval.D1,
        adjustment=Adjustment.QFQ,
    )


def empty_bar_query() -> BarQuery:
    return BarQuery(
        instruments=(maotai(),),
        start=date(2020, 1, 1),
        end=date(2020, 1, 2),
        interval=BarInterval.D1,
        adjustment=Adjustment.QFQ,
    )


def unknown_bar_query() -> BarQuery:
    return BarQuery(
        instruments=(ping_an(),),
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=BarInterval.D1,
        adjustment=Adjustment.QFQ,
    )


def valid_calendar_query() -> CalendarQuery:
    return CalendarQuery(market_id="cn_a", start=date(2026, 8, 1), end=date(2026, 8, 31))


def empty_calendar_query() -> CalendarQuery:
    return CalendarQuery(market_id="cn_a", start=date(2020, 1, 1), end=date(2020, 1, 2))


def unknown_calendar_query() -> CalendarQuery:
    return CalendarQuery(market_id="us", start=date(2026, 8, 1), end=date(2026, 8, 31))


def eastmoney_get_json(
    *,
    stock: str = "stock_klines_valid.json",
    index: str = "index_klines_valid.json",
    weekly: str = "stock_klines_weekly.json",
    monthly: str = "stock_klines_monthly.json",
    empty: str = "stock_klines_empty.json",
):
    stock_payload = load_json("eastmoney", stock)
    index_payload = load_json("eastmoney", index)
    weekly_payload = load_json("eastmoney", weekly)
    monthly_payload = load_json("eastmoney", monthly)
    empty_payload = load_json("eastmoney", empty)

    def get_json(url: str, params: dict[str, str], timeout: float) -> object:
        secid = params["secid"]
        klt = params["klt"]
        beg = params["beg"]
        if secid == "0.000001":
            return {"data": None}
        if beg.startswith("2020"):
            return empty_payload
        if secid.endswith(".000300") or secid == "1.000300":
            return index_payload
        if klt == "102":
            return weekly_payload
        if klt == "103":
            return monthly_payload
        return stock_payload

    return get_json


def make_eastmoney_bar_adapter(**overrides) -> EastmoneyBarAdapter:
    kwargs = {
        "get_json": eastmoney_get_json(),
        "timeout": 20.0,
        "retries": 1,
        "sleep": lambda _seconds: None,
        "clock": lambda: FIXED_NOW,
    }
    kwargs.update(overrides)
    return EastmoneyBarAdapter(**kwargs)


def make_akshare_bar_adapter(
    *,
    hist_tx_rows: object | None = None,
    daily_rows: object | None = None,
    hist_rows: object | None = None,
    weekly_rows: object | None = None,
    monthly_rows: object | None = None,
    **overrides,
) -> AkshareBarAdapter:
    tx_rows = hist_tx_rows if hist_tx_rows is not None else load_json("akshare", "hist_tx_valid.json")
    sina_rows = daily_rows if daily_rows is not None else []
    em_rows = hist_rows if hist_rows is not None else load_json("akshare", "hist_em_valid.json")
    em_weekly = weekly_rows if weekly_rows is not None else load_json("akshare", "hist_em_weekly.json")
    em_monthly = monthly_rows if monthly_rows is not None else load_json("akshare", "hist_em_monthly.json")

    def hist_tx(symbol: str, start_date: str, end_date: str, adjust: str, timeout: float | None = None):
        if symbol == "000001":
            raise InstrumentNotFound("CN.XSHE.000001")
        if start_date.startswith("2020"):
            return []
        return tx_rows

    def daily(symbol: str, adjust: str, start_date: str | None = None, end_date: str | None = None, timeout=None):
        if symbol.endswith("000001"):
            raise InstrumentNotFound("CN.XSHE.000001")
        if start_date and str(start_date).startswith("2020"):
            return []
        return sina_rows

    def hist(symbol: str, period: str, start_date: str, end_date: str, adjust: str, timeout=None):
        if symbol == "000001":
            raise InstrumentNotFound("CN.XSHE.000001")
        if start_date.startswith("2020"):
            return []
        if period == "weekly":
            return em_weekly
        if period == "monthly":
            return em_monthly
        return em_rows

    kwargs = {
        "hist_tx": hist_tx,
        "daily": daily,
        "hist": hist,
        "timeout": 20.0,
        "retries": 1,
        "sleep": lambda _seconds: None,
        "clock": lambda: FIXED_NOW,
    }
    kwargs.update(overrides)
    return AkshareBarAdapter(**kwargs)


def make_akshare_calendar_adapter(rows: object | None = None, **overrides) -> AkshareCalendarAdapter:
    payload = rows if rows is not None else load_json("akshare", "calendar_valid.json")

    def trade_date_hist():
        return payload

    kwargs = {
        "trade_date_hist": trade_date_hist,
        "timeout": 20.0,
        "retries": 1,
        "sleep": lambda _seconds: None,
        "clock": lambda: FIXED_NOW,
    }
    kwargs.update(overrides)
    return AkshareCalendarAdapter(**kwargs)


def pufa() -> InstrumentId:
    return InstrumentId(country="CN", exchange="XSHG", symbol="600000")


def valid_instrument_query() -> InstrumentQuery:
    return InstrumentQuery(asset_types=(AssetType.STOCK,))


def empty_instrument_query() -> InstrumentQuery:
    return InstrumentQuery(asset_types=(AssetType.ETF,))


def valid_snapshot_query() -> SnapshotQuery:
    return SnapshotQuery(instruments=(maotai(),))


def empty_snapshot_query() -> SnapshotQuery:
    return SnapshotQuery(instruments=(pufa(),))


def unknown_snapshot_query() -> SnapshotQuery:
    return SnapshotQuery(instruments=(ping_an(),))


def valid_valuation_query() -> ValuationQuery:
    return ValuationQuery(instruments=(maotai(),))


def empty_valuation_query() -> ValuationQuery:
    return ValuationQuery(instruments=(pufa(),))


def unknown_valuation_query() -> ValuationQuery:
    return ValuationQuery(instruments=(ping_an(),))


def eastmoney_quote_get_json(
    *,
    valid: str = "stock_quote_valid.json",
    empty: str = "stock_quote_empty.json",
    malformed: str | None = None,
):
    valid_payload = load_json("eastmoney", valid)
    empty_payload = load_json("eastmoney", empty)
    malformed_payload = load_json("eastmoney", malformed) if malformed else None

    def get_json(url: str, params: dict[str, str], timeout: float) -> object:
        secid = params["secid"]
        if malformed_payload is not None:
            return malformed_payload
        if secid.endswith(".000001"):
            return {"data": None}
        if secid.endswith(".600000"):
            return empty_payload
        return valid_payload

    return get_json


def make_eastmoney_snapshot_adapter(**overrides) -> EastmoneySnapshotAdapter:
    kwargs = {
        "get_json": eastmoney_quote_get_json(),
        "timeout": 20.0,
        "retries": 1,
        "sleep": lambda _seconds: None,
        "clock": lambda: FIXED_NOW,
        "pause": 0.0,
    }
    kwargs.update(overrides)
    return EastmoneySnapshotAdapter(**kwargs)


def make_akshare_instrument_adapter(rows: object | None = None, **overrides) -> AkshareInstrumentAdapter:
    payload = rows if rows is not None else load_json("akshare", "spot_valid.json")

    kwargs = {
        "spot": lambda: payload,
        "timeout": 20.0,
        "retries": 1,
        "sleep": lambda _seconds: None,
        "clock": lambda: FIXED_NOW,
    }
    kwargs.update(overrides)
    return AkshareInstrumentAdapter(**kwargs)


def make_akshare_snapshot_adapter(**overrides) -> AkshareSnapshotAdapter:
    spot_rows = load_json("akshare", "spot_valid.json")
    bid_rows = load_json("akshare", "bid_ask_valid.json")
    info_rows = load_json("akshare", "individual_valid.json")
    value_rows = load_json("akshare", "value_valid.json")
    st_rows = load_json("akshare", "st_empty.json")
    tfp_rows = load_json("akshare", "tfp_empty.json")

    def bid_ask(symbol: str):
        if symbol == "000001":
            raise InstrumentNotFound("CN.XSHE.000001")
        if symbol == "600000":
            return []
        return bid_rows

    def individual(symbol: str):
        if symbol == "000001":
            raise InstrumentNotFound("CN.XSHE.000001")
        if symbol == "600000":
            return []
        return info_rows

    def value(symbol: str):
        if symbol == "000001":
            raise InstrumentNotFound("CN.XSHE.000001")
        if symbol == "600000":
            return []
        return value_rows

    kwargs = {
        "spot": lambda: spot_rows,
        "bid_ask": bid_ask,
        "individual": individual,
        "value": value,
        "st_list": lambda: st_rows,
        "tfp": lambda _date: tfp_rows,
        "timeout": 20.0,
        "retries": 1,
        "sleep": lambda _seconds: None,
        "clock": lambda: FIXED_NOW,
        "pause": 0.0,
    }
    kwargs.update(overrides)
    return AkshareSnapshotAdapter(**kwargs)


def valid_fundamental_query() -> FundamentalQuery:
    return FundamentalQuery(
        instruments=(ping_an(),),
        start=date(2025, 1, 1),
        end=date(2026, 12, 31),
    )


def empty_fundamental_query() -> FundamentalQuery:
    return FundamentalQuery(
        instruments=(ping_an(),),
        start=date(2020, 1, 1),
        end=date(2020, 3, 31),
    )


def valid_batch_fundamental_query() -> FundamentalQuery:
    return FundamentalQuery(
        instruments=(ping_an(), from_legacy_symbol("000002")),
        start=date(2026, 6, 30),
        end=date(2026, 6, 30),
    )


def valid_statement_query() -> StatementQuery:
    return StatementQuery(
        instruments=(ping_an(),),
        sheet=FinancialSheet.PROFIT,
        start=date(2025, 1, 1),
        end=date(2026, 12, 31),
    )


def empty_statement_query() -> StatementQuery:
    return StatementQuery(
        instruments=(ping_an(),),
        sheet=FinancialSheet.PROFIT,
        start=date(2020, 1, 1),
        end=date(2020, 3, 31),
    )


def make_akshare_fundamental_adapter_single(
    rows: object | None = None, **overrides
) -> AkshareFundamentalAdapter:
    payload = rows if rows is not None else load_json("akshare", "fundamentals_indicator_valid.json")

    def indicator(symbol: str, indicator: str):
        if symbol.startswith("600"):
            return []
        return payload

    kwargs = {
        "indicator": indicator,
        "batch_min_instruments": 8,
        "timeout": 20.0,
        "retries": 1,
        "sleep": lambda _seconds: None,
        "clock": lambda: FIXED_NOW,
        "today": lambda: date(2026, 8, 31),
    }
    kwargs.update(overrides)
    return AkshareFundamentalAdapter(**kwargs)


def make_akshare_fundamental_adapter_batch(**overrides) -> AkshareFundamentalAdapter:
    yjbb_rows = load_json("akshare", "fundamentals_yjbb.json")
    zcfz_rows = load_json("akshare", "fundamentals_zcfz.json")
    lrb_rows = load_json("akshare", "fundamentals_lrb.json")

    def yjbb(date_value: str):
        return yjbb_rows if date_value == "20260630" else []

    def zcfz(date_value: str):
        return zcfz_rows if date_value == "20260630" else []

    def lrb(date_value: str):
        return lrb_rows if date_value == "20260630" else []

    kwargs = {
        "yjbb": yjbb,
        "zcfz": zcfz,
        "lrb": lrb,
        "batch_min_instruments": 1,
        "timeout": 20.0,
        "retries": 1,
        "sleep": lambda _seconds: None,
        "clock": lambda: FIXED_NOW,
        "today": lambda: date(2026, 8, 31),
    }
    kwargs.update(overrides)
    return AkshareFundamentalAdapter(**kwargs)


def make_akshare_statement_adapter(
    *,
    profit_rows: object | None = None,
    balance_rows: object | None = None,
    cashflow_rows: object | None = None,
    **overrides,
) -> AkshareStatementAdapter:
    profit_payload = (
        profit_rows if profit_rows is not None else load_json("akshare", "statements_profit_valid.json")
    )
    balance_payload = (
        balance_rows if balance_rows is not None else load_json("akshare", "statements_balance_valid.json")
    )
    cashflow_payload = (
        cashflow_rows
        if cashflow_rows is not None
        else load_json("akshare", "statements_cashflow_valid.json")
    )

    def profit(symbol: str):
        if symbol.endswith("600519"):
            return []
        return profit_payload

    def balance(symbol: str):
        if symbol.endswith("600519"):
            return []
        return balance_payload

    def cashflow(symbol: str):
        if symbol.endswith("600519"):
            return []
        return cashflow_payload

    kwargs = {
        "profit": profit,
        "balance": balance,
        "cashflow": cashflow,
        "timeout": 20.0,
        "retries": 1,
        "sleep": lambda _seconds: None,
        "clock": lambda: FIXED_NOW,
    }
    kwargs.update(overrides)
    return AkshareStatementAdapter(**kwargs)
