# Plan 16: Tushare Registry Integration and Atomic Cutover

Status: not started

Release boundary: final integration gate for the single Tushare migration release

## Objective

Integrate every completed Tushare Adapter into the capability registry, migrate
settings atomically to schema version 2, run all release gates, rehearse rollback,
and switch every capability to Tushare primary only when the complete release is
accepted. This is the only plan authorized to change production source defaults.

## Required reading

1. [`../tushare-migration-spec.md`](../tushare-migration-spec.md), completely
2. [`../spec.md`](../spec.md), completely
3. Plans 09–15 and every completed Handoff
4. Registry, fallback, settings catalog/API/UI, migrations, scheduler and release tooling
5. Repository-wide direct source-call and secret searches

## Dependencies

Plans 09–15 complete with no deferred acceptance criterion.

## File ownership

This plan owns final cross-cutting integration:

```text
tools/ingest/src/astock/providers/registry.py
tools/ingest/src/astock/providers/tushare/__init__.py
tools/ingest/src/astock/config.py
packages/core/src/astock_core/settings/catalog.py
settings migration/tests and schema-driven UI tests
release verification documentation
```

Capability Adapter behavior changes must return to the owning plan unless needed
to fix a release-blocking integration defect, which must be documented.

## Deliverables

### 1. Registry integration

- Add `tushare` to known sources and construct every Adapter from one shared
  client/executor per registry instance.
- Validate support for all 11 capability keys at registry construction.
- Preserve actual `Dataset.source` and existing typed fallback semantics.
- Prove Tushare-to-AKShare fallback for each protocol using fakes/fixtures.

### 2. Atomic settings migration

- Add source-order schema version 2 exactly as specified.
- Replace untouched version 1 defaults in one transaction.
- Preserve explicitly customized existing orders and require operator opt-in.
- Reject partial/missing capability sets, duplicates, unknown sources, and invalid versions.
- Keep tokens/endpoints out of serializable settings responses.

### 3. Release gates

Before changing defaults, capture and retain evidence that:

- the credentialed production endpoint/account probe passes every required API;
- the complete shadow comparison has no unexplained invariant/completeness failure;
- bootstrap and incremental synchronization pass;
- architecture and secret scans pass;
- all targeted and repository-wide tests pass.

If any gate fails, do not perform the settings migration and mark this plan blocked
with concrete evidence. AKShare fallback is not a substitute for a failed primary
capability release probe.

### 4. Atomic activation and rollback rehearsal

- Capture the exact pre-migration source setting.
- Apply schema version 2 in one settings transaction.
- Confirm every capability resolves Tushare first and AKShare second.
- Run bounded post-activation smoke queries for every capability.
- Restore the captured setting in one transaction and prove all prior sources resolve.
- Reapply version 2 only after rollback rehearsal and smoke tests succeed.

No destructive data deletion, code rollback, or per-capability activation is allowed.

### 5. Final audit

Search for direct Tushare/AKShare/Eastmoney calls outside Adapters, embedded tokens,
private SDK attribute access outside the client factory, old defaults, schema
version drift, and stale documentation describing AKShare as the ingest source.

Update the implementation evidence section of the migration spec and this plan's
Handoff with exact results. Do not record secrets or raw proprietary payloads.

## Required tests

- registry factory and all 11 Tushare-first source orders;
- per-capability fallback and source provenance;
- schema 1 untouched/custom migrations and schema 2 validation;
- settings API/UI ordering and secret-free serialization;
- missing token behavior when Tushare selected versus not selected;
- full-system bootstrap/incremental and bounded smoke orchestration;
- rollback and reapply transaction tests;
- log/error/CLI redaction and architecture checks.

## Verification

Run targeted integration tests first, then:

```bash
pnpm check
./scripts/check-architecture.sh
git diff --check
```

Run and record narrow repository searches for:

```text
Tushare/AKShare/Eastmoney direct calls outside approved Adapter directories
_DataApi__token and _DataApi__http_url outside the client factory
token-like literals and TUSHARE_TOKEN serialization
schema_version 1/default source-order remnants
```

Run the credentialed probe and shadow comparison through their approved commands
with secret injection that does not expose the token in arguments or logs.

## Acceptance criteria

Every criterion in section 13 of the migration spec must have concrete evidence.
Additionally:

- the final source-order object exactly matches specification section 8;
- all 11 post-activation smoke queries select `tushare` without fallback;
- all 11 fallback tests select AKShare when the primary raises an eligible typed error;
- rollback and reapplication both succeed transactionally;
- `pnpm check` and architecture/secret audits pass;
- no acceptance item is deferred.

Failure of any item blocks the entire cutover.

## Handoff

Append:

- final changed-file summary;
- SDK version and redacted endpoint host label;
- API/entitlement probe matrix;
- source settings before, after, rollback, and reapply;
- shadow comparison summary and discrepancy dispositions;
- test commands/counts and architecture/search evidence;
- post-activation smoke result for every capability;
- optional Standard Record fields intentionally unavailable;
- final release decision.

Mark `Status: complete` only after the defaults are atomically activated and all
evidence is present. Otherwise use `blocked`; never report partial migration complete.

## Cursor subagent invocation

```text
Implement docs/market-data/plans/16-tushare-atomic-cutover.md only after Plans
09–15 are complete. Read the full specs and every handoff. This is the sole plan
allowed to change registry/settings defaults. Run every release gate before the
atomic migration; on any failure, leave defaults unchanged and report blocked.
Append complete, secret-free evidence and the final release decision.
```

