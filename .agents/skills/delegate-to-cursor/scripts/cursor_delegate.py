#!/usr/bin/env python3
"""Run one bounded Cursor Agent delegation and emit an auditable JSON result."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator, TextIO


DEFAULT_AGENT = Path("/home/xun/.local/bin/agent")
DEFAULT_MODEL = "composer-2.5"
DEFAULT_DENY = (
    "Shell(rm:*)",
    "Shell(sudo:*)",
    "Shell(ssh:*)",
    "Shell(scp:*)",
    "Shell(git:push*)",
    "Shell(git:commit*)",
    "Read(**/.env*)",
    "Read(**/*.pem)",
    "Read(**/*.key)",
    "Write(**/.env*)",
    "Write(**/*.pem)",
    "Write(**/*.key)",
)
SKILL_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}[a-z0-9]|[a-z0-9]")


@dataclass(frozen=True)
class GitChange:
    status: str
    path: str
    source: str | None = None


@dataclass
class CursorRun:
    exit_code: int
    terminal_event: dict[str, Any] | None
    init_event: dict[str, Any] | None
    event_counts: dict[str, int]
    stderr_tail: list[str]
    timed_out: bool = False
    interrupted: bool = False


def json_error(message: str, **details: Any) -> None:
    print(json.dumps({"error": message, **details}, ensure_ascii=False), file=sys.stderr)


def run_capture(
    command: list[str],
    cwd: Path,
    *,
    timeout: int = 30,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        input=input_text,
        timeout=timeout,
        check=False,
    )


def git_head(cwd: Path) -> str:
    result = run_capture(["git", "rev-parse", "HEAD"], cwd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git rev-parse HEAD failed")
    return result.stdout.strip()


def git_resolve(cwd: Path, revision: str) -> str:
    result = run_capture(["git", "rev-parse", "--verify", f"{revision}^{{commit}}"], cwd)
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or f"git could not resolve revision: {revision}"
        )
    return result.stdout.strip()


def git_changes(cwd: Path) -> list[GitChange]:
    result = run_capture(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")

    fields = result.stdout.split("\0")
    changes: list[GitChange] = []
    index = 0
    while index < len(fields):
        record = fields[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise RuntimeError(f"unexpected git status record: {record!r}")
        status = record[:2]
        path = record[3:]
        source: str | None = None
        if "R" in status or "C" in status:
            if index >= len(fields) or not fields[index]:
                raise RuntimeError(f"missing rename/copy source for: {record!r}")
            source = fields[index]
            index += 1
        changes.append(GitChange(status=status, path=path, source=source))
    return changes


def git_diff_check(cwd: Path) -> dict[str, Any]:
    unstaged = run_capture(["git", "diff", "--check"], cwd)
    staged = run_capture(["git", "diff", "--cached", "--check"], cwd)
    return {
        "ok": unstaged.returncode == 0 and staged.returncode == 0,
        "unstaged": (unstaged.stdout + unstaged.stderr).strip(),
        "staged": (staged.stdout + staged.stderr).strip(),
    }


def git_worktree_fingerprint(cwd: Path) -> str:
    head = git_head(cwd)
    diff = run_capture(["git", "diff", "--binary", "HEAD", "--"], cwd)
    if diff.returncode != 0:
        raise RuntimeError(diff.stderr.strip() or "git diff HEAD failed")
    changes = git_changes(cwd)
    digest = hashlib.sha256()
    digest.update(head.encode())
    digest.update(diff.stdout.encode())
    for change in sorted(changes, key=lambda item: (item.path, item.status)):
        digest.update(change.status.encode())
        digest.update(change.path.encode())
        if change.status == "??":
            path = cwd / change.path
            if path.is_symlink():
                digest.update(os.readlink(path).encode())
            elif path.is_file():
                digest.update(path.read_bytes())
    return digest.hexdigest()


def path_allowed(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        return args.prompt
    try:
        return args.prompt_file.expanduser().read_text(encoding="utf-8")
    except OSError as error:
        raise RuntimeError(f"cannot read prompt file: {error}") from error


def attach_skills(prompt: str, skills: list[str]) -> str:
    if not skills:
        return prompt
    invalid = [name for name in skills if not SKILL_RE.fullmatch(name)]
    if invalid:
        raise RuntimeError(f"invalid skill name(s): {', '.join(invalid)}")
    return " ".join(f"/{name}" for name in skills) + "\n\n" + prompt


def extract_structured_result(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    decoder = json.JSONDecoder()
    candidate: dict[str, Any] | None = None
    for index, character in enumerate(value):
        if character != "{":
            continue
        try:
            parsed, end = decoder.raw_decode(value[index:])
        except json.JSONDecodeError:
            continue
        suffix = value[index + end :].strip()
        if isinstance(parsed, dict) and not suffix.strip("`").strip():
            candidate = parsed
    return candidate


def find_agent(explicit: Path | None) -> str | None:
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        return str(candidate) if candidate.is_file() else None
    found = shutil.which("agent")
    if found:
        return found
    return str(DEFAULT_AGENT) if DEFAULT_AGENT.is_file() else None


def permission_token(kind: str, value: str) -> str:
    return value if value.startswith(f"{kind}(") else f"{kind}({value})"


@contextmanager
def isolated_cursor_config(
    args: argparse.Namespace, sandbox_mode: str
) -> Iterator[dict[str, str]]:
    with tempfile.TemporaryDirectory(prefix="cursor-delegate-config.") as directory:
        config_dir = Path(directory)
        config_dir.chmod(0o700)
        allow = ["Read(**)"]
        allow.extend(permission_token("Write", path) for path in args.allow_path)
        allow.extend(permission_token("Shell", shell) for shell in args.allow_shell)
        allow.extend(f"Mcp({server}:*)" for server in args.require_mcp)
        allow.extend(permission_token("Mcp", tool) for tool in args.allow_mcp_tool)

        deny = list(DEFAULT_DENY)
        deny.extend(permission_token("Shell", shell) for shell in args.deny_shell)
        if args.mode in ("ask", "plan"):
            deny.append("Write(**)")

        config = {
            "version": 1,
            "editor": {"vimMode": False},
            "permissions": {"allow": sorted(set(allow)), "deny": sorted(set(deny))},
            "sandbox": {
                "mode": sandbox_mode,
                "networkAccess": "user_config_with_defaults",
            },
            "attribution": {
                "attributeCommitsToAgent": False,
                "attributePRsToAgent": False,
            },
        }
        config_path = config_dir / "cli-config.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        config_path.chmod(0o600)

        global_mcp = Path.home() / ".cursor" / "mcp.json"
        if global_mcp.is_file():
            copied_mcp = config_dir / "mcp.json"
            shutil.copy2(global_mcp, copied_mcp)
            copied_mcp.chmod(0o600)

        env = os.environ.copy()
        env["CURSOR_CONFIG_DIR"] = str(config_dir)
        yield env


def check_auth(agent: str, cwd: Path, env: dict[str, str]) -> bool:
    result = run_capture([agent, "status"], cwd, env=env)
    return result.returncode == 0


def validate_model(agent: str, cwd: Path, env: dict[str, str], model: str) -> bool:
    result = run_capture([agent, "--list-models"], cwd, env=env)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "cannot list Cursor models")
    base_model = model.split("[", 1)[0]
    available = {
        line.split(" - ", 1)[0].strip()
        for line in result.stdout.splitlines()
        if " - " in line
    }
    return base_model in available


def preflight_mcps(
    agent: str, cwd: Path, env: dict[str, str], servers: list[str]
) -> dict[str, str]:
    results: dict[str, str] = {}
    for server in servers:
        result = run_capture([agent, "mcp", "list-tools", server], cwd, env=env, timeout=60)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"MCP {server!r} is unavailable: {detail}")
        results[server] = result.stdout.strip()
    return results


def sandbox_available(agent: str, cwd: Path, env: dict[str, str]) -> bool:
    result = run_capture(
        [
            agent,
            "-p",
            "--trust",
            "--workspace",
            str(cwd),
            "--mode",
            "ask",
            "--sandbox",
            "enabled",
            "--model",
            "__cursor_sandbox_probe_invalid_model__",
            "--output-format=json",
        ],
        cwd,
        env=env,
        input_text="Reply with no tool use.",
    )
    combined = result.stdout + result.stderr
    return "Sandbox mode is enabled but not available" not in combined


def event_name(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", "unknown"))
    subtype = event.get("subtype")
    return f"{event_type}/{subtype}" if subtype else event_type


def tool_name(event: dict[str, Any]) -> str:
    tool_call = event.get("tool_call")
    if not isinstance(tool_call, dict):
        return "tool"
    for key in tool_call:
        if key.endswith("ToolCall"):
            return key.removesuffix("ToolCall")
    return next(iter(tool_call), "tool")


def stop_process_group(process: subprocess.Popen[str], *, force: bool = False) -> None:
    if process.poll() is not None:
        return
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        return


def run_cursor_stream(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    prompt: str,
    timeout: int,
    log_path: Path,
) -> CursorRun:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path = log_path.with_suffix(log_path.suffix + ".stderr")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        text=True,
        bufsize=1,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    process.stdin.write(prompt)
    process.stdin.close()

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    deadline = time.monotonic() + timeout
    terminal_event: dict[str, Any] | None = None
    init_event: dict[str, Any] | None = None
    counts: dict[str, int] = {}
    stderr_tail: list[str] = []
    timed_out = False
    interrupted = False

    try:
        with log_path.open("w", encoding="utf-8") as event_log, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_log:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    stop_process_group(process)
                    break
                ready = selector.select(timeout=min(1.0, remaining))
                if not ready and process.poll() is not None:
                    for key in list(selector.get_map().values()):
                        selector.unregister(key.fileobj)
                    break
                for key, _ in ready:
                    line = key.fileobj.readline()
                    if line == "":
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == "stderr":
                        stderr_log.write(line)
                        stderr_log.flush()
                        stderr_tail.append(line.rstrip())
                        stderr_tail = stderr_tail[-40:]
                        print(f"[cursor stderr] {line.rstrip()}", file=sys.stderr, flush=True)
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        counts["non_json"] = counts.get("non_json", 0) + 1
                        stderr_log.write(f"[cursor stdout] {line}")
                        stderr_log.flush()
                        print(
                            f"[cursor stdout] {line.rstrip()}",
                            file=sys.stderr,
                            flush=True,
                        )
                        continue
                    event_log.write(line)
                    event_log.flush()
                    name = event_name(event)
                    counts[name] = counts.get(name, 0) + 1
                    if name == "system/init":
                        init_event = event
                        print(
                            f"[cursor] model={event.get('model')} cwd={event.get('cwd')}",
                            file=sys.stderr,
                            flush=True,
                        )
                    elif event.get("type") == "tool_call" and event.get("subtype") == "started":
                        print(f"[cursor] tool started: {tool_name(event)}", file=sys.stderr, flush=True)
                    elif event.get("type") == "result":
                        terminal_event = event
                        print("[cursor] terminal result received", file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        interrupted = True
        stop_process_group(process)
    finally:
        selector.close()

    if process.poll() is None:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            stop_process_group(process, force=True)
            process.wait(timeout=5)

    return CursorRun(
        exit_code=130 if interrupted else (124 if timed_out else process.returncode),
        terminal_event=terminal_event,
        init_event=init_event,
        event_counts=counts,
        stderr_tail=stderr_tail,
        timed_out=timed_out,
        interrupted=interrupted,
    )


def default_log_path() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Path.home() / ".cursor" / "delegations" / f"{stamp}-{os.getpid()}.jsonl"


def build_command(
    agent: str,
    args: argparse.Namespace,
    workspace: Path,
    model: str,
    worktree_name: str | None,
    sandbox_mode: str,
) -> list[str]:
    command = [
        agent,
        "-p",
        "--trust",
        "--workspace",
        str(workspace),
        "--output-format=stream-json",
        "--model",
        model,
        "--sandbox",
        sandbox_mode,
    ]
    if args.stream_partial_output:
        command.append("--stream-partial-output")
    if args.mode in ("ask", "plan"):
        command.extend(["--mode", args.mode])
    if args.force:
        command.append("--force")
    elif args.auto_review:
        command.append("--auto-review")
    if args.resume:
        command.extend(["--resume", args.resume])
    elif args.continue_session:
        command.append("--continue")
    for directory in args.add_dir:
        command.extend(["--add-dir", str(directory)])
    for directory in args.plugin_dir:
        command.extend(["--plugin-dir", str(directory)])
    if args.isolate:
        command.extend(["--worktree", worktree_name or "codex-delegation"])
        command.extend(["--worktree-base", args.worktree_base])
        if args.skip_worktree_setup:
            command.append("--skip-worktree-setup")
    return command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("ask", "plan", "execute"), default="ask")
    parser.add_argument("--cwd", "--workspace", dest="cwd", type=Path, default=Path.cwd())
    prompt = parser.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt")
    prompt.add_argument("--prompt-file", type=Path)
    parser.add_argument("--agent-bin", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--auto-review", action="store_true")
    parser.add_argument(
        "--sandbox", choices=("auto", "enabled", "disabled"), default="auto"
    )
    parser.add_argument("--accept-allowlist-risk", action="store_true")
    parser.add_argument(
        "--accept-dirty-worktree",
        action="store_true",
        help="allow a focused --resume repair in an existing dirty worktree",
    )
    parser.add_argument("--allow-path", action="append", default=[])
    parser.add_argument("--allow-shell", action="append", default=[])
    parser.add_argument("--deny-shell", action="append", default=[])
    parser.add_argument("--allow-mcp-tool", action="append", default=[])
    parser.add_argument("--require-mcp", action="append", default=[])
    parser.add_argument("--skill", action="append", default=[])
    parser.add_argument("--plugin-dir", action="append", type=Path, default=[])
    parser.add_argument("--add-dir", action="append", type=Path, default=[])
    parser.add_argument("--resume")
    parser.add_argument("--continue", dest="continue_session", action="store_true")
    parser.add_argument("--isolate", action="store_true")
    parser.add_argument("--worktree-name")
    parser.add_argument("--worktree-base", default="HEAD")
    parser.add_argument("--skip-worktree-setup", action="store_true")
    parser.add_argument("--stream-partial-output", action="store_true")
    parser.add_argument(
        "--require-result-json",
        action="store_true",
        help="reject a terminal response without a final structured JSON object",
    )
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--warn-input-tokens", type=int, default=40_000)
    parser.add_argument("--max-input-tokens", type=int, default=120_000)
    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.warn_input_tokens < 0 or args.max_input_tokens <= 0:
        parser.error("token thresholds must be non-negative/positive")
    if args.warn_input_tokens > args.max_input_tokens:
        parser.error("--warn-input-tokens cannot exceed --max-input-tokens")
    if args.force and args.auto_review:
        parser.error("choose either --force or --auto-review")
    if args.resume and args.continue_session:
        parser.error("choose either --resume or --continue")
    if args.mode == "execute" and not args.allow_path:
        parser.error("execute mode requires at least one --allow-path")
    if args.mode != "execute" and args.isolate:
        parser.error("--isolate is valid only with --mode execute")
    if args.force and not args.isolate:
        parser.error("--force requires --isolate")
    if args.force and args.sandbox == "disabled" and not args.accept_allowlist_risk:
        parser.error(
            "--force with --sandbox disabled requires --accept-allowlist-risk"
        )
    if args.worktree_name and not args.isolate:
        parser.error("--worktree-name requires --isolate")
    if args.accept_dirty_worktree and (
        args.mode != "execute" or not args.resume or args.isolate
    ):
        parser.error(
            "--accept-dirty-worktree requires non-isolated execute mode with explicit --resume"
        )
    return args


def main() -> int:
    args = parse_args()
    if os.environ.get("CURSOR_AGENT"):
        json_error("refusing recursive Cursor invocation", environment="CURSOR_AGENT")
        return 8
    workspace = args.cwd.expanduser().resolve()
    if not workspace.is_dir():
        json_error("workspace is not a directory", workspace=str(workspace))
        return 2

    agent = find_agent(args.agent_bin)
    if not agent:
        json_error(
            "Cursor CLI not found",
            install="curl https://cursor.com/install -fsS | bash",
        )
        return 2

    source_fingerprint_before: str | None = None
    try:
        prompt = attach_skills(load_prompt(args), args.skill)
        source_head = git_head(workspace) if args.mode == "execute" else None
        expected_head = (
            git_resolve(workspace, args.worktree_base)
            if args.mode == "execute" and args.isolate
            else source_head
        )
        source_before = git_changes(workspace) if args.mode == "execute" else []
        if args.mode in ("ask", "plan"):
            try:
                source_fingerprint_before = git_worktree_fingerprint(workspace)
            except RuntimeError:
                source_fingerprint_before = None
    except RuntimeError as error:
        json_error(str(error))
        return 2

    if args.mode == "execute" and not args.isolate and source_before:
        if not args.accept_dirty_worktree:
            json_error(
                "execute mode requires a clean worktree unless --isolate is used",
                status=[asdict(change) for change in source_before],
            )
            return 5
        initial_violations = [
            change.path
            for change in source_before
            if not path_allowed(change.path, args.allow_path)
        ]
        if initial_violations:
            json_error(
                "dirty worktree contains paths outside the repair allowlist",
                violations=initial_violations,
            )
            return 5

    for directory in [*args.add_dir, *args.plugin_dir]:
        if not directory.expanduser().resolve().is_dir():
            json_error("additional/plugin directory does not exist", path=str(directory))
            return 2

    worktree_name = args.worktree_name
    if args.isolate and not worktree_name:
        worktree_name = f"codex-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    log_path = (args.log_file or default_log_path()).expanduser().resolve()

    effective_sandbox = "enabled" if args.sandbox == "auto" else args.sandbox
    sandbox_fallback = False
    with isolated_cursor_config(args, effective_sandbox) as env:
        if not check_auth(agent, workspace, env):
            json_error("Cursor CLI is not logged in", login=f"{agent} login")
            return 4
        try:
            if not validate_model(agent, workspace, env, args.model):
                json_error("Cursor model is unavailable", model=args.model)
                return 2
            mcp_preflight = preflight_mcps(agent, workspace, env, args.require_mcp)
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            json_error(str(error))
            return 4

        if args.sandbox == "auto" and not sandbox_available(agent, workspace, env):
            can_fallback = args.mode in ("ask", "plan") or (
                args.isolate and args.accept_allowlist_risk
            )
            if not can_fallback:
                json_error(
                    "Cursor sandbox is unavailable; isolated write execution requires --accept-allowlist-risk to use allowlist mode"
                )
                return 9
            effective_sandbox = "disabled"
            sandbox_fallback = True
            print(
                "[cursor] sandbox unavailable; using explicit allowlist mode",
                file=sys.stderr,
                flush=True,
            )

        command = build_command(
            agent, args, workspace, args.model, worktree_name, effective_sandbox
        )
        print(
            f"[cursor] starting mode={args.mode} model={args.model} isolate={args.isolate}",
            file=sys.stderr,
            flush=True,
        )
        run = run_cursor_stream(command, workspace, env, prompt, args.timeout, log_path)

    actual_workspace = workspace
    if run.init_event and run.init_event.get("cwd"):
        actual_workspace = Path(str(run.init_event["cwd"])).resolve()

    changes: list[GitChange] = []
    violations: list[str] = []
    diff_check: dict[str, Any] | None = None
    actual_head: str | None = None
    source_after: list[GitChange] = []
    source_head_after: str | None = None
    read_only_worktree_unchanged: bool | None = None
    audit_errors: list[str] = []
    if args.mode == "execute" and actual_workspace.is_dir():
        try:
            changes = git_changes(actual_workspace)
            violations = [
                change.path
                for change in changes
                if not path_allowed(change.path, args.allow_path)
            ]
            diff_check = git_diff_check(actual_workspace)
            actual_head = git_head(actual_workspace)
            if expected_head and actual_head != expected_head:
                violations.append("<unexpected git commit: HEAD changed>")
            if args.isolate:
                source_after = git_changes(workspace)
                source_head_after = git_head(workspace)
                if source_after != source_before:
                    violations.append("<source worktree changed during isolated run>")
                if source_head_after != source_head:
                    violations.append("<source worktree HEAD changed during isolated run>")
        except RuntimeError as error:
            audit_errors.append(str(error))
    elif args.mode in ("ask", "plan") and actual_workspace.is_dir():
        if source_fingerprint_before is not None:
            try:
                read_only_worktree_unchanged = (
                    git_worktree_fingerprint(actual_workspace)
                    == source_fingerprint_before
                )
                if not read_only_worktree_unchanged:
                    violations.append("<read-only run changed worktree>")
            except RuntimeError as error:
                audit_errors.append(str(error))

    terminal = run.terminal_event or {}
    structured_result = extract_structured_result(terminal.get("result"))
    usage = terminal.get("usage") if isinstance(terminal, dict) else None
    input_tokens = usage.get("inputTokens", 0) if isinstance(usage, dict) else 0
    warnings: list[str] = []
    if input_tokens >= args.warn_input_tokens:
        warnings.append(
            f"Cursor input token usage {input_tokens} reached warning threshold {args.warn_input_tokens}"
        )
    if sandbox_fallback:
        warnings.append(
            "Cursor sandbox is unavailable on this system; this run used explicit allowlist mode"
        )
    if not args.force:
        warnings.append(
            "allowed paths are enforced by Cursor permissions when possible and audited with git status; ignored files and external side effects require sandbox/MCP policy"
        )
    else:
        warnings.append(
            "--force makes allowed paths post-run audit expectations; sandbox confines the isolated workspace but does not make MCP actions reversible"
        )

    rejection_reasons: list[str] = []
    if run.exit_code != 0:
        rejection_reasons.append(f"Cursor process exited with code {run.exit_code}")
    if not run.terminal_event:
        rejection_reasons.append("Cursor emitted no terminal result")
    elif run.terminal_event.get("is_error"):
        rejection_reasons.append("Cursor terminal result reported an error")
    if violations:
        rejection_reasons.append(
            f"path audit / git audit found {len(set(violations))} violation(s)"
        )
    if "<read-only run changed worktree>" in violations:
        rejection_reasons.append("read-only Cursor review changed the worktree")
    if audit_errors:
        rejection_reasons.append(f"audit raised {len(audit_errors)} error(s)")
    if diff_check and not diff_check["ok"]:
        rejection_reasons.append("git diff --check failed")
    if input_tokens > args.max_input_tokens:
        rejection_reasons.append(
            f"Cursor input token limit exceeded: {input_tokens} > {args.max_input_tokens}"
        )
    if args.require_result_json and structured_result is None:
        rejection_reasons.append("Cursor terminal result did not contain structured JSON")

    result = {
        "runner": {
            "mode": args.mode,
            "source_workspace": str(workspace),
            "actual_workspace": str(actual_workspace),
            "isolated": args.isolate,
            "accepted_dirty_worktree": args.accept_dirty_worktree,
            "read_only_worktree_unchanged": read_only_worktree_unchanged,
            "worktree_name": worktree_name,
            "expected_head": expected_head,
            "source_head_before": source_head,
            "source_head_after": source_head_after,
            "model_requested": args.model,
            "model_actual": run.init_event.get("model") if run.init_event else None,
            "sandbox_requested": args.sandbox,
            "sandbox_effective": effective_sandbox,
            "sandbox_fallback": sandbox_fallback,
            "skills": args.skill,
            "required_mcps": list(mcp_preflight),
            "allowed_paths": args.allow_path,
            "changed_paths": [change.path for change in changes],
            "changes": [asdict(change) for change in changes],
            "violations": sorted(set(violations)),
            "diff_check": diff_check,
            "audit_errors": audit_errors,
            "event_counts": run.event_counts,
            "log_file": str(log_path),
            "stderr_log_file": str(log_path.with_suffix(log_path.suffix + ".stderr")),
            "timed_out": run.timed_out,
            "interrupted": run.interrupted,
            "warnings": warnings,
            "accepted": not rejection_reasons,
            "rejection_reasons": rejection_reasons,
        },
        "cursor": terminal or None,
        "structured_result": structured_result,
        "session_id": terminal.get("session_id") if isinstance(terminal, dict) else None,
        "request_id": terminal.get("request_id") if isinstance(terminal, dict) else None,
        "usage": usage,
        "stderr_tail": run.stderr_tail,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if run.exit_code != 0:
        return run.exit_code
    if not run.terminal_event or run.terminal_event.get("is_error"):
        return 3
    if args.require_result_json and structured_result is None:
        return 10
    if violations or audit_errors or (diff_check and not diff_check["ok"]):
        return 6
    if input_tokens > args.max_input_tokens:
        return 7
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
