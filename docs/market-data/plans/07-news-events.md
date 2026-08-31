# Plan 07: News and Typed Events

Status: not started

## Objective

Move real-time news and market-event fetching behind stable interfaces, normalize publication time and identity, and replace internal arbitrary event dictionaries with typed variants while preserving existing HTTP response shapes.

## Required reading

1. [`CONTEXT.md`](../../../CONTEXT.md)
2. [`spec.md`](../spec.md), sections 8–10, 15–20
3. Plans 01–06 and their handoffs
4. `tools/ingest/src/astock/news.py`
5. `tools/ingest/src/astock/events.py`
6. control-plane news/event Adapters and queries
7. UI news/event types and rendering code

## Preconditions

- Plans 01–06 are complete.
- Identify current CLI JSON and HTTP compatibility shapes with tests before editing.

## Scope

Migrate:

- stock news;
- notices;
- research reports;
- block trades;
- holder changes;
- CLI/control-plane compatibility projections;
- related source and interface tests.

Persistence remains out of scope; these capabilities stay request-time in v1.

## Deliverables

### 1. News Adapter and contract

Implement current AKShare news fetching behind `NewsSource`. Normalize:

- Instrument identity;
- stable item identity;
- title and optional summary;
- publisher;
- URL;
- timezone-aware publication time or declared date-only normalization warning.

Completion criterion: valid, empty, malformed, missing-time, duplicate, and source-failure fixtures pass the reusable News contract expectations.

### 2. Event Adapters and discriminated records

Implement all four event kinds behind `EventSource` using typed variants from specification section 15.2. Normalize volume to shares, amount to CNY, and percentage values to percentage points.

Completion criterion: no arbitrary `extra: dict[str, Any]` crosses the internal interface.

### 3. Compatibility projection

Generate the existing CLI/HTTP item dictionaries from Standard Records at the control-plane or CLI presentation edge. Preserve:

```text
title, summary, published_at, source, url, extra
```

For typed events, construct `extra` deterministically from the variant. UI types need not change unless tightening them is backward compatible.

Completion criterion: existing API response tests pass and new tests prove projection of every event variant.

### 4. Control-plane seam

The control plane currently launches ingest subprocesses for request-time data. It may continue that deployment shape, but the JSON crossing the process must represent Standard Records or a versioned compatibility DTO produced from them. Document the chosen seam and keep parsing validation explicit.

Completion criterion: control-plane code does not know AKShare columns or vendor exception types and distinguishes typed source failures from successful empty results before applying the user-facing generic error message.

### 5. Cleanup

Remove old mapping functions and tests that patch AKShare calls at use-case level. Keep source payload tests inside Adapter tests.

Completion criterion: direct news/event source calls exist only under Adapter directories.

## Verification

```bash
uv run --directory tools/ingest pytest tests/test_news.py tests/test_events.py tests/test_cli.py
uv run --directory apps/control-plane/core pytest tests/test_http.py tests/test_feature_http.py
pnpm --filter @astock/ui test
pnpm run typecheck
pnpm run check:architecture
```

## Acceptance criteria

- News and Event use cases consume capability interfaces.
- Internal events are typed variants.
- Publication time, units, identity, and errors are normalized.
- Existing CLI/HTTP/UI shapes remain compatible.
- No source-specific mapping remains outside Adapters.

## Handoff

Record:

- Standard Record serialization/process seam;
- stable ID generation rule;
- date-only normalization behavior;
- typed-event-to-`extra` mapping location;
- removed source-shaped paths;
- verification outcomes.
