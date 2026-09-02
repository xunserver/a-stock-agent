# Plan 10: Tushare Instruments and Calendar Adapters

Status: not started

Release boundary: internal work package; not independently deployable

## Objective

Implement contract-complete Tushare `InstrumentSource`,
`InstrumentProfileSource`, and `CalendarSource` Adapters using `stock_basic`, the
entitled ST/status data, and `trade_cal`. Do not register or enable them.

## Required reading

1. [`../tushare-migration-spec.md`](../tushare-migration-spec.md), sections 1–6.2
2. [`../spec.md`](../spec.md), all Instrument, Profile, Calendar, Dataset, and error sections
3. [`../../../CONTEXT.md`](../../../CONTEXT.md)
4. Plan 09 handoff
5. Existing AKShare Instrument/Calendar Adapters and shared contract tests

## Dependencies

Plan 09 complete.

## File ownership

```text
tools/ingest/src/astock/providers/tushare/instruments.py
tools/ingest/src/astock/providers/tushare/calendar.py
tools/ingest/tests/providers/tushare/fixtures/instruments/
tools/ingest/tests/providers/tushare/fixtures/calendar/
tools/ingest/tests/providers/test_tushare_instruments.py
tools/ingest/tests/providers/test_tushare_calendar.py
```

Only add exports to `providers/tushare/__init__.py` after coordinating with Plan
09/other Adapter owners. Do not edit registry/settings files.

## Deliverables

### Instruments

- Query all requested listing statuses needed for listed, suspended, and delisted
  instruments; do not assume the API default covers them.
- Map SH/SZ/BJ suffixes strictly to XSHG/XSHE/BSE.
- Normalize currency to ISO 4217 and timezone to `Asia/Shanghai`.
- Map name, list/delist dates, industry, and area exactly as specified.
- Resolve duplicate status rows deterministically and reject conflicting identity.
- Support `asset_types`, `exchanges`, and explicit `instruments` filters.
- Populate `is_st` from an explicit Tushare dataset when entitled; document and
  test the name-based fallback used only when explicit status is unavailable.

### Calendar

- Query the complete inclusive date range from `trade_cal`.
- Return open and closed dates; map source integer/string booleans strictly.
- Preserve query market identity and reject unsupported markets.
- Validate duplicate dates, gaps, coverage metadata, order, and conclusive empty.
- Test SSE/SZSE equivalence logic rather than assuming it.

## Required fixtures/tests

- SH, SZ, BJ; listed, suspended, delisted; missing optional values;
- unknown exchange suffix, invalid currency/date, duplicate and conflicting rows;
- ST explicit, name fallback, and unavailable status API;
- open/closed calendar, unsorted rows, duplicate dates, malformed flag, empty range;
- shared Instrument, Profile, and Calendar source contracts;
- auth/rate-limit/source-unavailable translation through the shared executor.

## Verification

```bash
uv run --directory tools/ingest pytest \
  tests/providers/test_tushare_instruments.py \
  tests/providers/test_tushare_calendar.py \
  tests/providers/test_calendar_contract.py
git diff --check
```

## Acceptance criteria

- All three capability protocols are satisfied without inheritance requirements.
- Source payload names exist only inside the Adapter/tests.
- Dataset provenance is `tushare` and coverage/order are deterministic.
- No production source order changes.
- Verification passes.

## Handoff

Record API calls/fields, listing-status strategy, ST strategy, supported exchanges,
fixture inventory, test counts, and any endpoint entitlement needed by Plan 16.

## Cursor subagent invocation

```text
Implement docs/market-data/plans/10-tushare-reference-calendar.md after Plan 09.
Read the required documents and Plan 09 handoff. Stay within file ownership, do
not edit registry/settings defaults, run verification, and append evidence to Handoff.
```

