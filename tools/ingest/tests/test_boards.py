from __future__ import annotations

from astock_core.db import MarketDB


def test_boards_schema_and_membership(tmp_path) -> None:
    db_path = tmp_path / "market.db"
    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行"), ("600519", "贵州茅台")])
        assert db.upsert_boards(
            [
                ("BK1027", "industry", "小金属", "eastmoney"),
                ("BK0655", "concept", "融资融券", "eastmoney"),
            ]
        ) == 2
        assert db.replace_board_members("BK1027", ["000001", "999999", "000001"]) == 1
        assert db.replace_board_members("BK0655", ["600519", "000001"]) == 2

        boards = db.list_boards(kind="industry")
        assert len(boards) == 1
        assert boards[0]["id"] == "BK1027"
        assert boards[0]["source"] == "eastmoney"

        for_code = db.boards_for_code("000001")
        assert {item["id"] for item in for_code} == {"BK1027", "BK0655"}

        counts = db.counts()
        assert counts["boards"] == 2
        assert counts["board_members"] == 3

        assert db.replace_board_members("BK0655", ["600519"]) == 1
        assert {item["id"] for item in db.boards_for_code("000001")} == {"BK1027"}
