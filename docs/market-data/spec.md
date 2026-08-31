# Market Data Source Abstraction Specification

Status: approved for implementation

Version: 1.0

Last updated: 2026-08-31

## 1. Purpose

The system must be able to replace or combine AKShare, Eastmoney, exchange data, paid vendors, and local fixtures without changing synchronization use cases, persistence code, Qlib export, analysis, control-plane queries, or UI contracts.

The seam is the source-independent Standard Record. External payloads, pandas DataFrames, Chinese source columns, source field numbers, retry behavior, authentication, and transport details remain behind Adapters.

## 2. Goals

1. Define one stable representation for each market-data capability.
2. Make units, identity, time, adjustment, provenance, completeness, and error meaning explicit.
3. Let each capability select and fall back across Data Sources independently.
4. Keep synchronization responsible for planning and persistence, not payload translation.
5. Test every Adapter through the same capability interface and contract suite.
6. Preserve existing CLI, HTTP, database, UI, and Qlib behavior during incremental migration.

## 3. Non-goals

- Replacing SQLite or redesigning control-plane HTTP endpoints.
- Adding intraday bars in this migration. The model must permit them later, but v1 supports daily, weekly, and monthly bars only.
- Implementing real-time streaming.
- Making every source support every capability.
- Requiring one Data Source to produce a complete stock detail view.
- Rewriting Qlib workflows or TradingAgents integration.

## 4. Architecture

```text
Data Source payload
        |
        v
Capability Adapter  -- transport, source schema, units, source retry
        |
        v
Standard Record + Dataset  -- the seam
        |
        v
Synchronization use case  -- range planning, fallback policy, derivation, persistence
        |
        v
MarketDB repository  -- SQLite schema and read models
        |
        +--> control-plane / UI
        +--> Qlib export
        +--> analysis
```

Dependency direction is one-way:

- `astock_core.market_data` contains dependency-free Standard Records, queries, errors, and validation.
- `astock.providers` contains capability interfaces, source Adapters, fallback, and registry logic.
- Existing ingest use cases depend on capability interfaces and `MarketDB`.
- `astock_core` never imports `astock`, pandas, AKShare, curl-cffi, or a source Adapter.
- Adapters return values and never write to `MarketDB`.

## 5. Module layout

The target layout is:

```text
packages/core/src/astock_core/market_data/
  __init__.py
  identity.py
  models.py
  queries.py
  dataset.py
  errors.py
  validation.py

tools/ingest/src/astock/providers/
  __init__.py
  protocols.py
  registry.py
  fallback.py
  akshare/
    __init__.py
    instruments.py
    calendar.py
    bars.py
    snapshots.py
    fundamentals.py
    classifications.py
    news.py
    events.py
  eastmoney/
    __init__.py
    bars.py
    snapshots.py
```

Files may be combined when that produces a deeper module, but the public imports and ownership rules above must remain true.

## 6. Shared conventions

### 6.1 Types

- Core models use Python standard-library dataclasses, enums, `date`, `datetime`, and generic types. `astock-core` remains dependency-free.
- Models are immutable (`frozen=True`) unless a documented reason requires mutation.
- Public collection fields are tuples, not mutable lists.
- Numeric values use finite `float` values in v1 to match SQLite and existing consumers. NaN and infinity are invalid.
- Missing optional values use `None`; empty strings never represent missing data.

### 6.2 Time

- Trading dates use `datetime.date` and refer to the exchange-local calendar date.
- Observations and fetch times use timezone-aware `datetime` values.
- Dates serialize as ISO `YYYY-MM-DD`; datetimes serialize as ISO 8601 with offset.
- Query `start` and `end` are inclusive.

### 6.3 Units

- Currency is an explicit ISO 4217 code; current A-share records use `CNY`.
- Price values are currency units per share.
- `volume` is shares. Adapters convert lots/hands into shares.
- `amount` is currency units, not thousands or ten-thousands.
- Fields ending in `_pct` use percentage points: `1.25` means `1.25%`.
- Share counts are shares.

### 6.4 Ordering and uniqueness

- Time-series Dataset items are ascending by effective time.
- Catalog records are ascending by `InstrumentId.value` unless the query defines another order.
- Duplicate natural keys are invalid. The Adapter must resolve or reject duplicates before returning.
- Callers may rely on deterministic ordering.

## 7. Identity

### 7.1 InstrumentId

```python
@dataclass(frozen=True, order=True)
class InstrumentId:
    country: str
    exchange: str
    symbol: str

    @property
    def value(self) -> str:
        return f"{self.country}.{self.exchange}.{self.symbol}"
```

Supported v1 exchange values:

| Exchange | Meaning |
|---|---|
| `XSHG` | Shanghai Stock Exchange |
| `XSHE` | Shenzhen Stock Exchange |
| `BSE` | Beijing Stock Exchange |

Six-digit symbols remain in existing persistence and HTTP DTOs during migration. Conversion between `InstrumentId` and legacy codes happens at repository/use-case edges, not in source payload mappers.

### 7.2 Instrument

Required fields:

```text
id, asset_type, name, currency, timezone
```

Optional fields:

```text
list_date, delist_date
```

`asset_type` v1 values are `stock`, `index`, and `etf`.

## 8. Dataset and provenance

Every capability returns `Dataset[T]`:

```python
@dataclass(frozen=True)
class Dataset(Generic[T]):
    items: tuple[T, ...]
    source: str
    fetched_at: datetime
    coverage_start: date | None = None
    coverage_end: date | None = None
    complete: bool = True
    warnings: tuple[str, ...] = ()
```

Invariants:

1. `source` is a stable registry key such as `eastmoney` or `akshare`, not a display label.
2. `fetched_at` is timezone-aware.
3. Coverage describes the interval the source conclusively answered, including a conclusive empty Dataset.
4. `complete=False` means the Adapter knows results are partial; the reason appears in `warnings`.
5. A successful empty Dataset is distinct from `NoData` only as follows:
   - return an empty Dataset when the source conclusively answered a valid collection/range query;
   - raise `NoData` when the requested Instrument or dataset is known but unavailable and callers must treat that condition explicitly.
6. Fallback preserves the selected Dataset's actual `source`; it never reports the registry or fallback wrapper as the source.

## 9. Errors

All capability errors derive from `MarketDataError`:

| Error | Meaning | Retry same source | Try next source |
|---|---|---:|---:|
| `UnsupportedQuery` | Source cannot serve the capability/query | No | Yes |
| `InstrumentNotFound` | Source does not recognize the Instrument | No | Yes |
| `NoData` | Instrument exists but requested dataset is unavailable | No | Configurable; default no |
| `RateLimited` | Source rejected due to request rate | After backoff | Yes |
| `SourceUnavailable` | Timeout, transport failure, or temporary upstream failure | Yes | Yes |
| `InvalidSourcePayload` | Payload violates expected source or Standard Record shape | No | Yes |
| `AuthenticationFailed` | Missing or rejected credentials | No | Yes |

Adapters translate third-party exceptions into these errors. Synchronization and UI code do not inspect AKShare, requests, curl-cffi, pandas, or vendor exception types.

An empty payload must never be used as a substitute for an error.

## 10. Capability interfaces

Interfaces live in `astock.providers.protocols`. Each capability has one method so callers learn only the query and result.

```python
class InstrumentSource(Protocol):
    def fetch_instruments(self, query: InstrumentQuery) -> Dataset[Instrument]: ...

class CalendarSource(Protocol):
    def fetch_calendar(self, query: CalendarQuery) -> Dataset[TradingDay]: ...

class BarSource(Protocol):
    def fetch_bars(self, query: BarQuery) -> Dataset[Bar]: ...

class QuoteSnapshotSource(Protocol):
    def fetch_snapshots(self, query: SnapshotQuery) -> Dataset[QuoteSnapshot]: ...

class ValuationSource(Protocol):
    def fetch_valuations(self, query: ValuationQuery) -> Dataset[ValuationSnapshot]: ...

class FundamentalSource(Protocol):
    def fetch_fundamentals(self, query: FundamentalQuery) -> Dataset[FundamentalPeriod]: ...

class StatementSource(Protocol):
    def fetch_statements(self, query: StatementQuery) -> Dataset[FinancialStatement]: ...

class ClassificationSource(Protocol):
    def fetch_classifications(self, query: ClassificationQuery) -> Dataset[Classification]: ...

class MembershipSource(Protocol):
    def fetch_memberships(self, query: MembershipQuery) -> Dataset[Membership]: ...

class NewsSource(Protocol):
    def fetch_news(self, query: NewsQuery) -> Dataset[NewsItem]: ...

class EventSource(Protocol):
    def fetch_events(self, query: EventQuery) -> Dataset[MarketEvent]: ...
```

Adapters may implement multiple interfaces. Callers request a capability interface, never a concrete all-purpose source object.

## 11. Bars and calendar

### 11.1 BarQuery

```text
instruments   one or more InstrumentId values
start         inclusive date
end           inclusive date; end >= start
interval      1d | 1w | 1mo
adjustment    raw | qfq | hfq
```

### 11.2 Bar

```text
instrument_id       required
trade_date          required
interval            required
adjustment          required
open                required
high                required
low                 required
close               required
volume              required; shares
amount              required; currency units
turnover_pct        optional
adjustment_factor   optional in migration, required before adjusted and raw data coexist
```

Natural key:

```text
(instrument_id, trade_date, interval, adjustment)
```

Validation:

- Prices are positive finite values.
- `high >= max(open, close, low)`.
- `low <= min(open, close, high)`.
- `volume >= 0`, `amount >= 0`, and `turnover_pct >= 0` when present.
- Every item falls within the query range and matches its requested interval and adjustment.
- `pct_change`, `change_amount`, `amplitude_pct`, and `vwap` are derived after normalization and are not source requirements.
- Weekly and monthly bars may be sourced or derived, but all returned records obey the same interface.

### 11.3 CalendarQuery and TradingDay

```text
CalendarQuery: market_id, start, end
TradingDay: market_id, trade_date, is_open, session_type?
```

The v1 persistence projection stores open dates only. Closed-day records may be returned by an Adapter but are filtered by the repository mapping. Calendar synchronization replaces a market's answered coverage atomically and records its watermark in the same transaction.

## 12. Instrument Profile, Quote Snapshot, and Valuation Snapshot

The existing mixed stock profile is split into three records.

### 12.1 InstrumentProfile

```text
instrument_id, name, industry?, region?, list_date?, is_st
```

This record contains slow-changing descriptive facts only.

### 12.2 QuoteSnapshot

```text
instrument_id, observed_at, last_price?, pre_close?, average_price?,
high_limit?, low_limit?, volume_ratio?, outer_volume?, inner_volume?,
is_suspended, suspend_reason?
```

Quote Snapshot Dataset items are sorted by `(instrument_id, observed_at)`. Snapshot values never masquerade as daily Bars.

### 12.3 ValuationSnapshot

```text
instrument_id, as_of, currency, total_shares?, float_shares?,
total_market_cap?, float_market_cap?, pe_ttm?, pe_static?, pb?
```

Derived values may fill missing fields only when their inputs share the same `as_of`. Derived-field provenance is recorded in Dataset warnings until field-level lineage exists.

During migration, these records project into existing `stocks` columns so HTTP and UI contracts remain unchanged.

## 13. Fundamentals and financial statements

### 13.1 FundamentalPeriod

```text
instrument_id, period_end, period_type, announced_at?, currency,
eps?, bps?, roe_pct?, revenue?, revenue_yoy_pct?, net_profit?,
net_profit_yoy_pct?, gross_margin_pct?, net_margin_pct?, debt_ratio_pct?
```

`period_type` is `Q1`, `H1`, `Q3`, or `FY`. `announced_at=None` is accepted for display compatibility but makes the record unsafe for point-in-time research. Research/export code must exclude such records unless explicitly configured otherwise.

### 13.2 FinancialStatement

```text
instrument_id, sheet, period_end, period_type, announced_at?, currency,
items: tuple[StatementItem, ...], source_payload?
```

`sheet` is `balance`, `profit`, or `cashflow`.

`StatementItem` fields:

```text
code, label, value, unit, yoy_pct?, qoq_pct?
```

- `code` is a stable internal snake_case identifier.
- `label` is display text and may change without changing identity.
- `unit` is `CNY`, `shares`, `per_share`, `percent`, or `text`.
- Source keys such as `TOTAL_ASSETS` are permitted only inside an Adapter mapping table or `source_payload`.
- Persistence may retain `source_payload` during migration, but control-plane and UI read models consume normalized items.

The first canonical item set must cover every key item currently displayed plus these minimums:

```text
balance: cash_and_equivalents, accounts_receivable, inventory,
         total_current_assets, total_assets, total_current_liabilities,
         total_liabilities, total_parent_equity, total_equity
profit:  total_revenue, operating_revenue, operating_profit, total_profit,
         net_profit, parent_net_profit, basic_eps
cashflow: operating_cash_inflow, operating_cash_outflow,
          net_operating_cashflow, net_investing_cashflow,
          net_financing_cashflow, net_change_in_cash, ending_cash
```

## 14. Classifications and memberships

### 14.1 Classification

```text
id, kind, name, taxonomy
```

`kind` is `industry`, `concept`, or `index`. `taxonomy` identifies the naming authority, for example `eastmoney`, `csindex`, or `custom`.

Classification identity is `(taxonomy, id)`. Source-local IDs are never assumed globally unique.

### 14.2 Membership

```text
classification_id, taxonomy, instrument_id,
effective_from?, effective_to?, weight_pct?
```

Current-source snapshots may omit effective dates. Such memberships describe current state and are unsafe for historical backtests. Persistence continues to replace current memberships atomically per Classification until historical membership storage is added.

## 15. News and events

### 15.1 NewsItem

```text
id, instrument_id, title, published_at, publisher?, summary?, url?
```

`title` is non-empty. `published_at` is a timezone-aware datetime or a declared date-only timestamp normalized to local midnight with a warning. `id` is the source ID when available, otherwise a stable hash of source, Instrument, publication time, title, and URL.

### 15.2 MarketEvent

Market events use a discriminated union with a common header:

```text
id, instrument_id, kind, title, published_at, source?, url?
```

Supported v1 variants:

- `NoticeEvent`: `notice_type?`, `summary?`
- `ResearchReportEvent`: `organization?`, `rating?`, `summary?`, `pdf_url?`
- `BlockTradeEvent`: `deal_price?`, `volume?`, `amount?`, `premium_pct?`, `buyer?`, `seller?`, `close_price?`, `pct_change?`
- `HolderChangeEvent`: `person?`, `role?`, `change_shares?`, `average_price?`, `reason?`

The existing HTTP `extra` object remains a compatibility projection generated from the typed variant. It is not the internal interface.

## 16. Source registry and fallback

Source selection is per capability. Registry keys are stable strings.

Example target configuration:

```json
{
  "bars": ["eastmoney", "akshare"],
  "calendar": ["akshare"],
  "instruments": ["akshare"],
  "quote_snapshots": ["eastmoney", "akshare"],
  "valuations": ["eastmoney", "akshare"],
  "fundamentals": ["akshare"],
  "statements": ["akshare"],
  "classifications": ["akshare"],
  "news": ["akshare"],
  "events": ["akshare"]
}
```

Rules:

1. Registry construction happens at the ingest entry point and dependencies are injected into use cases.
2. Transport retry belongs to each Adapter; cross-source fallback belongs to the fallback module.
3. Fallback tries the next source only according to the error table in section 9.
4. A successful empty Dataset stops fallback unless capability policy explicitly says otherwise.
5. Validation runs before an Adapter Dataset crosses the seam. Invalid data raises `InvalidSourcePayload` and may trigger fallback.
6. Warnings and failed attempts are logged with capability, source, query identity, elapsed time, and error category. Secrets and raw credentials are never logged.

## 17. Persistence compatibility

The first migration keeps existing SQLite tables and public read models.

| Standard Record | Existing projection |
|---|---|
| Instrument | `stocks`, `index_daily.name` |
| TradingDay | `trade_calendar` |
| Bar | `bars_daily`, `bars_weekly`, `bars_monthly`, `index_daily` |
| InstrumentProfile | descriptive `stocks` columns |
| QuoteSnapshot | quote/status `stocks` columns |
| ValuationSnapshot | shares/market-cap/valuation `stocks` columns |
| FundamentalPeriod | `financial_reports` and latest `stocks` metrics |
| FinancialStatement | `financial_statements` |
| Classification | `boards`, universe metadata |
| Membership | `board_members`, `universe_members` |
| NewsItem / MarketEvent | real-time response only in v1 |

Repository methods accept Standard Records or explicit persistence projections. Tuple position and source DataFrame columns must not cross into repository method calls after the relevant plan completes.

Schema additions are permitted only when required to preserve semantics that cannot be represented today. Every addition requires a versioned migration and migration test.

## 18. Derived data

Derivation happens after source normalization:

- Bar `change_amount`, `pct_change`, and `amplitude_pct` derive from Standard Bars.
- Weekly/monthly bars may derive from daily Bars using exchange calendar periods.
- Yearly bars remain a read-model derivation.
- `vwap` remains `(high + low + close) / 3` until a volume-weighted source is introduced; the name and limitation stay documented in Qlib code.
- Price limits may derive from `pre_close`, board rules, and ST state when the source omits them.
- Financial ratios may derive only from values sharing one reporting period and currency.

Derived values must be deterministic and tested independently from Adapters.

## 19. Contract tests

Every capability has a reusable contract-test function. An Adapter test supplies a fixture-backed Adapter and the contract suite asserts only behavior visible through the interface.

Minimum coverage:

- valid query and deterministic ordering;
- empty successful Dataset;
- normalized units and timezones;
- duplicate and malformed payload rejection;
- query range enforcement;
- typed error translation;
- completeness and coverage metadata;
- no pandas objects or vendor exceptions crossing the seam.

Live network tests are optional and excluded from the default suite. Default tests use captured minimal fixtures or in-memory Adapters.

## 20. Compatibility and removal policy

Each migration plan follows expand-and-contract:

1. Add Standard Records, interfaces, and Adapter tests.
2. Add an Adapter over current behavior.
3. Switch one use case and its tests to the interface.
4. Verify existing public behavior.
5. Remove the replaced source-shaped path and tests that inspect implementation details.

Compatibility façades may exist only while callers remain. Each façade includes a removal comment naming the final plan that removes it.

After a capability is migrated:

- production modules outside its Adapter directory contain no direct call to its external Data Source;
- tests for use cases inject an in-memory capability Adapter rather than monkeypatching AKShare functions;
- Adapter tests alone know source column names and payload schemas.

## 21. Final acceptance criteria

The migration is complete when all conditions hold:

1. Every external market-data call is inside `astock.providers` Adapter code.
2. No synchronization, repository, control-plane, Qlib, analysis, or UI module imports AKShare, curl-cffi, or pandas source payloads.
3. Every capability returns a validated `Dataset` of Standard Records.
4. Existing CLI commands, HTTP routes, UI behavior, and Qlib exports remain compatible unless a separately approved change says otherwise.
5. Source order is configurable per capability and fallback follows section 16.
6. The scheduler obtains calendars through the same Calendar interface as manual synchronization.
7. Financial statement read models no longer depend on Eastmoney field identifiers.
8. Every Adapter passes its reusable capability contract suite.
9. Architecture checks reject new direct source calls outside Adapter directories.
10. `pnpm check` passes.
