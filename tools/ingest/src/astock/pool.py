from __future__ import annotations

import logging

from astock.indexes import index_member_tuples
from astock.providers.protocols import MembershipSource
from astock_core.db import MarketDB
from astock_core.paths import DEFAULT_POOL_ID

logger = logging.getLogger(__name__)


def add_index_to_pool(
    db: MarketDB,
    index: str,
    *,
    pool_id: str = DEFAULT_POOL_ID,
    replace: bool = False,
    membership_source: MembershipSource | None = None,
) -> dict:
    symbol, members = index_member_tuples(index, membership_source=membership_source)
    catalog = set(db.stock_codes())
    kept = [(code, name) for code, name in members if code in catalog]
    skipped = len(members) - len(kept)
    if members and not kept:
        raise ValueError("指数成分都不在系统股票里，请先在股票管理中按指数加入")
    source = f"index:{symbol}"
    if replace:
        result = db.set_pool_members(pool_id, kept, source=source)
    else:
        result = db.add_pool_members(pool_id, kept, source=source)
    result["index"] = symbol
    result["fetched"] = len(members)
    result["skipped"] = skipped
    result["pool"] = pool_id
    result["active"] = len(db.active_pool_codes(pool_id))
    return result


def add_codes_to_pool(
    db: MarketDB,
    codes: list[str],
    *,
    pool_id: str = DEFAULT_POOL_ID,
    source: str = "manual",
) -> dict:
    names = db.stock_names(codes)
    members = [(code, names.get(code) or code) for code in codes]
    result = db.add_pool_members(pool_id, members, source=source)
    result["pool"] = pool_id
    result["active"] = len(db.active_pool_codes(pool_id))
    return result


def add_codes_to_stocks(db: MarketDB, codes: list[str]) -> dict:
    names = db.stock_names(codes)
    members = [(code, names.get(code) or code) for code in codes]
    return db.add_stocks(members)


def add_index_to_stocks(
    db: MarketDB,
    index: str,
    *,
    membership_source: MembershipSource | None = None,
) -> dict:
    symbol, members = index_member_tuples(index, membership_source=membership_source)
    result = db.add_stocks(members)
    result["index"] = symbol
    result["fetched"] = len(members)
    return result
