from __future__ import annotations

import logging

from astock.config import hs300_symbol, index_aliases
from astock.ingest import _call, fetch_hs300_members
from astock_core.db import MarketDB
from astock_core.paths import DEFAULT_POOL_ID

logger = logging.getLogger(__name__)


def resolve_index_symbol(index: str) -> str:
    aliases = index_aliases()
    key = index.strip().lower()
    if key in aliases:
        return aliases[key]
    code = index.strip()
    if code.isdigit():
        return code.zfill(6)
    raise ValueError(f"未知指数：{index}。可用别名：{', '.join(aliases)}")


def fetch_index_members(index: str) -> tuple[str, list[tuple[str, str]]]:
    symbol = resolve_index_symbol(index)
    if symbol == hs300_symbol():
        return symbol, fetch_hs300_members()

    import akshare as ak

    logger.info("拉取指数 %s 成分股", symbol)
    try:
        frame = _call(ak.index_stock_cons_csindex, symbol=symbol)
        members = [
            (str(code).zfill(6), str(name))
            for code, name in zip(frame["成分券代码"], frame["成分券名称"], strict=True)
        ]
        logger.info("中证官网 %s 成分股 %s 只", symbol, len(members))
        return symbol, members
    except Exception as exc:
        logger.warning("中证官网失败，改用新浪：%s", exc)

    frame = _call(ak.index_stock_cons_sina, symbol=symbol)
    code_col = "code" if "code" in frame.columns else frame.columns[0]
    name_col = "name" if "name" in frame.columns else frame.columns[1]
    members = [
        (str(code).replace("sh", "").replace("sz", "").zfill(6), str(name))
        for code, name in zip(frame[code_col], frame[name_col], strict=True)
    ]
    logger.info("新浪 %s 成分股 %s 只", symbol, len(members))
    return symbol, members


def add_index_to_pool(
    db: MarketDB,
    index: str,
    *,
    pool_id: str = DEFAULT_POOL_ID,
    replace: bool = False,
) -> dict:
    symbol, members = fetch_index_members(index)
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


def add_index_to_stocks(db: MarketDB, index: str) -> dict:
    symbol, members = fetch_index_members(index)
    result = db.add_stocks(members)
    result["index"] = symbol
    result["fetched"] = len(members)
    return result
