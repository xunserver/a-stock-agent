# Plan 14: Tushare News and Market Events

Status: not started

Release boundary: internal work package; not independently deployable

## Objective

Implement Tushare News and all four typed Market Event variants with deterministic
Instrument association, stable identities, bounded text handling, honest
completeness, and entitlement-aware errors. Do not register or enable them.

## Required reading

1. [`../tushare-migration-spec.md`](../tushare-migration-spec.md), sections 6.8–6.9
2. [`../spec.md`](../spec.md), News/Event models, identity, time and errors
3. Plan 09 handoff
4. Current AKShare News/Event Adapters and compatibility projections

## Dependencies

Plan 09 complete. May run in parallel with Plans 10–13.

## File ownership

```text
tools/ingest/src/astock/providers/tushare/news.py
tools/ingest/src/astock/providers/tushare/events.py
tools/ingest/src/astock/providers/tushare/_ids.py
tools/ingest/tests/providers/tushare/fixtures/news/
tools/ingest/tests/providers/tushare/fixtures/events/
tools/ingest/tests/providers/test_tushare_news.py
tools/ingest/tests/providers/test_tushare_events.py
```

Do not edit control-plane projections, registry, or defaults unless a proven
backward-compatible defect requires coordinated ownership.

## Deliverables

### News

- Query all configured/entitled sources for the inclusive time range and handle
  the documented per-request window/row limit.
- Map title, publication time, publisher, bounded summary/content, and URL.
- Associate an article only through exact TS code, exact full security name, or
  a maintained unambiguous alias supplied to the Adapter.
- Reject fuzzy, LLM, and raw substring-only association.
- De-duplicate syndicated/repeated records using a stable normalized identity.
- Mark incomplete time/source coverage explicitly; never turn unknown coverage
  into a conclusive empty Dataset.

### Events

- Implement `NoticeEvent`, `ResearchReportEvent`, `BlockTradeEvent`, and
  `HolderChangeEvent` using the production-entitled Tushare APIs.
- Map source primary IDs/URLs where available and construct stable IDs with a
  variant discriminator.
- Normalize date-only publication times to Asia/Shanghai with warnings.
- Normalize volumes/changes to shares, amounts to CNY, and ratios to percentage points.
- Filter broad market responses to exact Instrument identity before returning.
- Distinguish no data, unsupported entitlement, auth failure, and partial coverage.

## Required fixtures/tests

- news exact code/name/alias matches and ambiguous/non-match cases;
- duplicate/syndicated news, missing URL, long content, timezone and row truncation;
- every typed event with all optional fields plus minimal rows;
- same-time same-title event discriminator, negative holder change, block-trade units;
- entitlement/auth/rate-limit/partial/empty/malformed responses;
- shared News/Event contracts and legacy CLI/HTTP projection compatibility.

## Verification

```bash
uv run --directory tools/ingest pytest \
  tests/providers/test_tushare_news.py \
  tests/providers/test_tushare_events.py \
  tests/providers/test_news_contract.py \
  tests/providers/test_events_contract.py \
  tests/test_compat_shapes.py tests/test_news.py tests/test_events.py
uv run --directory apps/control-plane/core pytest \
  tests/test_http.py tests/test_feature_http.py
git diff --check
```

## Acceptance criteria

- Tushare can answer all current News/Event protocols under the production entitlements.
- Association and stable identity rules are deterministic and tested.
- All four event variants preserve current public response compatibility.
- No registration/default change occurs.
- Verification passes.

## Handoff

Record exact entitled APIs, association rules/coverage limitations, stable-ID
inputs, unit conversions, fixture inventory, compatibility results, and counts.

## Cursor subagent invocation

```text
Implement docs/market-data/plans/14-tushare-news-events.md after Plan 09.
Read required material, stay within ownership, do not register/enable the source,
run verification, and append API/entitlement and coverage evidence to Handoff.
```

