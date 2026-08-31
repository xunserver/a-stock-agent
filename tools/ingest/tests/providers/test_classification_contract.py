from __future__ import annotations

from datetime import date

import pytest

from astock_core.market_data import (
    CSINDEX_TAXONOMY,
    Classification,
    ClassificationKind,
    ClassificationQuery,
    EASTMONEY_TAXONOMY,
    Membership,
    MembershipQuery,
    UnsupportedQuery,
    from_legacy_symbol,
)

from .contracts import (
    assert_classification_source_contract,
    assert_membership_source_contract,
)
from .fakes import InMemoryClassificationSource, InMemoryMembershipSource, maotai, ping_an


def _industry_board() -> Classification:
    return Classification(
        id="BK1027",
        kind=ClassificationKind.INDUSTRY,
        name="小金属",
        taxonomy=EASTMONEY_TAXONOMY,
    )


def _concept_board() -> Classification:
    return Classification(
        id="BK0655",
        kind=ClassificationKind.CONCEPT,
        name="融资融券",
        taxonomy=EASTMONEY_TAXONOMY,
    )


def test_in_memory_classification_contract() -> None:
    source = InMemoryClassificationSource((_industry_board(), _concept_board()))
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


def test_in_memory_membership_contract() -> None:
    memberships = (
        Membership(
            classification_id="000300",
            taxonomy=CSINDEX_TAXONOMY,
            instrument_id=maotai(),
        ),
        Membership(
            classification_id="000300",
            taxonomy=CSINDEX_TAXONOMY,
            instrument_id=ping_an(),
        ),
    )
    source = InMemoryMembershipSource(memberships, names={"600519": "贵州茅台", "000001": "平安银行"})
    assert_membership_source_contract(
        source,
        valid_query=MembershipQuery(taxonomy=CSINDEX_TAXONOMY, classification_id="000300"),
        empty_query=MembershipQuery(taxonomy=CSINDEX_TAXONOMY, classification_id="000905"),
        undated_as_of_query=MembershipQuery(
            taxonomy=CSINDEX_TAXONOMY,
            classification_id="000300",
            as_of=date(2024, 1, 1),
        ),
    )


def test_undated_membership_as_of_raises_unsupported_query() -> None:
    source = InMemoryMembershipSource(
        (
            Membership(
                classification_id="000300",
                taxonomy=CSINDEX_TAXONOMY,
                instrument_id=maotai(),
            ),
        ),
    )
    with pytest.raises(UnsupportedQuery):
        source.fetch_memberships(
            MembershipQuery(
                taxonomy=CSINDEX_TAXONOMY,
                classification_id="000300",
                as_of=date(2024, 1, 1),
            )
        )
