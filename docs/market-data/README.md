# Market Data Source Abstraction

This directory is the execution index for replacing source-shaped calls with source-independent market-data interfaces.

## Source of truth

- [Specification](./spec.md) defines the required architecture, records, invariants, errors, and final acceptance criteria.
- [Plans](./plans/) divide the migration into sequential tasks that can be assigned to separate coding agents.
- [`CONTEXT.md`](../../CONTEXT.md) defines the canonical domain language. Agents must use those terms in code and documentation.

If a plan conflicts with the specification, the specification wins. If existing code conflicts with the specification, preserve current externally observable behavior while moving the implementation toward the specification.

## Execution order

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

Execute one plan at a time. Each agent must finish its plan's acceptance criteria and update the plan's handoff section before the next plan starts.

## Agent invocation template

Use this prompt when assigning a plan:

```text
Implement docs/market-data/plans/NN-name.md.
Read docs/market-data/spec.md and CONTEXT.md completely before editing.
Treat the plan's scope, invariants, acceptance criteria, and handoff requirements as binding.
Preserve unrelated workspace changes. Do not begin later plans.
```

## Progress tracking

Agents should change only the status marker in the plan they execute:

```text
Status: not started | in progress | complete | blocked
```

`complete` means every acceptance criterion passes. `blocked` requires a concrete blocker and evidence in the handoff section.
