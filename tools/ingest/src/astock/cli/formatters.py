"""Presentation functions for CLI results."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from astock_core.paths import DB_PATH

if TYPE_CHECKING:
    from astock_core.db import MarketDB


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def format_pool_summary(db: MarketDB, pool_id: str) -> str:
    plan = db.pool_quote_plan(pool_id)
    counts = db.counts(pool_id)
    active = counts.get("pool_active", 0)
    return "\n".join([
        f"池 {pool_id}",
        f"在池 {active}  已移除 {counts.get('pool_removed', 0)}",
        f"行情  需同步 {len(plan['full']) + len(plan['fill'])}  已齐 {len(plan['current'])}",
        f"资料  已同步行业 {db.profile_filled_count(pool_id)} / {active}",
        f"库    {DB_PATH}",
    ])


def format_pool_list(members: list[dict]) -> str:
    if not members:
        return "(空)"
    lines = [f"{'代码':<8} {'名称':<10} {'状态':<8} {'最新K':<12} {'来源'}", "-" * 56]
    for item in members:
        lines.append(f"{item.get('code', ''):<8} {str(item.get('name') or ''):<10} {item.get('status', ''):<8} {str(item.get('last_bar') or '-'):<12} {item.get('source') or ''}")
    return "\n".join(lines)


def format_stock_catalog(stocks: list[dict]) -> str:
    if not stocks:
        return "(空)"
    lines = [f"{'代码':<8} {'名称':<10} {'行业':<10} {'最新K':<12} {'所在池'}", "-" * 64]
    for item in stocks:
        pools = item.get("pools") or []
        pool_text = ",".join(str(pool.get("id") or "") for pool in pools) or "-"
        lines.append(f"{item.get('code', ''):<8} {str(item.get('name') or ''):<10} {str(item.get('industry') or '-'):<10} {str(item.get('last_bar') or '-'):<12} {pool_text}")
    return "\n".join(lines)
