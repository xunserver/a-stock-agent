# Plan 06: Classifications and Memberships

Status: not started

## Objective

Unify index constituents, industry boards, and concept boards as source-independent Classifications and Memberships while preserving current pools, universes, board displays, and synchronization commands.

## Required reading

1. [`CONTEXT.md`](../../../CONTEXT.md)
2. [`spec.md`](../spec.md), sections 7–10, 14, 16–20
3. Plans 01–05 and their handoffs
4. `tools/ingest/src/astock/boards.py`
5. `tools/ingest/src/astock/pool.py`
6. index membership functions in `tools/ingest/src/astock/ingest.py`
7. stock, pool, universe, and board repository methods/tests

## Preconditions

- Plans 01–05 are complete.
- Existing InstrumentId conversion covers stocks and index identifiers used here.
- Inventory all current classification identifiers and `source` filtering assumptions.

## Scope

Migrate:

- industry and concept catalogs;
- industry and concept memberships;
- index constituent fetching used by universes and pool operations;
- current-state persistence projections;
- affected commands and tests.

Do not implement historical membership tables unless a current source supplies trustworthy effective dates and the change remains bounded.

## Deliverables

### 1. Classification and Membership Adapters

Implement current AKShare-backed source calls behind `ClassificationSource` and `MembershipSource`. Represent index groupings as `kind=index`; declare taxonomy explicitly.

Completion criterion: source IDs are qualified by taxonomy and cannot collide across taxonomies.

### 2. Contracts

Complete reusable contracts covering:

- stable classification identity;
- valid kinds and taxonomies;
- InstrumentId membership identity;
- duplicate removal/rejection policy;
- optional effective dates and weights;
- deterministic ordering;
- conclusive empty membership sets.

Completion criterion: in-memory and source fixture Adapters pass identical contracts.

### 3. Persistence projection

Project current Classifications and Memberships into existing `boards`, `board_members`, and `universe_members` structures. Remove implicit `source="em"` read filtering; callers either specify a taxonomy/source deliberately or consume the configured canonical taxonomy.

Any schema change must be versioned and migration-tested. Preserve current pool-member history semantics.

Completion criterion: existing board and pool queries return the same user-visible groups/members for equivalent fixtures.

### 4. Synchronization cutover

Switch `sync_boards`, index-to-pool, index-to-stocks, and HS300 universe ingestion to the new interfaces. Tests inject in-memory Adapters.

Completion criterion: use-case tests do not monkeypatch AKShare index/board functions.

### 5. Historical-safety marker

Expose or document whether Memberships have effective dates. Qlib/backtest code must not treat undated current membership snapshots as historical truth.

Completion criterion: a test or explicit projection rejects historical-as-of membership queries when only current snapshots exist.

### 6. Cleanup

Remove duplicate HS300/index constituent fetch implementations and source-shaped board helpers once all callers migrate.

Completion criterion: board/index source columns and function names exist only in Adapter code/tests.

## Verification

```bash
uv run --directory tools/ingest pytest tests/test_boards.py tests/test_stock_info.py tests/test_cli.py
uv run --directory apps/control-plane/core pytest tests/test_pool_members.py tests/test_http.py tests/test_feature_http.py
uv run --directory apps/control-plane/core pytest ../../../packages/core/tests/test_market_read_model.py ../../../packages/core/tests/test_market_migrations.py
pnpm --filter @astock/ui test
pnpm run check:architecture
```

## Acceptance criteria

- Indexes, industries, and concepts use the Classification/Membership interfaces.
- Taxonomy-qualified identities eliminate implicit global source IDs.
- Current user-visible pool/board behavior remains compatible.
- Undated memberships are not presented as historical truth.
- Duplicate source fetch paths are removed.

## Handoff

Record:

- taxonomy keys and identity format;
- persistence/read default policy after removing implicit `em` filtering;
- historical-safety behavior;
- removed duplicate functions;
- verification outcomes.
