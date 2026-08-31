# Plan 01: Contract Foundation

Status: complete

## Objective

Create the dependency-free Standard Records, queries, Dataset envelope, typed errors, validation module, and capability interfaces described in the specification. This plan establishes the seam but does not switch production ingest behavior.

## Required reading

Read completely before editing:

1. [`CONTEXT.md`](../../../CONTEXT.md)
2. [`spec.md`](../spec.md), especially sections 4–11 and 19
3. `packages/core/pyproject.toml`
4. `packages/core/src/astock_core/__init__.py`
5. Existing core tests under `packages/core/tests/`

## Preconditions

- No earlier plan is required.
- Inspect `git status --short` and preserve unrelated changes.
- Confirm `astock-core` still has no runtime dependencies. This plan must keep it dependency-free.

## Scope

Create:

```text
packages/core/src/astock_core/market_data/
tools/ingest/src/astock/providers/protocols.py
packages/core/tests/market_data/
tools/ingest/tests/providers/
```

Update package exports only as needed to expose deliberate public types.

Do not:

- add AKShare or Eastmoney Adapters;
- modify current ingest orchestration;
- change SQLite schemas;
- change HTTP or UI types;
- add Pydantic, pandas, or third-party dependencies to `astock-core`.

## Deliverables

### 1. Identity and enums

Implement and test:

- `InstrumentId` parsing, formatting, ordering, and legacy six-digit conversion helpers;
- `AssetType`, `BarInterval`, `Adjustment`, `FinancialPeriodType`, `FinancialSheet`, `ClassificationKind`;
- supported A-share exchange inference in one named function, with Beijing `4`, `8`, and `92` prefixes handled explicitly.

Completion criterion: valid identifiers round-trip; malformed and unsupported identifiers raise a documented `ValueError` subtype or validation error.

### 2. Dataset and errors

Implement `Dataset[T]` and every error in specification sections 8 and 9.

Completion criterion: Dataset construction rejects empty source keys, naive `fetched_at`, inverted coverage, and mutable collection inputs that bypass the tuple interface.

### 3. Queries and Standard Records

Implement all query and Standard Record types from specification sections 7 and 10–15. Types not migrated until later plans still belong here so later Agents do not invent competing shapes.

Keep constructors readable. Put cross-field validation in the validation module when embedding it in dataclass `__post_init__` would make models shallow wrappers around validation complexity.

Completion criterion: every field and natural key in the specification has one canonical Python representation and a focused test.

### 4. Validation

Implement reusable validation for:

- finite numeric values;
- timezone-aware datetimes;
- inclusive query ranges;
- Dataset ordering and duplicate natural keys;
- Bar units and OHLC invariants;
- record/query agreement for Instrument, date range, interval, and adjustment.

Validation functions return the validated value or raise `InvalidSourcePayload`; they do not silently drop invalid records.

Completion criterion: tests cover every invariant in specification section 11.2, including malformed multi-record Datasets.

### 5. Capability interfaces

Implement runtime-checkable Protocols in `astock.providers.protocols`, importing Standard Records from `astock_core.market_data`.

Completion criterion: an in-memory fake can satisfy each Protocol without inheriting a base class, and no Protocol exposes DataFrame, `dict[str, Any]`, or source-specific parameters.

### 6. Reusable contract-test helpers

Create the contract-test structure that later plans can invoke for fixture-backed Adapters. Implement complete Bar and Calendar contracts; add named placeholders or minimal generic helpers for later capabilities without marking unimplemented capabilities as passing.

Completion criterion: an in-memory Bar Adapter and Calendar Adapter pass the reusable contracts; deliberately broken Adapters fail for ordering, duplicate, timezone, and range violations.

## Verification

Run:

```bash
uv run --directory apps/control-plane/core pytest ../../../packages/core/tests
uv run --directory tools/ingest pytest
pnpm run check:architecture
```

Run `pnpm check` if the targeted commands pass and the working tree permits the full suite.

## Acceptance criteria

- All deliverables above exist and are tested.
- `astock-core` has no new runtime dependency.
- No production call site has been switched.
- Public types use the terminology from `CONTEXT.md`.
- No source column name or vendor field identifier appears in `astock_core.market_data` or `protocols.py`.
- Targeted verification passes.

## Handoff

Completed 2026-08-31. No production ingest, persistence, HTTP, or UI call sites were switched.

### Files created

```text
packages/core/src/astock_core/market_data/__init__.py
packages/core/src/astock_core/market_data/identity.py
packages/core/src/astock_core/market_data/enums.py
packages/core/src/astock_core/market_data/errors.py
packages/core/src/astock_core/market_data/dataset.py
packages/core/src/astock_core/market_data/models.py
packages/core/src/astock_core/market_data/queries.py
packages/core/src/astock_core/market_data/validation.py
packages/core/tests/market_data/test_identity.py
packages/core/tests/market_data/test_dataset.py
packages/core/tests/market_data/test_models.py
packages/core/tests/market_data/test_queries.py
packages/core/tests/market_data/test_validation.py
packages/core/tests/market_data/test_no_vendor_surface.py
tools/ingest/src/astock/providers/__init__.py
tools/ingest/src/astock/providers/protocols.py
tools/ingest/tests/providers/__init__.py
tools/ingest/tests/providers/fakes.py
tools/ingest/tests/providers/contracts/__init__.py
tools/ingest/tests/providers/contracts/bars.py
tools/ingest/tests/providers/contracts/calendar.py
tools/ingest/tests/providers/contracts/pending.py
tools/ingest/tests/providers/test_bar_contract.py
tools/ingest/tests/providers/test_calendar_contract.py
tools/ingest/tests/providers/test_protocols.py
```

`packages/core/pyproject.toml` is unchanged: `dependencies = []`. Unrelated workspace modifications were left untouched.

### Public import paths

```python
from astock_core.market_data import (
    InstrumentId, from_legacy_symbol, infer_a_share_exchange, to_legacy_symbol,
    Dataset, MarketDataError, InvalidSourcePayload,  # and the other typed errors
    Bar, BarQuery, TradingDay, CalendarQuery,  # and remaining records/queries
    validate_bar, validate_bar_dataset, validate_calendar_dataset,
)
from astock.providers.protocols import BarSource, CalendarSource  # and remaining Protocols
```

Do not import `astock_core.market_data` types from `astock_core` top-level. Capability callers request a Protocol, never a concrete all-purpose source object.

### Validation entry points

- Envelope: `Dataset.__post_init__` rejects empty `source`, naive `fetched_at`, inverted coverage, and non-tuple `items`/`warnings` (`ValueError`).
- Identity: `InstrumentId.parse` / `infer_a_share_exchange` / `from_legacy_symbol` raise `InstrumentIdError`.
- Seam: `validate_bar_dataset(dataset, query)` and `validate_calendar_dataset(dataset, query)` raise `InvalidSourcePayload` and never drop records.
- Primitives: `require_finite`, `require_positive`, `require_non_negative`, `require_aware_datetime`, `require_inclusive_range`, `reject_vendor_types`.

Adapters in Plan 02 must run `validate_bar_dataset` / `validate_calendar_dataset` before a Dataset crosses the seam.

### Contract-test helpers

```python
from tests.providers.contracts import (
    assert_bar_source_contract,
    assert_calendar_source_contract,
    PENDING_CAPABILITY_CONTRACTS,
    unimplemented_capability_contract,
)
```

Relative import from `tools/ingest/tests/providers/` also works: `from .contracts import assert_bar_source_contract`.

In-memory fakes used to prove the contracts live in `tools/ingest/tests/providers/fakes.py` and are not production Adapters. Later capabilities are named in `PENDING_CAPABILITY_CONTRACTS` and raise `NotImplementedError`; they are not marked passing.

### Design decisions

- `infer_a_share_exchange` is the single exchange-inference function. Prefixes `4`, `8`, and `92` map to `BSE`; remaining `9xxxx` maps to `XSHG` (Shanghai B-shares such as `900901`).
- Closed vocabularies live in `enums.py` (extra file vs spec layout) so models stay record-shaped. Public imports are unchanged.
- Query `instruments` lists are coerced to tuples. Dataset collections are rejected unless they are tuples, per this plan's Dataset completion criterion.
- Cross-field Bar/Calendar checks live in `validation.py`, not dataclass `__post_init__`, so malformed records can be constructed and then rejected without being dropped.
- Query types not fully spelled out in spec sections 10–15 (`InstrumentQuery`, `SnapshotQuery`, `ValuationQuery`, `FundamentalQuery`, `StatementQuery`, `ClassificationQuery`, `MembershipQuery`, `NewsQuery`, `EventQuery`) are defined here so later plans do not invent competing shapes.
- `FinancialStatement.source_payload` is `object | None` (opaque) so `dict[str, Any]` does not appear on the seam.
- `InstrumentProfile` is a Standard Record only. Spec section 10 has no `InstrumentProfileSource`; Plan 04 should not assume one exists until it adds it.

### Deviations from the specification

- Dataset envelope construction raises `ValueError`, not `InvalidSourcePayload`. Section 9 describes Adapter payload failures after a source response; constructor misuse is a caller error.
- Spec file list does not include `enums.py`. Split for locality; ownership and public imports still match section 5.

No other semantic deviations. Empty Dataset vs `NoData` follows section 8: a conclusive empty range returns `Dataset(items=())`; an unrecognized Instrument raises `InstrumentNotFound` (in-memory Bar fake) or `UnsupportedQuery` (unknown calendar market).

### Verification

```bash
uv run --directory apps/control-plane/core pytest ../../../packages/core/tests
# 83 passed (packages/core/tests only); 219 passed when collected with control-plane tests

uv run --directory tools/ingest pytest
# 58 passed

pnpm run check:architecture
# passed

pnpm check
# passed: architecture, UI 51, typecheck, python (core 219, cli 1, ingest 58, analyze 19, qlib 8)
```

`astock-core` runtime dependencies remain empty. No ingest orchestration, SQLite schema, HTTP, or UI types were modified.

### Notes for Plan 02

- Implement Eastmoney/AKShare Bar Adapters and AKShare Calendar Adapter against `BarSource` / `CalendarSource`.
- Invoke `assert_bar_source_contract` and `assert_calendar_source_contract`; do not copy the assertions.
- Normalize volume to shares and amount to CNY inside the Adapter, then let the contract's `validate_bar` checks enforce finiteness and sign.
- Translate vendor exceptions to the section 9 error types before they leave the Adapter.
- Do not switch `ingest_bars`, `sync_quotes`, `ingest_indexes`, or scheduler behavior; that is Plan 03.
- Do not add registry/fallback; that is Plan 08.
- Compatibility façades, if needed, must contain no duplicated mapping and must be labeled for removal by Plan 03.
