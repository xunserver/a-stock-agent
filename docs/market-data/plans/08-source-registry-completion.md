# Plan 08: Source Registry and Migration Completion

Status: complete

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

Completed 2026-08-31. Inherited baseline before edits: `pnpm check` passed with **250** core/control-plane tests, **140** ingest, **19** analyze, **8** qlib, **51** UI, plus architecture and typecheck.

### Source registry defaults and configuration path

- Settings section: `ingest.sources` in `system.db` (seeded by `packages/core/src/astock_core/settings/catalog.py`, `SCHEMA_VERSION=3`).
- Runtime read: `astock.config.sources_settings()` → `validate_source_order_config()` in `tools/ingest/src/astock/providers/registry.py`.
- Registry construction: `build_registry()` / `CapabilityRegistry.from_settings()` in `tools/ingest/src/astock/providers/registry.py`.
- Default source order (spec section 16):

```json
{
  "schema_version": 1,
  "bars": ["eastmoney", "akshare"],
  "calendar": ["akshare"],
  "instruments": ["akshare"],
  "quote_snapshots": ["eastmoney", "akshare"],
  "valuations": ["eastmoney", "akshare"],
  "fundamentals": ["akshare"],
  "statements": ["akshare"],
  "classifications": ["akshare"],
  "memberships": ["akshare"],
  "news": ["akshare"],
  "events": ["akshare"]
}
```

Validation fails fast on unknown sources, unknown capability keys, missing required capabilities, duplicate sources per capability, and empty source order (`tools/ingest/tests/providers/test_registry.py`).
Runtime validation also rejects unsupported `schema_version` values; settings-schema tests cover invalid source/capability patches and preserve configured order.

### Fallback behavior summary

- Module: `tools/ingest/src/astock/providers/fallback.py`.
- Follows spec section 9 error table via `should_try_next_source()`.
- `NoData` stops by default (`_NO_DATA_FALLBACK_CAPABILITIES` empty).
- Successful empty `Dataset` stops fallback; selected `Dataset.source` is preserved (never reports registry/fallback wrapper).
- Authentication failures advance to the next source without same-source retry.
- A policy stop such as default `NoData` re-raises the original typed error without touching the next source. True exhaustion raises `FallbackExhausted` with categorized attempt summaries and secret-stripped messages.
- Tests: `tools/ingest/tests/providers/test_fallback.py` (first success, retryable failure, unsupported query, empty dataset, NoData policy, auth failure, invalid payload, exhaustion).

### Observability

- Module: `tools/ingest/src/astock/providers/observability.py`.
- Logger: `astock.providers.market_data`.
- JSON log fields: `capability`, `source`, `query_identity`, `attempt`, `elapsed_ms`, `item_count`, `coverage_start`, `coverage_end`, `complete`, `warning_count`, `error_category`, `outcome`.
- Large instrument lists truncated; `redact_message()` masks api_key/token/cookie/password patterns.
- Tests: `tools/ingest/tests/providers/test_observability.py`.

### Composition roots changed

| Location | Change |
|---|---|
| `tools/ingest/src/astock/cli/handlers.py` | Builds one registry and injects sources for news/events, index pool/stock operations, stock sync, boards, calendar, and quotes |
| `tools/ingest/src/astock/providers/registry.py` | `resolve_capability(key)` supports explicit registry-backed direct library/debug calls |
| `tools/ingest/src/astock/config.py` | `sources_settings()` reads validated `ingest.sources` |
| Use cases (`ingest.py`, `quotes.py`, `stock.py`, `boards.py`, `news.py`, `events.py`, `financial.py`, `indexes.py`) | Keep injectable public signatures; `None` sources resolve by capability key, never a concrete/default Adapter helper |

`StockInfoComposite` (Eastmoney primary + AKShare ST/suspend overlay) is built inside the registry when both sources appear in `quote_snapshots` order.

### Direct-call search output summary

```bash
rg -n "import akshare|from akshare|ak\.|push2(his)?\.eastmoney|stock_zh_|tool_trade_date" \
  tools/ingest/src apps/control-plane/core/src packages/core/src tools/analyze/src tools/qlib/src
```

All matches are under `tools/ingest/src/astock/providers/{akshare,eastmoney}/` only (Adapter implementation). Zero matches in control-plane, core, analyze, qlib production code.

```bash
rg -n "TODO.*Plan 08|remove.*Plan 08|compatibility facade" \
  tools/ingest/src apps/control-plane/core/src packages/core/src
```

No matches (exit code 1).

### Architecture rules added

`scripts/check-architecture.sh` now rejects outside the approved source Adapter directories (`providers/akshare/**`, `providers/eastmoney/**`) and tests:

- `import akshare` / `from akshare` / `ak.stock_*` / `ak.tool_*` / `ak.index_*`
- `push2` / `push2his` Eastmoney hosts
- `stock_zh_*` / `tool_trade_date`
- common AKShare board/financial/news function prefixes
- source transport imports such as `curl_cffi`

It also rejects pandas/AKShare/curl-cffi/ingest imports inside `packages/core/src/astock_core/market_data`.

Probe test proves detection: `tools/ingest/tests/test_architecture_market_data.py` (temporary `_architecture_violation_probe.py` created then removed).

### Compatibility code removed

- `providers/defaults.py`, `DefaultStockInfoAdapter`, and all per-capability default helper façades (replaced by registry composition + `StockInfoComposite`).
- Legacy `astock/eastmoney.py`; the `curl_cffi` transport now lives inside `providers/eastmoney/_transport.py`.
- Public tuple writers `MarketDB.upsert_bars` / `upsert_index_bars` (`packages/core/src/astock_core/_market_bars.py`); tests migrated to `upsert_standard_bars` / `upsert_standard_index_bars`.
- Plan 08 removal markers in production Python (verified by search above).

### Specification section 21 evidence

| # | Criterion | Evidence |
|---|---|---|
| 1 | External market-data calls only in Adapters | Direct-call `rg` output: matches only under `tools/ingest/src/astock/providers/` |
| 2 | No sync/repo/control-plane/Qlib/UI imports vendor clients or source payloads | vendor-import/source-call search has no non-Adapter matches; Qlib's own pandas frames are not source payloads; `packages/core/tests/market_data/test_no_vendor_surface.py` |
| 3 | Every capability returns validated `Dataset` | Plans 02–07 contract suites; registry wraps existing Adapters without bypassing validation |
| 4 | CLI/HTTP/UI/Qlib behavior compatible | `pnpm check` green; ingest/control-plane/UI/qlib test suites unchanged in public contracts |
| 5 | Per-capability source order + fallback | `ingest.sources` settings + `fallback.py` + `test_registry.py` / `test_fallback.py` |
| 6 | Scheduler/manual sync share Calendar interface | Plan 03 scheduler path and CLI manual sync both resolve the registry-backed `CalendarSource` |
| 7 | Statement read models free of Eastmoney field IDs | Plan 05 handoff; `statement_items_v1` canonical codes |
| 8 | Every Adapter passes contract suite | `tools/ingest/tests/providers/test_*_contract.py` and adapter tests in full ingest suite |
| 9 | Architecture checks reject new direct calls | `scripts/check-architecture.sh` + `test_architecture_market_data.py` |
| 10 | `pnpm check` passes | See below |

### Exact `pnpm check` result

```text
pnpm check
# architecture: passed
# UI: 51 passed
# typecheck: passed
# python:
#   core+control-plane: 250 passed
#   cli: 1 passed
#   ingest: 174 passed
#   analyze: 19 passed
#   qlib: 8 passed
```

Targeted first: `pytest tests/providers/test_registry.py tests/providers/test_fallback.py tests/providers/test_observability.py tests/test_architecture_market_data.py` → 29 passed.

### Intentionally deferred (outside spec v1)

- News/events persistence (Plan 07 note; real-time response only).
- Historical membership effective dates (no trustworthy source dates).
- Intraday bars, streaming, new Data Sources beyond `eastmoney`/`akshare`.
- `InstrumentProfile` as a separate settings capability key (profiles follow `quote_snapshots` registry path + overlay).
- Field-level provenance beyond Dataset warnings.
