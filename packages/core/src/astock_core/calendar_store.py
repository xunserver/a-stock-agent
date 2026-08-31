from __future__ import annotations

from pathlib import Path
from typing import Protocol

from astock_core.db import MarketDB
from astock_core.paths import DB_PATH
from astock_core.session import DEFAULT_MARKET


class TradingCalendar(Protocol):
    """Minimal calendar seam required by scheduling use-cases."""

    def is_trading_day(self, day: str) -> bool | None: ...

    def replace(self, trade_dates: list[str]) -> int: ...


class MarketCalendar:
    """Calendar adapter backed by the canonical market database."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        market_id: str = DEFAULT_MARKET,
    ) -> None:
        self.path = Path(path) if path else DB_PATH
        self.market_id = market_id

    def is_trading_day(self, day: str) -> bool | None:
        with MarketDB(self.path) as db:
            return db.trading_day_status(day, market_id=self.market_id)

    def replace(self, trade_dates: list[str]) -> int:
        with MarketDB(self.path) as db:
            return db.sync_calendar(trade_dates, market_id=self.market_id)
