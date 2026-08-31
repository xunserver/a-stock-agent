---
name: delegate-to-cursor
description: Decompose a repository spec into bounded slices and orchestrate Cursor implement-review-repair loops in isolated worktrees.
---

# Delegate to Cursor

Use only when the user invokes `$delegate-to-cursor`. If loaded inside Cursor Agent, stop rather than delegate recursively.

## Roles

- **Codex orchestrator:** inspect current state, split the spec, build the dependency plan and acceptance packets, run deterministic gates, route structured findings, and integrate accepted slices.
- **Cursor implementer:** implement one slice and repair it in the same session.
- **Fresh Cursor reviewer:** inspect the implementation independently, execute the slice's evidence commands, and return a structured verdict.

Keep the normal path inside this loop. Codex does not manually review the full diff or reimplement failed work unless the loop reaches an escalation condition.

## 1. Split the spec

Create a dependency-ordered plan. One slice owns one semantic seam: one cohesive behavior, its tests, and directly coupled callers. Split independent deliverables such as registry, fallback, observability, composition wiring, and compatibility cleanup.

For each slice, define:

- objective and stopping boundary;
- base slice/OID;
- authoritative entry files;
- acceptance criteria and edge cases;
- focused evidence commands and the later integration gate;
- expected write-path globs;
- compatibility invariants and non-goals.

Finish planning only when every spec requirement belongs to exactly one slice or the final integration gate. Use a read-only Cursor `plan` run when callers or path ownership are unclear, then review only the plan structure before execution.

## 2. Build the implementation packet

Give the implementer only the slice-local context. Summarize inherited plans instead of asking it to reread the whole project history. Include exact acceptance criteria, permitted paths, edge cases, focused commands, and required report fields: changed paths, commands with exit codes, unresolved criteria, and surprises.

Keep global status and handoff files outside slice allowlists. The orchestrator updates them after the final loop passes. Exclude secrets and external side effects.

Input-token warnings mean the slice is still too large. Split the next attempt; do not raise the hard limit to finish a monolithic run.

## 3. Prepare an exact base

Use `execute --isolate`. An isolated worktree contains only `--worktree-base`.

For dependent slices, preserve the accepted tree as an immutable Git object and pass its exact OID. `git stash create` does not move refs or alter the worktree, but new files must already be indexed; preserve and restore the user's original index state while preparing the base.

Derive `--allow-path` globs from the slice. Include its tests and fixtures without using repository-wide wildcards.

## 4. Run the implementer

Resolve `scripts/cursor_delegate.py` relative to this file:

```bash
python3 <skill-dir>/scripts/cursor_delegate.py \
  --mode execute \
  --workspace <repo> \
  --isolate \
  --worktree-base <exact-oid> \
  --sandbox auto \
  --accept-allowlist-risk \
  --force \
  --model composer-2.5 \
  --allow-path 'src/seam/**' \
  --allow-path 'tests/seam/**' \
  --allow-shell git \
  --allow-shell pytest \
  --prompt-file <implementation-packet>
```

Record `actual_workspace` and `session_id`. Treat `runner.accepted` as the structural gate: it covers process, token, Git, path, and diff-check integrity, not semantic correctness. Classify every rejection reason before continuing; preserve useful isolated work before cleanup.

## 5. Run a fresh reviewer

Start a new read-only Cursor session against `actual_workspace`; never resume the implementer's session for review. Give it the raw acceptance packet, exact base OID, and evidence commands—not the implementer's conclusions.

```bash
python3 <skill-dir>/scripts/cursor_delegate.py \
  --mode ask \
  --workspace <actual-worktree> \
  --model composer-2.5 \
  --require-result-json \
  --allow-shell git \
  --allow-shell pytest \
  --prompt-file <review-packet>
```

Require this final JSON object:

```json
{
  "status": "pass | fail",
  "findings": [
    {
      "criterion": "acceptance criterion id",
      "severity": "blocking | non_blocking",
      "evidence": "file:line, command result, or observed behavior",
      "repair": "specific required change"
    }
  ],
  "verified_commands": ["command + exit code"],
  "unverified": ["criterion and reason"]
}
```

A pass requires zero blocking findings, an empty `unverified` list, and direct evidence for every slice criterion. The runner exposes the object as `structured_result`.

## 6. Execute the repair loop

Route any structural-gate failure, deterministic test failure, blocking finding, or unverified criterion back to the implementer with exact evidence. Resume inside its dedicated worktree:

```bash
python3 <skill-dir>/scripts/cursor_delegate.py \
  --mode execute \
  --workspace <actual-worktree> \
  --resume <implementation-session-id> \
  --accept-dirty-worktree \
  --sandbox auto \
  --allow-path 'src/seam/**' \
  --allow-path 'tests/seam/**' \
  --prompt '<structured findings plus failing commands>'
```

After repair, run deterministic gates and launch another **fresh** reviewer. Accept the slice when all three gates agree:

1. runner structural gate is accepted;
2. focused tests pass with trustworthy exit codes;
3. fresh reviewer returns `pass` with no blocking or unverified items.

Limit a slice to three repair rounds. Escalate when the same finding survives twice, the third review fails, reviewers contradict deterministic evidence, or repairs cross into another slice. On escalation, Codex may inspect the disputed area, resplit the slice, or finish a small repair locally.

## 7. Integrate and continue

Transfer an accepted slice to the orchestrator tree, create the next exact base OID, and dispatch the next dependency-ready slice. Preserve unrelated user changes.

After all slices pass, run the full project gate and one fresh Cursor integration review across the accumulated diff and global acceptance matrix. Route integration findings through the same repair loop. Update plan status and handoff only after the integration gates pass.

## Safety boundary

Git auditing cannot observe ignored files, services, databases, or external MCP mutations. Keep them outside the loop unless explicitly authorized and independently gated. Keep commits, pushes, deployments, credential changes, and destructive external actions outside packets unless the user expressly authorizes them.
