from __future__ import annotations

import pandas as pd

from astock.boards import sync_boards
from astock_core.db import MarketDB


def test_boards_schema_and_membership(tmp_path) -> None:
    db_path = tmp_path / "market.db"
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行"), ("600519", "贵州茅台")])
        assert db.upsert_boards(
            [
                ("BK1027", "industry", "小金属", "em"),
                ("BK0655", "concept", "融资融券", "em"),
            ]
        ) == 2
        assert db.replace_board_members("BK1027", ["000001", "999999", "000001"]) == 1
        assert db.replace_board_members("BK0655", ["600519", "000001"]) == 2

        boards = db.list_boards(kind="industry")
        assert len(boards) == 1
        assert boards[0]["id"] == "BK1027"

        for_code = db.boards_for_code("000001")
        assert {item["id"] for item in for_code} == {"BK1027", "BK0655"}

        counts = db.counts()
        assert counts["boards"] == 2
        assert counts["board_members"] == 3

        # replace clears previous members for that board
        assert db.replace_board_members("BK0655", ["600519"]) == 1
        assert {item["id"] for item in db.boards_for_code("000001")} == {"BK1027"}


def test_sync_boards_filters_to_system_stocks(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"

    def fake_names(kind: str) -> pd.DataFrame:
        if kind == "industry":
            return pd.DataFrame([{"板块代码": "BK1027", "板块名称": "小金属"}])
        return pd.DataFrame([{"板块代码": "BK0655", "板块名称": "融资融券"}])

    def fake_cons(kind: str, board_id: str) -> pd.DataFrame:
        if board_id == "BK1027":
            return pd.DataFrame([{"代码": "000001"}, {"代码": "300750"}])
        return pd.DataFrame([{"代码": "600519"}, {"代码": "000002"}])

    monkeypatch.setattr("astock.boards._fetch_board_names", fake_names)
    monkeypatch.setattr("astock.boards._fetch_board_cons", fake_cons)

    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行"), ("600519", "贵州茅台")])
        result = sync_boards(db, kinds=("industry", "concept"), sleep=0)

    assert result["boards"] == 2
    assert result["members"] == 2
    assert result["error"] == 0
    with MarketDB(db_path) as db:
        assert {row["code"] for row in db.conn.execute("SELECT code FROM board_members")} == {
            "000001",
            "600519",
        }
        assert db.boards_for_code("000001")[0]["kind"] == "industry"
        assert db.boards_for_code("600519")[0]["kind"] == "concept"
