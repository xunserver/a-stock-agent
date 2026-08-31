from __future__ import annotations

from astock.boards import sync_boards
from astock_core.db import MarketDB
from astock_core.market_data import (
    Classification,
    ClassificationKind,
    EASTMONEY_TAXONOMY,
    Membership,
    from_legacy_symbol,
)

from .fakes import InMemoryClassificationSource, InMemoryMembershipSource


def test_sync_boards_filters_to_system_stocks(tmp_path) -> None:
    db_path = tmp_path / "market.db"
    classifications = InMemoryClassificationSource(
        (
            Classification(
                id="BK1027",
                kind=ClassificationKind.INDUSTRY,
                name="小金属",
                taxonomy=EASTMONEY_TAXONOMY,
            ),
            Classification(
                id="BK0655",
                kind=ClassificationKind.CONCEPT,
                name="融资融券",
                taxonomy=EASTMONEY_TAXONOMY,
            ),
        )
    )
    memberships = InMemoryMembershipSource(
        (
            Membership(
                classification_id="BK1027",
                taxonomy=EASTMONEY_TAXONOMY,
                instrument_id=from_legacy_symbol("000001"),
            ),
            Membership(
                classification_id="BK1027",
                taxonomy=EASTMONEY_TAXONOMY,
                instrument_id=from_legacy_symbol("300750"),
            ),
            Membership(
                classification_id="BK0655",
                taxonomy=EASTMONEY_TAXONOMY,
                instrument_id=from_legacy_symbol("600519"),
            ),
            Membership(
                classification_id="BK0655",
                taxonomy=EASTMONEY_TAXONOMY,
                instrument_id=from_legacy_symbol("000002"),
            ),
        ),
        board_kinds={
            "BK1027": ClassificationKind.INDUSTRY,
            "BK0655": ClassificationKind.CONCEPT,
        },
    )

    with MarketDB(db_path) as db:
        db.add_stocks([("000001", "平安银行"), ("600519", "贵州茅台")])
        result = sync_boards(
            db,
            kinds=("industry", "concept"),
            sleep=0,
            classification_source=classifications,
            membership_source=memberships,
        )

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
