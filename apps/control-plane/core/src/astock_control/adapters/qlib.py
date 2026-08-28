from __future__ import annotations

from collections.abc import Callable
from typing import Any

from astock_core.paths import REPO_ROOT
from astock_core.qlib_store import QlibStore

from astock_control.adapters.ingest import _run_uv, parse_trailing_json
from astock_control.config import load_settings

QLIB_DIR = REPO_ROOT / "tools" / "qlib"


def effective_workflow(
    pool_id: str,
    overrides: dict[str, Any] | None = None,
    *,
    store: QlibStore | None = None,
) -> dict[str, Any]:
    settings = load_settings()
    defaults = dict((settings.get("qlib") or {}).get("workflow") or {})
    defaults.pop("market", None)
    repository = store or QlibStore()
    workflow = repository.get_workflow(pool_id, defaults)
    workflow.update(overrides or {})
    effective = {
        "config": str(workflow["config"]),
        "benchmark": str(workflow["benchmark"]),
        "topk": int(workflow["topk"]),
        "n_drop": int(workflow["n_drop"]),
        "account": float(workflow["account"]),
        "data_end": workflow.get("data_end"),
        "test_start": workflow.get("test_start"),
        "learning_rate": workflow.get("learning_rate"),
    }
    if effective["n_drop"] > effective["topk"]:
        raise ValueError("每期换出数不能大于候选只数")
    return effective


def _workflow_cli_args(workflow: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    if workflow.get("data_end"):
        argv.extend(["--data-end", str(workflow["data_end"])])
    if workflow.get("test_start"):
        argv.extend(["--test-start", str(workflow["test_start"])])
    if workflow.get("learning_rate") not in (None, ""):
        argv.extend(["--learning-rate", str(workflow["learning_rate"])])
    return argv


def qlib_prepare_argv(command: dict[str, Any], workflow: dict[str, Any]) -> list[str]:
    return [
        "uv",
        "--directory",
        str(QLIB_DIR),
        "run",
        "python",
        "-m",
        "astock_qlib",
        "--pool",
        str(command["pool"]),
        "--json",
        "prepare",
        "--benchmark",
        str(workflow["benchmark"]),
    ]


def qlib_select_argv(command: dict[str, Any], workflow: dict[str, Any]) -> list[str]:
    return [
        "uv",
        "--directory",
        str(QLIB_DIR),
        "run",
        "python",
        "-m",
        "astock_qlib",
        "--pool",
        str(command["pool"]),
        "--json",
        "select",
        "--run-id",
        str(command["run_id"]),
        "--config",
        str(workflow["config"]),
        "--benchmark",
        str(workflow["benchmark"]),
        "--topk",
        str(workflow["topk"]),
        "--n-drop",
        str(workflow["n_drop"]),
        "--account",
        str(workflow["account"]),
        *_workflow_cli_args(workflow),
    ]


class QlibRunner:
    def __init__(self, store: QlibStore | None = None) -> None:
        self.store = store or QlibStore()

    def run(
        self,
        command: dict[str, Any],
        on_log: Callable[[str], None],
        *,
        timeout: float | None = None,
        cancel_event=None,
    ) -> dict[str, Any]:
        typ = command.get("type")
        pool_id = str(command["pool"])
        if typ == "qlib.workflow.update":
            workflow = effective_workflow(
                pool_id,
                dict(command.get("workflow") or {}),
                store=self.store,
            )
            on_log(f"保存股票池 {pool_id} 的 workflow")
            return self.store.save_workflow(pool_id, workflow)
        if typ == "qlib.dump":
            workflow = effective_workflow(pool_id, store=self.store)
            argv = qlib_prepare_argv(command, workflow)
            on_log("$ " + " ".join(argv))
            stdout = _run_uv(argv, on_log, timeout=timeout, cancel_event=cancel_event)
            result = parse_trailing_json(stdout)
            if result is None:
                raise RuntimeError("Qlib 没有返回 JSON 结果")
            stored = self.store.save_pool_data(pool_id, result)
            return {**result, "stored_data": stored}
        if typ != "qlib.run":
            raise ValueError(f"Qlib 执行器不支持命令: {typ}")

        workflow = effective_workflow(
            pool_id,
            dict(command.get("workflow") or {}),
            store=self.store,
        )
        argv = qlib_select_argv(command, workflow)
        on_log("$ " + " ".join(argv))
        stdout = _run_uv(argv, on_log, timeout=timeout, cancel_event=cancel_event)
        result = parse_trailing_json(stdout)
        if result is None:
            raise RuntimeError("Qlib 没有返回 JSON 结果")
        result["workflow"] = workflow
        stored = self.store.record_run(result)
        return {**result, "stored_run": stored}
