#!/usr/bin/env python3
"""Deterministic tests for cursor_delegate.py without Cursor API usage."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


SCRIPT = Path(__file__).with_name("cursor_delegate.py")
SPEC = importlib.util.spec_from_file_location("cursor_delegate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


FAKE_AGENT = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import time

args = sys.argv[1:]
if args == ["status"]:
    print("authenticated")
    raise SystemExit(0)
if args == ["--list-models"]:
    print("composer-2.5 - Composer 2.5")
    print("auto - Auto")
    raise SystemExit(0)
if len(args) >= 3 and args[:2] == ["mcp", "list-tools"]:
    if args[2] == "missing":
        print("not approved", file=sys.stderr)
        raise SystemExit(1)
    print(f"Tools for {args[2]} (1):\n- search (query)")
    raise SystemExit(0)

prompt = sys.stdin.read()
workspace = Path(os.environ.get("FAKE_ACTUAL_WORKSPACE", args[args.index("--workspace") + 1]))
model = args[args.index("--model") + 1]
if os.environ.get("FAKE_SANDBOX_UNAVAILABLE") and args[args.index("--sandbox") + 1] == "enabled":
    print("Error: Sandbox mode is enabled but not available on this system.", file=sys.stderr)
    raise SystemExit(1)
if model == "__cursor_sandbox_probe_invalid_model__":
    print("invalid model", file=sys.stderr)
    raise SystemExit(1)
if "SLEEP" in prompt:
    time.sleep(30)
if "WRITE:" in prompt:
    relative = prompt.split("WRITE:", 1)[1].split()[0]
    target = workspace / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("created by fake Cursor\n", encoding="utf-8")

session_id = "fake-session"
if os.environ.get("FAKE_STDOUT_BANNER"):
    print("Using worktree: fake-banner", flush=True)
result_text = '{"status":"pass","findings":[]}' if "JSON_RESULT" in prompt else "done"
print(json.dumps({
    "type": "system", "subtype": "init", "cwd": str(workspace),
    "session_id": session_id, "model": model, "permissionMode": "default"
}), flush=True)
print(json.dumps({
    "type": "tool_call", "subtype": "started", "session_id": session_id,
    "tool_call": {"writeToolCall": {"args": {"path": "fixture"}}}
}), flush=True)
print(json.dumps({
    "type": "result", "subtype": "success", "is_error": False,
    "result": result_text, "session_id": session_id, "request_id": "fake-request",
    "usage": {"inputTokens": 100, "outputTokens": 10, "cacheReadTokens": 0,
              "cacheWriteTokens": 0}
}), flush=True)
'''


def command(*args: str) -> list[str]:
    return [sys.executable, str(SCRIPT), *args]


def run(command_args: list[str], cwd: Path, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command_args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def run_with_env(
    command_args: list[str], cwd: Path, environment: dict[str, str], timeout: int = 20
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command_args,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)


class CursorDelegateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="cursor-delegate-test.")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        init_repo(self.repo)
        self.fake = self.root / "agent"
        self.fake.write_text(FAKE_AGENT, encoding="utf-8")
        self.fake.chmod(0o755)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def base(self, *extra: str) -> list[str]:
        return command(
            "--agent-bin", str(self.fake), "--cwd", str(self.repo),
            "--log-file", str(self.root / "events.jsonl"), *extra,
        )

    def test_attach_skills(self) -> None:
        self.assertEqual(MODULE.attach_skills("task", ["tdd"]), "/tdd\n\ntask")
        with self.assertRaises(RuntimeError):
            MODULE.attach_skills("task", ["../escape"])

    def test_git_status_parses_rename_without_losing_paths(self) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo), "mv", "README.md", "README renamed.md"],
            check=True,
        )
        changes = MODULE.git_changes(self.repo)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].path, "README renamed.md")
        self.assertEqual(changes[0].source, "README.md")

    def test_execute_streams_and_audits_allowed_change(self) -> None:
        result = run(
            self.base(
                "--mode", "execute", "--allow-path", "allowed.txt",
                "--require-mcp", "memory", "--skill", "tdd",
                "--prompt", "WRITE:allowed.txt complete task",
            ),
            self.repo,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["runner"]["changed_paths"], ["allowed.txt"])
        self.assertEqual(payload["runner"]["skills"], ["tdd"])
        self.assertEqual(payload["session_id"], "fake-session")
        self.assertEqual(payload["usage"]["inputTokens"], 100)
        self.assertTrue((self.root / "events.jsonl").is_file())

    def test_path_violation_fails_closed(self) -> None:
        result = run(
            self.base(
                "--mode", "execute", "--allow-path", "allowed.txt",
                "--prompt", "WRITE:outside.txt complete task",
            ),
            self.repo,
        )
        self.assertEqual(result.returncode, 6)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["runner"]["violations"], ["outside.txt"])

    def test_result_reports_all_rejection_reasons(self) -> None:
        result = run(
            self.base(
                "--mode", "execute", "--allow-path", "allowed.txt",
                "--warn-input-tokens", "0", "--max-input-tokens", "50",
                "--prompt", "WRITE:outside.txt complete task",
            ),
            self.repo,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        reasons = payload["runner"]["rejection_reasons"]
        self.assertTrue(any("path audit" in reason for reason in reasons))
        self.assertTrue(any("token limit" in reason for reason in reasons))
        self.assertFalse(payload["runner"]["accepted"])

    def test_isolated_run_compares_head_to_requested_base(self) -> None:
        base = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        (self.repo / "later.txt").write_text("later\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "later.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "later"], check=True)
        isolated = self.root / "isolated"
        subprocess.run(
            ["git", "-C", str(self.repo), "worktree", "add", "--detach", str(isolated), base],
            check=True,
            capture_output=True,
            text=True,
        )
        environment = os.environ.copy()
        environment["FAKE_ACTUAL_WORKSPACE"] = str(isolated)
        result = run_with_env(
            self.base(
                "--mode", "execute", "--isolate", "--worktree-base", base,
                "--allow-path", "allowed.txt", "--prompt", "complete task",
            ),
            self.repo,
            environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["runner"]["expected_head"], base)
        self.assertNotIn("<unexpected git commit: HEAD changed>", payload["runner"]["violations"])

    def test_resume_can_accept_allowed_changes_in_dedicated_dirty_worktree(self) -> None:
        (self.repo / "allowed.txt").write_text("existing\n", encoding="utf-8")
        result = run(
            self.base(
                "--mode", "execute", "--resume", "fake-session",
                "--accept-dirty-worktree", "--allow-path", "allowed.txt",
                "--prompt", "WRITE:allowed.txt repair task",
            ),
            self.repo,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["runner"]["accepted_dirty_worktree"])

    def test_event_log_remains_jsonl_when_cursor_prints_banner(self) -> None:
        environment = os.environ.copy()
        environment["FAKE_STDOUT_BANNER"] = "1"
        result = run_with_env(
            self.base("--mode", "ask", "--prompt", "question"),
            self.repo,
            environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        log_lines = (self.root / "events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertTrue(log_lines)
        for line in log_lines:
            json.loads(line)

    def test_required_structured_result_is_parsed(self) -> None:
        result = run(
            self.base(
                "--mode", "ask", "--require-result-json",
                "--prompt", "JSON_RESULT review this patch",
            ),
            self.repo,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["structured_result"], {"status": "pass", "findings": []})

    def test_required_structured_result_rejects_prose(self) -> None:
        result = run(
            self.base(
                "--mode", "ask", "--require-result-json", "--prompt", "review this patch",
            ),
            self.repo,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(
            any("structured JSON" in reason for reason in payload["runner"]["rejection_reasons"])
        )

    def test_read_only_review_rejects_worktree_mutation(self) -> None:
        result = run(
            self.base(
                "--mode", "ask", "--prompt", "WRITE:review-mutation.txt inspect patch",
            ),
            self.repo,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["runner"]["read_only_worktree_unchanged"])
        self.assertTrue(
            any("read-only" in reason for reason in payload["runner"]["rejection_reasons"])
        )

    def test_dirty_nonisolated_worktree_is_rejected_before_agent(self) -> None:
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        result = run(
            self.base(
                "--mode", "execute", "--allow-path", "allowed.txt",
                "--prompt", "WRITE:allowed.txt complete task",
            ),
            self.repo,
        )
        self.assertEqual(result.returncode, 5)
        self.assertIn("clean worktree", result.stderr)

    def test_missing_mcp_fails_before_model_run(self) -> None:
        result = run(
            self.base(
                "--mode", "ask", "--require-mcp", "missing",
                "--prompt", "question",
            ),
            self.repo,
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("unavailable", result.stderr)

    def test_timeout_returns_124_and_no_terminal_result(self) -> None:
        result = run(
            self.base(
                "--mode", "ask", "--timeout", "1", "--prompt", "SLEEP",
            ),
            self.repo,
            timeout=10,
        )
        self.assertEqual(result.returncode, 124)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["runner"]["timed_out"])
        self.assertIsNone(payload["cursor"])

    def test_force_requires_isolation_and_sandbox(self) -> None:
        result = run(
            self.base(
                "--mode", "execute", "--allow-path", "allowed.txt",
                "--force", "--prompt", "task",
            ),
            self.repo,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--force requires --isolate", result.stderr)

    def test_force_without_sandbox_requires_explicit_risk_acceptance(self) -> None:
        result = run(
            self.base(
                "--mode", "execute", "--allow-path", "allowed.txt",
                "--isolate", "--force", "--sandbox", "disabled",
                "--prompt", "task",
            ),
            self.repo,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--accept-allowlist-risk", result.stderr)

    def test_read_only_auto_sandbox_falls_back_to_allowlist(self) -> None:
        environment = os.environ.copy()
        environment["FAKE_SANDBOX_UNAVAILABLE"] = "1"
        result = run_with_env(
            self.base(
                "--mode", "ask", "--prompt", "question",
            ),
            self.repo,
            environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["runner"]["sandbox_fallback"])
        self.assertEqual(payload["runner"]["sandbox_effective"], "disabled")

    def test_cursor_environment_refuses_recursive_invocation(self) -> None:
        environment = os.environ.copy()
        environment["CURSOR_AGENT"] = "1"
        result = run_with_env(
            self.base("--mode", "ask", "--prompt", "question"),
            self.repo,
            environment,
        )
        self.assertEqual(result.returncode, 8)
        self.assertIn("recursive Cursor invocation", result.stderr)


if __name__ == "__main__":
    unittest.main()
