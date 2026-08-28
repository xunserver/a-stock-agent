from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from astock_core.db import MarketDB
from astock_core.paths import DB_PATH, REPO_ROOT, pool_qlib_dir

from astock_qlib.dump import pool_data_ready, prepare_pool_qlib
from astock_qlib.ranking import top_scores
from astock_qlib.workflow import run_workflow

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"
CONFIG_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def resolve_config_path(name: str) -> Path:
    config_name = str(name).strip()
    if not CONFIG_NAME_RE.fullmatch(config_name):
        raise ValueError("workflow 配置名只能包含字母、数字、下划线和短横线")
    path = CONFIG_DIR / f"{config_name}.yaml"
    if not path.is_file():
        raise ValueError(f"找不到 workflow 配置: {config_name}")
    return path


def _pred_snapshot(root: Path) -> dict[Path, int]:
    return {path: path.stat().st_mtime_ns for path in root.rglob("pred.pkl")}


def _changed_prediction(root: Path, before: dict[Path, int]) -> Path:
    changed = [
        path
        for path in root.rglob("pred.pkl")
        if before.get(path) != path.stat().st_mtime_ns
    ]
    if not changed:
        raise RuntimeError("workflow 完成，但没有生成本次 pred.pkl")
    return max(changed, key=lambda path: path.stat().st_mtime_ns)


def prepare_pool_data(*, pool_id: str, benchmark: str) -> dict[str, Any]:
    """Dump market.db rows for one pool into its dedicated Qlib directory."""
    with MarketDB(DB_PATH) as db:
        return prepare_pool_qlib(db, pool_id=pool_id, benchmark=benchmark)


def run_selection(
    *,
    pool_id: str,
    run_id: str,
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Run workflow on prepared pool data and return one immutable candidate result."""
    pool_dir = pool_qlib_dir(pool_id)
    if not pool_data_ready(pool_id):
        raise ValueError(f"请先为股票池 {pool_id} 准备量化数据")

    with MarketDB(DB_PATH) as db:
        pool_codes = set(db.active_pool_codes(pool_id))
        if not pool_codes:
            raise ValueError(f"股票池没有活跃成员: {pool_id}")

    config_path = resolve_config_path(str(workflow["config"]))
    mlruns = REPO_ROOT / "mlruns"
    mlruns.mkdir(parents=True, exist_ok=True)
    before = _pred_snapshot(mlruns)
    experiment = f"astock_{pool_id}_{run_id}"
    topk = min(int(workflow["topk"]), len(pool_codes))
    run_workflow(
        config_path,
        experiment_name=experiment,
        uri_folder=mlruns,
        provider_uri=pool_dir,
        market=pool_id,
        benchmark=str(workflow["benchmark"]),
        topk=topk,
        n_drop=int(workflow["n_drop"]),
        account=float(workflow["account"]),
        data_end=_optional_str(workflow.get("data_end")),
        test_start=_optional_str(workflow.get("test_start")),
        learning_rate=_optional_float(workflow.get("learning_rate")),
    )
    pred_path = _changed_prediction(mlruns, before)
    ranked = top_scores(
        topk,
        pred_path=pred_path,
        pool_codes=pool_codes,
    )
    return {
        "ok": True,
        "run_id": run_id,
        "job_id": run_id,
        "pool": pool_id,
        "workflow": dict(workflow),
        "as_of": ranked["as_of"],
        "artifact_ref": str(pred_path),
        "universe_size": len(pool_codes),
        "candidates": ranked["top"],
        "data": {"qlib_dir": str(pool_dir), "pool_members": len(pool_codes)},
        "experiment": experiment,
    }


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip() or None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
