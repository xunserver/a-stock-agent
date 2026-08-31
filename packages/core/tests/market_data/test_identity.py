from __future__ import annotations

import pytest

from astock_core.market_data import (
    Adjustment,
    AssetType,
    BarInterval,
    ClassificationKind,
    FinancialPeriodType,
    FinancialSheet,
    InstrumentId,
    InstrumentIdError,
    from_legacy_symbol,
    infer_a_share_exchange,
    to_legacy_symbol,
)


def test_instrument_id_formats_and_round_trips() -> None:
    instrument_id = InstrumentId.parse("CN.XSHG.600519")
    assert instrument_id.country == "CN"
    assert instrument_id.exchange == "XSHG"
    assert instrument_id.symbol == "600519"
    assert instrument_id.value == "CN.XSHG.600519"
    assert InstrumentId.parse(instrument_id.value) == instrument_id


def test_instrument_id_orders_by_value_components() -> None:
    shenzhen = InstrumentId.parse("CN.XSHE.000001")
    shanghai = InstrumentId.parse("CN.XSHG.600519")
    beijing = InstrumentId.parse("CN.BSE.830001")
    ordered = tuple(sorted((shanghai, beijing, shenzhen)))
    assert ordered == (beijing, shenzhen, shanghai)
    assert [item.value for item in ordered] == sorted(item.value for item in ordered)


def test_legacy_six_digit_conversion_uses_named_exchange_inference() -> None:
    assert from_legacy_symbol("600519") == InstrumentId("CN", "XSHG", "600519")
    assert from_legacy_symbol("000001") == InstrumentId("CN", "XSHE", "000001")
    assert from_legacy_symbol("300750") == InstrumentId("CN", "XSHE", "300750")
    assert from_legacy_symbol("510300") == InstrumentId("CN", "XSHG", "510300")
    assert to_legacy_symbol(from_legacy_symbol("600519")) == "600519"


@pytest.mark.parametrize(
    ("symbol", "exchange"),
    [
        ("430047", "BSE"),
        ("830001", "BSE"),
        ("920001", "BSE"),
        ("900901", "XSHG"),
        ("688001", "XSHG"),
        ("159915", "XSHE"),
        ("200625", "XSHE"),
    ],
)
def test_infer_a_share_exchange_handles_beijing_prefixes(symbol: str, exchange: str) -> None:
    assert infer_a_share_exchange(symbol) == exchange
    assert from_legacy_symbol(symbol).exchange == exchange


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "CN.XSHG",
        "CN.XSHG.600519.extra",
        "CN.NASDAQ.AAPL",
        "CN.XSHG.60051",
        "CN.XSHG.6005190",
        "CN.XSHG.ABC123",
        "600519",
        "cn.xshg.600519",
    ],
)
def test_malformed_and_unsupported_instrument_ids_raise(raw: str) -> None:
    with pytest.raises(InstrumentIdError):
        InstrumentId.parse(raw)


@pytest.mark.parametrize("symbol", ["", "7", "700001", "92", "A60051", "60051"])
def test_legacy_and_inference_reject_malformed_symbols(symbol: str) -> None:
    with pytest.raises(InstrumentIdError):
        infer_a_share_exchange(symbol)
    with pytest.raises(InstrumentIdError):
        from_legacy_symbol(symbol)


def test_instrument_id_constructor_rejects_unsupported_exchange() -> None:
    with pytest.raises(InstrumentIdError):
        InstrumentId("CN", "NASDAQ", "AAPL")


def test_v1_enums_use_specification_values() -> None:
    assert AssetType.STOCK == "stock"
    assert AssetType.INDEX == "index"
    assert AssetType.ETF == "etf"
    assert BarInterval.D1 == "1d"
    assert BarInterval.W1 == "1w"
    assert BarInterval.M1 == "1mo"
    assert Adjustment.RAW == "raw"
    assert Adjustment.QFQ == "qfq"
    assert Adjustment.HFQ == "hfq"
    assert tuple(FinancialPeriodType) == (
        FinancialPeriodType.Q1,
        FinancialPeriodType.H1,
        FinancialPeriodType.Q3,
        FinancialPeriodType.FY,
    )
    assert tuple(item.value for item in FinancialSheet) == ("balance", "profit", "cashflow")
    assert tuple(item.value for item in ClassificationKind) == (
        "industry",
        "concept",
        "index",
    )
