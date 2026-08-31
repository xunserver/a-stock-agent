from __future__ import annotations

from pathlib import Path

from astock_core._market_bars import _MarketBars
from astock_core._market_base import (
    BAR_TABLES,
    INGEST_KINDS,
    _MarketBase,
    _ymd,
    ensure_data_dir,
)
from astock_core._market_calendar_store import _MarketCalendarStore
from astock_core._market_financials import _MarketFinancials
from astock_core._market_pools import _MarketPools
from astock_core._market_stocks import _MarketStocks
from astock_core.paths import DEFAULT_POOL_ID


class MarketDB(
    _MarketStocks,
    _MarketFinancials,
    _MarketCalendarStore,
    _MarketPools,
    _MarketBars,
    _MarketBase,
):
    """SQLite 行情库：按领域 mixin 组合的公共数据库入口。"""

    def __init__(self, path: Path | None = None) -> None:
        super().__init__(path)
        self.ensure_pool(DEFAULT_POOL_ID, "默认股票池")
        self._migrate_universe_into_default_pool()


__all__ = ["BAR_TABLES", "INGEST_KINDS", "MarketDB", "_ymd", "ensure_data_dir"]
