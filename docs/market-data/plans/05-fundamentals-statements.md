# Plan 05: Fundamentals and Financial Statements

Status: complete

## Objective

Move financial summary and three-statement data behind source-independent Fundamental and Statement interfaces. Introduce stable internal line-item codes so read models no longer depend on Eastmoney identifiers.

## Required reading

1. [`CONTEXT.md`](../../../CONTEXT.md)
2. [`spec.md`](../spec.md), sections 8–10, 13, 16–20
3. Plans 01–04 and their handoffs
4. `tools/ingest/src/astock/financial.py`
5. Current profile financial fetch/mapping modules
6. `packages/core/src/astock_core/financial_statements.py`
7. `financial_statement_templates.json` and `financial_statement_labels.json`
8. Financial repository, control-plane, and UI tests/types

## Preconditions

- Plans 01–04 are complete.
- The Plan 04 handoff assigns every current financial field to Fundamental Period.
- Capture the set of statement keys currently displayed by `extract_statement_items`; this is the compatibility baseline.

## Scope

Migrate:

- single-stock and batch financial summaries;
- balance, profit, and cash-flow statement fetching;
- stable line-item normalization;
- financial persistence projections and read models;
- related control-plane/UI compatibility tests.

Do not redesign the visual layout of financial tabs or add new accounting analytics.

## Deliverables

### 1. Fundamental Adapter and contract

Implement the current AKShare financial summary sources behind `FundamentalSource`. Normalize reporting period, announcement date, currency, units, and percentage points.

Batch and single-Instrument implementations must produce the same Standard Record shape and natural key.

Completion criterion: one reusable contract suite passes for both batch fixtures and single-Instrument fixtures, including missing announcement dates and restated periods.

### 2. Statement Adapter and contract

Implement balance/profit/cashflow source mapping behind `StatementSource`. Convert each source row into `FinancialStatement` and normalized `StatementItem` records.

Completion criterion: no source field identifier crosses the Statement interface; malformed mixed-period or empty statements produce typed outcomes.

### 3. Canonical line-item registry

Create one internal registry that maps stable snake_case item codes to labels, units, and source aliases. It must cover:

- every minimum item in specification section 13.2;
- every key item currently displayed;
- existing YoY and QoQ associations needed by the UI.

Keep source aliases inside Adapter-owned mapping data. The domain registry contains only canonical codes and display metadata.

Completion criterion: a test proves every previously displayed key item maps to one canonical code or is explicitly classified as unsupported with a documented reason.

### 4. Persistence migration

Choose the smallest persistence change that allows normalized statement items to be reconstructed without source identifiers. Acceptable approaches:

- store normalized item JSON in the existing payload column; or
- add versioned normalized payload columns/tables with migration tests.

Preserve existing report dates and summary queries. Existing databases must migrate in place.

Completion criterion: migration tests open both legacy and new database fixtures and return equivalent key-item read models.

### 5. Point-in-time safety

Persist and expose announcement date when supplied. Add a clear internal predicate/helper for whether a Fundamental Period is safe for point-in-time research. Do not silently substitute period end for announcement date.

Completion criterion: tests prove records without announcement dates remain displayable but are excluded by the point-in-time-safe projection.

### 6. Cut over and remove source-shaped paths

Switch stock info sync, explicit statement sync, repository methods, and read-model extraction to Standard Records. Remove obsolete source-row mappers and implementation-detail tests.

Completion criterion: production financial code outside Adapter directories contains no AKShare function name or Eastmoney statement key.

## Verification

```bash
uv run --directory tools/ingest pytest tests/test_financial_reports.py tests/test_financial_statements.py tests/test_stock_info.py
uv run --directory apps/control-plane/core pytest tests/test_financial_statements.py tests/test_http.py tests/test_feature_http.py
uv run --directory apps/control-plane/core pytest ../../../packages/core/tests/test_financial_statements.py ../../../packages/core/tests/test_market_migrations.py
pnpm --filter @astock/ui test
pnpm run typecheck
pnpm run check:architecture
```

Run `pnpm check` before completion.

## Acceptance criteria

- Fundamental and Statement interfaces are the only production source-data seam.
- Batch and single fetches yield identical Standard Record semantics.
- Read models no longer depend on Eastmoney statement identifiers.
- Legacy databases migrate without losing statement display data.
- Point-in-time safety is explicit.
- Full verification passes.

## Handoff

Completed 2026-08-31. Financial summaries and three-statement fetching now consume `FundamentalSource` / `StatementSource`. Read models use canonical snake_case line-item codes. No source registry was added (Plan 08).

### Canonical line-item registry

Location: `packages/core/src/astock_core/market_data/line_items.py`

Contains spec section 13.2 minimums plus the previously displayed key-item set, with labels and units only. Source aliases are not in this module.

Extension procedure:

1. Add a `LineItemSpec` (stable snake_case `code`, display `label`, `unit`, `sheet`).
2. If it is a specification minimum, also add the code to `CANONICAL_*_ITEMS` in `models.py`.
3. Map Data Source field names in `tools/ingest/src/astock/providers/akshare/statement_aliases.py` (live Adapter table) and keep `LEGACY_SOURCE_ALIASES` in `astock_core.financial_statements` in sync.
4. YoY/QoQ are `StatementItem.yoy_pct` / `qoq_pct`, not separate registry codes.

### Legacy-to-canonical mapping coverage

Previously displayed `extract_statement_items` key items:

| Source key | Canonical code |
|---|---|
| `OPERATE_INCOME` | `operating_revenue` |
| `TOTAL_PROFIT` | `total_profit` |
| `PARENT_NETPROFIT` | `parent_net_profit` |
| `NETPROFIT` | `net_profit` |
| `TOTAL_ASSETS` | `total_assets` |
| `TOTAL_LIABILITIES` | `total_liabilities` |
| `TOTAL_EQUITY` | `total_equity` |
| `NETCASH_OPERATE` | `net_operating_cashflow` |
| `NETCASH_INVEST` | `net_investing_cashflow` |
| `NETCASH_FINANCE` | `net_financing_cashflow` |

Remaining template fields default to `key.lower()`. Companions (`_YOY` / `_QOQ` / `_MOM` / `_TZ`) attach to the parent item. `SECURITY_TYPE_CODE` and statement metadata keys are classified unsupported (not line items). Tests: `test_previously_displayed_key_items_map_to_canonical_codes`, `test_template_line_items_map_or_are_documented_unsupported`.

### Persistence choice and migration number

Normalized statement items are stored in the existing `payload_json` column as:

```json
{"schema": "statement_items_v1", "items": [{"code", "label", "value", "unit", "yoy_pct", "qoq_pct"}]}
```

Market schema migration **5** (`_normalize_statement_payloads`) rewrites legacy Eastmoney-keyed JSON in place. Report dates, sheet keys, and summary queries are unchanged. `financial_reports` columns are unchanged; Fundamental Periods project into them via `upsert_fundamental_periods`. Latest period also projects into `stocks` fundamental columns (`eps`, `bps`, `roe`, …).

Read: `MarketDB.get_financial_statement` returns canonical `payload` / `items`. Control-plane `key_items` come from `extract_statement_items`.

### Point-in-time-safe helper

```python
from astock_core.market_data import is_point_in_time_safe, point_in_time_safe_periods
```

`announced_at=None` remains displayable. Those records are excluded by `point_in_time_safe_periods`. Period end is never substituted for announcement time.

### Public import paths

```python
from astock.providers.akshare import AkshareFundamentalAdapter, AkshareStatementAdapter
from astock.providers.protocols import FundamentalSource, StatementSource
from astock.providers.defaults import default_fundamental_source, default_statement_source
from astock_core.market_data import (
    line_item, LINE_ITEMS, period_type_from_end,
    is_point_in_time_safe, point_in_time_safe_periods,
    validate_fundamental_dataset, validate_statement_dataset,
)
```

```python
MarketDB.upsert_fundamental_periods(periods) -> int
MarketDB.upsert_standard_statements(statements) -> int
```

`upsert_financial_reports` / `upsert_financial_statements` remain for dict rows and convert statement JSON to `statement_items_v1` on write.

### Use-case dependency shapes

```python
sync_stock_info(
    db, codes, *, sleep=None, with_statements=False,
    profile_source=None, snapshot_source=None, valuation_source=None,
    fundamental_source=None, statement_source=None,
)
sync_financial_statements(db, codes, *, sheets=("balance", "profit", "cashflow"), statement_source=None)
```

`None` source arguments construct defaults. Tests inject in-memory Adapters.

### Removed source-shaped modules/functions

Deleted:

- `tools/ingest/src/astock/profile.py`
- `tools/ingest/src/astock/_profile_fetchers.py`
- `tools/ingest/src/astock/_profile_mappers.py`
- `tools/ingest/src/astock/_profile_codec.py`
- `tools/ingest/tests/test_profile.py`

Removed from `financial.py`: `em_symbol`, `normalize_statement_row`, `fetch_financial_statement_sheet`, `extract_key_items`, and direct AKShare sheet fetchers. `financial.py` is now Statement sync orchestration only.

AKShare function names for this capability exist only in:

```text
tools/ingest/src/astock/providers/akshare/fundamentals.py
tools/ingest/src/astock/providers/akshare/statements.py
```

### Design decisions

- One Adapter handles both batch (yjbb/zcfz/lrb, default `batch_min_instruments=8`) and single-Instrument (indicator) paths; both emit the same `FundamentalPeriod` natural key `(instrument_id, period_end, period_type)`.
- Restated periods with the same natural key keep the later `announced_at` and add a Dataset warning.
- Statement Dataset items are ascending by `(instrument_id, period_end, period_type)`. HTTP list endpoints still return report dates descending.
- HTTP `payload` keys are now canonical codes (`operating_revenue`, not `OPERATE_INCOME`). `key_items[].key` matches. UI companion lookup accepts `_yoy`/`_qoq` as well as `_YOY`/`_QOQ`.
- Live source aliases are Adapter-owned (`statement_aliases.py`); `LEGACY_SOURCE_ALIASES` in core reconstructs pre-migration stored JSON. A test requires the two dicts to stay equal.

### Known leftover

`astock_core.financial_statements.LEGACY_SOURCE_ALIASES` still names Eastmoney keys for in-place database reconstruction. After migration 5, new writes are `statement_items_v1` only. Do not use those keys in control-plane or UI read models.

### Verification

```bash
uv run --directory tools/ingest pytest tests/test_financial_reports.py tests/test_financial_statements.py tests/test_stock_info.py
# passed (with the rest of ingest: 107 passed)

uv run --directory apps/control-plane/core pytest tests/test_financial_statements.py tests/test_http.py tests/test_feature_http.py
# passed

uv run --directory apps/control-plane/core pytest ../../../packages/core/tests/test_financial_statements.py ../../../packages/core/tests/test_market_migrations.py
# passed

pnpm --filter @astock/ui test
# 51 passed

pnpm run typecheck
# passed

pnpm run check:architecture
# passed

pnpm check
# passed: architecture, UI 51, typecheck, python (core+control-plane 242, cli 1, ingest 107, analyze 19, qlib 8)
```

Acceptance: Fundamental and Statement interfaces are the production source-data seam; batch and single fetches share Standard Record semantics; read models no longer depend on Eastmoney identifiers; legacy databases migrate without losing key-item display data; point-in-time safety is explicit; full verification passed.

### Notes for Plan 06

- Keep `astock.providers.defaults`; Plan 08 replaces it with the per-capability registry.
- Classifications/memberships still use source-shaped board fetchers.
- Do not fold financial fields back into snapshot Adapters.
- Prefer `upsert_fundamental_periods` / `upsert_standard_statements` for new writers.
