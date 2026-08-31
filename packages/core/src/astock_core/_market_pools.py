from __future__ import annotations

from datetime import datetime

from astock_core._market_base import _MarketBase, _POOL_ID_RE, _preview_codes, _quote_sync_fields
from astock_core.paths import DEFAULT_ADJUST, DEFAULT_POOL_ID

class _MarketPools(_MarketBase):
    def pool_membership(self, pool_id: str, code: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT * FROM pool_members
            WHERE pool_id = ? AND code = ?
            """,
            (pool_id, code),
        ).fetchone()
        return dict(row) if row else None

    def active_pools_for_code(self, code: str) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT p.id, p.name
            FROM pool_members m
            JOIN pools p ON p.id = m.pool_id
            WHERE m.code = ? AND m.status = 'active'
            ORDER BY p.id
            """,
            (code,),
        ).fetchall()
        return [{"id": row["id"], "name": row["name"]} for row in rows]

    def ensure_pool(self, pool_id: str = DEFAULT_POOL_ID, name: str = "默认股票池") -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO pools (id, name, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (pool_id, name, now),
            )

    def list_pools(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT
                p.id,
                p.name,
                p.created_at,
                COALESCE(SUM(CASE WHEN m.status = 'active' THEN 1 ELSE 0 END), 0) AS active,
                COALESCE(SUM(CASE WHEN m.status = 'removed' THEN 1 ELSE 0 END), 0) AS removed
            FROM pools p
            LEFT JOIN pool_members m ON m.pool_id = p.id
            GROUP BY p.id
            ORDER BY CASE WHEN p.id = ? THEN 0 ELSE 1 END, p.created_at, p.id
            """,
            (DEFAULT_POOL_ID,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "active": int(row["active"]),
                "removed": int(row["removed"]),
            }
            for row in rows
        ]

    def create_pool(self, pool_id: str, name: str = "") -> dict:
        pool_id = str(pool_id).strip()
        name = str(name).strip() or pool_id
        if not _POOL_ID_RE.match(pool_id):
            raise ValueError("池 id 只能是字母、数字、下划线和短横线，最长 32 位")
        existing = self.conn.execute(
            "SELECT id FROM pools WHERE id = ?",
            (pool_id,),
        ).fetchone()
        if existing is not None:
            raise ValueError(f"股票池已存在: {pool_id}")
        self.ensure_pool(pool_id, name)
        return {"pool": pool_id, "name": name, "created": True}

    def delete_pool(self, pool_id: str) -> dict:
        existing = self.conn.execute(
            "SELECT id FROM pools WHERE id = ?",
            (pool_id,),
        ).fetchone()
        if existing is None:
            raise ValueError(f"找不到股票池: {pool_id}")
        total = int(self.conn.execute("SELECT COUNT(*) AS n FROM pools").fetchone()["n"])
        if total <= 1:
            raise ValueError("至少保留一个股票池")
        members = int(
            self.conn.execute(
                "SELECT COUNT(*) AS n FROM pool_members WHERE pool_id = ?",
                (pool_id,),
            ).fetchone()["n"]
        )
        with self.conn:
            self.conn.execute("DELETE FROM pool_members WHERE pool_id = ?", (pool_id,))
            self.conn.execute("DELETE FROM pools WHERE id = ?", (pool_id,))
        return {"pool": pool_id, "deleted": True, "members_cleared": members}

    def _migrate_universe_into_default_pool(self) -> None:
        existing = self.conn.execute(
            "SELECT COUNT(*) AS n FROM pool_members WHERE pool_id = ?",
            (DEFAULT_POOL_ID,),
        ).fetchone()
        if existing and int(existing["n"]) > 0:
            return
        rows = self.conn.execute(
            """
            SELECT code, name FROM universe_members
            WHERE universe = 'hs300'
            ORDER BY code
            """
        ).fetchall()
        if not rows:
            return
        members = [(row["code"], row["name"]) for row in rows]
        self.replace_stocks(members)
        self.add_pool_members(DEFAULT_POOL_ID, members, source="index:000300")

    def add_pool_members(
        self,
        pool_id: str,
        members: list[tuple[str, str]],
        *,
        source: str = "manual",
    ) -> dict[str, int]:
        self.ensure_pool(pool_id)
        if members:
            catalog = set(self.stock_codes())
            missing = [code for code, _ in members if code not in catalog]
            if missing:
                raise ValueError(
                    "这些股票还不在系统里，请先在股票管理中加入: "
                    f"{_preview_codes(missing)}"
                )
        now = datetime.now().isoformat(timespec="seconds")
        added = 0
        reactivated = 0
        unchanged = 0
        with self.conn:
            next_order = self._next_pool_sort_order(pool_id)
            for code, name in members:
                row = self.conn.execute(
                    """
                    SELECT status FROM pool_members
                    WHERE pool_id = ? AND code = ?
                    """,
                    (pool_id, code),
                ).fetchone()
                if row is None:
                    self.conn.execute(
                        """
                        INSERT INTO pool_members (
                            pool_id, code, name, status, source,
                            first_added_at, last_added_at, removed_at, sort_order
                        ) VALUES (?, ?, ?, 'active', ?, ?, ?, NULL, ?)
                        """,
                        (pool_id, code, name, source, now, now, next_order),
                    )
                    added += 1
                    next_order += 1
                elif row["status"] == "removed":
                    self.conn.execute(
                        """
                        UPDATE pool_members
                        SET name = ?, status = 'active', source = ?,
                            last_added_at = ?, removed_at = NULL, sort_order = ?
                        WHERE pool_id = ? AND code = ?
                        """,
                        (name, source, now, next_order, pool_id, code),
                    )
                    reactivated += 1
                    next_order += 1
                else:
                    self.conn.execute(
                        """
                        UPDATE pool_members
                        SET name = ?, source = ?
                        WHERE pool_id = ? AND code = ?
                        """,
                        (name, source, pool_id, code),
                    )
                    unchanged += 1
        return {"added": added, "reactivated": reactivated, "unchanged": unchanged}

    def _next_pool_sort_order(self, pool_id: str) -> int:
        row = self.conn.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) + 1 AS n
            FROM pool_members
            WHERE pool_id = ?
            """,
            (pool_id,),
        ).fetchone()
        return int(row["n"])

    def reorder_pool_members(self, pool_id: str, codes: list[str]) -> dict[str, int]:
        if not codes:
            raise ValueError("排序需要至少一只股票")
        if len(codes) != len(set(codes)):
            raise ValueError("排序列表不能有重复代码")
        active = self.active_pool_codes(pool_id)
        wanted = set(codes)
        current = set(active)
        extra = wanted - current
        missing = current - wanted
        if extra or missing:
            parts: list[str] = []
            if extra:
                parts.append(f"不在池中: {_preview_codes(sorted(extra))}")
            if missing:
                parts.append(f"缺少: {_preview_codes(sorted(missing))}")
            raise ValueError("排序必须覆盖当前全部成员。" + "；".join(parts))
        with self.conn:
            for index, code in enumerate(codes):
                self.conn.execute(
                    """
                    UPDATE pool_members
                    SET sort_order = ?
                    WHERE pool_id = ? AND code = ?
                    """,
                    (index, pool_id, code),
                )
        return {"count": len(codes)}

    def remove_pool_members(self, pool_id: str, codes: list[str]) -> dict[str, int]:
        now = datetime.now().isoformat(timespec="seconds")
        removed = 0
        missing = 0
        already = 0
        with self.conn:
            for code in codes:
                row = self.conn.execute(
                    """
                    SELECT status FROM pool_members
                    WHERE pool_id = ? AND code = ?
                    """,
                    (pool_id, code),
                ).fetchone()
                if row is None:
                    missing += 1
                    continue
                if row["status"] == "removed":
                    already += 1
                    continue
                self.conn.execute(
                    """
                    UPDATE pool_members
                    SET status = 'removed', removed_at = ?
                    WHERE pool_id = ? AND code = ?
                    """,
                    (now, pool_id, code),
                )
                removed += 1
        return {"removed": removed, "already_removed": already, "missing": missing}

    def set_pool_members(
        self,
        pool_id: str,
        members: list[tuple[str, str]],
        *,
        source: str,
    ) -> dict[str, int]:
        wanted = {code for code, _ in members}
        result = self.add_pool_members(pool_id, members, source=source)
        extra = [
            code
            for code in self.active_pool_codes(pool_id)
            if code not in wanted
        ]
        removed = self.remove_pool_members(pool_id, extra)
        result["removed"] = removed["removed"]
        return result

    def active_pool_codes(self, pool_id: str = DEFAULT_POOL_ID) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT code FROM pool_members
            WHERE pool_id = ? AND status = 'active'
            ORDER BY sort_order, code
            """,
            (pool_id,),
        ).fetchall()
        return [row["code"] for row in rows]

    def list_pool_members(
        self,
        pool_id: str = DEFAULT_POOL_ID,
        *,
        include_removed: bool = False,
        adjust: str = DEFAULT_ADJUST,
    ) -> list[dict]:
        sql = """
            SELECT
                m.code,
                m.name,
                m.status,
                m.source,
                m.first_added_at,
                m.last_added_at,
                m.removed_at,
                m.sort_order,
                (
                    SELECT MAX(b.trade_date)
                    FROM bars_daily b
                    WHERE b.code = m.code AND b.adjust = ?
                ) AS last_bar
            FROM pool_members m
            WHERE m.pool_id = ?
        """
        params: list = [adjust, pool_id]
        if not include_removed:
            sql += " AND m.status = 'active'"
        sql += " ORDER BY m.status, m.sort_order, m.code"
        rows = self.conn.execute(sql, params).fetchall()
        last_cal = self.current_trade_date()
        members = []
        for row in rows:
            item = dict(row)
            item.update(_quote_sync_fields(item.get("last_bar"), last_cal))
            members.append(item)
        return members

    def pool_quote_plan(
        self,
        pool_id: str = DEFAULT_POOL_ID,
        *,
        adjust: str = DEFAULT_ADJUST,
        now: datetime | None = None,
    ) -> dict[str, list[str]]:
        last_cal = self.current_trade_date(now=now)
        full: list[str] = []
        fill: list[str] = []
        current: list[str] = []
        for code in self.active_pool_codes(pool_id):
            last = self.last_bar_date(code, adjust=adjust)
            if last is None:
                full.append(code)
            elif last_cal and last >= last_cal:
                current.append(code)
            else:
                fill.append(code)
        return {"full": full, "fill": fill, "current": current}
