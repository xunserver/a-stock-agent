# Plan 06: Classifications and Memberships

Status: complete

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

Completed 2026-08-31. Industry/concept boards and index constituents now flow through `ClassificationSource` / `MembershipSource`. Board reads default to the canonical eastmoney taxonomy; legacy `em` rows migrate in place.

### Taxonomy keys and identity format

| Taxonomy key | Kind | Classification `id` | Example natural key |
|---|---|---|---|
| `eastmoney` | `industry`, `concept` | Eastmoney board code | `("eastmoney", "BK1027")` |
| `csindex` | `index` | Six-digit index symbol | `("csindex", "000300")` |

Membership natural key: `(taxonomy, classification_id, instrument_id, effective_from)`. Current AKShare snapshots omit `effective_from`.

Helpers: `classification_identity(taxonomy, id)`, `EASTMONEY_TAXONOMY`, `CSINDEX_TAXONOMY`, `DEFAULT_BOARD_TAXONOMY`.

### Persistence/read default policy

- `boards.source` stores taxonomy keys (`eastmoney`, not `em`). Migration **6** rewrites legacy `em` values.
- `list_boards` / `boards_for_code` default `source=DEFAULT_BOARD_TAXONOMY` (`eastmoney`). Pass `source=None` to read all taxonomies; `normalize_board_taxonomy` maps legacy `em` on read.
- Writers: `upsert_classifications`, `replace_classification_members`, `replace_universe_memberships` project Standard Records into `boards`, `board_members`, `universe_members`.
- Pool provenance remains `index:{symbol}`; universe key remains `hs300`.

### Historical-safety behavior

```python
from astock_core.market_data import (
    is_historically_safe,
    historically_safe_memberships,
    memberships_effective_on,
    reject_undated_as_of_query,
    validate_membership_dataset,
)
```

Undated current snapshots remain displayable. `MembershipQuery.as_of` with undated items raises `UnsupportedQuery` via `validate_membership_dataset` / `reject_undated_as_of_query`. Qlib/backtest must not treat undated memberships as historical truth.

### Removed duplicate functions

Deleted from production orchestration:

- `boards.py`: `_fetch_board_names`, `_fetch_board_cons`, `BOARD_SOURCE`, direct AKShare/pandas paths
- `pool.py`: `fetch_index_members`, `resolve_index_symbol` (moved to `indexes.py`)
- `ingest.py`: `fetch_hs300_members` and duplicated csindex/sina index fetch logic

AKShare board/index function names exist only in `tools/ingest/src/astock/providers/akshare/classifications.py`.
Malformed or duplicate catalog/member rows now raise `InvalidSourcePayload`; they are never silently omitted at the Adapter seam.

### Public import paths

```python
from astock.providers.akshare import AkshareClassificationAdapter, AkshareMembershipAdapter
from astock.providers.protocols import ClassificationSource, MembershipSource
from astock.providers.defaults import default_classification_source, default_membership_source
from astock.indexes import index_member_tuples, resolve_index_symbol
from astock_core.market_data import (
    EASTMONEY_TAXONOMY, CSINDEX_TAXONOMY, DEFAULT_BOARD_TAXONOMY,
    validate_classification_dataset, validate_membership_dataset,
    board_rows_from_classifications, membership_code_name_pairs,
)
```

```python
sync_boards(db, *, classification_source=None, membership_source=None)
ingest_hs300_members(db, *, membership_source=None)
ingest_hs300(db, *, ..., membership_source=None)
add_index_to_pool(..., membership_source=None)
```

Board membership queries carry `MembershipQuery.kind`; orchestration does not call Adapter-specific setup methods.

### Verification

```bash
uv run --directory tools/ingest pytest tests/test_boards.py tests/test_stock_info.py tests/test_cli.py
# 9 passed (plan-listed); full ingest suite: 116 passed

uv run --directory apps/control-plane/core pytest tests/test_pool_members.py tests/test_http.py tests/test_feature_http.py
# 18 passed

uv run --directory apps/control-plane/core pytest ../../../packages/core/tests/test_market_read_model.py ../../../packages/core/tests/test_market_migrations.py
# passed (migration version 6, board taxonomy rewrite)

pnpm --filter @astock/ui test
# 51 passed

pnpm run check:architecture
# passed
```

Targeted Plan 06 commands all passed after `pnpm install` (node_modules were absent in the worktree).

### Notes for Plan 07

- News/events still use source-shaped fetchers in `astock/news.py` and `astock/events.py`.
- Keep `astock.providers.defaults`; Plan 08 replaces it with the per-capability registry.
- Do not add historical membership tables until a source supplies trustworthy effective dates.
