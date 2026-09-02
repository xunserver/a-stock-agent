# Market Data Source Abstraction

This directory is the execution index for replacing source-shaped calls with source-independent market-data interfaces.

## Source of truth

- [Specification](./spec.md) defines the required architecture, records, invariants, errors, and final acceptance criteria.
- [Tushare primary-source migration specification](./tushare-migration-spec.md)
  defines the next source migration. It is a single-version, all-capability,
  atomic cutover; it is not divided into the historical plans below.
- [Plans](./plans/) divide the migration into sequential tasks that can be assigned to separate coding agents.
- [`CONTEXT.md`](../../CONTEXT.md) defines the canonical domain language. Agents must use those terms in code and documentation.

If a plan conflicts with the specification, the specification wins. If existing code conflicts with the specification, preserve current externally observable behavior while moving the implementation toward the specification.

## Completed historical execution order

| Order | Plan | Depends on | Outcome |
|---:|---|---|---|
| 1 | [Contract foundation](./plans/01-contract-foundation.md) | None | Standard records, queries, Dataset, errors, validation, capability interfaces |
| 2 | [Bar and calendar Adapters](./plans/02-bar-calendar-adapters.md) | 1 | Eastmoney/AKShare payloads translated behind Bar and Calendar interfaces |
| 3 | [Quote ingest cutover](./plans/03-quote-ingest-cutover.md) | 2 | Existing quote/calendar synchronization consumes the new interfaces |
| 4 | [Instrument and snapshot split](./plans/04-instrument-snapshot-split.md) | 3 | Instrument Profile, Quote Snapshot, and Valuation Snapshot replace the mixed profile flow |
| 5 | [Fundamentals and statements](./plans/05-fundamentals-statements.md) | 4 | Financial summaries and statements use stable, source-independent records |
| 6 | [Classifications and memberships](./plans/06-classifications-memberships.md) | 5 | Index, industry, and concept membership data use standard records |
| 7 | [News and events](./plans/07-news-events.md) | 6 | News and typed market events cross stable interfaces |
| 8 | [Source registry and completion](./plans/08-source-registry-completion.md) | 7 | Per-capability source selection, fallback, observability, and direct-call removal |

Plans 01–08 describe the completed source-abstraction migration. Do not split the
Tushare migration across these plans; execute and accept it as one release under
`tushare-migration-spec.md`.

## Tushare implementation work packages

These plans divide implementation work for subagents without dividing the
production release. Plans 10–14 may run in parallel after Plan 09. Plan 16 is the
only plan allowed to change source defaults.

| Order | Plan | Depends on | Ownership/outcome |
|---:|---|---|---|
| 9 | [Client foundation](./plans/09-tushare-client-foundation.md) | None | SDK boundary, secrets, rate limiting, table helpers, architecture |
| 10 | [Reference data and calendar](./plans/10-tushare-reference-calendar.md) | 9 | Instruments, profiles, trading calendar |
| 11 | [Market prices](./plans/11-tushare-market-prices.md) | 9 | Bars, quote snapshots, valuations |
| 12 | [Financials](./plans/12-tushare-financials.md) | 9 | Fundamentals and three statements |
| 13 | [Classifications](./plans/13-tushare-classifications.md) | 9 | Index/industry/concept classifications and memberships |
| 14 | [News and events](./plans/14-tushare-news-events.md) | 9 | News and all four typed events |
| 15 | [Synchronization and shadow comparison](./plans/15-tushare-sync-shadow.md) | 10–14 | Bootstrap/incremental integration, probes, comparison |
| 16 | [Atomic cutover](./plans/16-tushare-atomic-cutover.md) | 9–15 | Registry, settings v2, release gates, rollback, activation |

The implementation sequence is:

```text
09 -> (10 || 11 || 12 || 13 || 14) -> 15 -> 16
```

## Tushare migration invocation template

Use this prompt for the next implementation:

```text
Implement docs/market-data/tushare-migration-spec.md as one atomic release.
Read docs/market-data/spec.md and CONTEXT.md completely before editing.
Treat every scope item, invariant, acceptance criterion, and handoff requirement
as binding. Do not split the work into capability releases or change production
defaults until every required capability passes its release probe.
Preserve unrelated workspace changes.
```

For one work package, prefer the plan-specific Cursor invocation at the bottom of
that plan. The root coordinator must review each Handoff before dispatching a
dependent plan and must not dispatch Plan 16 until Plans 09–15 are complete.

## Historical plan progress tracking

Agents should change only the status marker in the plan they execute:

```text
Status: not started | in progress | complete | blocked
```

`complete` means every acceptance criterion passes. `blocked` requires a concrete blocker and evidence in the handoff section.
