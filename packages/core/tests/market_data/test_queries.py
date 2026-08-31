from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from astock_core.market_data import (
    Adjustment,
    AssetType,
    BarInterval,
    BarQuery,
    CalendarQuery,
    ClassificationKind,
    ClassificationQuery,
    EventKind,
    EventQuery,
    FinancialPeriodType,
    FinancialSheet,
    FundamentalQuery,
    InstrumentQuery,
    MembershipQuery,
    NewsQuery,
    SnapshotQuery,
    StatementQuery,
    ValuationQuery,
    from_legacy_symbol,
)


def _id(symbol: str = "600519"):
    return from_legacy_symbol(symbol)


def test_bar_query_fields_and_inclusive_range() -> None:
    query = BarQuery(
        instruments=(_id(),),
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        interval=BarInterval.D1,
        adjustment=Adjustment.QFQ,
    )
    assert query.instruments == (_id(),)
    assert query.end >= query.start


def test_bar_query_accepts_list_instruments_as_tuple() -> None:
    query = BarQuery(
        instruments=[_id("600519"), _id("000001")],  # type: ignore[arg-type]
        start=date(2026, 1, 1),
        end=date(2026, 1, 1),
        interval=BarInterval.W1,
        adjustment=Adjustment.RAW,
    )
    assert query.instruments == (_id("600519"), _id("000001"))


def test_bar_query_rejects_empty_instruments_and_inverted_range() -> None:
    with pytest.raises(ValueError, match="instruments"):
        BarQuery(
            instruments=(),
            start=date(2026, 1, 1),
            end=date(2026, 1, 2),
            interval=BarInterval.D1,
            adjustment=Adjustment.QFQ,
        )
    with pytest.raises(ValueError, match="on or after"):
        BarQuery(
            instruments=(_id(),),
            start=date(2026, 1, 31),
            end=date(2026, 1, 1),
            interval=BarInterval.D1,
            adjustment=Adjustment.QFQ,
        )


def test_calendar_query_fields() -> None:
    query = CalendarQuery(market_id="cn_a", start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert query.market_id == "cn_a"
    with pytest.raises(ValueError, match="on or after"):
        CalendarQuery(market_id="cn_a", start=date(2026, 2, 1), end=date(2026, 1, 1))


def test_remaining_query_shapes() -> None:
    instrument = _id()
    catalog = InstrumentQuery(asset_types=(AssetType.STOCK,), exchanges=("XSHG",))
    assert catalog.instruments == ()
    snapshot = SnapshotQuery(instruments=(instrument,))
    valuation = ValuationQuery(instruments=(instrument,), as_of=date(2026, 8, 28))
    fundamentals = FundamentalQuery(
        instruments=(instrument,),
        period_types=(FinancialPeriodType.FY,),
        start=date(2024, 1, 1),
        end=date(2025, 12, 31),
    )
    statements = StatementQuery(
        instruments=(instrument,),
        sheet=FinancialSheet.PROFIT,
        period_types=(FinancialPeriodType.Q1,),
    )
    classifications = ClassificationQuery(
        kind=ClassificationKind.INDUSTRY,
        taxonomy="eastmoney",
        ids=("bk0478",),
    )
    memberships = MembershipQuery(
        taxonomy="csindex",
        classification_id="000300",
        instrument_id=instrument,
        as_of=date(2026, 8, 28),
    )
    news = NewsQuery(
        instruments=(instrument,),
        start=datetime(2026, 8, 1, tzinfo=timezone.utc),
        end=datetime(2026, 8, 31, tzinfo=timezone.utc),
        limit=20,
    )
    events = EventQuery(
        instruments=(instrument,),
        kinds=(EventKind.NOTICE, EventKind.BLOCK_TRADE),
        limit=10,
    )
    assert snapshot.instruments == (instrument,)
    assert valuation.as_of == date(2026, 8, 28)
    assert fundamentals.period_types == (FinancialPeriodType.FY,)
    assert statements.sheet is FinancialSheet.PROFIT
    assert classifications.kind is ClassificationKind.INDUSTRY
    assert memberships.classification_id == "000300"
    assert news.limit == 20
    assert events.kinds == (EventKind.NOTICE, EventKind.BLOCK_TRADE)


def test_news_query_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone"):
        NewsQuery(
            instruments=(_id(),),
            start=datetime(2026, 8, 1),
        )
