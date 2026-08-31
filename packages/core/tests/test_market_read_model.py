from __future__ import annotations

from astock_core.db import MarketDB


def _bar(code: str, day: str, pct_chg: float) -> tuple:
    return (
        code,
        day,
        10.0,
        10.5,
        10.8,
        9.9,
        1000.0,
        10000.0,
        9.0,
        pct_chg,
        0.5,
        1.2,
        "qfq",
    )


def test_catalog_and_candidate_return_projections(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行"), ("600000", "浦发银行")])
        db.upsert_bars(
            [
                _bar("000001", "2026-08-27", 1.2),
                _bar("000001", "2026-08-28", -0.5),
                _bar("600000", "2026-08-28", 0.8),
            ]
        )

        assert db.stock_names({"000001", "999999"}) == {"000001": "平安银行"}
        assert db.next_bar_date("2026-08-27") == "2026-08-28"
        assert db.pct_changes_on_date(
            ["000001", "600000", "999999"], "2026-08-28"
        ) == {"000001": -0.5, "600000": 0.8}


def test_export_projections_are_ordered_and_hide_storage_schema(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.upsert_bars(
            [
                _bar("600000", "2026-08-28", 0.8),
                _bar("000001", "2026-08-27", 1.2),
            ]
        )
        db.upsert_index_bars(
            [
                ("000300", "沪深300", "2026-08-28", 1, 2, 3, 0.5, 100, 200),
                ("000001", "上证指数", "2026-08-27", 1, 2, 3, 0.5, 100, 200),
            ]
        )

        bars = db.list_bar_export_rows()
        indexes = db.list_index_bar_export_rows()

    assert [(row["code"], row["date"]) for row in bars] == [
        ("000001", "2026-08-27"),
        ("600000", "2026-08-28"),
    ]
    assert list(bars[0]) == [
        "code",
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
    ]
    assert [(row["code"], row["date"]) for row in indexes] == [
        ("000001", "2026-08-27"),
        ("000300", "2026-08-28"),
    ]
