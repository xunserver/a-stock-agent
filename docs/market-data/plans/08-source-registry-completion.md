# Plan 08: Source Registry and Migration Completion

Status: not started

## Objective

Complete the migration with per-capability source selection, typed fallback, observability, settings integration, architecture enforcement, compatibility cleanup, and full-system verification.

## Required reading

1. [`CONTEXT.md`](../../../CONTEXT.md)
2. [`spec.md`](../spec.md), all sections
3. Plans 01–07 and every handoff
4. ingest settings/configuration modules
5. `scripts/check-architecture.sh`
6. control-plane scheduler, task registry, and ingest process composition roots
7. repository-wide direct source-call search results

## Preconditions

- Plans 01–07 are complete.
- Every migrated capability has at least one production Adapter and one in-memory test Adapter.
- Run `pnpm check` and record inherited failures before editing.

## Scope

This plan may touch cross-cutting ingest configuration, composition roots, settings UI/schema, fallback/registry modules, architecture checks, documentation, and obsolete compatibility code.

Do not add a new Data Source merely to test the registry. Existing multiple Bar Adapters plus in-memory Adapters are sufficient.

## Deliverables

### 1. Capability registry

Implement registry construction at ingest composition roots. Callers resolve a capability interface by capability key, not by importing a concrete Adapter.

Required capability keys:

```text
instruments, calendar, bars, quote_snapshots, valuations,
fundamentals, statements, classifications, memberships, news, events
```

Completion criterion: registry validation fails fast on unknown sources, missing required capabilities, duplicate registry keys, and empty source order.

### 2. Settings integration

Add a versioned ingest settings section for source order per capability. Preserve defaults in specification section 16. Existing installations receive defaults through normal settings migration/merge behavior.

If exposed in UI, use the existing schema-driven settings form rather than a custom page.

Completion criterion: settings tests cover defaults, partial patch, invalid source key, invalid capability key, ordering, and secret-free serialization.

### 3. Fallback module

Implement reusable capability fallback following the error table in specification section 9 and rules in section 16.

Required tests:

- first source succeeds;
- retryable first-source failure selects second;
- unsupported query selects second;
- successful empty Dataset stops;
- `NoData` follows capability policy and defaults to stop;
- authentication failure may select another configured source but is never retried on the same source;
- invalid payload selects next source;
- exhaustion returns an error containing categorized attempt summaries without secrets.

Completion criterion: fallback behavior is fully interface-observable and contains no capability-specific payload mapping.

### 4. Observability

Emit structured or consistently formatted logs for:

```text
capability, source, query identity, attempt, elapsed time,
item count, coverage, completeness, warning count, error category
```

Avoid logging full raw payloads, credentials, cookies, tokens, or unnecessarily large Instrument lists.

Completion criterion: tests capture representative success/fallback/failure logs and assert secret redaction.

### 5. Direct-call removal

Search all production Python code. Move or remove every remaining market-data source call outside `astock.providers` Adapter directories, including scheduler expressions and compatibility façades.

Completion criterion: only Adapter implementation files import/call AKShare, source HTTP endpoints, or source transport libraries for market data.

### 6. Architecture enforcement

Extend `scripts/check-architecture.sh` so future production code cannot reintroduce direct market-data source calls outside approved Adapter paths. Keep patterns narrow enough to allow Adapter code and tests.

Also enforce that `astock_core.market_data` does not import pandas, AKShare, curl-cffi, or ingest modules.

Completion criterion: an intentional temporary violation is detected by the check, then removed; the final check passes.

### 7. Compatibility cleanup

Remove every compatibility façade marked for Plan 08. Remove superseded implementation-detail tests after equivalent interface tests exist. Update README descriptions that still describe ingest as AKShare-specific.

Completion criterion: repository search finds no Plan 08 removal marker and no active duplicate source path.

### 8. Final specification audit

Audit every final acceptance criterion in specification section 21. Record evidence for each criterion in the handoff.

Completion criterion: all ten criteria have concrete file/test/search evidence, not a general assertion.

## Verification

Run targeted settings/fallback/architecture tests first, then:

```bash
pnpm check
```

Also run and record these searches with patterns adjusted only to reduce false positives, not to hide violations:

```bash
rg -n "import akshare|from akshare|ak\.|push2(his)?\.eastmoney|stock_zh_|tool_trade_date" \
  tools/ingest/src apps/control-plane/core/src packages/core/src tools/analyze/src tools/qlib/src

rg -n "TODO.*Plan 08|remove.*Plan 08|compatibility facade" \
  tools/ingest/src apps/control-plane/core/src packages/core/src
```

## Acceptance criteria

- Per-capability source order is configurable and validated.
- Fallback follows typed error semantics and preserves actual provenance.
- Logs provide useful attempt/coverage data without secrets.
- No direct market-data source call remains outside Adapters.
- Architecture checks prevent regression.
- All compatibility façades marked for removal are gone.
- Every final criterion in the specification has evidence.
- `pnpm check` passes.

## Handoff

Replace this section with the final migration report containing:

- source registry defaults and configuration path;
- fallback behavior summary;
- direct-call search output summary;
- architecture rules added;
- compatibility code removed;
- evidence table for specification section 21;
- exact `pnpm check` result;
- any intentionally deferred work, which must be outside specification v1.
