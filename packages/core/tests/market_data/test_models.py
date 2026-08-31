from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from astock_core.market_data import (
    Adjustment,
    AssetType,
    Bar,
    BarInterval,
    BlockTradeEvent,
    CANONICAL_STATEMENT_ITEMS,
    Classification,
    ClassificationKind,
    EventKind,
    FinancialPeriodType,
    FinancialSheet,
    FinancialStatement,
    FundamentalPeriod,
    HolderChangeEvent,
    Instrument,
    InstrumentId,
    InstrumentProfile,
    MARKET_EVENT_TYPES,
    Membership,
    NewsItem,
    NoticeEvent,
    QuoteSnapshot,
    ResearchReportEvent,
    StatementItem,
    StatementUnit,
    TradingDay,
    ValuationSnapshot,
    from_legacy_symbol,
)


def _id(symbol: str = "600519") -> InstrumentId:
    return from_legacy_symbol(symbol)


def _aware() -> datetime:
    return datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)


def test_instrument_required_and_optional_fields() -> None:
    instrument = Instrument(
        id=_id(),
        asset_type=AssetType.STOCK,
        name="Kweichow Moutai",
        currency="CNY",
        timezone="Asia/Shanghai",
        list_date=date(2001, 8, 27),
        delist_date=None,
    )
    assert instrument.natural_key == _id()
    assert instrument.asset_type is AssetType.STOCK
    assert instrument.currency == "CNY"


def test_trading_day_natural_key() -> None:
    day = TradingDay(market_id="cn_a", trade_date=date(2026, 8, 31), is_open=True)
    assert day.natural_key == ("cn_a", date(2026, 8, 31))
    closed = TradingDay(
        market_id="cn_a",
        trade_date=date(2026, 8, 30),
        is_open=False,
        session_type="weekend",
    )
    assert closed.is_open is False
    assert closed.session_type == "weekend"


def test_bar_natural_key_and_required_fields() -> None:
    bar = Bar(
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
    assert bar.natural_key == (_id(), date(2026, 8, 28), BarInterval.D1, Adjustment.QFQ)
    assert bar.volume == 1_000_000.0
    assert bar.amount == 10_500_000.0


def test_instrument_profile_descriptive_fields_only() -> None:
    profile = InstrumentProfile(
        instrument_id=_id(),
        name="Kweichow Moutai",
        industry="liquor",
        region="Guizhou",
        list_date=date(2001, 8, 27),
        is_st=False,
    )
    assert profile.natural_key == _id()
    assert profile.is_st is False


def test_quote_snapshot_identity_includes_observation_time() -> None:
    snapshot = QuoteSnapshot(
        instrument_id=_id(),
        observed_at=_aware(),
        last_price=1400.0,
        pre_close=1390.0,
        average_price=1395.0,
        high_limit=1529.0,
        low_limit=1251.0,
        volume_ratio=1.1,
        outer_volume=100.0,
        inner_volume=80.0,
        is_suspended=False,
        suspend_reason=None,
    )
    assert snapshot.natural_key == (_id(), _aware())
    assert snapshot.is_suspended is False


def test_valuation_snapshot_natural_key() -> None:
    snapshot = ValuationSnapshot(
        instrument_id=_id(),
        as_of=date(2026, 8, 28),
        currency="CNY",
        total_shares=1.25e9,
        float_shares=1.2e9,
        total_market_cap=1.8e12,
        float_market_cap=1.7e12,
        pe_ttm=20.5,
        pe_static=22.0,
        pb=8.1,
    )
    assert snapshot.natural_key == (_id(), date(2026, 8, 28))
    assert snapshot.currency == "CNY"


def test_fundamental_period_natural_key_and_optional_announcement() -> None:
    period = FundamentalPeriod(
        instrument_id=_id(),
        period_end=date(2025, 12, 31),
        period_type=FinancialPeriodType.FY,
        currency="CNY",
        announced_at=None,
        eps=50.0,
        bps=200.0,
        roe_pct=25.0,
        revenue=1.5e11,
        revenue_yoy_pct=8.0,
        net_profit=7.5e10,
        net_profit_yoy_pct=6.0,
        gross_margin_pct=90.0,
        net_margin_pct=50.0,
        debt_ratio_pct=20.0,
    )
    assert period.natural_key == (_id(), date(2025, 12, 31), FinancialPeriodType.FY)
    assert period.announced_at is None


def test_financial_statement_uses_canonical_item_codes() -> None:
    items = (
        StatementItem(
            code="total_assets",
            label="Total assets",
            value=1.0e11,
            unit=StatementUnit.CNY,
            yoy_pct=5.0,
            qoq_pct=1.2,
        ),
    )
    statement = FinancialStatement(
        instrument_id=_id(),
        sheet=FinancialSheet.BALANCE,
        period_end=date(2025, 12, 31),
        period_type=FinancialPeriodType.FY,
        currency="CNY",
        items=items,
        announced_at=_aware(),
        source_payload=None,
    )
    assert statement.natural_key == (
        _id(),
        FinancialSheet.BALANCE,
        date(2025, 12, 31),
        FinancialPeriodType.FY,
    )
    assert "total_assets" in CANONICAL_STATEMENT_ITEMS[FinancialSheet.BALANCE]
    assert set(CANONICAL_STATEMENT_ITEMS[FinancialSheet.BALANCE]) == {
        "cash_and_equivalents",
        "accounts_receivable",
        "inventory",
        "total_current_assets",
        "total_assets",
        "total_current_liabilities",
        "total_liabilities",
        "total_parent_equity",
        "total_equity",
    }
    assert set(CANONICAL_STATEMENT_ITEMS[FinancialSheet.PROFIT]) == {
        "total_revenue",
        "operating_revenue",
        "operating_profit",
        "total_profit",
        "net_profit",
        "parent_net_profit",
        "basic_eps",
    }
    assert set(CANONICAL_STATEMENT_ITEMS[FinancialSheet.CASHFLOW]) == {
        "operating_cash_inflow",
        "operating_cash_outflow",
        "net_operating_cashflow",
        "net_investing_cashflow",
        "net_financing_cashflow",
        "net_change_in_cash",
        "ending_cash",
    }


def test_classification_identity_is_taxonomy_and_id() -> None:
    industry = Classification(
        id="bk0478",
        kind=ClassificationKind.INDUSTRY,
        name="Baijiu",
        taxonomy="eastmoney",
    )
    other = Classification(
        id="bk0478",
        kind=ClassificationKind.CONCEPT,
        name="Same local id",
        taxonomy="csindex",
    )
    assert industry.natural_key == ("eastmoney", "bk0478")
    assert industry.natural_key != other.natural_key


def test_membership_natural_key_includes_effective_from() -> None:
    membership = Membership(
        classification_id="000300",
        taxonomy="csindex",
        instrument_id=_id(),
        effective_from=date(2024, 1, 2),
        effective_to=None,
        weight_pct=1.5,
    )
    assert membership.natural_key == ("csindex", "000300", _id(), date(2024, 1, 2))


def test_news_item_requires_non_empty_title() -> None:
    item = NewsItem(
        id="n-1",
        instrument_id=_id(),
        title="Earnings beat",
        published_at=_aware(),
        publisher="SSE",
        summary="summary",
        url="https://example.invalid/n-1",
    )
    assert item.natural_key == "n-1"
    with pytest.raises(ValueError, match="title"):
        NewsItem(
            id="n-2",
            instrument_id=_id(),
            title="",
            published_at=_aware(),
        )
    with pytest.raises(ValueError, match="industry"):
        InstrumentProfile(instrument_id=_id(), name="x", industry="")


def test_market_event_variants_share_header_and_discriminate_kind() -> None:
    header = dict(
        instrument_id=_id(),
        title="Event",
        published_at=_aware(),
        source="akshare",
        url="https://example.invalid/e",
    )
    notice = NoticeEvent(id="e-1", **header, notice_type="annual", summary="text")
    research = ResearchReportEvent(
        id="e-2",
        **header,
        organization="CITIC",
        rating="buy",
        summary="note",
        pdf_url="https://example.invalid/r.pdf",
    )
    block = BlockTradeEvent(
        id="e-3",
        **header,
        deal_price=10.0,
        volume=1_000_000.0,
        amount=10_000_000.0,
        premium_pct=1.5,
        buyer="fund A",
        seller="fund B",
        close_price=9.8,
        pct_change=2.0,
    )
    holder = HolderChangeEvent(
        id="e-4",
        **header,
        person="Zhang",
        role="director",
        change_shares=-10_000.0,
        average_price=9.5,
        reason="personal",
    )
    assert notice.kind is EventKind.NOTICE
    assert research.kind is EventKind.RESEARCH_REPORT
    assert block.kind is EventKind.BLOCK_TRADE
    assert holder.kind is EventKind.HOLDER_CHANGE
    assert MARKET_EVENT_TYPES == (
        NoticeEvent,
        ResearchReportEvent,
        BlockTradeEvent,
        HolderChangeEvent,
    )
    assert all(isinstance(event, MARKET_EVENT_TYPES) for event in (notice, research, block, holder))
