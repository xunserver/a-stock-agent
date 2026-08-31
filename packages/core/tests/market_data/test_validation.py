from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from astock_core.market_data import (
    Adjustment,
    AssetType,
    Bar,
    BarInterval,
    BarQuery,
    CalendarQuery,
    Dataset,
    Instrument,
    InstrumentProfile,
    InstrumentQuery,
    InvalidSourcePayload,
    QuoteSnapshot,
    SnapshotQuery,
    TradingDay,
    ValuationQuery,
    ValuationSnapshot,
    from_legacy_symbol,
    require_aware_datetime,
    require_finite,
    require_inclusive_range,
    validate_bar,
    validate_bar_dataset,
    validate_calendar_dataset,
    validate_instrument_dataset,
    validate_quote_snapshot_dataset,
    validate_valuation_dataset,
)


def _id(symbol: str = "600519"):
    return from_legacy_symbol(symbol)


def _aware() -> datetime:
    return datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


def _bar(**overrides: object) -> Bar:
    values: dict[str, object] = dict(
        instrument_id=_id(),
        trade_date=date(2026, 8, 28),
        interval=BarInterval.D1,
        adjustment=Adjustment.QFQ,
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=1_000_000.0,
        amount=10_500_000.0,
        turnover_pct=1.25,
        adjustment_factor=1.0,
    )
    values.update(overrides)
    return Bar(**values)  # type: ignore[arg-type]


def _query(**overrides: object) -> BarQuery:
    values: dict[str, object] = dict(
        instruments=(_id(),),
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        interval=BarInterval.D1,
        adjustment=Adjustment.QFQ,
    )
    values.update(overrides)
    return BarQuery(**values)  # type: ignore[arg-type]


def _dataset(items: tuple[Bar, ...], **overrides: object) -> Dataset[Bar]:
    values: dict[str, object] = dict(
        items=items,
        source="memory",
        fetched_at=_aware(),
        coverage_start=date(2026, 8, 1),
        coverage_end=date(2026, 8, 31),
        complete=True,
    )
    values.update(overrides)
    return Dataset(**values)  # type: ignore[arg-type]


def test_require_finite_rejects_nan_and_infinity() -> None:
    assert require_finite(1.25, field="turnover_pct") == 1.25
    with pytest.raises(InvalidSourcePayload, match="finite"):
        require_finite(float("nan"), field="open")
    with pytest.raises(InvalidSourcePayload, match="finite"):
        require_finite(float("inf"), field="high")


def test_require_aware_datetime_and_inclusive_range() -> None:
    assert require_aware_datetime(_aware(), field="fetched_at") == _aware()
    with pytest.raises(InvalidSourcePayload, match="timezone"):
        require_aware_datetime(datetime(2026, 8, 31, 9, 30), field="fetched_at")
    assert require_inclusive_range(date(2026, 1, 1), date(2026, 1, 1)) == (
        date(2026, 1, 1),
        date(2026, 1, 1),
    )
    with pytest.raises(InvalidSourcePayload, match="inverted"):
        require_inclusive_range(date(2026, 1, 31), date(2026, 1, 1))


def test_validate_bar_accepts_valid_ohlc() -> None:
    bar = _bar()
    assert validate_bar(bar) is bar


@pytest.mark.parametrize(
    "field,value",
    [
        ("open", 0.0),
        ("high", -1.0),
        ("low", float("nan")),
        ("close", float("inf")),
    ],
)
def test_validate_bar_requires_positive_finite_prices(field: str, value: float) -> None:
    with pytest.raises(InvalidSourcePayload):
        validate_bar(_bar(**{field: value}))


def test_validate_bar_enforces_high_and_low_invariants() -> None:
    with pytest.raises(InvalidSourcePayload, match="high"):
        validate_bar(_bar(open=10.0, high=9.9, low=9.0, close=9.5))
    with pytest.raises(InvalidSourcePayload, match="low"):
        validate_bar(_bar(open=10.0, high=11.0, low=10.6, close=10.5))


@pytest.mark.parametrize("field,value", [("volume", -1.0), ("amount", -0.01), ("turnover_pct", -0.1)])
def test_validate_bar_rejects_negative_size_fields(field: str, value: float) -> None:
    with pytest.raises(InvalidSourcePayload):
        validate_bar(_bar(**{field: value}))


def test_validate_bar_allows_zero_volume_and_amount() -> None:
    bar = _bar(volume=0.0, amount=0.0, turnover_pct=0.0)
    assert validate_bar(bar) is bar


def test_validate_bar_dataset_enforces_query_agreement() -> None:
    query = _query()
    valid = _dataset((_bar(),))
    assert validate_bar_dataset(valid, query).items[0].trade_date == date(2026, 8, 28)

    outside = _dataset((_bar(trade_date=date(2026, 7, 31)),))
    with pytest.raises(InvalidSourcePayload, match="outside query range"):
        validate_bar_dataset(outside, query)

    other_instrument = _dataset((_bar(instrument_id=_id("000001")),))
    with pytest.raises(InvalidSourcePayload, match="instrument"):
        validate_bar_dataset(other_instrument, query)

    wrong_interval = _dataset((_bar(interval=BarInterval.W1),))
    with pytest.raises(InvalidSourcePayload, match="interval"):
        validate_bar_dataset(wrong_interval, query)

    wrong_adjustment = _dataset((_bar(adjustment=Adjustment.HFQ),))
    with pytest.raises(InvalidSourcePayload, match="adjustment"):
        validate_bar_dataset(wrong_adjustment, query)


def test_validate_bar_dataset_rejects_duplicates_and_unsorted_items() -> None:
    query = _query()
    first = _bar(trade_date=date(2026, 8, 27))
    second = _bar(trade_date=date(2026, 8, 28))
    duplicate = _dataset((first, _bar(trade_date=date(2026, 8, 27))))
    with pytest.raises(InvalidSourcePayload, match="duplicate"):
        validate_bar_dataset(duplicate, query)
    unsorted = _dataset((second, first))
    with pytest.raises(InvalidSourcePayload, match="ascending"):
        validate_bar_dataset(unsorted, query)


def test_validate_bar_dataset_does_not_drop_malformed_records() -> None:
    query = _query()
    good = _bar(trade_date=date(2026, 8, 27))
    bad = _bar(trade_date=date(2026, 8, 28), high=1.0, open=10.0, close=10.0, low=9.0)
    with pytest.raises(InvalidSourcePayload, match="index 1"):
        validate_bar_dataset(_dataset((good, bad)), query)


def test_validate_calendar_dataset_range_order_and_duplicates() -> None:
    query = CalendarQuery(market_id="cn_a", start=date(2026, 8, 1), end=date(2026, 8, 31))
    days = (
        TradingDay(market_id="cn_a", trade_date=date(2026, 8, 3), is_open=True),
        TradingDay(market_id="cn_a", trade_date=date(2026, 8, 4), is_open=True),
    )
    dataset = Dataset(items=days, source="memory", fetched_at=_aware())
    assert validate_calendar_dataset(dataset, query).items == days

    with pytest.raises(InvalidSourcePayload, match="outside query range"):
        validate_calendar_dataset(
            Dataset(
                items=(TradingDay(market_id="cn_a", trade_date=date(2026, 7, 31), is_open=True),),
                source="memory",
                fetched_at=_aware(),
            ),
            query,
        )
    with pytest.raises(InvalidSourcePayload, match="duplicate"):
        validate_calendar_dataset(
            Dataset(
                items=(days[0], TradingDay(market_id="cn_a", trade_date=date(2026, 8, 3), is_open=False)),
                source="memory",
                fetched_at=_aware(),
            ),
            query,
        )
    with pytest.raises(InvalidSourcePayload, match="ascending"):
        validate_calendar_dataset(
            Dataset(items=(days[1], days[0]), source="memory", fetched_at=_aware()),
            query,
        )
    with pytest.raises(InvalidSourcePayload, match="market_id"):
        validate_calendar_dataset(
            Dataset(
                items=(TradingDay(market_id="us", trade_date=date(2026, 8, 3), is_open=True),),
                source="memory",
                fetched_at=_aware(),
            ),
            query,
        )


def _instrument(**overrides: object) -> Instrument:
    values: dict[str, object] = dict(
        id=_id(),
        asset_type=AssetType.STOCK,
        name="Kweichow Moutai",
        currency="CNY",
        timezone="Asia/Shanghai",
        list_date=date(2001, 8, 27),
    )
    values.update(overrides)
    return Instrument(**values)  # type: ignore[arg-type]


def _snapshot(**overrides: object) -> QuoteSnapshot:
    values: dict[str, object] = dict(
        instrument_id=_id(),
        observed_at=_aware(),
        last_price=1400.0,
        pre_close=1390.0,
        is_suspended=False,
    )
    values.update(overrides)
    return QuoteSnapshot(**values)  # type: ignore[arg-type]


def _valuation(**overrides: object) -> ValuationSnapshot:
    values: dict[str, object] = dict(
        instrument_id=_id(),
        as_of=date(2026, 8, 28),
        currency="CNY",
        total_shares=1.25e9,
        pe_ttm=20.5,
    )
    values.update(overrides)
    return ValuationSnapshot(**values)  # type: ignore[arg-type]


def test_validate_instrument_dataset_orders_and_filters() -> None:
    maotai = _instrument()
    ping_an = _instrument(id=_id("000001"), name="Ping An Bank")
    query = InstrumentQuery(asset_types=(AssetType.STOCK,))
    dataset = Dataset(items=(ping_an, maotai), source="memory", fetched_at=_aware())
    assert validate_instrument_dataset(dataset, query).items == (ping_an, maotai)

    unsorted = Dataset(items=(maotai, ping_an), source="memory", fetched_at=_aware())
    with pytest.raises(InvalidSourcePayload, match="ascending"):
        validate_instrument_dataset(unsorted, query)

    duplicate = Dataset(items=(maotai, _instrument()), source="memory", fetched_at=_aware())
    with pytest.raises(InvalidSourcePayload, match="duplicate"):
        validate_instrument_dataset(duplicate, query)

    wrong_type = Dataset(
        items=(_instrument(asset_type=AssetType.ETF),),
        source="memory",
        fetched_at=_aware(),
    )
    with pytest.raises(InvalidSourcePayload, match="asset_type"):
        validate_instrument_dataset(wrong_type, InstrumentQuery(asset_types=(AssetType.STOCK,)))


def test_validate_quote_snapshot_dataset_time_units_and_order() -> None:
    query = SnapshotQuery(instruments=(_id(),))
    valid = Dataset(items=(_snapshot(),), source="memory", fetched_at=_aware())
    assert validate_quote_snapshot_dataset(valid, query).items[0].last_price == 1400.0

    missing = Dataset(
        items=(_snapshot(last_price=None, pre_close=None, volume_ratio=None),),
        source="memory",
        fetched_at=_aware(),
    )
    assert validate_quote_snapshot_dataset(missing, query).items[0].last_price is None

    with pytest.raises(InvalidSourcePayload, match="finite"):
        validate_quote_snapshot_dataset(
            Dataset(
                items=(_snapshot(last_price=float("nan")),),
                source="memory",
                fetched_at=_aware(),
            ),
            query,
        )
    with pytest.raises(InvalidSourcePayload, match="volume_ratio"):
        validate_quote_snapshot_dataset(
            Dataset(
                items=(_snapshot(volume_ratio=-0.1),),
                source="memory",
                fetched_at=_aware(),
            ),
            query,
        )
    with pytest.raises(InvalidSourcePayload, match="timezone"):
        validate_quote_snapshot_dataset(
            Dataset(
                items=(_snapshot(observed_at=datetime(2026, 8, 31, 9, 30)),),
                source="memory",
                fetched_at=_aware(),
            ),
            query,
        )
    other = Dataset(
        items=(_snapshot(instrument_id=_id("000001")),),
        source="memory",
        fetched_at=_aware(),
    )
    with pytest.raises(InvalidSourcePayload, match="instrument"):
        validate_quote_snapshot_dataset(other, query)


def test_validate_valuation_dataset_units_and_as_of() -> None:
    query = ValuationQuery(instruments=(_id(),))
    valid = Dataset(items=(_valuation(),), source="memory", fetched_at=_aware())
    assert validate_valuation_dataset(valid, query).items[0].pe_ttm == 20.5

    missing = Dataset(
        items=(_valuation(total_shares=None, pe_ttm=None, pb=None),),
        source="memory",
        fetched_at=_aware(),
    )
    assert validate_valuation_dataset(missing, query).items[0].total_shares is None

    with pytest.raises(InvalidSourcePayload, match="finite"):
        validate_valuation_dataset(
            Dataset(
                items=(_valuation(pb=float("inf")),),
                source="memory",
                fetched_at=_aware(),
            ),
            query,
        )
    with pytest.raises(InvalidSourcePayload, match="total_shares"):
        validate_valuation_dataset(
            Dataset(
                items=(_valuation(total_shares=-1.0),),
                source="memory",
                fetched_at=_aware(),
            ),
            query,
        )
    with pytest.raises(InvalidSourcePayload, match="as_of"):
        validate_valuation_dataset(
            Dataset(items=(_valuation(),), source="memory", fetched_at=_aware()),
            ValuationQuery(instruments=(_id(),), as_of=date(2020, 1, 1)),
        )
