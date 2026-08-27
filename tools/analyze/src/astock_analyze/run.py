"""Run one TradingAgents graph and write reports under ANALYZE_DIR."""

from __future__ import annotations

import json
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from astock_core.db import MarketDB
from astock_core.paths import ANALYZE_DIR

from astock_analyze.codes import CodeError, parse_a_share
from astock_analyze.config import (
    VENDOR_DIR,
    AnalyzeError,
    AnalyzeSettings,
    apply_api_key_env,
    load_settings,
    redact_secret,
    validate_run_config,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


def progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def import_graph() -> tuple[Any, dict[str, Any]]:
    """Lazy import so status / fail-fast never load langchain."""
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    return TradingAgentsGraph, DEFAULT_CONFIG


def reports_root() -> Path:
    return ANALYZE_DIR / "reports"


def cache_dir() -> Path:
    return ANALYZE_DIR / "cache"


def memory_log_path() -> Path:
    return ANALYZE_DIR / "memory" / "trading_memory.md"


def write_meta(report_dir: Path, meta: dict[str, Any]) -> None:
    path = report_dir / "meta.json"
    path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def read_meta(report_dir: Path) -> dict[str, Any] | None:
    path = report_dir / "meta.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def shanghai_today() -> str:
    return datetime.now(SHANGHAI).date().isoformat()


def lookup_name(code: str) -> str:
    try:
        with MarketDB() as db:
            stock = db.get_stock(code)
    except OSError:
        return ""
    if not stock:
        return ""
    return str(stock.get("name") or "")


def default_trade_date(code: str) -> str:
    try:
        with MarketDB() as db:
            last = db.last_bar_date(code)
    except OSError:
        last = None
    return last or shanghai_today()


def ensure_in_pool(code: str, pool: str) -> None:
    try:
        with MarketDB() as db:
            member = db.pool_membership(pool, code)
    except OSError as exc:
        raise AnalyzeError(f"无法打开行情库以检查股票池: {exc}", exit_code=1) from exc
    if member is None or member.get("status") != "active":
        raise AnalyzeError(f"股票 {code} 不在股票池 {pool} 的活跃成员中")


def fill_graph_config(config: dict[str, Any], settings: AnalyzeSettings) -> dict[str, Any]:
    config["results_dir"] = str(reports_root())
    config["data_cache_dir"] = str(cache_dir())
    config["memory_log_path"] = str(memory_log_path())
    config["llm_provider"] = settings.llm_provider
    config["deep_think_llm"] = settings.deep_think_llm
    config["quick_think_llm"] = settings.quick_think_llm
    config["backend_url"] = settings.backend_url or None
    config["output_language"] = settings.output_language
    config["max_debate_rounds"] = settings.max_debate_rounds
    config["max_risk_discuss_rounds"] = settings.max_risk_discuss_rounds
    config["checkpoint_enabled"] = settings.checkpoint_enabled
    config["temperature"] = settings.temperature
    return config


def run_analysis(
    *,
    raw_code: str,
    date: str | None = None,
    analysts: list[str] | None = None,
    pool: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    try:
        code, ticker = parse_a_share(raw_code)
    except CodeError as exc:
        raise AnalyzeError(str(exc)) from exc

    settings = load_settings(analysts=analysts)
    validate_run_config(settings)

    if pool:
        ensure_in_pool(code, pool)

    trade_date = date or default_trade_date(code)
    _validate_date(trade_date)

    run_id = run_id or secrets.token_hex(6)
    report_dir = reports_root() / code / trade_date / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    cache_dir().mkdir(parents=True, exist_ok=True)
    memory_log_path().parent.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    name = lookup_name(code)
    meta: dict[str, Any] = {
        "code": code,
        "ticker": ticker,
        "name": name,
        "date": trade_date,
        "run_id": run_id,
        "analysts": list(settings.analysts),
        "created_at": created_at,
        "status": "running",
    }
    write_meta(report_dir, meta)

    started = time.perf_counter()
    try:
        progress(f"开始分析 {code} {ticker} {trade_date}")
        apply_api_key_env(settings)
        TradingAgentsGraph, default_config = import_graph()
        config = fill_graph_config(default_config.copy(), settings)
        progress("调用 TradingAgents")
        ta = TradingAgentsGraph(
            selected_analysts=tuple(settings.analysts),
            debug=False,
            config=config,
        )
        state, decision = ta.propagate(ticker, trade_date)
        progress("保存报告")
        ta.save_reports(state, ticker, save_path=report_dir)
        elapsed = round(time.perf_counter() - started, 3)
        meta.update(
            {
                "decision": decision,
                "status": "succeeded",
                "elapsed_seconds": elapsed,
                "finished_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            }
        )
        write_meta(report_dir, meta)
    except AnalyzeError as exc:
        _mark_failed(report_dir, meta, settings.api_key, str(exc))
        raise
    except Exception as exc:
        message = redact_secret(f"分析失败: {exc}", settings.api_key)
        _mark_failed(report_dir, meta, settings.api_key, message)
        raise AnalyzeError(message, exit_code=1) from exc

    complete_report = report_dir / "complete_report.md"
    return {
        "code": code,
        "ticker": ticker,
        "date": trade_date,
        "run_id": run_id,
        "decision": decision,
        "report_dir": str(report_dir),
        "complete_report": str(complete_report),
    }


def collect_status(*, recent: int = 10) -> dict[str, Any]:
    settings = load_settings()
    importable, import_error = _try_import_tradingagents()
    reports_dir = reports_root()
    return {
        "vendor_exists": _vendor_exists(),
        "tradingagents_importable": importable,
        "import_error": import_error,
        "llm_provider": settings.llm_provider,
        "api_key_set": settings.api_key_set,
        "backend_url_set": bool(settings.backend_url),
        "models_set": bool(settings.deep_think_llm and settings.quick_think_llm),
        "reports_dir": str(reports_dir),
        "reports_writable": _dir_writable(reports_dir),
        "recent_reports": list_recent_reports(limit=recent),
    }


def list_recent_reports(limit: int = 10) -> list[dict[str, Any]]:
    root = reports_root()
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for meta_path in root.glob("*/*/*/meta.json"):
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            items.append(payload)
    items.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return items[:limit]


def load_complete_report(raw_code: str, date: str, run_id: str | None = None) -> str:
    try:
        code, _ticker = parse_a_share(raw_code)
    except CodeError as exc:
        raise AnalyzeError(str(exc)) from exc
    _validate_date(date)
    report_dir = find_report_dir(code, date, run_id)
    path = report_dir / "complete_report.md"
    if not path.is_file():
        raise AnalyzeError(f"找不到完整报告: {path}", exit_code=1)
    return path.read_text(encoding="utf-8")


def find_report_dir(code: str, date: str, run_id: str | None) -> Path:
    day_dir = reports_root() / code / date
    if run_id:
        path = day_dir / run_id
        if not path.is_dir():
            raise AnalyzeError(f"找不到报告目录: {path}", exit_code=1)
        return path
    if not day_dir.is_dir():
        raise AnalyzeError(f"找不到 {code} 在 {date} 的报告", exit_code=1)
    ranked: list[tuple[str, float, Path]] = []
    for child in day_dir.iterdir():
        if not child.is_dir():
            continue
        meta = read_meta(child)
        created = str((meta or {}).get("created_at") or "")
        ranked.append((created, child.stat().st_mtime, child))
    if not ranked:
        raise AnalyzeError(f"找不到 {code} 在 {date} 的报告", exit_code=1)
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def _vendor_exists() -> bool:
    return VENDOR_DIR.is_dir()


def _try_import_tradingagents() -> tuple[bool, str]:
    # find_spec does not execute tradingagents/__init__.py, so status
    # does not pull langchain. The graph import stays in import_graph().
    import importlib.util

    spec = importlib.util.find_spec("tradingagents")
    if spec is None:
        return False, "找不到 tradingagents 包"
    return True, ""


def _dir_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True


def _validate_date(value: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise AnalyzeError(f"日期不合法: {value}，需要 YYYY-MM-DD") from exc


def _mark_failed(
    report_dir: Path,
    meta: dict[str, Any],
    secret: str,
    message: str,
) -> None:
    meta["status"] = "failed"
    meta["error"] = redact_secret(message, secret)
    meta["finished_at"] = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    try:
        write_meta(report_dir, meta)
    except OSError:
        pass
