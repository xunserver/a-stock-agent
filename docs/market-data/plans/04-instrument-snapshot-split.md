# Plan 04: Instrument and Snapshot Split

Status: complete

## Objective

Replace the mixed stock-profile source flow with separate Instrument, Instrument Profile, Quote Snapshot, and Valuation Snapshot capabilities while preserving the current `stocks` persistence projection and HTTP/UI response shape.

## Required reading

1. [`CONTEXT.md`](../../../CONTEXT.md)
2. [`spec.md`](../spec.md), sections 7, 8–10, 12, 16–20
3. Plans 01–03 and their handoffs
4. `tools/ingest/src/astock/profile.py`
5. `tools/ingest/src/astock/_profile_fetchers.py`
6. `tools/ingest/src/astock/_profile_mappers.py`
7. `tools/ingest/src/astock/stock.py`
8. Stock repository/read-model and UI stock types

## Preconditions

- Plans 01–03 are complete and `pnpm check` passed at Plan 03 handoff.
- Inventory every current `PROFILE_VALUE_KEYS` field and assign it to exactly one target record or to Plan 05 fundamentals.

## Scope

Migrate:

- stock catalog/Instrument fetching;
- descriptive Instrument Profile data;
- current quote and suspension state;
- share count, capitalization, and valuation data;
- related source mapping tests and stock sync orchestration.

Leave financial-period and statement fetching for Plan 05.

## Required field assignment

Use this ownership unless the specification is amended first:

| Target | Existing fields |
|---|---|
| Instrument/Profile | `code`, `name`, `industry`, `region`, `list_date`, `is_st` |
| Quote Snapshot | `latest_price`, `pre_close`, `avg_price`, `high_limit`, `low_limit`, `volume_ratio`, `outer_vol`, `inner_vol`, `is_suspended`, `suspend_info` |
| Valuation Snapshot | `total_shares`, `float_shares`, `total_mv`, `float_mv`, `pe_dyn`→`pe_ttm`, `pe_static`, `pb` |
| Plan 05 Fundamental Period | `eps`, `bps`, `roe`, `revenue`, `revenue_yoy`, `net_profit`, `net_profit_yoy`, `gross_margin`, `net_margin`, `debt_ratio` |

## Deliverables

### 1. Source Adapters

Implement fixture-backed capability Adapters for the current AKShare/Eastmoney sources. Source payload merging may occur inside a composite Adapter, but returned Standard Records must have explicit observation/as-of times and one capability meaning.

Completion criterion: current source columns and field numbers appear only in Adapter code/tests.

### 2. Contract tests

Complete reusable contracts for Instrument, Quote Snapshot, and Valuation Snapshot. Cover missing optional values, observed/as-of time, units, identifiers, invalid numerics, and deterministic ordering.

Completion criterion: at least one in-memory and one source Adapter pass each capability contract.

### 3. Sync orchestration

Refactor stock info sync to request each capability explicitly and persist available records independently. One failed capability must not erase or null fields successfully supplied by another capability.

Completion criterion: tests prove partial success, independent failure accounting, and preservation of previously stored values.

### 4. Persistence compatibility

Project Standard Records into existing `stocks` columns. Avoid one shared freshness claim in new internal code: each Dataset retains its timestamp even if the legacy table continues to expose one `updated_at`.

Do not add timestamp columns in this plan unless preserving correctness otherwise proves impossible. If added, use a versioned migration and migration tests.

Completion criterion: `GET /api/stocks` and `GET /api/stocks/{code}` retain current response types and fallback-to-latest-Bar behavior.

### 5. Derivation locality

Move price-limit and valuation derivation behind normalized use-case functions. Derive only from values sharing a compatible observation/as-of date and record a Dataset warning.

Completion criterion: derivation tests are source-independent and no Adapter duplicates exchange-board rules.

### 6. Remove the mixed profile path

Delete `load_profiles` and compatibility helpers after all production callers migrate, or leave one named compatibility façade with a Plan 08 removal marker if an external caller is proven. Do not retain two active orchestration paths.

## Verification

```bash
uv run --directory tools/ingest pytest
uv run --directory apps/control-plane/core pytest tests/test_stock_quotes.py tests/test_http.py tests/test_feature_http.py
pnpm --filter @astock/ui test
pnpm run typecheck
pnpm run check:architecture
```

## Acceptance criteria

- Mixed profile source mapping is replaced by capability-specific Standard Records.
- Current HTTP/UI behavior remains compatible.
- Partial source failures preserve successful and previously stored data.
- Capability contract suites pass.
- Fundamental fields are explicitly deferred to Plan 05 rather than silently retained in profile logic.

## Handoff

Completed 2026-08-31. Mixed stock-profile fetching is replaced by Instrument, Instrument Profile, Quote Snapshot, and Valuation Snapshot capabilities. Financial-period and statement fetching remain on the existing path for Plan 05. No schema migration was added.

### Field ownership

| Target | Existing `stocks` columns |
|---|---|
| Instrument catalog | `code`, `name` |
| Instrument Profile | `name`, `industry`, `region`, `list_date`, `is_st` |
| Quote Snapshot | `latest_price`, `pre_close`, `avg_price`, `high_limit`, `low_limit`, `volume_ratio`, `outer_vol`, `inner_vol`, `is_suspended`, `suspend_info` |
| Valuation Snapshot | `total_shares`, `float_shares`, `total_mv`, `float_mv`, `pe_dyn`←`pe_ttm`, `pe_static`, `pb` |
| Plan 05 Fundamental Period | `eps`, `bps`, `roe`, `revenue`, `revenue_yoy`, `net_profit`, `net_profit_yoy`, `gross_margin`, `net_margin`, `debt_ratio` |

Snapshot sync no longer writes Plan 05 columns. Previously stored fundamental values are left untouched.

### Files created or updated

```text
packages/core/src/astock_core/market_data/derive.py
packages/core/src/astock_core/market_data/validation.py
packages/core/src/astock_core/market_data/__init__.py
packages/core/src/astock_core/_market_stocks.py
packages/core/tests/market_data/test_validation.py
packages/core/tests/test_standard_bar_projection.py
tools/ingest/src/astock/providers/protocols.py
tools/ingest/src/astock/providers/defaults.py
tools/ingest/src/astock/providers/eastmoney/snapshots.py
tools/ingest/src/astock/providers/akshare/instruments.py
tools/ingest/src/astock/providers/akshare/snapshots.py
tools/ingest/src/astock/ingest.py
tools/ingest/src/astock/stock.py
tools/ingest/src/astock/profile.py          # financial-period façade only
tools/ingest/src/astock/_profile_fetchers.py
tools/ingest/src/astock/_profile_mappers.py
tools/ingest/src/astock/eastmoney.py        # stock_profile removed; _get remains
tools/ingest/tests/providers/contracts/instruments.py
tools/ingest/tests/providers/contracts/snapshots.py
tools/ingest/tests/providers/contracts/valuations.py
tools/ingest/tests/providers/fakes.py
tools/ingest/tests/providers/fixtures/
```

Unrelated workspace modifications were left untouched. No SQLite schema change.

### Public import paths

```python
from astock.providers.eastmoney import EastmoneySnapshotAdapter
from astock.providers.akshare import AkshareInstrumentAdapter, AkshareSnapshotAdapter
from astock.providers.protocols import (
    InstrumentSource, InstrumentProfileSource, QuoteSnapshotSource, ValuationSource,
)
from astock.providers.defaults import (
    default_instrument_source, default_stock_info_source,
    default_profile_source, default_quote_snapshot_source, default_valuation_source,
)
from astock_core.market_data import (
    fill_quote_limits, fill_share_counts, derive_price_limits, derive_share_counts, limit_ratio,
    validate_instrument_dataset, validate_quote_snapshot_dataset, validate_valuation_dataset,
)
```

`InstrumentProfileSource` was added in this plan. Plan 01 noted that spec section 10 has no profile Protocol; callers now request `fetch_profiles(InstrumentQuery) -> Dataset[InstrumentProfile]`.

Do not import concrete Adapters from `astock.providers`. Tests inject in-memory sources; they do not monkeypatch AKShare or Eastmoney.

### Use-case dependency shapes

```python
ingest_stocks(db, *, instrument_source: InstrumentSource | None = None) -> int
sync_stock_info(
    db, codes, *, sleep=None, with_statements=False,
    profile_source=None, snapshot_source=None, valuation_source=None,
) -> dict[str, int]
ingest_all(..., instrument_source=None)
```

`None` source arguments construct defaults. One failed capability does not null columns written by another. Result keys keep `info_ok` / `info_error` / `info_total` and add per-capability `profile_*` / `snapshot_*` / `valuation_*` counts.

### Default composition roots

```python
default_instrument_source() -> AkshareInstrumentAdapter(retries=request_retries())
default_stock_info_source(pause=...) -> DefaultStockInfoAdapter
# primary: EastmoneySnapshotAdapter (profile + quote + valuation from qt/stock/get)
# overlay: AkshareSnapshotAdapter ST list + TFP suspend map only
```

`DefaultStockInfoAdapter` reports `source="eastmoney"`. Plan 08 replaces `astock.providers.defaults`. Eastmoney→AKShare quote-field fallback (individual info + bid-ask when the Eastmoney payload is thin) is gone until Plan 08; the Eastmoney payload already carries those fields.

### Persistence projections

```python
MarketDB.upsert_instruments(instruments) -> int          # stocks code/name via replace_stocks
MarketDB.upsert_instrument_profiles(profiles) -> int     # descriptive columns only
MarketDB.upsert_quote_snapshots(snapshots) -> int        # quote/status columns only
MarketDB.upsert_valuation_snapshots(snapshots) -> int    # shares/cap/valuation columns; pe_ttm -> pe_dyn
```

Each method updates only its columns plus the legacy single `updated_at`. Dataset `fetched_at` is not persisted. `upsert_stock_profile` remains for existing tests and mixed writes.

`GET /api/stocks` and `GET /api/stocks/{code}` are unchanged, including fallback of missing `latest_price` to the latest Bar close.

### Derivation

`limit_ratio` / `derive_price_limits` / `fill_quote_limits` and `derive_share_counts` / `fill_share_counts` live in `astock_core.market_data.derive`. Adapters do not duplicate board rules. Share counts derive only when Quote Snapshot `observed_at` (exchange-local date) equals Valuation Snapshot `as_of`. PE/PB/margin derivation from `eps`/`bps`/`revenue` is deferred to Plan 05.

### Removed mixed profile path

Deleted: `load_profiles`, `_load_batch`, `_load_each`, `eastmoney.stock_profile`, `map_spot`, `map_bid_ask`, `map_individual_info`, `map_value`, `derive_profile`, and quote fetchers in `_profile_fetchers`. No second orchestration path remains.

`astock.profile` is now a Plan 05 financial-period façade (`fetch_financial_reports`, `sync_financial_summaries_batch`, yjbb/zcfz/lrb mappers).

### Direct-call search after cutover

```text
stock_zh_a_spot_em (production):
  tools/ingest/src/astock/providers/akshare/instruments.py
  tools/ingest/src/astock/providers/akshare/snapshots.py

stock_bid_ask_em / stock_individual_info_em / stock_value_em /
stock_zh_a_st_em / stock_tfp_em (production):
  tools/ingest/src/astock/providers/akshare/snapshots.py

eastmoney qt/stock/get (production):
  tools/ingest/src/astock/providers/eastmoney/snapshots.py

load_profiles / eastmoney.stock_profile / stock.py AKShare ST/TFP: none
```

yjbb/zcfz/lrb/financial-indicator calls remain in `_profile_fetchers` for Plan 05.

### Design decisions

- Catalog ingest uses `InstrumentQuery(asset_types=(STOCK,))` against AKShare spot. Eastmoney snapshot queries require an instrument list (`UnsupportedQuery` otherwise).
- One Eastmoney HTTP payload is cached on the Adapter instance so profile, quote, and valuation methods share it during a sync.
- Quote `observed_at` uses Eastmoney `f86` when present, otherwise fetch time with a Dataset warning. Valuation `as_of` is the query date or the fetch date in `Asia/Shanghai`.
- Outer/inner volume keep the Eastmoney numeric values as stored today (HTTP/UI compatible). Price/share/cap units match the previous profile path.

### Verification

```bash
uv run --directory tools/ingest pytest
# 109 passed (was 94 after Plan 03)

uv run --directory apps/control-plane/core pytest tests/test_stock_quotes.py tests/test_http.py tests/test_feature_http.py
# 31 passed

pnpm --filter @astock/ui test
# 51 passed

pnpm run typecheck
# passed

pnpm run check:architecture
# passed
```

Targeted core+HTTP collection also passed: 130 passed (`packages/core/tests` plus the three control-plane files).

Acceptance: mixed profile mapping is gone; HTTP/UI types and latest-Bar fallback remain; partial capability failure preserves other and previously stored columns; Instrument / Quote Snapshot / Valuation contract suites pass for in-memory and source Adapters; fundamental fields stay on the Plan 05 path.

### Notes for Plan 05

- Keep `astock.profile` financial fetchers and yjbb/zcfz/lrb mappers until Fundamental Period / Statement Adapters replace them.
- `sync_stock_info` still calls `sync_financial_summaries_batch` / `fetch_financial_reports` for `financial_reports` rows; do not fold those fields back into snapshot Adapters.
- Do not add the source registry; that remains Plan 08.
- `upsert_stock_profile` can stay until remaining mixed writers move to the Standard Record methods.
