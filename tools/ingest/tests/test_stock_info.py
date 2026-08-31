from __future__ import annotations

from datetime import date, datetime, timezone

from astock.ingest import ingest_stocks
from astock.stock import sync_stock_info
from astock_core.db import MarketDB
from astock_core.market_data import (
    AssetType,
    Dataset,
    FundamentalQuery,
    Instrument,
    InstrumentProfile,
    QuoteSnapshot,
    SourceUnavailable,
    ValuationSnapshot,
    from_legacy_symbol,
)

FETCHED_AT = datetime(2026, 8, 31, 9, 30, tzinfo=timezone.utc)


def _id(symbol: str = "000408"):
    return from_legacy_symbol(symbol)


class _InstrumentSource:
    def __init__(self, instruments: tuple[Instrument, ...]) -> None:
        self._instruments = instruments
        self.calls = 0

    def fetch_instruments(self, query):
        self.calls += 1
        items = tuple(
            sorted(
                (
                    item
                    for item in self._instruments
                    if (not query.instruments or item.id in query.instruments)
                    and (not query.asset_types or item.asset_type in query.asset_types)
                ),
                key=lambda item: item.id.value,
            )
        )
        return Dataset(items=items, source="memory", fetched_at=FETCHED_AT, complete=True)


class _ProfileSource:
    def __init__(self, profiles=(), *, error=None) -> None:
        self._profiles = profiles
        self.error = error

    def fetch_profiles(self, query):
        if self.error is not None:
            raise self.error
        wanted = frozenset(query.instruments)
        items = tuple(
            item for item in self._profiles if not wanted or item.instrument_id in wanted
        )
        return Dataset(items=items, source="memory", fetched_at=FETCHED_AT, complete=True)


class _SnapshotSource:
    def __init__(self, snapshots=(), *, error=None) -> None:
        self._snapshots = snapshots
        self.error = error

    def fetch_snapshots(self, query):
        if self.error is not None:
            raise self.error
        items = tuple(item for item in self._snapshots if item.instrument_id in query.instruments)
        return Dataset(items=items, source="memory", fetched_at=FETCHED_AT, complete=True)


class _ValuationSource:
    def __init__(self, snapshots=(), *, error=None) -> None:
        self._snapshots = snapshots
        self.error = error

    def fetch_valuations(self, query):
        if self.error is not None:
            raise self.error
        items = tuple(item for item in self._snapshots if item.instrument_id in query.instruments)
        return Dataset(items=items, source="memory", fetched_at=FETCHED_AT, complete=True)


class _FundamentalSource:
    def __init__(self, periods=(), *, error=None) -> None:
        self._periods = periods
        self.error = error

    def fetch_fundamentals(self, query: FundamentalQuery):
        if self.error is not None:
            raise self.error
        items = tuple(item for item in self._periods if item.instrument_id in query.instruments)
        return Dataset(items=items, source="memory", fetched_at=FETCHED_AT, complete=True)


def _profile(**overrides):
    values = dict(
        instrument_id=_id(),
        name="藏格矿业",
        industry="化学原料",
        region="西藏板块",
        list_date=date(1996, 7, 15),
        is_st=False,
    )
    values.update(overrides)
    return InstrumentProfile(**values)


def _snapshot(**overrides):
    values = dict(
        instrument_id=_id(),
        observed_at=FETCHED_AT,
        last_price=79.29,
        pre_close=75.72,
        average_price=78.5,
        high_limit=83.29,
        low_limit=68.15,
        volume_ratio=1.36,
        outer_volume=120000.0,
        inner_volume=90000.0,
        is_suspended=False,
    )
    values.update(overrides)
    return QuoteSnapshot(**values)


def _valuation(**overrides):
    values = dict(
        instrument_id=_id(),
        as_of=date(2026, 8, 31),
        currency="CNY",
        total_shares=1.5e9,
        float_shares=1.1e9,
        total_market_cap=1.2e11,
        float_market_cap=8e10,
        pe_ttm=22.1,
        pe_static=36.9,
        pb=4.3,
    )
    values.update(overrides)
    return ValuationSnapshot(**values)


def test_sync_stock_info_persists_split_capabilities(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000408", "藏格矿业")])
        result = sync_stock_info(
            db,
            ["000408"],
            sleep=0,
            profile_source=_ProfileSource((_profile(),)),
            snapshot_source=_SnapshotSource((_snapshot(),)),
            valuation_source=_ValuationSource((_valuation(),)),
            fundamental_source=_FundamentalSource(),
        )
        assert result["info_ok"] == 1
        assert result["info_error"] == 0
        assert result["profile_ok"] == 1
        assert result["snapshot_ok"] == 1
        assert result["valuation_ok"] == 1
        got = db.get_stock("000408")
        assert got is not None
        assert got["industry"] == "化学原料"
        assert got["region"] == "西藏板块"
        assert got["pre_close"] == 75.72
        assert got["avg_price"] == 78.5
        assert got["pe_static"] == 36.9
        assert got["pe_dyn"] == 22.1
        assert got["outer_vol"] == 120000
        assert got["eps"] is None


def test_sync_stock_info_partial_failure_preserves_other_capabilities(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000408", "藏格矿业")])
        db.upsert_stock_profile(
            "000408",
            name="藏格矿业",
            latest_price=10.0,
            pre_close=9.5,
            eps=2.15,
        )
        result = sync_stock_info(
            db,
            ["000408"],
            sleep=0,
            profile_source=_ProfileSource((_profile(),)),
            snapshot_source=_SnapshotSource(error=SourceUnavailable("quote down")),
            valuation_source=_ValuationSource((_valuation(),)),
            fundamental_source=_FundamentalSource(),
        )
        assert result["info_ok"] == 1
        assert result["snapshot_error"] == 1
        assert result["snapshot_ok"] == 0
        assert result["profile_ok"] == 1
        assert result["valuation_ok"] == 1
        got = db.get_stock("000408")
        assert got is not None
        assert got["industry"] == "化学原料"
        assert got["latest_price"] == 10.0
        assert got["pre_close"] == 9.5
        assert got["pe_dyn"] == 22.1
        assert got["eps"] == 2.15


def test_sync_stock_info_all_capabilities_fail_preserves_stored_row(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000408", "藏格矿业")])
        db.upsert_stock_profile("000408", name="藏格矿业", industry="化学原料", pe_dyn=8.5)
        result = sync_stock_info(
            db,
            ["000408"],
            sleep=0,
            profile_source=_ProfileSource(error=SourceUnavailable("profile down")),
            snapshot_source=_SnapshotSource(error=SourceUnavailable("quote down")),
            valuation_source=_ValuationSource(error=SourceUnavailable("valuation down")),
            fundamental_source=_FundamentalSource(),
        )
        assert result["info_ok"] == 0
        assert result["info_error"] == 1
        got = db.get_stock("000408")
        assert got is not None
        assert got["industry"] == "化学原料"
        assert got["pe_dyn"] == 8.5


def test_ingest_stocks_uses_instrument_source(tmp_path) -> None:
    source = _InstrumentSource(
        (
            Instrument(
                id=_id("000001"),
                asset_type=AssetType.STOCK,
                name="平安银行",
                currency="CNY",
                timezone="Asia/Shanghai",
            ),
            Instrument(
                id=_id("600519"),
                asset_type=AssetType.STOCK,
                name="贵州茅台",
                currency="CNY",
                timezone="Asia/Shanghai",
            ),
        )
    )
    with MarketDB(tmp_path / "market.db") as db:
        written = ingest_stocks(db, instrument_source=source)
        assert written == 2
        assert db.stock_codes() == ["000001", "600519"]
        assert db.get_stock("600519")["name"] == "贵州茅台"
        assert source.calls == 1
