from __future__ import annotations

import pytest

from astock.providers.akshare.classifications import (
    AkshareClassificationAdapter,
    AkshareMembershipAdapter,
)
from astock_core.market_data import (
    CSINDEX_TAXONOMY,
    ClassificationKind,
    ClassificationQuery,
    EASTMONEY_TAXONOMY,
    InvalidSourcePayload,
    MembershipQuery,
)

from .contracts import (
    assert_classification_source_contract,
    assert_membership_source_contract,
)


def test_akshare_classification_fixture_contract() -> None:
    source = AkshareClassificationAdapter(
        industry_names=lambda: [
            {"板块代码": "BK1027", "板块名称": "小金属"},
        ],
        concept_names=lambda: [
            {"板块代码": "BK0655", "板块名称": "融资融券"},
        ],
    )
    assert_classification_source_contract(
        source,
        valid_query=ClassificationQuery(
            kind=ClassificationKind.INDUSTRY,
            taxonomy=EASTMONEY_TAXONOMY,
        ),
        empty_query=ClassificationQuery(
            kind=ClassificationKind.INDUSTRY,
            taxonomy=EASTMONEY_TAXONOMY,
            ids=("BK9999",),
        ),
    )


def test_akshare_index_classification_is_taxonomy_qualified() -> None:
    source = AkshareClassificationAdapter(
        index_names=lambda: [
            {"index_code": "000300", "display_name": "沪深300"},
        ],
    )
    dataset = source.fetch_classifications(
        ClassificationQuery(
            kind=ClassificationKind.INDEX,
            taxonomy=CSINDEX_TAXONOMY,
            ids=("000300",),
        )
    )
    assert dataset.items[0].natural_key == (CSINDEX_TAXONOMY, "000300")
    assert dataset.items[0].kind == ClassificationKind.INDEX


def test_akshare_classification_rejects_duplicate_and_malformed_rows() -> None:
    duplicate = AkshareClassificationAdapter(
        industry_names=lambda: [
            {"板块代码": "BK1027", "板块名称": "小金属"},
            {"板块代码": "BK1027", "板块名称": "小金属"},
        ],
    )
    malformed = AkshareClassificationAdapter(
        industry_names=lambda: [{"板块代码": "BK1027"}],
    )
    query = ClassificationQuery(
        kind=ClassificationKind.INDUSTRY,
        taxonomy=EASTMONEY_TAXONOMY,
    )
    with pytest.raises(InvalidSourcePayload, match="duplicate"):
        duplicate.fetch_classifications(query)
    with pytest.raises(InvalidSourcePayload, match="malformed"):
        malformed.fetch_classifications(query)


def test_akshare_membership_fixture_contract() -> None:
    def index_members(symbol: str) -> list[dict[str, str]]:
        if symbol == "000905":
            return []
        return [
            {"成分券代码": "600519", "成分券名称": "贵州茅台"},
            {"成分券代码": "000001", "成分券名称": "平安银行"},
        ]

    source = AkshareMembershipAdapter(index_members_csindex=index_members)
    assert_membership_source_contract(
        source,
        valid_query=MembershipQuery(taxonomy=CSINDEX_TAXONOMY, classification_id="000300"),
        empty_query=MembershipQuery(taxonomy=CSINDEX_TAXONOMY, classification_id="000905"),
        undated_as_of_query=MembershipQuery(
            taxonomy=CSINDEX_TAXONOMY,
            classification_id="000300",
            as_of=__import__("datetime").date(2024, 1, 1),
        ),
    )


def test_akshare_board_membership_fixture() -> None:
    source = AkshareMembershipAdapter(
        industry_members=lambda board_id: [
            {"代码": "000001", "名称": "平安银行"},
            {"代码": "300750", "名称": "宁德时代"},
        ],
    )
    dataset = source.fetch_memberships(
        MembershipQuery(
            taxonomy=EASTMONEY_TAXONOMY,
            classification_id="BK1027",
            kind=ClassificationKind.INDUSTRY,
        )
    )
    assert len(dataset.items) == 2
    assert source.display_names()["000001"] == "平安银行"


def test_akshare_membership_rejects_duplicate_and_malformed_rows() -> None:
    duplicate = AkshareMembershipAdapter(
        index_members_csindex=lambda symbol: [
            {"成分券代码": "600519", "成分券名称": "贵州茅台"},
            {"成分券代码": "600519", "成分券名称": "贵州茅台"},
        ],
    )
    malformed = AkshareMembershipAdapter(
        index_members_csindex=lambda symbol: [{"成分券名称": "贵州茅台"}],
    )
    query = MembershipQuery(taxonomy=CSINDEX_TAXONOMY, classification_id="000300")
    with pytest.raises(InvalidSourcePayload, match="duplicate"):
        duplicate.fetch_memberships(query)
    with pytest.raises(InvalidSourcePayload, match="malformed"):
        malformed.fetch_memberships(query)
