# Tushare Primary Source Migration Specification

Status: specified for implementation

Target version: one atomic release

Last updated: 2026-09-02

## 1. Decision

This release migrates every existing market-data capability to Tushare as the
primary Data Source and AKShare as the first fallback. Eastmoney may remain a
later fallback where it already has a production Adapter, but it is not the
primary source after this release.

The migration is delivered, tested, and enabled in one version. There are no
phased production cutovers, mixed old/new defaults, or follow-up capability
migrations. A release that does not satisfy every acceptance criterion in this
specification must not change the production source defaults.

This specification extends [`spec.md`](./spec.md). Where its single-release
requirement conflicts with the incremental execution language in the existing
plans, this specification wins for the Tushare migration.

## 2. Scope

The release must implement Tushare production Adapters for all current
capability keys:

```text
instruments, calendar, bars, quote_snapshots, valuations,
fundamentals, statements, classifications, memberships, news, events
```

It must also deliver:

1. Tushare SDK and transport configuration;
2. credential handling and redaction;
3. source registry and settings-schema changes;
4. field, unit, identity, time, and error translation;
5. pagination, rate limiting, retry, and request budgeting;
6. fixture-backed Adapter contracts and optional credentialed integration probes;
7. full historical/bootstrap and incremental synchronization behavior;
8. an atomic default-order cutover with a configuration-only rollback;
9. documentation and full-system verification.

No new Standard Record is required merely because Tushare exposes additional
fields. Useful fields that do not fit a current record require a separately
approved model change; they must not leak as source-shaped dictionaries.

## 3. Non-goals

- Intraday Bar persistence or streaming market data.
- Replacing SQLite, Qlib, control-plane HTTP contracts, or UI read models.
- Persisting every field exposed by Tushare.
- Treating AKShare as a validation oracle for Tushare values.
- Guaranteeing that a third-party Tushare-compatible endpoint has the same
  provenance, entitlements, availability, or semantics as the official service.

## 4. Source and transport identity

`Dataset.source` is `tushare` for records returned through the Tushare Adapter,
regardless of whether the configured HTTP endpoint is official or compatible.
Transport identity is recorded separately in structured logs as a redacted host
label. It must not be used as taxonomy or record provenance.

The implementation must not hard-code an endpoint or token. Configuration is:

```text
TUSHARE_TOKEN       required when any Tushare Adapter is selected
TUSHARE_API_URL     optional; absence means the SDK official default
TUSHARE_TIMEOUT     optional positive seconds
TUSHARE_MAX_RPM     optional positive request budget
```

Requirements:

- secrets are read from the process environment or an approved secret store;
- tokens are never stored in settings JSON, SQLite settings, fixtures, command
  arguments, exception text, logs, HTTP responses, or source control;
- SDK private attributes may be set only inside one Tushare client factory,
  because the compatible endpoint requires `_DataApi__http_url`;
- the factory validates an HTTPS URL, rejects embedded credentials, and logs
  only the hostname;
- official and compatible endpoints run the same capability probe suite before
  a production cutover;
- authentication failure is terminal for that source attempt and may fall back
  according to the existing typed fallback policy.

Any credential disclosed in chat, an issue, or a log is considered compromised
and must be rotated before integration testing.

## 5. Dependency and module layout

`tools/ingest` adds a bounded `tushare` dependency compatible with the approved
SDK baseline (initial target `>=1.4.24,<2`). The target layout is:

```text
tools/ingest/src/astock/providers/tushare/
  __init__.py
  client.py
  _tables.py
  _time.py
  instruments.py
  calendar.py
  bars.py
  snapshots.py
  fundamentals.py
  statements.py
  classifications.py
  news.py
  events.py
```

Only this directory may import `tushare` or manipulate the SDK client. Adapters
remain read-only and return validated Standard Records; they never write to
`MarketDB`.

## 6. Capability mapping

The following is the required production mapping. Equivalent compatible-server
API names are accepted only when the credentialed capability probe proves the
same input and output contract.

| Capability | Required Tushare APIs | Required mapping |
|---|---|---|
| instruments | `stock_basic` | code, exchange, name, currency, list/delist date, area and industry |
| calendar | `trade_cal` | exchange, calendar date, open flag |
| bars | `daily`, `weekly`, `monthly`, `adj_factor`, `daily_basic` | OHLC, volume, amount, turnover and adjustment factor |
| quote_snapshots | real-time quote API, `stk_limit`, `suspend_d`, `daily_basic` | price, prior close, limits, volume ratio and suspension state |
| valuations | `daily_basic` | shares, market caps, PE and PB |
| fundamentals | `fina_indicator` | all current `FundamentalPeriod` fields |
| statements | `income`, `balancesheet`, `cashflow` | canonical statement items and announcement metadata |
| classifications | index basic data, `index_classify`, THS/DC concept catalogs where entitled | index, industry and concept taxonomies |
| memberships | `index_weight`, `index_member`, `index_member_all`, THS/DC concept members where entitled | member identity, effective dates and weight |
| news | `news` and/or entitled long-news API | title, time, publisher, summary, URL and deterministic instrument association |
| events | announcement, research-report, `block_trade`, and `stk_holdertrade` APIs | all four existing typed event variants |

An unavailable entitlement does not make an Adapter complete. Before release,
the configured production endpoint and account must pass every API probe needed
for the table above. If a required API is absent, the release is blocked rather
than silently shipping AKShare as the effective primary for that capability.

### 6.1 Instruments and profiles

`stock_basic` must be queried for listed, delisted, and suspended statuses needed
to answer the requested `InstrumentQuery`. Mapping is:

```text
ts_code       -> InstrumentId
name          -> Instrument.name and InstrumentProfile.name
curr_type     -> currency (normalized to ISO 4217)
list_date     -> list_date
delist_date   -> delist_date
industry      -> InstrumentProfile.industry
area          -> InstrumentProfile.region
```

Exchange conversion is `SH -> XSHG`, `SZ -> XSHE`, and `BJ -> BSE`; unexpected
suffixes raise `InvalidSourcePayload`. ST status comes from the entitled ST list
or an explicit Tushare status API, with the security name as a documented
fallback signal only.

### 6.2 Calendar

`trade_cal` maps `cal_date` to `trade_date` and `is_open` to `bool`. The Adapter
must return the entire inclusive requested range, including closed days. SSE and
SZSE may share a market calendar only after the returned range is verified equal;
the query market identity remains explicit.

### 6.3 Bars and adjustment

Daily, weekly, and monthly intervals are supported. Unit conversion is mandatory:

```text
daily/weekly/monthly vol      hands * 100 -> shares
daily/weekly/monthly amount   thousand CNY * 1,000 -> CNY
daily_basic.turnover_rate     -> turnover_pct
adj_factor.adj_factor         -> adjustment_factor
```

The Adapter must define and test the exact formula for `none`, `forward`, and
`backward` adjustment against a fixed fixture. It must not combine a Tushare
adjustment factor with an already adjusted price series. Whole-market history is
planned by trading date, not one request per Instrument, unless an API contract
requires otherwise.

### 6.4 Quote snapshots

One snapshot may be composed from multiple Tushare responses inside the Adapter.
`observed_at` uses a source timestamp when available; fetch time is permitted
only with a Dataset warning. `stk_limit` supplies high/low limits and `suspend_d`
supplies suspension state/reason. A field absent from the entitled real-time API
maps to `None`; it must not be synthesized from unrelated historical data.

The Adapter is considered contract-complete only if the production probe proves
that latest price and prior close are available. Average price, inner volume,
and outer volume are optional Standard Record fields and may remain `None`.

### 6.5 Valuations

`daily_basic` conversion is:

```text
total_share * 10,000 -> total_shares
float_share * 10,000 -> float_shares
total_mv * 10,000    -> total_market_cap
circ_mv * 10,000     -> float_market_cap
pe_ttm               -> pe_ttm
pe                   -> pe_static
pb                   -> pb
```

When `ValuationQuery.as_of` is set, the Adapter must return that date or the last
available trading date on or before it and record the actual date. It must not
label the latest observation with the requested historical date.

### 6.6 Fundamentals and statements

Financial rows are identified by Instrument, report period, report type, actual
announcement date, company type, and update flag. Duplicate or revised reports
must be resolved deterministically: prefer the latest published update available
as of synchronization time while preserving `announced_at`.

At minimum, `fina_indicator` must populate every current optional field when the
source supplies it. Statement mappings must cover every canonical code in
`CANONICAL_STATEMENT_ITEMS` for ordinary industrial companies and must have
fixture coverage for bank, insurer, and broker `comp_type` variants. Unknown
source columns are ignored; known source columns must never appear as canonical
codes.

### 6.7 Classifications and memberships

Taxonomies are stable and source-explicit, for example:

```text
tushare.csindex
tushare.sw2021
tushare.ths
tushare.dc
```

IDs are the provider's stable classification codes, not display names. Index
weights map directly to percentage points. Effective dates come from source
in/out dates when available; a monthly index weight date is an observation date,
not an invented effective start. The Adapter must not merge different taxonomy
versions under one key.

### 6.8 News

The current Standard Record requires an Instrument. Tushare news that does not
carry a security identifier may be associated only by deterministic rules based
on exact TS code, exact full security name, or a maintained unambiguous alias.
Fuzzy language-model or substring-only association is prohibited at the Adapter
seam.

A requested Instrument with no deterministically associated Tushare articles may
return a conclusive empty Dataset only when the queried time/source coverage is
complete. Otherwise the Adapter returns `complete=False` with warnings, which is
not converted into invented records. The production account must have the
required separately entitled news API before cutover.

### 6.9 Events

All existing variants are required in the same release:

```text
NoticeEvent
ResearchReportEvent
BlockTradeEvent
HolderChangeEvent
```

Stable IDs use source, Instrument, event kind, source primary key when available,
publication/trade time, and a variant discriminator. Amount is CNY, volume and
holder changes are shares, and ratios are percentage points. Announcement and
research URLs must be retained when supplied. Unsupported event kinds or absent
entitlements fail the pre-release probe; they do not disappear silently.

## 7. Query planning, limits, and caching

Each Adapter documents the API row limit and chooses one deterministic paging
dimension: trading date, announcement date, report period, or Instrument. It
must detect truncation using the documented limit and continue until coverage is
complete. Pages are de-duplicated by Standard Record natural key and sorted only
after all pages are translated.

One process-wide request governor enforces `TUSHARE_MAX_RPM`. Server rate-limit
responses translate to `RateLimited`, honor a bounded server retry delay when
present, and remain eligible for typed fallback. Static catalogs and identical
in-flight requests may be cached within one job; cache keys include endpoint
host label, API name, normalized parameters, and requested fields. Tokens never
appear in cache keys.

## 8. Source order after cutover

The settings schema adds `tushare` to the allowed source enum and changes the
complete default configuration atomically to:

```json
{
  "schema_version": 2,
  "instruments": ["tushare", "akshare"],
  "calendar": ["tushare", "akshare"],
  "bars": ["tushare", "akshare", "eastmoney"],
  "quote_snapshots": ["tushare", "akshare", "eastmoney"],
  "valuations": ["tushare", "akshare", "eastmoney"],
  "fundamentals": ["tushare", "akshare"],
  "statements": ["tushare", "akshare"],
  "classifications": ["tushare", "akshare"],
  "memberships": ["tushare", "akshare"],
  "news": ["tushare", "akshare"],
  "events": ["tushare", "akshare"]
}
```

Schema version 2 migration replaces untouched version 1 defaults. Explicit user
source orders are preserved after validating newly supported names; operators
must opt in when an existing installation has a customized order.

Fallback remains per capability and per query. A successful empty Dataset stops
fallback under the existing policy. Partial datasets do not cause record-level
cross-source blending; a capability-specific use case may request the next source
only through an explicit, tested completeness policy.

## 9. Synchronization and storage

Existing repositories and public read models remain compatible. The release must
support both:

- bootstrap: a clean database can ingest all configured universes and historical
  ranges exclusively through registry-resolved capabilities;
- incremental: watermarks request only missing or revisable ranges, including
  recent financial-report restatements and membership changes.

Before changing defaults, run a shadow comparison that writes no production
records. Compare Tushare with the currently selected source over fixed samples:

```text
at least 30 Instruments across XSHG, XSHE and BSE;
at least 250 trading days of Bars;
at least four report periods including financial companies;
HS300 plus one industry and one concept classification;
all four event variants and a bounded news window.
```

Differences are reported by coverage, missingness, unit/order invariants, and
field-level tolerances. Source disagreement alone is not an automatic failure;
unexplained unit, identity, date, duplicate, or completeness violations are.

## 10. Testing

Required tests include:

1. one shared contract suite pass for every Tushare capability Adapter;
2. fixture tests for valid, empty, malformed, truncated, duplicate, revised,
   rate-limited, authentication-failed, and unavailable responses;
3. unit tests for all conversions in section 6;
4. SDK client tests proving endpoint validation and token redaction;
5. registry/settings tests for schema version 2 and every default order;
6. fallback tests proving Tushare-to-AKShare selection and actual provenance;
7. bootstrap and incremental synchronization tests;
8. CLI/control-plane compatibility tests;
9. architecture tests allowing Tushare imports only in its Adapter directory;
10. credentialed, non-destructive production-endpoint probes for every required
    API, skipped only in ordinary local/CI runs and mandatory in release evidence.

Fixtures contain no real token, account identifier, cookie, or proprietary bulk
payload. Small synthetic rows model the documented schema.

## 11. Observability

Every attempt logs capability, source, redacted endpoint host label, API name,
query identity, page count, request count, elapsed time, item count, coverage,
completeness, warning count, rate-budget state, and typed error category.

Logs must not contain tokens, SDK authorization payloads, full news/report text,
cookies, raw response bodies, or unbounded Instrument lists.

The synchronization summary distinguishes:

```text
primary success
fallback success
conclusive empty
partial
failed
```

## 12. Atomic release and rollback

All code, settings schema, tests, and documentation ship together. The release
sequence is:

1. deploy code capable of reading schema versions 1 and 2;
2. run mandatory credential and capability probes;
3. run shadow comparison and full verification;
4. migrate the source-order setting to version 2 in one transaction;
5. start synchronization with Tushare primary for all capabilities.

There is no capability-by-capability production enablement. If any step before
step 4 fails, defaults remain unchanged. After step 4, operational rollback is a
single settings transaction restoring the captured version 1 source order; no
code rollback or destructive data deletion is required. Records already written
remain valid Standard Records and retain actual Dataset/source observability.

## 13. Acceptance criteria

The migration is complete only when all criteria pass in the same release:

1. `tushare` is a valid source for all 11 capability keys.
2. Every Tushare Adapter passes its shared contract and source fixture suite.
3. The production endpoint/account passes the required API and entitlement probe
   without exposing credentials.
4. Default source settings exactly match section 8 and AKShare is the first
   fallback for every capability.
5. All field/unit/date/identity/adjustment rules in section 6 have tests.
6. Bootstrap and incremental ingestion pass without direct source imports outside
   Adapter directories.
7. Existing SQLite, CLI, HTTP, UI, analysis, and Qlib contracts remain compatible.
8. Shadow comparison has no unexplained invariant or completeness failures.
9. Logs and errors pass token/credential redaction tests.
10. A settings-only rollback is rehearsed and restores the pre-migration order.
11. Repository architecture checks and `pnpm check` pass.
12. Release evidence records SDK version, endpoint host label, entitled APIs,
    test counts, comparison summary, setting migration, and rollback result.

No criterion may be deferred to a later version. Failure of one criterion blocks
the entire default-source cutover.

## 14. Implementation work packages

Implementation is divided into Plans 09–16 solely so bounded subagents can work
with explicit ownership and handoffs:

```text
09 client foundation
  -> 10 instruments/calendar
  -> 11 bars/snapshots/valuations
  -> 12 fundamentals/statements
  -> 13 classifications/memberships
  -> 14 news/events
10–14 complete -> 15 synchronization/probes/shadow comparison
09–15 complete -> 16 registry/settings/atomic cutover
```

Plans 10–14 may execute in parallel after Plan 09. No plan before Plan 16 may
change production source defaults, and completion of an individual plan is not a
partial release. The plan index and direct Cursor invocation prompts are in
[`README.md`](./README.md).

## 15. Required implementation evidence

The implementation handoff appended to this document must contain:

- changed modules and public configuration keys;
- the final API-to-capability matrix with probe result per row;
- fixture and contract test locations;
- source-order settings before and after migration;
- shadow comparison sample and discrepancy disposition;
- complete verification commands and results;
- credential-redaction evidence;
- rollback rehearsal result;
- any intentionally unavailable optional Standard Record fields.
