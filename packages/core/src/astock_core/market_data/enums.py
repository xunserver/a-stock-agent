"""Closed vocabularies for Standard Records and queries."""

from __future__ import annotations

from enum import StrEnum


class AssetType(StrEnum):
    STOCK = "stock"
    INDEX = "index"
    ETF = "etf"


class BarInterval(StrEnum):
    D1 = "1d"
    W1 = "1w"
    M1 = "1mo"


class Adjustment(StrEnum):
    RAW = "raw"
    QFQ = "qfq"
    HFQ = "hfq"


class FinancialPeriodType(StrEnum):
    Q1 = "Q1"
    H1 = "H1"
    Q3 = "Q3"
    FY = "FY"


class FinancialSheet(StrEnum):
    BALANCE = "balance"
    PROFIT = "profit"
    CASHFLOW = "cashflow"


class ClassificationKind(StrEnum):
    INDUSTRY = "industry"
    CONCEPT = "concept"
    INDEX = "index"


class StatementUnit(StrEnum):
    CNY = "CNY"
    SHARES = "shares"
    PER_SHARE = "per_share"
    PERCENT = "percent"
    TEXT = "text"


class EventKind(StrEnum):
    NOTICE = "notice"
    RESEARCH_REPORT = "research_report"
    BLOCK_TRADE = "block_trade"
    HOLDER_CHANGE = "holder_change"
