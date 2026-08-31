# Plan 02: Bar and Calendar Adapters

Status: complete

## Objective

Move source-specific Bar and Calendar payload translation behind capability Adapters while leaving current synchronization entry points operational. Add Eastmoney and AKShare Bar Adapters, an AKShare Calendar Adapter, and reusable fixture-backed contract tests.

## Required reading

1. [`CONTEXT.md`](../../../CONTEXT.md)
2. [`spec.md`](../spec.md), sections 4, 8–11, 16, 18–20
3. [Plan 01](./01-contract-foundation.md), including its handoff
4. `tools/ingest/src/astock/ingest.py`
5. `tools/ingest/src/astock/eastmoney.py`
6. Existing quote and calendar tests under `tools/ingest/tests/`

## Preconditions

- Plan 01 Status is `complete`.
- Run Plan 01's targeted tests before editing. If they fail, stop and document the inherited failure rather than working around the contract.
- Preserve the observable behavior of current public fetch helpers until Plan 03 cuts over their callers.

## Scope

Create or update only Adapter, fixture, and directly related compatibility code for Bars and Calendar.

Target modules:

```text
tools/ingest/src/astock/providers/eastmoney/bars.py
tools/ingest/src/astock/providers/akshare/bars.py
tools/ingest/src/astock/providers/akshare/calendar.py
tools/ingest/tests/providers/
```

Do not switch `ingest_bars`, `sync_quotes`, `ingest_indexes`, or scheduler behavior in this plan.

## Deliverables

### 1. Eastmoney Bar Adapter

- Reuse transport behavior from the current Eastmoney module without returning pandas objects across the interface.
- Translate stock and index payloads into Standard Bars.
- Normalize source periods and adjustment values to canonical enums.
- Normalize volume to shares and amount to CNY. Establish this with a fixture assertion, not an undocumented assumption.
- Translate transport, JSON, and payload failures into typed market-data errors.

Completion criterion: the Adapter passes the Bar contract suite for stock and index fixtures, all supported intervals, empty ranges, and malformed payloads.

### 2. AKShare Bar Adapter

- Encapsulate the current AKShare Tencent, Sina, and Eastmoney-backed functions inside the AKShare Adapter implementation.
- Keep internal source fallback private to the Adapter only when those calls are all considered the `akshare` registry source. Cross-registry fallback remains for Plan 08.
- Map English and Chinese DataFrame columns internally.
- Convert pandas missing values to `None` or typed errors before records cross the seam.

Completion criterion: no pandas DataFrame leaves an Adapter method, and the Adapter passes the same Bar contract suite as Eastmoney.

### 3. AKShare Calendar Adapter

- Wrap `tool_trade_date_hist_sina` behind `CalendarSource`.
- Return `TradingDay` records for the requested inclusive range.
- Set coverage and completeness explicitly.
- Translate absent columns, malformed dates, and network failures into typed errors.

Completion criterion: the Adapter passes the Calendar contract suite for valid, empty, unsorted, duplicate, malformed, and failed fixtures.

### 4. Compatibility façades

Existing source-shaped helper functions may delegate to the new Adapters until Plan 03, but each façade must:

- contain no duplicated mapping logic;
- be labeled for removal by Plan 03;
- preserve current caller return shape only where still required.

Completion criterion: one mapping implementation exists per source payload.

### 5. Fixture discipline

Use minimal local fixtures containing only fields needed to prove mapping. Scrub cookies, tokens, request headers, and personal data. Default tests make no network calls.

Completion criterion: searching test output and fixtures finds no live credential or authorization material.

## Verification

```bash
uv run --directory tools/ingest pytest tests/providers tests/test_quotes_periods.py tests/test_calendar_sync.py
uv run --directory tools/ingest pytest
pnpm run check:architecture
```

## Acceptance criteria

- Both Bar Adapters pass one shared contract suite.
- Calendar Adapter passes the shared Calendar contract suite.
- Source-specific columns appear only in Adapter implementation/tests.
- No production use case has been cut over prematurely.
- Existing ingest tests pass.

## Handoff

Completed 2026-08-31. No production ingest, persistence, HTTP, UI, or scheduler call sites were switched. `ingest_bars`, `sync_quotes`, `ingest_indexes`, and `ingest_calendar` still use the existing DataFrame helpers.

### Files created or updated

```text
tools/ingest/src/astock/providers/_support.py
tools/ingest/src/astock/providers/eastmoney/__init__.py
tools/ingest/src/astock/providers/eastmoney/bars.py
tools/ingest/src/astock/providers/akshare/__init__.py
tools/ingest/src/astock/providers/akshare/_tables.py
tools/ingest/src/astock/providers/akshare/bars.py
tools/ingest/src/astock/providers/akshare/calendar.py
tools/ingest/src/astock/eastmoney.py          # Plan 03 removal comments only; return shape unchanged
tools/ingest/tests/providers/fixture_sources.py
tools/ingest/tests/providers/test_bar_adapters_contract.py
tools/ingest/tests/providers/test_eastmoney_bars.py
tools/ingest/tests/providers/test_akshare_bars.py
tools/ingest/tests/providers/test_akshare_calendar.py
tools/ingest/tests/providers/test_fixture_hygiene.py
tools/ingest/tests/providers/fixtures/eastmoney/
tools/ingest/tests/providers/fixtures/akshare/
```

Unrelated workspace modifications were left untouched.

### Public import paths

```python
from astock.providers.eastmoney import EastmoneyBarAdapter
from astock.providers.akshare import AkshareBarAdapter, AkshareCalendarAdapter
from astock.providers.protocols import BarSource, CalendarSource
```

Do not import concrete Adapters from `astock.providers` (that package still exports Protocols only). Composition roots construct Adapters; callers request `BarSource` / `CalendarSource`.

Constructors (all keyword-only):

```python
EastmoneyBarAdapter(get_json=None, timeout=20.0, retries=1, sleep=None, clock=None)
AkshareBarAdapter(hist_tx=None, daily=None, hist=None, timeout=20.0, retries=1, sleep=None, clock=None)
AkshareCalendarAdapter(trade_date_hist=None, timeout=20.0, retries=1, sleep=None, clock=None)
```

Default `get_json` reuses `astock.eastmoney._get` (curl_cffi chrome impersonation). Default AKShare callables lazily import `akshare.stock_zh_a_hist_tx`, `stock_zh_a_daily`, `stock_zh_a_hist`, and `tool_trade_date_hist_sina`. Tests inject fixtures; the default suite makes no network calls.

### Retries and timeouts

Transport retry belongs to each Adapter via `call_with_retries` in `astock.providers._support`. `retries` is the total attempt count (default `1` = no extra retry, matching current Eastmoney helpers; ingest-level `_call` still wraps the façades). Backoff is `min(2 ** attempt, 16)` seconds. `timeout` is passed into Eastmoney `get_json` and into AKShare functions that accept it. Sina `tool_trade_date_hist_sina` has no timeout parameter; `AkshareCalendarAdapter.timeout` is stored for constructor symmetry and retries still wrap the call. `clock` injects `fetched_at` (default `datetime.now(timezone.utc)`).

Vendor exceptions are translated before they leave an Adapter: timeout/connection → `SourceUnavailable`, HTTP 429 → `RateLimited`, 401/403 → `AuthenticationFailed`, JSON decode → `InvalidSourcePayload`.

### Confirmed source unit conversions

Established by fixture assertions, not undocumented assumptions:

| Source path | volume in payload | Adapter `Bar.volume` | amount | `turnover_pct` |
|---|---|---|---|---|
| Eastmoney kline (stock and index) | 手 (lots) | `lots * 100` shares | CNY, unchanged | percentage points as returned |
| AKShare Tencent `stock_zh_a_hist_tx` | already shares (AKShare converts) | unchanged | already CNY | Tencent ratio `* 100` → percentage points |
| AKShare Sina `stock_zh_a_daily` | shares | unchanged | CNY | ratio `* 100` → percentage points |
| AKShare Eastmoney-backed `stock_zh_a_hist` | 手 | `lots * 100` shares | CNY | already percentage points |

Example: Eastmoney fixture volume `10000` lots → `1_000_000` shares; amount `10500000` stays `10_500_000` CNY.

### Compatibility façades remaining for Plan 03

- `astock.eastmoney.stock_kline` / `stock_daily` / `index_daily` — still return source-shaped DataFrames with original units (lots, not shares) so `ingest_bars` and `ingest_indexes` stay unchanged. Labeled `Removed by Plan 03`. Standard Record mapping lives only in `EastmoneyBarAdapter`.
- `astock.ingest._fetch_stock_bars` still does Eastmoney → AKShare cross-registry fallback. That cutover is Plan 03; registry fallback is Plan 08.
- `astock.ingest.ingest_calendar` still calls `ak.tool_trade_date_hist_sina` directly.

One Standard Record mapping exists per source payload. Façade DataFrame column assignment is the legacy return shape, not a second Bar mapper.

### Fixture locations

```text
tools/ingest/tests/providers/fixtures/eastmoney/
  stock_klines_valid.json, _empty.json, _malformed.json, _unsorted.json,
  _duplicate.json, _weekly.json, _monthly.json, index_klines_valid.json
tools/ingest/tests/providers/fixtures/akshare/
  hist_tx_valid.json, hist_em_valid.json, hist_em_weekly.json, hist_em_monthly.json,
  calendar_valid.json, _unsorted.json, _duplicate.json, _malformed.json,
  _missing_column.json
```

Factories: `tests.providers.fixture_sources.make_eastmoney_bar_adapter`, `make_akshare_bar_adapter`, `make_akshare_calendar_adapter`. Shared contract: `assert_bar_source_contract` / `assert_calendar_source_contract` (not copied).

### Design decisions

- Index vs stock for Eastmoney uses `InstrumentId.exchange` plus symbol prefix: XSHG `000`/`880`, XSHE `399`, BSE `899` are indexes. `from_legacy_symbol("000300")` infers XSHE; HS300 must be constructed as `InstrumentId(country="CN", exchange="XSHG", symbol="000300")`.
- AKShare daily fallback is Tencent then Sina, both reported as `source="akshare"`. Empty Tencent tables fall through to Sina; `InvalidSourcePayload` and `InstrumentNotFound` do not. Weekly/monthly use `stock_zh_a_hist` only.
- AKShare index Bars other than daily raise `UnsupportedQuery`.
- Calendar supports `cn_a` only; unknown markets raise `UnsupportedQuery`. Sina returns open days; Adapter sets `is_open=True`, `coverage_start`/`coverage_end` to the query range, `complete=True`. Duplicate dates are rejected, not silently dropped. Unsorted input is sorted.
- `data: null` from Eastmoney is `InstrumentNotFound`; `data.klines: []` is a successful empty Dataset.

### Known upstream limitations

- Eastmoney public kline `ut` token remains in `eastmoney.py` transport; it is a public client id, not a user credential. Fixtures do not contain it.
- STAR (688) lot size is not special-cased; Eastmoney volume is treated as 手 `* 100` for all A-share stocks and indexes. Tencent already normalizes 科创板 to shares inside AKShare.
- Calendar `timeout` cannot be forwarded to `tool_trade_date_hist_sina`.
- Cross-registry Eastmoney→AKShare fallback remains in `ingest._fetch_stock_bars` until Plan 03/08.

### Verification

```bash
uv run --directory tools/ingest pytest tests/providers tests/test_quotes_periods.py tests/test_calendar_sync.py
# 47 passed

uv run --directory tools/ingest pytest
# 85 passed (was 58 after Plan 01)

pnpm run check:architecture
# passed
```

Acceptance: both Bar Adapters pass `assert_bar_source_contract`; Calendar Adapter passes `assert_calendar_source_contract` for valid, empty, unsorted, duplicate, malformed, and failed fixtures; source columns stay in Adapter implementation/tests plus the labeled Eastmoney façades; no production use case was cut over; existing ingest tests pass.

### Notes for Plan 03

- Inject `BarSource` / `CalendarSource`; default-construct the Adapters only at CLI/process composition roots.
- Project Standard Bars into existing SQLite columns after unit conversion (shares, CNY). Current façades still store lots for Eastmoney volume.
- Remove `eastmoney.stock_kline` / `index_daily` once callers use the interface.
- Do not add registry/fallback; that remains Plan 08.
