# Plan 11: Tushare Bars, Snapshots, and Valuations

Status: not started

Release boundary: internal work package; not independently deployable

## Objective

Implement Tushare Bar, Quote Snapshot, and Valuation Adapters, including exact
unit conversion, adjustment semantics, multi-response snapshot composition,
historical as-of behavior, and efficient whole-market query planning. Do not
register or enable them.

## Required reading

1. [`../tushare-migration-spec.md`](../tushare-migration-spec.md), sections 6.3–6.5 and 7
2. [`../spec.md`](../spec.md), Bar/Snapshot/Valuation sections and invariants
3. Plan 09 handoff
4. Existing Eastmoney and AKShare Bar/Snapshot contract suites
5. Quote ingest range planning and Qlib export assumptions

## Dependencies

Plan 09 complete. May run in parallel with Plans 10, 12, 13, and 14.

## File ownership

```text
tools/ingest/src/astock/providers/tushare/bars.py
tools/ingest/src/astock/providers/tushare/snapshots.py
tools/ingest/tests/providers/tushare/fixtures/bars/
tools/ingest/tests/providers/tushare/fixtures/snapshots/
tools/ingest/tests/providers/test_tushare_bars.py
tools/ingest/tests/providers/test_tushare_snapshots.py
```

Do not edit synchronization, registry, settings, persistence, or Qlib code.

## Deliverables

### Bars

- Support stock and index daily Bars plus supported stock weekly/monthly Bars.
- Use documented APIs for raw prices, `adj_factor`, and `daily_basic` turnover.
- Convert hands to shares and thousand CNY to CNY exactly once.
- Specify and implement fixed-anchor formulas for none/forward/backward adjustment.
- Join auxiliary rows by Instrument and trade date; reject conflicting duplicates.
- Return requested inclusive coverage in ascending order.
- Detect API row-limit truncation and plan whole-market history by trading date.
- Do not issue one request per Instrument when a date-oriented API can answer the query.

### Quote snapshots

- Compose source real-time quotes, `stk_limit`, `suspend_d`, and `daily_basic`
  inside the Adapter only.
- Require latest price and prior close for a returned non-suspended Instrument.
- Prefer source observation time; warn when fetch time is used.
- Keep average price, inner volume, and outer volume `None` when absent rather
  than deriving misleading values.
- Distinguish absent Instrument, suspended Instrument, unavailable API, and a
  conclusive empty request.

### Valuations

- Apply all `daily_basic` share/market-cap multipliers in the spec.
- Map PE/PB fields without treating zero as missing.
- For historical `as_of`, return the actual latest trading date on or before it.
- Batch Instruments and dates within API limits.

## Required tests

- daily/weekly/monthly, stock/index, all adjustment modes;
- corporate-action fixture proving adjustment formula and no double adjustment;
- volume, amount, share, market-cap, turnover and percentage conversions;
- auxiliary join gaps, duplicates, nonfinite values, truncation and multi-page ranges;
- active/suspended/missing snapshot and optional field behavior;
- historical valuation weekend/as-of behavior;
- shared Bar, Snapshot, Profile if implemented, and Valuation contracts;
- Qlib-facing Bar projection compatibility using fixtures.

## Verification

```bash
uv run --directory tools/ingest pytest \
  tests/providers/test_tushare_bars.py \
  tests/providers/test_tushare_snapshots.py \
  tests/providers/test_bar_adapters_contract.py
uv run --directory tools/ingest pytest \
  tests/test_quote_ingest.py tests/test_quotes_periods.py
git diff --check
```

## Acceptance criteria

- Every numeric unit/adjustment rule has an explicit assertion.
- Tushare payloads and pandas objects do not cross the Adapter seam.
- Query count scales by date pages/batches rather than Instrument count where supported.
- No registration/default change occurs.
- Verification passes.

## Handoff

Record exact APIs/fields, adjustment formulas, row limits, batch strategy, optional
snapshot gaps, test counts, and entitlement/probe prerequisites for Plan 16.

## Cursor subagent invocation

```text
Implement docs/market-data/plans/11-tushare-market-prices.md after Plan 09.
Read all required material, stay within ownership, do not edit registry/defaults,
run verification, and append exact formulas and evidence to Handoff.
```

