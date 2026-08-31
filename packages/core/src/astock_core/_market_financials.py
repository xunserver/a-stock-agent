from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

from astock_core._market_base import _MarketBase, _ymd
from astock_core.financial_statements import (
    deserialize_statement_items,
    serialize_statement_items,
)
from astock_core.market_data import (
    FinancialPeriodType,
    FinancialStatement,
    FundamentalPeriod,
    to_legacy_symbol,
)

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_REPORT_TYPE_LABELS = {
    FinancialPeriodType.Q1: "一季报",
    FinancialPeriodType.H1: "中报",
    FinancialPeriodType.Q3: "三季报",
    FinancialPeriodType.FY: "年报",
}
_STOCK_FUNDAMENTAL_COLUMNS = (
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
)


def report_type_label(period_end, period_type: FinancialPeriodType) -> str:
    return f"{period_end.year}{_REPORT_TYPE_LABELS[period_type]}"


class _MarketFinancials(_MarketBase):
    def upsert_financial_reports(self, code: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        now = datetime.now().isoformat(timespec="seconds")
        payload: list[tuple] = []
        for row in rows:
            report_date = _ymd(row.get("report_date") or "")
            if not report_date:
                continue
            payload.append(
                (
                    code,
                    report_date,
                    row.get("report_type"),
                    row.get("notice_date"),
                    row.get("eps"),
                    row.get("bps"),
                    row.get("roe"),
                    row.get("revenue"),
                    row.get("revenue_yoy"),
                    row.get("net_profit"),
                    row.get("net_profit_yoy"),
                    row.get("gross_margin"),
                    row.get("net_margin"),
                    row.get("debt_ratio"),
                    now,
                )
            )
        if not payload:
            return 0
        self._insert_financial_report_rows(payload)
        return len(payload)

    def upsert_fundamental_periods(self, periods: Sequence[FundamentalPeriod]) -> int:
        """Project Fundamental Periods into ``financial_reports`` and latest ``stocks`` metrics."""
        if not periods:
            return 0
        now = datetime.now().isoformat(timespec="seconds")
        payload: list[tuple] = []
        codes: set[str] = set()
        for period in periods:
            code = to_legacy_symbol(period.instrument_id)
            codes.add(code)
            notice = None
            if period.announced_at is not None:
                notice = period.announced_at.astimezone(_SHANGHAI).date().isoformat()
            payload.append(
                (
                    code,
                    period.period_end.isoformat(),
                    report_type_label(period.period_end, period.period_type),
                    notice,
                    period.eps,
                    period.bps,
                    period.roe_pct,
                    period.revenue,
                    period.revenue_yoy_pct,
                    period.net_profit,
                    period.net_profit_yoy_pct,
                    period.gross_margin_pct,
                    period.net_margin_pct,
                    period.debt_ratio_pct,
                    now,
                )
            )
        if not payload:
            return 0
        self._insert_financial_report_rows(payload)
        for code in codes:
            self._project_latest_fundamental_to_stock(code)
        return len(payload)

    def _insert_financial_report_rows(self, payload: list[tuple]) -> None:
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO financial_reports (
                    code, report_date, report_type, notice_date,
                    eps, bps, roe, revenue, revenue_yoy,
                    net_profit, net_profit_yoy, gross_margin, net_margin,
                    debt_ratio, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, report_date) DO UPDATE SET
                    report_type = excluded.report_type,
                    notice_date = excluded.notice_date,
                    eps = excluded.eps,
                    bps = excluded.bps,
                    roe = excluded.roe,
                    revenue = excluded.revenue,
                    revenue_yoy = excluded.revenue_yoy,
                    net_profit = excluded.net_profit,
                    net_profit_yoy = excluded.net_profit_yoy,
                    gross_margin = excluded.gross_margin,
                    net_margin = excluded.net_margin,
                    debt_ratio = excluded.debt_ratio,
                    updated_at = excluded.updated_at
                """,
                payload,
            )

    def _project_latest_fundamental_to_stock(self, code: str) -> None:
        latest = self.list_financial_reports(code, limit=1)
        if not latest:
            return
        row = latest[0]
        self._upsert_stock_fields(
            code,
            **{column: row.get(column) for column in _STOCK_FUNDAMENTAL_COLUMNS},
        )

    def list_financial_reports(
        self,
        code: str,
        *,
        limit: int = 12,
    ) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT
                report_date, report_type, notice_date,
                eps, bps, roe, revenue, revenue_yoy,
                net_profit, net_profit_yoy, gross_margin, net_margin,
                debt_ratio, updated_at
            FROM financial_reports
            WHERE code = ?
            ORDER BY report_date DESC
            LIMIT ?
            """,
            (code, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def financial_report_count(self, code: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM financial_reports WHERE code = ?",
            (code,),
        ).fetchone()
        return int(row["c"]) if row else 0

    def latest_financial_report_date(self, code: str) -> str | None:
        row = self.conn.execute(
            """
            SELECT MAX(report_date) AS d
            FROM financial_reports
            WHERE code = ?
            """,
            (code,),
        ).fetchone()
        return row["d"] if row and row["d"] else None

    def upsert_financial_statements(self, code: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        now = datetime.now().isoformat(timespec="seconds")
        payload: list[tuple] = []
        for row in rows:
            report_date = _ymd(row.get("report_date") or "")
            sheet = str(row.get("sheet") or "").strip()
            raw_json = row.get("payload_json")
            if not report_date or not sheet or not raw_json:
                continue
            if isinstance(raw_json, dict):
                items = deserialize_statement_items(raw_json)
                raw_json = serialize_statement_items(items)
            else:
                items = deserialize_statement_items(str(raw_json))
                raw_json = serialize_statement_items(items)
            payload.append(
                (
                    code,
                    report_date,
                    sheet,
                    row.get("report_type"),
                    row.get("notice_date"),
                    str(raw_json),
                    now,
                )
            )
        if not payload:
            return 0
        self._insert_financial_statement_rows(payload)
        return len(payload)

    def upsert_standard_statements(self, statements: Sequence[FinancialStatement]) -> int:
        """Project Financial Statements into ``financial_statements`` as normalized items."""
        if not statements:
            return 0
        now = datetime.now().isoformat(timespec="seconds")
        payload: list[tuple] = []
        for statement in statements:
            notice = None
            if statement.announced_at is not None:
                notice = statement.announced_at.astimezone(_SHANGHAI).date().isoformat()
            payload.append(
                (
                    to_legacy_symbol(statement.instrument_id),
                    statement.period_end.isoformat(),
                    statement.sheet.value,
                    report_type_label(statement.period_end, statement.period_type),
                    notice,
                    serialize_statement_items(statement.items),
                    now,
                )
            )
        self._insert_financial_statement_rows(payload)
        return len(payload)

    def _insert_financial_statement_rows(self, payload: list[tuple]) -> None:
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO financial_statements (
                    code, report_date, sheet, report_type, notice_date,
                    payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, report_date, sheet) DO UPDATE SET
                    report_type = excluded.report_type,
                    notice_date = excluded.notice_date,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                payload,
            )

    def list_financial_statement_dates(
        self,
        code: str,
        sheet: str,
        *,
        limit: int = 12,
    ) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT report_date
            FROM financial_statements
            WHERE code = ? AND sheet = ?
            ORDER BY report_date DESC
            LIMIT ?
            """,
            (code, sheet, limit),
        ).fetchall()
        return [str(row["report_date"]) for row in rows]

    def get_financial_statement(
        self,
        code: str,
        report_date: str,
        sheet: str,
    ) -> dict | None:
        row = self.conn.execute(
            """
            SELECT
                code, report_date, sheet, report_type, notice_date,
                payload_json, updated_at
            FROM financial_statements
            WHERE code = ? AND report_date = ? AND sheet = ?
            """,
            (code, _ymd(report_date), sheet),
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        raw = data.pop("payload_json")
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except json.JSONDecodeError:
            parsed = {}
        items = deserialize_statement_items(parsed)
        data["items"] = [
            {
                "code": item.code,
                "label": item.label,
                "value": item.value,
                "unit": item.unit.value,
                "yoy_pct": item.yoy_pct,
                "qoq_pct": item.qoq_pct,
            }
            for item in items
        ]
        data["payload"] = {
            item.code: item.value
            for item in items
        }
        for item in items:
            if item.yoy_pct is not None:
                data["payload"][f"{item.code}_yoy"] = item.yoy_pct
            if item.qoq_pct is not None:
                data["payload"][f"{item.code}_qoq"] = item.qoq_pct
        return data

    def financial_statement_summary(self, code: str) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        for sheet in ("balance", "profit", "cashflow"):
            row = self.conn.execute(
                """
                SELECT COUNT(*) AS c, MAX(report_date) AS latest
                FROM financial_statements
                WHERE code = ? AND sheet = ?
                """,
                (code, sheet),
            ).fetchone()
            out[sheet] = {
                "count": int(row["c"]) if row else 0,
                "latest_report_date": row["latest"] if row and row["latest"] else None,
            }
        return out
