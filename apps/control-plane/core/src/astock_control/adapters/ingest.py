from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Callable
from typing import Any

from astock_control.protocol import JobCancelled
from astock_core.paths import DEFAULT_POOL_ID, REPO_ROOT

INGEST_DIR = REPO_ROOT / "tools" / "ingest"


def _ingest_prefix(pool: str) -> list[str]:
    return [
        "uv",
        "--directory",
        str(INGEST_DIR),
        "run",
        "python",
        "-m",
        "astock",
        "--json",
        "--pool",
        pool,
    ]


def calendar_sync_argv(command: dict[str, Any] | None = None) -> list[str]:
    argv = _ingest_prefix(str((command or {}).get("pool") or DEFAULT_POOL_ID))
    argv.extend(["calendar", "sync"])
    if command and command.get("force"):
        argv.append("--force")
    return argv


def quotes_sync_argv(command: dict[str, Any]) -> list[str]:
    argv = _ingest_prefix(str(command.get("pool") or DEFAULT_POOL_ID))
    argv.extend(["quotes", "sync"])
    if command.get("codes"):
        argv.extend(["--codes", ",".join(str(code) for code in command["codes"])])
    if command.get("adjust") is not None:
        argv.extend(["--adjust", str(command["adjust"])])
    if command.get("sleep") is not None:
        argv.extend(["--sleep", str(command["sleep"])])
    if command.get("history_start") is not None:
        argv.extend(["--history-start", str(command["history_start"])])
    if command.get("periods"):
        argv.extend(["--periods", ",".join(str(item) for item in command["periods"])])
    if command.get("limit") is not None:
        argv.extend(["--limit", str(command["limit"])])
    return argv


def boards_sync_argv(command: dict[str, Any]) -> list[str]:
    argv = _ingest_prefix(str(command.get("pool") or DEFAULT_POOL_ID))
    argv.extend(["boards", "sync"])
    argv.extend(["--kind", str(command.get("kind") or "all")])
    if command.get("sleep") is not None:
        argv.extend(["--sleep", str(command["sleep"])])
    if command.get("limit") is not None:
        argv.extend(["--limit", str(command["limit"])])
    return argv


def pool_command_argv(command: dict[str, Any]) -> list[str]:
    pool = str(command.get("pool") or DEFAULT_POOL_ID)
    argv = _ingest_prefix(pool)
    typ = command.get("type")
    if typ == "pool.add":
        argv.extend(["pool", "add"])
        if command.get("index"):
            argv.extend(["--index", str(command["index"])])
        else:
            argv.extend(["--codes", ",".join(str(code) for code in command.get("codes") or [])])
        return argv
    if typ == "pool.set":
        argv.extend(["pool", "set", "--index", str(command.get("index") or "")])
        return argv
    if typ == "pool.remove":
        argv.extend(["pool", "remove", "--codes", ",".join(str(code) for code in command.get("codes") or [])])
        return argv
    raise ValueError(f"无法为命令生成 ingest argv: {typ}")


def stock_command_argv(command: dict[str, Any]) -> list[str]:
    argv = _ingest_prefix(str(command.get("pool") or DEFAULT_POOL_ID))
    typ = command.get("type")
    if typ == "stock.add":
        argv.extend(["stock", "add"])
        if command.get("index"):
            argv.extend(["--index", str(command["index"])])
        else:
            argv.extend(["--codes", ",".join(str(code) for code in command.get("codes") or [])])
        return argv
    if typ == "stock.remove":
        argv.extend(
            ["stock", "remove", "--codes", ",".join(str(code) for code in command.get("codes") or [])]
        )
        return argv
    if typ == "stock.sync":
        argv.extend(["stock", "sync", ",".join(str(code) for code in command.get("codes") or [])])
        if command.get("sleep") is not None:
            argv.extend(["--sleep", str(command["sleep"])])
        if command.get("with_statements"):
            argv.append("--statements")
        return argv
    raise ValueError(f"无法为命令生成 ingest argv: {typ}")


def parse_trailing_json(text: str) -> dict[str, Any] | None:
    last: dict[str, Any] | None = None
    idx = 0
    while True:
        start = text.find("{", idx)
        if start < 0:
            return last
        try:
            data, end = json.JSONDecoder().raw_decode(text, start)
        except json.JSONDecodeError:
            idx = start + 1
            continue
        if isinstance(data, dict):
            last = data
        idx = max(end, start + 1)


class IngestRunner:
    SUPPORTED = frozenset(
        {
            "quotes.sync",
            "boards.sync",
            "calendar.sync",
            "stock.add",
            "stock.sync",
            "pool.add",
            "pool.set",
            "pool.remove",
        }
    )

    def run(
        self,
        command: dict[str, Any],
        on_log: Callable[[str], None],
        *,
        timeout: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        typ = command.get("type")
        if typ not in self.SUPPORTED:
            raise ValueError(f"ingest 适配器不支持命令: {typ}")
        if typ == "quotes.sync":
            argv = quotes_sync_argv(command)
        elif typ == "boards.sync":
            argv = boards_sync_argv(command)
        elif typ == "calendar.sync":
            argv = calendar_sync_argv(command)
        elif typ in {"stock.add", "stock.remove", "stock.sync"}:
            argv = stock_command_argv(command)
        else:
            argv = pool_command_argv(command)
        on_log("$ " + " ".join(argv))
        stdout = _run_uv(argv, on_log, timeout=timeout, cancel_event=cancel_event)
        result = parse_trailing_json(stdout)
        if result is None:
            raise RuntimeError("ingest 没有返回 JSON 结果")
        return result


def _kill_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def _run_uv(
    argv: list[str],
    on_log: Callable[[str], None],
    extra_env: dict[str, str] | None = None,
    *,
    timeout: float | None = None,
    cancel_event: threading.Event | None = None,
) -> str:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        bufsize=1,
    )
    stdout_chunks: list[str] = []
    stderr_lines: list[str] = []

    def read_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            text = line.rstrip("\n")
            stderr_lines.append(text)
            on_log(text)

    def read_stdout() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            stdout_chunks.append(line)

    def watch_cancel() -> None:
        if cancel_event is None:
            return
        while proc.poll() is None:
            if cancel_event.wait(timeout=0.2):
                _kill_process(proc)
                return

    err_thread = threading.Thread(target=read_stderr)
    out_thread = threading.Thread(target=read_stdout)
    killer = threading.Thread(target=watch_cancel, daemon=True)
    err_thread.start()
    out_thread.start()
    killer.start()
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_process(proc)
        err_thread.join(timeout=1)
        out_thread.join(timeout=1)
        killer.join(timeout=1)
        if cancel_event is not None and cancel_event.is_set():
            raise JobCancelled("已取消") from exc
        limit = int(timeout) if timeout is not None else 0
        raise RuntimeError(f"任务超时（{limit}s），已终止子进程") from exc
    err_thread.join()
    out_thread.join()
    killer.join(timeout=1)
    if cancel_event is not None and cancel_event.is_set():
        raise JobCancelled("已取消")
    stdout = "".join(stdout_chunks)
    if code != 0:
        err = "\n".join(line for line in stderr_lines if line).strip()
        snippet = err or stdout.strip() or "(无输出)"
        raise RuntimeError(f"子进程退出码 {code}: {snippet[-500:]}")
    return stdout
