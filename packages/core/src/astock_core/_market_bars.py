from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from astock_core._market_base import BAR_TABLES, _MarketBase, _ymd
from astock_core.market_data import Adjustment, Bar, BarInterval, derive_bar_change, to_legacy_symbol
from astock_core.paths import DEFAULT_ADJUST, DEFAULT_POOL_ID
from astock_core.session import DEFAULT_MARKET

_INTERVAL_TO_PERIOD = {
    BarInterval.D1: "daily",
    BarInterval.W1: "weekly",
    BarInterval.M1: "monthly",
}


def persist_adjustment(adjustment: Adjustment) -> str:
    """Map Standard Record adjustment onto the existing SQLite adjust key."""
    return "" if adjustment is Adjustment.RAW else str(adjustment)


class _MarketBars(_MarketBase):
    def latest_bar(self, code: str, adjust: str = DEFAULT_ADJUST) -> dict | None:
        row = self.conn.execute(
            """
            SELECT * FROM bars_daily
            WHERE code = ? AND adjust = ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (code, adjust),
        ).fetchone()
        return dict(row) if row else None

    def list_daily_bars(
        self,
        code: str,
        *,
        adjust: str = DEFAULT_ADJUST,
        limit: int | None = None,
    ) -> list[dict]:
        return self.list_bars(code, period="daily", adjust=adjust, limit=limit)

    def list_bars(
        self,
        code: str,
        *,
        period: str = "daily",
        adjust: str = DEFAULT_ADJUST,
        limit: int | None = None,
    ) -> list[dict]:
        if period == "yearly":
            return self.list_yearly_bars(code, adjust=adjust, limit=limit)
        table = BAR_TABLES.get(period)
        if table is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        sql = f"""
            SELECT trade_date, open, close, high, low, volume, amount,
                   pct_chg, turnover, amplitude, change_amount
            FROM {table}
            WHERE code = ? AND adjust = ?
            ORDER BY trade_date DESC
        """
        params: list = [code, adjust]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in reversed(rows)]

    def list_yearly_bars(
        self,
        code: str,
        *,
        adjust: str = DEFAULT_ADJUST,
        limit: int | None = None,
    ) -> list[dict]:
        """年 K：优先用月线聚合，没有月线再用日线。"""
        source = self.list_bars(code, period="monthly", adjust=adjust)
        if not source:
            source = self.list_bars(code, period="daily", adjust=adjust)
        if not source:
            return []

        grouped: dict[str, list[dict]] = {}
        for bar in source:
            year = str(bar.get("trade_date") or "")[:4]
            if len(year) != 4:
                continue
            grouped.setdefault(year, []).append(bar)

        yearly: list[dict] = []
        prev_close: float | None = None
        for year in sorted(grouped):
            rows = grouped[year]
            first = rows[0]
            last = rows[-1]
            opens = [row["open"] for row in rows if row.get("open") is not None]
            highs = [row["high"] for row in rows if row.get("high") is not None]
            lows = [row["low"] for row in rows if row.get("low") is not None]
            close = last.get("close")
            open_ = opens[0] if opens else first.get("open")
            high = max(highs) if highs else None
            low = min(lows) if lows else None
            volume = sum(float(row["volume"]) for row in rows if row.get("volume") is not None) or None
            amount = sum(float(row["amount"]) for row in rows if row.get("amount") is not None) or None
            change_amount = None
            pct_chg = None
            if close is not None and prev_close not in (None, 0):
                change_amount = float(close) - float(prev_close)
                pct_chg = change_amount / float(prev_close) * 100
            amplitude = None
            if high is not None and low is not None and prev_close not in (None, 0):
                amplitude = (float(high) - float(low)) / float(prev_close) * 100
            yearly.append(
                {
                    "trade_date": last.get("trade_date"),
                    "open": open_,
                    "close": close,
                    "high": high,
                    "low": low,
                    "volume": volume,
                    "amount": amount,
                    "pct_chg": pct_chg,
                    "turnover": None,
                    "amplitude": amplitude,
                    "change_amount": change_amount,
                }
            )
            if close is not None:
                prev_close = float(close)

        if limit is not None:
            return yearly[-limit:]
        return yearly

    def bar_summary(self, code: str, adjust: str = DEFAULT_ADJUST) -> dict:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS n, MIN(trade_date) AS first, MAX(trade_date) AS last
            FROM bars_daily
            WHERE code = ? AND adjust = ?
            """,
            (code, adjust),
        ).fetchone()
        first = row["first"]
        last = row["last"]
        last_cal = self.current_trade_date()
        missing = 0
        if first and last_cal:
            missing = int(
                self.conn.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM trade_calendar c
                    WHERE c.market_id = ?
                      AND c.trade_date >= ?
                      AND c.trade_date <= ?
                      AND NOT EXISTS (
                        SELECT 1 FROM bars_daily b
                        WHERE b.code = ? AND b.adjust = ? AND b.trade_date = c.trade_date
                      )
                    """,
                    (DEFAULT_MARKET, first, last_cal, code, adjust),
                ).fetchone()["n"]
            )
        return {
            "adjust": adjust,
            "bars": int(row["n"] or 0),
            "first": first,
            "last": last,
            "calendar_as_of": last_cal,
            "missing_sessions": missing,
        }

    def next_bar_date(self, after: date | str, *, period: str = "daily") -> str | None:
        """Return the next stored bar date after ``after`` across all symbols."""
        table = BAR_TABLES.get(period)
        if table is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        row = self.conn.execute(
            f"SELECT MIN(trade_date) AS trade_date FROM {table} WHERE trade_date > ?",
            (_ymd(after),),
        ).fetchone()
        return str(row["trade_date"]) if row and row["trade_date"] else None

    def last_bar_date(
        self,
        code: str,
        adjust: str = DEFAULT_ADJUST,
        period: str = "daily",
    ) -> str | None:
        table = BAR_TABLES.get(period)
        if table is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        row = self.conn.execute(
            f"""
            SELECT MAX(trade_date) AS d
            FROM {table}
            WHERE code = ? AND adjust = ?
            """,
            (code, adjust),
        ).fetchone()
        return row["d"] if row and row["d"] else None

    def last_index_date(self, code: str) -> str | None:
        row = self.conn.execute(
            "SELECT MAX(trade_date) AS d FROM index_daily WHERE code = ?",
            (code,),
        ).fetchone()
        return row["d"] if row and row["d"] else None

    def pct_changes_on_date(
        self,
        codes: list[str],
        trade_date: date | str,
        *,
        adjust: str = DEFAULT_ADJUST,
    ) -> dict[str, float | None]:
        """Return the daily return projection for a bounded symbol set."""
        if not codes:
            return {}
        unique_codes = list(dict.fromkeys(codes))
        placeholders = ",".join("?" for _ in unique_codes)
        rows = self.conn.execute(
            f"""
            SELECT code, pct_chg FROM bars_daily
            WHERE adjust = ? AND trade_date = ? AND code IN ({placeholders})
            """,
            [adjust, _ymd(trade_date), *unique_codes],
        ).fetchall()
        return {
            str(row["code"]): (
                float(row["pct_chg"]) if row["pct_chg"] is not None else None
            )
            for row in rows
        }

    def list_bar_export_rows(self, *, adjust: str = DEFAULT_ADJUST) -> list[dict]:
        """Read the stable daily-bar projection consumed by data exporters."""
        rows = self.conn.execute(
            """
            SELECT code, trade_date AS date, open, close, high, low, volume, amount
            FROM bars_daily
            WHERE adjust = ?
            ORDER BY code, trade_date
            """,
            (adjust,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_index_bar_export_rows(self) -> list[dict]:
        """Read the stable index-bar projection consumed by data exporters."""
        rows = self.conn.execute(
            """
            SELECT code, trade_date AS date, open, close, high, low, volume, amount
            FROM index_daily
            ORDER BY code, trade_date
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def upsert_standard_bars(self, bars: Sequence[Bar]) -> int:
        """Project Standard Bars into existing bar tables, deriving change fields."""
        if not bars:
            return 0
        written = 0
        grouped: dict[tuple[str, str, str], list[Bar]] = {}
        for bar in bars:
            period = _INTERVAL_TO_PERIOD.get(bar.interval)
            if period is None:
                raise ValueError(f"不支持的 K 线周期: {bar.interval}")
            code = to_legacy_symbol(bar.instrument_id)
            adjust = persist_adjustment(bar.adjustment)
            grouped.setdefault((code, adjust, period), []).append(bar)
        for (code, adjust, period), group in grouped.items():
            ordered = sorted(group, key=lambda item: item.trade_date)
            prev_close = self._close_before(
                code,
                adjust=adjust,
                period=period,
                before=ordered[0].trade_date,
            )
            rows: list[tuple] = []
            for bar in ordered:
                change_amount, pct_chg, amplitude = derive_bar_change(
                    close=bar.close,
                    high=bar.high,
                    low=bar.low,
                    prev_close=prev_close,
                )
                rows.append(
                    (
                        code,
                        bar.trade_date.isoformat(),
                        bar.open,
                        bar.close,
                        bar.high,
                        bar.low,
                        bar.volume,
                        bar.amount,
                        amplitude,
                        pct_chg,
                        change_amount,
                        bar.turnover_pct,
                        adjust,
                    )
                )
                prev_close = bar.close
            written += self._upsert_bar_tuples(rows, period=period)
        return written

    def upsert_standard_index_bars(
        self,
        bars: Sequence[Bar],
        *,
        code: str,
        name: str,
    ) -> int:
        """Project Standard Bars into ``index_daily`` using the existing code/name keys."""
        if not bars:
            return 0
        rows = [
            (
                code,
                name,
                bar.trade_date.isoformat(),
                bar.open,
                bar.close,
                bar.high,
                bar.low,
                bar.volume,
                bar.amount,
            )
            for bar in sorted(bars, key=lambda item: item.trade_date)
        ]
        return self._upsert_index_bar_tuples(rows)

    def upsert_bars(self, rows: list[tuple], *, period: str = "daily") -> int:
        # Tuple compatibility for test fixtures and remaining writers.
        # Removed by Plan 08 once all writers use upsert_standard_bars.
        return self._upsert_bar_tuples(rows, period=period)

    def _upsert_bar_tuples(self, rows: list[tuple], *, period: str = "daily") -> int:
        if not rows:
            return 0
        table = BAR_TABLES.get(period)
        if table is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        with self.conn:
            self.conn.executemany(
                f"""
                INSERT INTO {table} (
                    code, trade_date, open, close, high, low,
                    volume, amount, amplitude, pct_chg, change_amount,
                    turnover, adjust
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, trade_date, adjust) DO UPDATE SET
                    open = excluded.open,
                    close = excluded.close,
                    high = excluded.high,
                    low = excluded.low,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    amplitude = excluded.amplitude,
                    pct_chg = excluded.pct_chg,
                    change_amount = excluded.change_amount,
                    turnover = excluded.turnover
                """,
                rows,
            )
        return len(rows)

    def upsert_index_bars(self, rows: list[tuple]) -> int:
        # Tuple compatibility for test fixtures and remaining writers.
        # Removed by Plan 08 once all writers use upsert_standard_index_bars.
        return self._upsert_index_bar_tuples(rows)

    def _upsert_index_bar_tuples(self, rows: list[tuple]) -> int:
        if not rows:
            return 0
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO index_daily (
                    code, name, trade_date, open, close, high, low, volume, amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, trade_date) DO UPDATE SET
                    name = excluded.name,
                    open = excluded.open,
                    close = excluded.close,
                    high = excluded.high,
                    low = excluded.low,
                    volume = excluded.volume,
                    amount = excluded.amount
                """,
                rows,
            )
        return len(rows)

    def _close_before(
        self,
        code: str,
        *,
        adjust: str,
        period: str,
        before: date,
    ) -> float | None:
        table = BAR_TABLES.get(period)
        if table is None:
            raise ValueError(f"不支持的 K 线周期: {period}")
        row = self.conn.execute(
            f"""
            SELECT close FROM {table}
            WHERE code = ? AND adjust = ? AND trade_date < ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (code, adjust, before.isoformat()),
        ).fetchone()
        if row is None or row["close"] is None:
            return None
        return float(row["close"])

    def mark_ingest(
        self,
        code: str,
        kind: str,
        status: str,
        *,
        adjust: str = DEFAULT_ADJUST,
        last_trade_date: str | None = None,
        rows: int = 0,
        error: str | None = None,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO ingest_state (
                    code, kind, adjust, last_trade_date, rows, status, error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, kind, adjust) DO UPDATE SET
                    last_trade_date = excluded.last_trade_date,
                    rows = ingest_state.rows + excluded.rows,
                    status = excluded.status,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (code, kind, adjust, last_trade_date, rows, status, error, now),
            )

    def counts(self, pool_id: str = DEFAULT_POOL_ID) -> dict[str, int]:
        tables = (
            "stocks",
            "trade_calendar",
            "bars_daily",
            "bars_weekly",
            "bars_monthly",
            "index_daily",
            "universe_members",
            "pool_members",
            "boards",
            "board_members",
        )
        out: dict[str, int] = {}
        for table in tables:
            row = self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            out[table] = int(row["n"])
        row = self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'removed' THEN 1 ELSE 0 END) AS removed
            FROM pool_members
            WHERE pool_id = ?
            """,
            (pool_id,),
        ).fetchone()
        out["pool_active"] = int(row["active"] or 0)
        out["pool_removed"] = int(row["removed"] or 0)
        row = self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error,
                SUM(CASE WHEN status = 'empty' THEN 1 ELSE 0 END) AS empty
            FROM ingest_state
            WHERE kind = 'stock'
            """
        ).fetchone()
        out["ingest_ok"] = int(row["ok"] or 0)
        out["ingest_error"] = int(row["error"] or 0)
        out["ingest_empty"] = int(row["empty"] or 0)
        return out
