from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from astock_core._market_base import _MarketBase, _preview_codes
from astock_core.market_data import (
    Classification,
    Instrument,
    InstrumentProfile,
    Membership,
    QuoteSnapshot,
    ValuationSnapshot,
    board_rows_from_classifications,
    membership_codes,
    membership_code_name_pairs,
    normalize_board_taxonomy,
    to_legacy_symbol,
)
from astock_core.market_data.taxonomies import DEFAULT_BOARD_TAXONOMY
from astock_core.paths import DEFAULT_ADJUST


class _MarketStocks(_MarketBase):
    def upsert_stock_profile(self, code: str, *, name: str, **fields: object) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        allowed = {
            "industry",
            "list_date",
            "total_shares",
            "float_shares",
            "total_mv",
            "float_mv",
            "latest_price",
            "is_st",
            "is_suspended",
            "suspend_info",
            "region",
            "pe_dyn",
            "pe_static",
            "pb",
            "volume_ratio",
            "high_limit",
            "low_limit",
            "pre_close",
            "avg_price",
            "outer_vol",
            "inner_vol",
            "eps",
            "bps",
            "roe",
            "revenue",
            "revenue_yoy",
            "net_profit",
            "net_profit_yoy",
            "gross_margin",
            "net_margin",
            "debt_ratio",
        }
        data = {key: fields[key] for key in allowed if key in fields}
        assignments = ", ".join(f"{key} = excluded.{key}" for key in ("name", *data))
        columns = ["code", "name", *data, "updated_at"]
        values = [code, name, *data.values(), now]
        placeholders = ", ".join("?" * len(columns))
        with self.conn:
            self.conn.execute(
                f"""
                INSERT INTO stocks ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(code) DO UPDATE SET
                    {assignments},
                    updated_at = excluded.updated_at
                """,
                values,
            )

    def _upsert_stock_fields(
        self,
        code: str,
        *,
        name: str | None = None,
        keep_none: frozenset[str] = frozenset(),
        **fields: object,
    ) -> None:
        """Write selected ``stocks`` columns without nulling omitted capabilities.

        ``updated_at`` is the legacy table's single freshness column. Each
        Dataset still retains its own ``fetched_at``. Fields listed in
        ``keep_none`` are written even when the value is ``None``.
        """
        now = datetime.now().isoformat(timespec="seconds")
        existing = self.get_stock(code) or {}
        resolved_name = name or existing.get("name") or code
        data = {
            key: value
            for key, value in fields.items()
            if value is not None or key in keep_none
        }
        assignments = ", ".join(f"{key} = excluded.{key}" for key in ("name", *data))
        columns = ["code", "name", *data, "updated_at"]
        values = [code, resolved_name, *data.values(), now]
        placeholders = ", ".join("?" * len(columns))
        with self.conn:
            self.conn.execute(
                f"""
                INSERT INTO stocks ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(code) DO UPDATE SET
                    {assignments},
                    updated_at = excluded.updated_at
                """,
                values,
            )

    def upsert_instruments(self, instruments: Sequence[Instrument]) -> int:
        """Project Instruments into the existing ``stocks`` catalog columns."""
        if not instruments:
            return 0
        return self.replace_stocks(
            [(to_legacy_symbol(item.id), item.name) for item in instruments]
        )

    def upsert_instrument_profiles(self, profiles: Sequence[InstrumentProfile]) -> int:
        """Project Instrument Profiles into descriptive ``stocks`` columns."""
        written = 0
        for profile in profiles:
            code = to_legacy_symbol(profile.instrument_id)
            self._upsert_stock_fields(
                code,
                name=profile.name,
                industry=profile.industry,
                region=profile.region,
                list_date=profile.list_date.isoformat() if profile.list_date else None,
                is_st=1 if profile.is_st else 0,
            )
            written += 1
        return written

    def upsert_quote_snapshots(self, snapshots: Sequence[QuoteSnapshot]) -> int:
        """Project Quote Snapshots into quote/status ``stocks`` columns."""
        written = 0
        for snapshot in snapshots:
            code = to_legacy_symbol(snapshot.instrument_id)
            self._upsert_stock_fields(
                code,
                latest_price=snapshot.last_price,
                pre_close=snapshot.pre_close,
                avg_price=snapshot.average_price,
                high_limit=snapshot.high_limit,
                low_limit=snapshot.low_limit,
                volume_ratio=snapshot.volume_ratio,
                outer_vol=snapshot.outer_volume,
                inner_vol=snapshot.inner_volume,
                is_suspended=1 if snapshot.is_suspended else 0,
                suspend_info=snapshot.suspend_reason,
                keep_none=frozenset({"suspend_info"}),
            )
            written += 1
        return written

    def upsert_valuation_snapshots(self, snapshots: Sequence[ValuationSnapshot]) -> int:
        """Project Valuation Snapshots into shares/market-cap ``stocks`` columns."""
        written = 0
        for snapshot in snapshots:
            code = to_legacy_symbol(snapshot.instrument_id)
            self._upsert_stock_fields(
                code,
                total_shares=snapshot.total_shares,
                float_shares=snapshot.float_shares,
                total_mv=snapshot.total_market_cap,
                float_mv=snapshot.float_market_cap,
                pe_dyn=snapshot.pe_ttm,
                pe_static=snapshot.pe_static,
                pb=snapshot.pb,
            )
            written += 1
        return written

    def get_stock(self, code: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM stocks WHERE code = ?",
            (code,),
        ).fetchone()
        return dict(row) if row else None

    def stock_names(self, codes: list[str] | set[str] | None = None) -> dict[str, str]:
        """Return the stock catalog projection used by adapters and reports."""
        if codes is not None and not codes:
            return {}
        params: list[str] = []
        sql = "SELECT code, name FROM stocks"
        if codes is not None:
            params = sorted(set(codes))
            sql += f" WHERE code IN ({','.join('?' for _ in params)})"
        rows = self.conn.execute(sql, params).fetchall()
        return {str(row["code"]): str(row["name"] or "") for row in rows}

    def profile_filled_count(self, pool_id: str | None = None) -> int:
        if pool_id is None:
            row = self.conn.execute(
                """
                SELECT COUNT(*) AS n FROM stocks
                WHERE industry IS NOT NULL AND industry != ''
                """
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM pool_members m
                JOIN stocks s ON s.code = m.code
                WHERE m.pool_id = ? AND m.status = 'active'
                  AND s.industry IS NOT NULL AND s.industry != ''
                """,
                (pool_id,),
            ).fetchone()
        return int(row["n"] or 0)

    def replace_stocks(self, stocks: list[tuple[str, str]]) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        payload = [(code, name, now) for code, name in stocks]
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO stocks (code, name, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return len(payload)

    def stock_codes(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT code FROM stocks ORDER BY code"
        ).fetchall()
        return [row["code"] for row in rows]

    def upsert_boards(self, rows: list[tuple[str, str, str, str]]) -> int:
        """rows: (id, kind, name, source)."""
        if not rows:
            return 0
        now = datetime.now().isoformat(timespec="seconds")
        payload = [(board_id, kind, name, source, now) for board_id, kind, name, source in rows]
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO boards (id, kind, name, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kind = excluded.kind,
                    name = excluded.name,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return len(payload)

    def replace_board_members(self, board_id: str, codes: list[str]) -> int:
        """按板块替换成员；只保留已在 stocks 表中的代码。"""
        now = datetime.now().isoformat(timespec="seconds")
        unique = sorted({str(code).zfill(6) for code in codes if str(code).strip()})
        if unique:
            placeholders = ",".join("?" for _ in unique)
            allowed = {
                row["code"]
                for row in self.conn.execute(
                    f"SELECT code FROM stocks WHERE code IN ({placeholders})",
                    unique,
                ).fetchall()
            }
            unique = sorted(code for code in unique if code in allowed)
        with self.conn:
            self.conn.execute("DELETE FROM board_members WHERE board_id = ?", (board_id,))
            if unique:
                self.conn.executemany(
                    """
                    INSERT INTO board_members (board_id, code, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    [(board_id, code, now) for code in unique],
                )
        return len(unique)

    def upsert_classifications(self, classifications: Sequence[Classification]) -> int:
        """Project Classifications into the legacy boards table."""
        return self.upsert_boards(board_rows_from_classifications(classifications))

    def replace_classification_members(
        self,
        classification: Classification,
        memberships: Sequence[Membership],
        *,
        allowed_codes: set[str] | None = None,
    ) -> int:
        """Replace board members for one Classification."""
        codes = membership_codes(memberships)
        if allowed_codes is not None:
            codes = sorted(code for code in codes if code in allowed_codes)
        return self.replace_board_members(classification.id, codes)

    def replace_universe_memberships(
        self,
        universe: str,
        memberships: Sequence[Membership],
        *,
        names: dict[str, str] | None = None,
    ) -> int:
        """Project Memberships into universe_members."""
        return self.replace_universe(
            universe,
            membership_code_name_pairs(memberships, names=names),
        )

    def list_boards(
        self,
        *,
        kind: str | None = None,
        source: str | None = DEFAULT_BOARD_TAXONOMY,
    ) -> list[dict]:
        resolved = normalize_board_taxonomy(source)
        clauses: list[str] = []
        params: list[str] = []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if resolved:
            clauses.append("source = ?")
            params.append(resolved)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"""
            SELECT id, kind, name, source, updated_at
            FROM boards
            {where}
            ORDER BY kind, name
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def boards_for_code(
        self,
        code: str,
        *,
        source: str | None = DEFAULT_BOARD_TAXONOMY,
    ) -> list[dict]:
        resolved = normalize_board_taxonomy(source)
        params: list[str] = [code.zfill(6)]
        source_clause = ""
        if resolved:
            source_clause = "AND b.source = ?"
            params.append(resolved)
        rows = self.conn.execute(
            f"""
            SELECT b.id, b.kind, b.name, b.source, b.updated_at
            FROM board_members m
            JOIN boards b ON b.id = m.board_id
            WHERE m.code = ? {source_clause}
            ORDER BY b.kind, b.name
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def list_stocks(self, *, adjust: str = DEFAULT_ADJUST) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT
                s.code,
                s.name,
                s.industry,
                s.is_st,
                s.is_suspended,
                (
                    SELECT MAX(b.trade_date)
                    FROM bars_daily b
                    WHERE b.code = s.code AND b.adjust = ?
                ) AS last_bar
            FROM stocks s
            ORDER BY s.code
            """,
            (adjust,),
        ).fetchall()
        pool_rows = self.conn.execute(
            """
            SELECT m.code, p.id, p.name
            FROM pool_members m
            JOIN pools p ON p.id = m.pool_id
            WHERE m.status = 'active'
            ORDER BY p.id
            """
        ).fetchall()
        pools_by_code: dict[str, list[dict]] = {}
        for row in pool_rows:
            pools_by_code.setdefault(row["code"], []).append(
                {"id": row["id"], "name": row["name"]}
            )
        return [
            {
                "code": row["code"],
                "name": row["name"],
                "industry": row["industry"],
                "is_st": int(row["is_st"] or 0),
                "is_suspended": int(row["is_suspended"] or 0),
                "last_bar": row["last_bar"],
                "pools": pools_by_code.get(row["code"], []),
            }
            for row in rows
        ]

    def add_stocks(self, stocks: list[tuple[str, str]]) -> dict[str, int]:
        catalog = set(self.stock_codes())
        added = 0
        unchanged = 0
        seen: set[str] = set()
        unique: list[tuple[str, str]] = []
        for code, name in stocks:
            if code in seen:
                continue
            seen.add(code)
            unique.append((code, name))
            if code in catalog:
                unchanged += 1
            else:
                added += 1
        if unique:
            self.replace_stocks(unique)
        return {"added": added, "unchanged": unchanged, "count": len(self.stock_codes())}

    def remove_stocks(self, codes: list[str]) -> dict:
        catalog = set(self.stock_codes())
        missing = [code for code in codes if code not in catalog]
        present = [code for code in codes if code in catalog]
        blocked: list[tuple[str, list[dict]]] = []
        removable: list[str] = []
        for code in present:
            pools = self.active_pools_for_code(code)
            if pools:
                blocked.append((code, pools))
            else:
                removable.append(code)
        if blocked:
            parts = []
            for code, pools in blocked:
                names = "、".join(str(pool["name"] or pool["id"]) for pool in pools)
                parts.append(f"{code}（{names}）")
            raise ValueError(f"这些股票还在股票池里，不能从系统移除: {'; '.join(parts)}")
        if not removable:
            raise ValueError(f"找不到股票: {_preview_codes(missing)}")
        with self.conn:
            for code in removable:
                self.conn.execute("DELETE FROM pool_members WHERE code = ?", (code,))
                self.conn.execute("DELETE FROM stocks WHERE code = ?", (code,))
        return {"removed": len(removable), "missing": len(missing), "codes": removable}

    def replace_universe(self, universe: str, members: list[tuple[str, str]]) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        payload = [(universe, code, name, now) for code, name in members]
        with self.conn:
            self.conn.execute(
                "DELETE FROM universe_members WHERE universe = ?",
                (universe,),
            )
            self.conn.executemany(
                """
                INSERT INTO universe_members (universe, code, name, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                payload,
            )
        return len(payload)

    def universe_codes(self, universe: str) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT code FROM universe_members
            WHERE universe = ?
            ORDER BY code
            """,
            (universe,),
        ).fetchall()
        return [row["code"] for row in rows]

    def universe_size(self, universe: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM universe_members WHERE universe = ?",
            (universe,),
        ).fetchone()
        return int(row["n"])
