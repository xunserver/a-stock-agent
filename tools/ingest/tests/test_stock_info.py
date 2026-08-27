from __future__ import annotations

from astock.stock import sync_stock_info
from astock_core.db import MarketDB


def test_sync_stock_info_persists_akshare_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("astock.stock.fetch_st_codes", lambda: set())
    monkeypatch.setattr("astock.stock.fetch_suspend_map", lambda _as_of: {})
    monkeypatch.setattr(
        "astock.stock.load_profiles",
        lambda codes, sleep=0, st_codes=None: {
            "000408": {
                "name": "藏格矿业",
                "industry": "化学原料",
                "pre_close": 75.72,
                "avg_price": 78.5,
                "high_limit": 83.29,
                "low_limit": 68.15,
                "volume_ratio": 1.36,
                "outer_vol": 120000,
                "inner_vol": 90000,
                "pe_dyn": 22.1,
                "pe_static": 36.9,
                "pb": 4.3,
                "total_mv": 1.2e11,
                "float_mv": 8e10,
                "total_shares": 1.5e9,
                "float_shares": 1.1e9,
                "eps": 2.15,
                "bps": 18.4,
                "roe": 12.3,
                "revenue": 1.1e10,
                "revenue_yoy": 8.5,
                "net_profit_yoy": 15.0,
                "gross_margin": 42.0,
                "net_margin": 20.0,
                "debt_ratio": 28.6,
            }
        },
    )
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000408", "藏格矿业")])
        result = sync_stock_info(db, ["000408"], sleep=0)
        assert result == {"info_ok": 1, "info_error": 0, "info_total": 1}
        got = db.get_stock("000408")
        assert got is not None
        assert got["pre_close"] == 75.72
        assert got["avg_price"] == 78.5
        assert got["pe_static"] == 36.9
        assert got["roe"] == 12.3
        assert got["net_margin"] == 20.0
        assert got["debt_ratio"] == 28.6
        assert got["outer_vol"] == 120000
