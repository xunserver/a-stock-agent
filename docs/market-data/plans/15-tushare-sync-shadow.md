# Plan 15: Tushare Synchronization and Shadow Comparison

Status: not started

Release boundary: internal work package; not independently deployable

## Objective

Integrate all completed Tushare Adapters into bootstrap/incremental synchronization
through injected capability interfaces, add credentialed capability probes and a
read-only shadow comparison, and prove downstream compatibility. Production
source defaults remain unchanged.

## Required reading

1. [`../tushare-migration-spec.md`](../tushare-migration-spec.md), sections 7, 9–11
2. [`../spec.md`](../spec.md), synchronization, fallback and observability sections
3. Plans 09–14 handoffs, all complete
4. Ingest composition roots, repositories, scheduler, Qlib export and analysis paths

## Dependencies

Plans 09–14 complete.

## File ownership

This plan owns synchronization composition and new diagnostic tooling/tests, but
not registry/settings defaults. Expected locations:

```text
tools/ingest/src/astock/              existing synchronization use cases
tools/ingest/src/astock/probes/       new Tushare capability probes
tools/ingest/src/astock/compare/      new read-only shadow comparison
tools/ingest/tests/integration/        bootstrap/incremental/probe/compare tests
tools/qlib/ and tools/analyze/ tests   compatibility changes only when required
```

Coordinate every edit outside these areas. Do not mutate production data during
probes/comparison and do not change source settings.

## Deliverables

### 1. Adapter assembly for tests/probes

Construct all Tushare Adapters from one client/executor and inject them through
existing protocols. Do not bypass the registry in production synchronization.

### 2. Bootstrap and incremental behavior

Prove a clean database bootstrap and watermark-driven incremental updates for all
persisted capabilities. Add bounded revisable windows for financial amendments
and membership changes where required. Preserve atomic repository writes and
existing public DTOs.

### 3. Credentialed capability probe

Add a non-destructive command that calls the configured endpoint/account for
every API required by Plans 10–14 using minimal bounded queries. Output contains
capability, API, entitlement/result, schema fields, row count, elapsed time and
redacted endpoint host. It never outputs token or full proprietary content.

The command exits nonzero if any required API is absent, unauthorized, malformed,
or semantically insufficient. Ordinary CI tests use fakes; release execution is mandatory.

### 4. Shadow comparison

Implement a read-only comparison command for the sample in spec section 9. It
compares coverage, natural keys, duplicates, missingness and configured numeric
tolerances. It produces machine-readable JSON plus a concise human summary. It
does not write MarketDB records or choose a winner silently.

### 5. Observability

Ensure all Tushare calls and fallback-ready results emit the required structured
fields without credentials, raw payloads, full article text or unbounded lists.

## Required tests

- clean bootstrap and second-run incremental idempotence;
- revised financial row and changed membership window;
- empty/partial/failure paths do not erase valid stored data;
- probe success, missing entitlement, schema mismatch, and redaction;
- shadow exact match, tolerated numeric difference, unit error, identity/date
  error, missing coverage, duplicate and partial data;
- CLI exit codes and JSON schemas;
- Qlib, analysis, control-plane and UI-facing compatibility as applicable.

## Verification

Run targeted new tests, then the existing ingest/control-plane/Qlib/analyze suites.
Record exact commands and counts in Handoff. At minimum:

```bash
uv run --directory tools/ingest pytest
uv run --directory apps/control-plane/core pytest
uv run --directory tools/qlib pytest
uv run --directory tools/analyze pytest
./scripts/check-architecture.sh
git diff --check
```

Do not run the credentialed probe with a token exposed in shell history or command
arguments. Release operators inject secrets through the approved environment.

## Acceptance criteria

- All 11 capabilities work through bootstrap/incremental orchestration.
- Probe and comparison are non-destructive, bounded, redacted, and have stable output.
- Downstream contracts remain compatible.
- Production source defaults remain unchanged.
- All local verification passes; credentialed results are ready for Plan 16.

## Handoff

Record orchestration changes, revisable windows, command syntax without secrets,
JSON schemas, comparison tolerances/sample, downstream results, and unresolved
release-probe requirements.

## Cursor subagent invocation

```text
Implement docs/market-data/plans/15-tushare-sync-shadow.md after Plans 09–14.
Read all handoffs. Do not change source defaults or production data. Implement
bounded/redacted probes and shadow comparison, run verification, and append evidence.
```

