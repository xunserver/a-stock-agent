from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astock_core.db import MarketDB


REPORT_LIST_LIMIT = 100
REPORT_MD_FILES = (
    ("complete_report", "complete_report.md"),
    ("market", "1_analysts/market.md"),
    ("social", "1_analysts/social.md"),
    ("news", "1_analysts/news.md"),
    ("fundamentals", "1_analysts/fundamentals.md"),
    ("bull", "2_research/bull.md"),
    ("bear", "2_research/bear.md"),
    ("manager", "2_research/manager.md"),
    ("trader", "3_trading/trader.md"),
    ("aggressive", "4_risk/aggressive.md"),
    ("conservative", "4_risk/conservative.md"),
    ("neutral", "4_risk/neutral.md"),
    ("portfolio", "5_portfolio/decision.md"),
)


def analyze_list_query(
    *, code: str | None = None, analyze_dir: Path, db_path: Path
) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    root = analyze_dir / "reports"
    if root.is_dir():
        for meta_path in root.rglob("meta.json"):
            item = _read_meta_summary(meta_path)
            if item is None:
                continue
            if code and item.get("code") != code:
                continue
            reports.append(item)
    reports.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    reports = reports[:REPORT_LIST_LIMIT]
    names = _stock_names(
        {str(item.get("code") or "") for item in reports if item.get("code")},
        db_path,
    )
    for item in reports:
        item["name"] = names.get(str(item.get("code") or ""), "")
    return {"count": len(reports), "reports": reports}


def analyze_get_query(
    *,
    code: str,
    date: str,
    run_id: str | None = None,
    analyze_dir: Path,
    db_path: Path,
) -> dict[str, Any]:
    run_dir = _resolve_run_dir(code, date, run_id, analyze_dir)
    meta_path = run_dir / "meta.json"
    if not meta_path.is_file():
        raise ValueError(_missing_report_message(code, date, run_id))
    meta = _load_meta(meta_path)
    if meta is None:
        raise ValueError(_missing_report_message(code, date, run_id))
    names = _stock_names({code}, db_path)
    payload: dict[str, Any] = {
        "code": meta.get("code") or code,
        "ticker": meta.get("ticker") or "",
        "name": names.get(code, ""),
        "date": meta.get("date") or date,
        "run_id": meta.get("run_id") or run_dir.name,
        "analysts": meta.get("analysts")
        if isinstance(meta.get("analysts"), list)
        else [],
        "created_at": meta.get("created_at") or "",
        "status": meta.get("status") or "",
        "decision": meta.get("decision") or "",
        "report_dir": str(run_dir),
    }
    for key, relative in REPORT_MD_FILES:
        path = run_dir / relative
        if path.is_file():
            try:
                payload[key] = path.read_text(encoding="utf-8")
            except OSError:
                continue
    return payload


def _resolve_run_dir(
    code: str, date: str, run_id: str | None, analyze_dir: Path
) -> Path:
    day_dir = analyze_dir / "reports" / code / date
    if run_id:
        return day_dir / run_id
    if not day_dir.is_dir():
        raise ValueError(_missing_report_message(code, date, run_id))
    candidates: list[tuple[str, Path]] = []
    for meta_path in day_dir.glob("*/meta.json"):
        meta = _load_meta(meta_path)
        created = str((meta or {}).get("created_at") or "")
        candidates.append((created, meta_path.parent))
    if not candidates:
        raise ValueError(_missing_report_message(code, date, run_id))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _read_meta_summary(meta_path: Path) -> dict[str, Any] | None:
    meta = _load_meta(meta_path)
    if meta is None:
        return None
    run_dir = meta_path.parent
    code = str(meta.get("code") or _path_code(run_dir) or "")
    date = str(meta.get("date") or _path_date(run_dir) or "")
    run_id = str(meta.get("run_id") or run_dir.name)
    return {
        "code": code,
        "ticker": str(meta.get("ticker") or ""),
        "name": str(meta.get("name") or ""),
        "date": date,
        "run_id": run_id,
        "decision": str(meta.get("decision") or ""),
        "created_at": str(meta.get("created_at") or ""),
        "status": str(meta.get("status") or ""),
        "report_dir": str(run_dir),
    }


def _load_meta(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _path_code(run_dir: Path) -> str:
    try:
        return run_dir.parent.parent.name
    except IndexError:
        return ""


def _path_date(run_dir: Path) -> str:
    try:
        return run_dir.parent.name
    except IndexError:
        return ""


def _stock_names(codes: set[str], db_path: Path) -> dict[str, str]:
    names = {code: "" for code in codes if code}
    if not names or not db_path.is_file():
        return names
    try:
        with MarketDB(db_path) as db:
            names.update(db.stock_names(set(names)))
    except OSError:
        return names
    return names


def _missing_report_message(code: str, date: str, run_id: str | None) -> str:
    if run_id:
        return f"找不到分析报告: {code} {date} {run_id}"
    return f"找不到分析报告: {code} {date}"
