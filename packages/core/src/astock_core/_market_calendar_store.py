from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from astock_core._market_base import _MarketBase, _ymd
from astock_core.market_data import TradingDay
from astock_core.session import DEFAULT_MARKET, get_policy, market_now, session_ceiling_date

class _MarketCalendarStore(_MarketBase):
    def replace_calendar(
        self,
        dates: list[date | str],
        *,
        market_id: str = DEFAULT_MARKET,
    ) -> int:
        rows = [(market_id, _ymd(item)) for item in dates]
        with self.conn:
            self.conn.execute(
                "DELETE FROM trade_calendar WHERE market_id = ?",
                (market_id,),
            )
            self.conn.executemany(
                "INSERT OR IGNORE INTO trade_calendar (market_id, trade_date) VALUES (?, ?)",
                rows,
            )
        return len(rows)

    def sync_calendar(
        self,
        dates: list[date | str],
        *,
        market_id: str = DEFAULT_MARKET,
        now: datetime | None = None,
    ) -> int:
        """Atomically replace a market calendar and record its sync watermark."""
        rows = [(market_id, _ymd(item)) for item in dates]
        policy = get_policy(market_id)
        synced_on = market_now(now, policy=policy).date().isoformat()
        updated_at = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                "DELETE FROM trade_calendar WHERE market_id = ?", (market_id,)
            )
            self.conn.executemany(
                "INSERT OR IGNORE INTO trade_calendar (market_id, trade_date) VALUES (?, ?)",
                rows,
            )
            self.conn.execute(
                """
                INSERT INTO ingest_state (
                    code, kind, adjust, last_trade_date, rows, status, error, updated_at
                ) VALUES (?, 'calendar', '', ?, ?, 'ok', NULL, ?)
                ON CONFLICT(code, kind, adjust) DO UPDATE SET
                    last_trade_date = excluded.last_trade_date,
                    rows = excluded.rows,
                    status = 'ok',
                    error = NULL,
                    updated_at = excluded.updated_at
                """,
                (market_id, synced_on, len(rows), updated_at),
            )
        return len(rows)

    def upsert_trading_days(
        self,
        days: Sequence[TradingDay],
        *,
        market_id: str = DEFAULT_MARKET,
    ) -> int:
        """Atomically replace open TradingDays for a market and record the watermark.

        Closed-day records may be present on the Dataset but are filtered here so
        v1 persistence stores open dates only.
        """
        open_dates = [
            day.trade_date
            for day in days
            if day.is_open and day.market_id == market_id
        ]
        return self.sync_calendar(open_dates, market_id=market_id)

    def last_calendar_date(
        self,
        as_of: date | None = None,
        *,
        market_id: str = DEFAULT_MARKET,
    ) -> str | None:
        today = (as_of or date.today()).isoformat()
        row = self.conn.execute(
            """
            SELECT MAX(trade_date) AS d
            FROM trade_calendar
            WHERE market_id = ? AND trade_date <= ?
            """,
            (market_id, today),
        ).fetchone()
        return row["d"] if row and row["d"] else None

    def current_trade_date(
        self,
        *,
        market_id: str = DEFAULT_MARKET,
        now: datetime | None = None,
    ) -> str | None:
        """系统当前交易日（展示 / 是否已齐），按市场 session 切点计算。"""
        policy = get_policy(market_id)
        ceiling = session_ceiling_date(now, policy=policy)
        return self.last_calendar_date(as_of=ceiling, market_id=market_id)

    def is_trading_day(
        self,
        day: date | str,
        *,
        market_id: str = DEFAULT_MARKET,
    ) -> bool:
        trade_date = _ymd(day)
        row = self.conn.execute(
            """
            SELECT 1 FROM trade_calendar
            WHERE market_id = ? AND trade_date = ?
            """,
            (market_id, trade_date),
        ).fetchone()
        return row is not None

    def trading_day_status(
        self,
        day: date | str,
        *,
        market_id: str = DEFAULT_MARKET,
    ) -> bool | None:
        """Return open/closed inside known coverage, or ``None`` outside it."""
        trade_date = _ymd(day)
        if self.is_trading_day(trade_date, market_id=market_id):
            return True
        coverage = self.calendar_coverage(market_id=market_id)
        first = coverage.get("first")
        last = coverage.get("last")
        if not first or not last or trade_date < first or trade_date > last:
            return None
        return False

    def list_calendar_dates(
        self,
        start: date | str,
        end: date | str,
        *,
        market_id: str = DEFAULT_MARKET,
    ) -> list[str]:
        start_s = _ymd(start)
        end_s = _ymd(end)
        rows = self.conn.execute(
            """
            SELECT trade_date FROM trade_calendar
            WHERE market_id = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date
            """,
            (market_id, start_s, end_s),
        ).fetchall()
        return [row["trade_date"] for row in rows]

    def calendar_month(
        self,
        year: int,
        month: int,
        *,
        market_id: str = DEFAULT_MARKET,
    ) -> dict[str, object]:
        if month < 1 or month > 12:
            raise ValueError("month 必须在 1–12")
        start = date(year, month, 1)
        if month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        trading = set(self.list_calendar_dates(start, end, market_id=market_id))
        days: list[dict[str, object]] = []
        cursor = start
        while cursor <= end:
            iso = cursor.isoformat()
            days.append({"date": iso, "is_trading": iso in trading})
            cursor += timedelta(days=1)
        return {
            "market": market_id,
            "year": year,
            "month": month,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "trading_days": len(trading),
            "days": days,
        }

    def calendar_coverage(self, *, market_id: str = DEFAULT_MARKET) -> dict[str, object]:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS n, MIN(trade_date) AS first, MAX(trade_date) AS last
            FROM trade_calendar
            WHERE market_id = ?
            """,
            (market_id,),
        ).fetchone()
        return {
            "count": int(row["n"] or 0),
            "first": row["first"],
            "last": row["last"],
        }

    def calendar_synced_today(
        self,
        *,
        market_id: str = DEFAULT_MARKET,
        now: datetime | None = None,
    ) -> bool:
        """交易日历是否已在该市场本地自然日同步过。"""
        policy = get_policy(market_id)
        today = market_now(now, policy=policy).date().isoformat()
        row = self.conn.execute(
            """
            SELECT last_trade_date FROM ingest_state
            WHERE code = ? AND kind = 'calendar' AND adjust = ''
            """,
            (market_id,),
        ).fetchone()
        return bool(row and row["last_trade_date"] == today)

    def mark_calendar_synced(
        self,
        *,
        market_id: str = DEFAULT_MARKET,
        now: datetime | None = None,
        rows: int = 0,
    ) -> None:
        policy = get_policy(market_id)
        today = market_now(now, policy=policy).date().isoformat()
        self.mark_ingest(
            market_id,
            "calendar",
            "ok",
            adjust="",
            last_trade_date=today,
            rows=rows,
        )
