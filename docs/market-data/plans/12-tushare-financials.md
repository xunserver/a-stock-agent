# Plan 12: Tushare Fundamentals and Financial Statements

Status: not started

Release boundary: internal work package; not independently deployable

## Objective

Implement Tushare Fundamental and Statement Adapters for `fina_indicator`,
`income`, `balancesheet`, and `cashflow`, including revisions, announcement time,
period type, company-type variants, and canonical statement line items. Do not
register or enable them.

## Required reading

1. [`../tushare-migration-spec.md`](../tushare-migration-spec.md), section 6.6
2. [`../spec.md`](../spec.md), Fundamental/Statement definitions and validation
3. [`../../../CONTEXT.md`](../../../CONTEXT.md)
4. Plan 09 handoff
5. Current AKShare financial Adapters, canonical labels/templates, persistence tests

## Dependencies

Plan 09 complete. May run in parallel with Plans 10, 11, 13, and 14.

## File ownership

```text
tools/ingest/src/astock/providers/tushare/fundamentals.py
tools/ingest/src/astock/providers/tushare/statements.py
tools/ingest/src/astock/providers/tushare/statement_aliases.py
tools/ingest/tests/providers/tushare/fixtures/financials/
tools/ingest/tests/providers/test_tushare_fundamentals.py
tools/ingest/tests/providers/test_tushare_statements.py
```

Changes to core canonical line-item files require explicit coordination and a
backward-compatible migration/test. Do not edit registry/defaults.

## Deliverables

### Fundamentals

- Map every current `FundamentalPeriod` field when present: EPS, BPS, ROE,
  revenue/profit and YoY, margins, and debt ratio.
- Convert report period and report type deterministically.
- Use actual announcement date in `announced_at`; define timezone for date-only values.
- Preserve legitimate zero/negative metrics and normalize nonfinite missing values.
- Resolve amended/duplicate rows using update flags and latest actual announcement.

### Statements

- Map all canonical Balance, Profit, and Cashflow codes.
- Implement and test ordinary industrial, bank, insurer, and securities-company rows.
- Keep source column aliases in the Tushare Adapter only.
- Select consolidated report type according to a documented priority and reject
  ambiguous conflicts rather than combining statements.
- Store optional raw/source payload only under the existing bounded policy; never
  make consumers depend on Tushare field names.
- Plan single-Instrument and VIP/report-period retrieval paths without changing
  Standard Records. The production probe determines which entitled path is used.

## Required fixtures/tests

- four period types and all three sheets;
- ordinary, bank, insurer, broker company types;
- original plus revised report, same-period report-type variants;
- missing optional lines, zero/negative values, malformed dates/numbers;
- row-limit/truncation and single-stock versus VIP equivalent output;
- every canonical item code and unit;
- shared Fundamental and Statement contracts;
- stored payload reconstruction and existing HTTP financial response compatibility.

## Verification

```bash
uv run --directory tools/ingest pytest \
  tests/providers/test_tushare_fundamentals.py \
  tests/providers/test_tushare_statements.py \
  tests/test_financial_statements.py
uv run --directory apps/control-plane/core pytest \
  tests/test_financial_statements.py
git diff --check
```

## Acceptance criteria

- Current financial UI/API fields are populated without source-name leakage.
- Revision selection and all company types are deterministic and tested.
- All canonical line items have mapping coverage.
- No registration/default change occurs.
- Verification passes.

## Handoff

Record mapping tables, report/revision priority, API/VIP entitlement choice,
company-type fixture coverage, compatibility results, and test counts.

## Cursor subagent invocation

```text
Implement docs/market-data/plans/12-tushare-financials.md after Plan 09.
Read all required material, stay within ownership, preserve canonical/public
contracts, do not register the source, run verification, and append evidence.
```

