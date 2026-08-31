# Plan 03: Quote Ingest Cutover

Status: complete

## Objective

Switch Bar, index-Bar, and trading-calendar synchronization to capability interfaces. The synchronization module must plan ranges, derive fields, validate Datasets, and persist projections without knowing source payload shapes.

## Required reading

1. [`CONTEXT.md`](../../../CONTEXT.md)
2. [`spec.md`](../spec.md), sections 4, 11, 16–20
3. Plans [01](./01-contract-foundation.md) and [02](./02-bar-calendar-adapters.md), including handoffs
4. `tools/ingest/src/astock/ingest.py`
5. `tools/ingest/src/astock/quotes.py`
6. `apps/control-plane/core/src/astock_control/scheduler.py`
7. Bar/calendar repository methods in `packages/core/src/astock_core/`

## Preconditions

- Plans 01 and 02 are complete.
- Their targeted suites pass before editing.
- Identify every direct calendar and Bar source call with `rg`; retain the output for comparison at completion.

## Scope

Migrate:

- stock daily/weekly/monthly Bar synchronization;
- index daily Bar synchronization;
- manual and scheduled trading-calendar synchronization;
- derived Bar fields and persistence projections;
- use-case tests for those flows.

Do not migrate Instrument Profile, fundamentals, classifications, news, or events.

## Deliverables

### 1. Inject capability dependencies

Refactor synchronization entry points to accept `BarSource` and `CalendarSource`, with default construction only at CLI/process composition roots. Tests inject in-memory Adapters.

Completion criterion: use-case tests do not monkeypatch AKShare or Eastmoney calls.

### 2. Standard Bar persistence projection

Add repository/use-case mapping from Standard Bar to existing SQLite columns. Compute `change_amount`, `pct_chg`, and `amplitude` after normalization when absent from persistence inputs. Preserve current percentage-point conventions and existing table keys.

Prefer repository methods accepting Standard Records over positional tuples. Keep any tuple compatibility method private and mark it for removal in Plan 08.

Completion criterion: existing UI read models and Qlib export receive equivalent values from fixture data.

### 3. Incremental range planning

Preserve current semantics:

- new Instruments fetch from configured history start;
- existing Instruments fetch from the day after their latest stored Bar;
- already-current Instruments skip;
- query bounds are inclusive;
- ingest state distinguishes `ok`, `empty`, and `error`.

Completion criterion: tests cover new, fill, current, valid empty, partial Dataset, and typed failure cases for every configured interval.

### 4. Calendar cutover

Route both ingest calendar synchronization and scheduler refresh through `CalendarSource`. Remove the scheduler's inline AKShare subprocess expression. The control-plane environment must not import the ingest package directly; have it invoke or submit the ingest calendar use case through the existing process/job Adapter, while the ingest use case receives `CalendarSource`. Calendar replacement and watermark recording remain atomic.

Completion criterion: `rg` finds no direct AKShare calendar call outside the AKShare Calendar Adapter and its tests.

### 5. Index unification

Use Standard Bars for index data. Preserve the existing index persistence projection and code/name behavior while eliminating the separate source-shaped DataFrame mapping path.

Completion criterion: index and stock Bar source translation share validation and differ only at explicit persistence projections.

### 6. Remove replaced paths

Delete the compatibility façades and obsolete unit tests identified in Plan 02 once all callers use the interface. Keep no dead alternate fetch path.

Completion criterion: source payload column names for Bars/Calendar exist only inside Adapter directories and Adapter tests.

## Verification

```bash
uv run --directory tools/ingest pytest
uv run --directory apps/control-plane/core pytest tests/test_calendar.py tests/test_calendar_month.py tests/test_stock_quotes.py tests/test_automations.py
uv run --directory tools/qlib pytest
pnpm run check:architecture
```

Run `pnpm check` before completion.

## Acceptance criteria

- All Bar and Calendar use cases depend on interfaces.
- Scheduler and manual calendar sync use the same interface.
- Existing database and public read behavior remain compatible.
- Qlib tests pass without changes to its public behavior.
- Direct Bar/Calendar source calls exist only in Adapters.
- Full verification passes.

## Handoff

Completed 2026-08-31. Bar, index-Bar, and trading-calendar synchronization now consume `BarSource` / `CalendarSource`. Instrument Profile, fundamentals, classifications, news, and events were not migrated.

### Files created or updated

```text
packages/core/src/astock_core/market_data/derive.py
packages/core/src/astock_core/market_data/__init__.py
packages/core/src/astock_core/_market_bars.py
packages/core/src/astock_core/_market_calendar_store.py
packages/core/tests/test_standard_bar_projection.py
tools/ingest/src/astock/providers/defaults.py
tools/ingest/src/astock/ingest.py
tools/ingest/src/astock/quotes.py
tools/ingest/src/astock/eastmoney.py
tools/ingest/src/astock/cli/parser.py
tools/ingest/src/astock/cli/handlers.py
tools/ingest/tests/test_quote_ingest.py
tools/ingest/tests/test_calendar_sync.py
tools/ingest/tests/test_quotes_periods.py
tools/ingest/tests/test_cli.py
apps/control-plane/core/src/astock_control/scheduler.py
apps/control-plane/core/src/astock_control/adapters/ingest.py
apps/control-plane/core/tests/test_automations.py
apps/control-plane/core/tests/test_ingest_argv.py
```

Unrelated workspace modifications were left untouched.

### Use-case dependency shapes

```python
ingest_calendar(db, *, force=False, market_id=MARKET_CN_A, calendar_source: CalendarSource | None = None) -> int
ingest_bars(db, *, codes=None, limit=None, adjust=None, sleep=None, start_date=None, period="daily", bar_source: BarSource | None = None) -> dict[str, int]
ingest_indexes(db, *, indexes=None, start_date=None, bar_source: BarSource | None = None) -> int
sync_quotes(db, *, ..., bar_source: BarSource | None = None, calendar_source: CalendarSource | None = None) -> dict
ingest_all(db, *, ..., bar_source=None, calendar_source=None)
ingest_hs300(db, *, ..., bar_source=None, calendar_source=None)
```

`None` source arguments construct defaults. Tests inject in-memory Adapters and do not monkeypatch AKShare or Eastmoney.

### Default composition roots

```python
from astock.providers.defaults import default_bar_source, default_calendar_source
# default_bar_source() -> EastmoneyBarAdapter(retries=request_retries())
# default_calendar_source() -> AkshareCalendarAdapter(retries=request_retries())
```

Constructed at:

- `astock.cli.handlers` for `quotes sync` and `calendar sync`
- ingest use-case defaults when a source is omitted (library callers such as `sync_stock` / `ingest_all`)
- control-plane `IngestRunner` via `python -m astock calendar sync --force`

Plan 08 replaces `astock.providers.defaults` with the per-capability registry. Cross-registry Eastmoney→AKShare Bar fallback was removed with `_fetch_stock_bars`; do not restore it here.

### Repository projection methods

```python
MarketDB.upsert_standard_bars(bars: Sequence[Bar]) -> int
MarketDB.upsert_standard_index_bars(bars: Sequence[Bar], *, code: str, name: str) -> int
MarketDB.upsert_trading_days(days: Sequence[TradingDay], *, market_id: str) -> int
derive_bar_change(close=..., high=..., low=..., prev_close=...) -> (change_amount, pct_chg, amplitude)
```

- Stock Bars: six-digit `code`, `adjust` key `""` for `Adjustment.RAW` else `qfq`/`hfq`, volume in shares, amount in CNY, `turnover` from `turnover_pct`.
- Derived `change_amount` / `pct_chg` / `amplitude` use percentage points and the previous close (stored then in-Dataset). First bar without a previous close stores `None`.
- Index Bars keep the existing `index_daily` keys (`sh000300` + display name). Index and stock translation share `BarSource`; they differ only at this projection.
- Calendar persistence filters `is_open=False` and writes via `sync_calendar` (replace + watermark in one transaction).

Tuple methods `upsert_bars` / `upsert_index_bars` remain as one-line wrappers over `_upsert_bar_tuples` / `_upsert_index_bar_tuples`, labeled `Removed by Plan 08`.

### Removed compatibility paths

- `astock.eastmoney.stock_kline` / `stock_daily` / `index_daily`
- `astock.ingest._fetch_stock_bars` / `_bars_from_frame`
- scheduler inline `uv run python -c "import akshare...tool_trade_date_hist_sina"`

`eastmoney._get` and `eastmoney.stock_profile` remain for Plan 04.

### CLI / control-plane calendar path

New ingest command: `python -m astock calendar sync [--force]`.

Scheduler `refresh_calendar` invokes `IngestRunner` with `{"type": "calendar.sync", "force": True}` (process Adapter). Control-plane does not import `astock`. `calendar.sync` is not a public HTTP command type. Tests inject `calendar_sync=`.

Empty calendar Datasets raise `ValueError("交易日历为空")` and do not wipe stored dates (matches the previous scheduler guard).

### Direct-call search after cutover

```text
tool_trade_date_hist_sina / stock_zh_a_hist* (production, excluding vendor):
  tools/ingest/src/astock/providers/akshare/calendar.py
  tools/ingest/src/astock/providers/akshare/bars.py

stock_kline / eastmoney.index_daily / scheduler akshare: none
```

Bar/Calendar source payload column names remain only in Adapter implementation and Adapter tests. `events.py` still maps source columns for news/events (Plan 07).

### Design decisions

- Query bounds stay inclusive. New Instruments start at `history_start`; existing ones start the day after `last_bar_date`; already-current skip when `last >= current_trade_date`. Indexes skip when `start > end` using today's date, unchanged.
- Ingest state still uses `ok` / `empty` / `error`. Partial Datasets persist returned items and mark `ok` when any rows exist.
- Default Bar Adapter is Eastmoney only. AKShare Bar Adapter stays available for Plan 08 fallback.
- Index codes such as `sh000300` map to `CN.XSHG.000300` via `instrument_id_for_index_code`; `from_legacy_symbol("000300")` would incorrectly infer XSHE.

### Known behavior changes vs pre-cutover

- Newly ingested Eastmoney volume is shares, not lots. UI/Qlib read models receive Standard Bar units. Existing SQLite rows written before this plan are unchanged.
- Eastmoney→AKShare Bar fallback is gone until Plan 08.
- Empty calendar sync no longer deletes the stored calendar.

### Verification

```bash
uv run --directory tools/ingest pytest
# 94 passed (was 85 after Plan 02)

uv run --directory apps/control-plane/core pytest tests/test_calendar.py tests/test_calendar_month.py tests/test_stock_quotes.py tests/test_automations.py
# 32 passed

uv run --directory tools/qlib pytest
# 8 passed

pnpm run check:architecture
# passed

pnpm check
# passed: architecture, UI 51, typecheck, python (core+control-plane 229, cli 1, ingest 94, analyze 19, qlib 8)
```

Acceptance: Bar/Calendar use cases depend on interfaces; scheduler and manual calendar sync share `CalendarSource` through the ingest CLI; SQLite/UI/Qlib public read models stay compatible; Qlib tests passed without public-behavior changes; direct Bar/Calendar source calls exist only in Adapters; full verification passed.

### Notes for Plan 04

- Inject `BarSource` / `CalendarSource` already done. Next split is Instrument Profile, Quote Snapshot, and Valuation Snapshot.
- `eastmoney.stock_profile` and `_profile_fetchers` still return mixed source-shaped dicts.
- Do not add the source registry; that remains Plan 08.
- Prefer `upsert_standard_bars` for new writers; tuple wrappers are labeled for Plan 08 removal.
