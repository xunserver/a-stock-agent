from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

from astock_core.paths import QLIB_DIR, REPO_ROOT

DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[2] / "configs" / "workflow_lightgbm_alpha158.yaml"
)


def run_workflow(
    config_path: Path | None = None,
    *,
    experiment_name: str = "astock_lightgbm",
    uri_folder: Path | None = None,
) -> Path:
    """用本仓库 data/qlib 跑官方 LightGBM+Alpha158 workflow。"""
    from qlib.cli.run import workflow

    src = Path(config_path or DEFAULT_CONFIG)
    if not src.is_file():
        raise FileNotFoundError(f"找不到 workflow 配置: {src}")
    if not (QLIB_DIR / "calendars" / "day.txt").is_file():
        raise FileNotFoundError(f"未找到 Qlib 数据，请先 dump：{QLIB_DIR}")

    # pyqlib 仍用本地 mlruns 目录；新版 mlflow 默认禁止 file store
    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

    cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
    cfg.setdefault("qlib_init", {})
    cfg["qlib_init"]["provider_uri"] = str(QLIB_DIR)
    cfg["qlib_init"]["region"] = "cn"

    mlruns = Path(uri_folder or (REPO_ROOT / "mlruns"))
    mlruns.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="astock_workflow_",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        yaml.safe_dump(cfg, tmp, sort_keys=False, allow_unicode=True)
        tmp_path = Path(tmp.name)

    try:
        workflow(str(tmp_path), experiment_name=experiment_name, uri_folder=str(mlruns))
    finally:
        tmp_path.unlink(missing_ok=True)
    return mlruns
