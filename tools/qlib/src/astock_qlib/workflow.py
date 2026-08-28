from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import yaml
from astock_core.paths import QLIB_DIR, REPO_ROOT

DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[2] / "configs" / "workflow_lightgbm_alpha158.yaml"
)


@contextlib.contextmanager
def _silence_stdout_to_stderr() -> Iterator[None]:
    """Keep Qlib/LightGBM training noise off the process stdout for --json."""
    stdout_fd = sys.stdout.fileno()
    saved = os.dup(stdout_fd)
    try:
        os.dup2(sys.stderr.fileno(), stdout_fd)
        yield
    finally:
        os.dup2(saved, stdout_fd)
        os.close(saved)


def run_workflow(
    config_path: Path | None = None,
    *,
    experiment_name: str = "astock_lightgbm",
    uri_folder: Path | None = None,
    provider_uri: Path | str | None = None,
    market: str | None = None,
    benchmark: str | None = None,
    topk: int | None = None,
    n_drop: int | None = None,
    account: float | None = None,
    data_end: str | None = None,
    test_start: str | None = None,
    learning_rate: float | None = None,
) -> Path:
    """用本仓库 data/qlib 跑官方 LightGBM+Alpha158 workflow。"""
    from qlib.cli.run import workflow

    src = Path(config_path or DEFAULT_CONFIG)
    if not src.is_file():
        raise FileNotFoundError(f"找不到 workflow 配置: {src}")
    data_root = Path(provider_uri or QLIB_DIR)
    if not (data_root / "calendars" / "day.txt").is_file():
        raise FileNotFoundError(f"未找到 Qlib 数据，请先准备：{data_root}")

    # pyqlib 仍用本地 mlruns 目录；新版 mlflow 默认禁止 file store
    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

    cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
    cfg.setdefault("qlib_init", {})
    cfg["qlib_init"]["provider_uri"] = str(data_root)
    cfg["qlib_init"]["region"] = "cn"
    if market:
        cfg["market"] = market
        cfg.setdefault("data_handler_config", {})["instruments"] = market
        handler_kwargs = (
            cfg.setdefault("task", {})
            .setdefault("dataset", {})
            .setdefault("kwargs", {})
            .setdefault("handler", {})
            .setdefault("kwargs", {})
        )
        handler_kwargs["instruments"] = market
    if benchmark:
        cfg["benchmark"] = benchmark
    port = cfg.setdefault("port_analysis_config", {})
    strategy = port.setdefault("strategy", {}).setdefault("kwargs", {})
    backtest = port.setdefault("backtest", {})
    if topk is not None:
        strategy["topk"] = int(topk)
    if n_drop is not None:
        strategy["n_drop"] = int(n_drop)
    if account is not None:
        backtest["account"] = float(account)
    if benchmark:
        backtest["benchmark"] = benchmark
    if data_end:
        handler = cfg.setdefault("data_handler_config", {})
        handler["end_time"] = data_end
        handler_kwargs = (
            cfg.setdefault("task", {})
            .setdefault("dataset", {})
            .setdefault("kwargs", {})
            .setdefault("handler", {})
            .setdefault("kwargs", {})
        )
        handler_kwargs["end_time"] = data_end
        segments = (
            cfg["task"]["dataset"]["kwargs"].setdefault("segments", {})
        )
        if isinstance(segments.get("test"), list) and len(segments["test"]) == 2:
            segments["test"][1] = data_end
        backtest["end_time"] = data_end
    if test_start:
        segments = (
            cfg.setdefault("task", {})
            .setdefault("dataset", {})
            .setdefault("kwargs", {})
            .setdefault("segments", {})
        )
        if isinstance(segments.get("test"), list) and len(segments["test"]) == 2:
            segments["test"][0] = test_start
        backtest["start_time"] = test_start
    if learning_rate is not None:
        cfg.setdefault("task", {}).setdefault("model", {}).setdefault("kwargs", {})[
            "learning_rate"
        ] = float(learning_rate)

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
        with _silence_stdout_to_stderr():
            workflow(
                str(tmp_path), experiment_name=experiment_name, uri_folder=str(mlruns)
            )
    finally:
        tmp_path.unlink(missing_ok=True)
    return mlruns
