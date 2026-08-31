# Plan 07: News and Typed Events

Status: complete

## Objective

Move real-time news and market-event fetching behind stable interfaces, normalize publication time and identity, and replace internal arbitrary event dictionaries with typed variants while preserving existing HTTP response shapes.

## Required reading

1. [`CONTEXT.md`](../../../CONTEXT.md)
2. [`spec.md`](../spec.md), sections 8–10, 15–20
3. Plans 01–06 and their handoffs
4. `tools/ingest/src/astock/news.py`
5. `tools/ingest/src/astock/events.py`
6. control-plane news/event Adapters and queries
7. UI news/event types and rendering code

## Preconditions

- Plans 01–06 are complete.
- Identify current CLI JSON and HTTP compatibility shapes with tests before editing.

## Scope

Migrate:

- stock news;
- notices;
- research reports;
- block trades;
- holder changes;
- CLI/control-plane compatibility projections;
- related source and interface tests.

Persistence remains out of scope; these capabilities stay request-time in v1.

## Deliverables

### 1. News Adapter and contract

Implement current AKShare news fetching behind `NewsSource`. Normalize:

- Instrument identity;
- stable item identity;
- title and optional summary;
- publisher;
- URL;
- timezone-aware publication time or declared date-only normalization warning.

Completion criterion: valid, empty, malformed, missing-time, duplicate, and source-failure fixtures pass the reusable News contract expectations.

### 2. Event Adapters and discriminated records

Implement all four event kinds behind `EventSource` using typed variants from specification section 15.2. Normalize volume to shares, amount to CNY, and percentage values to percentage points.

Completion criterion: no arbitrary `extra: dict[str, Any]` crosses the internal interface.

### 3. Compatibility projection

Generate the existing CLI/HTTP item dictionaries from Standard Records at the control-plane or CLI presentation edge. Preserve:

```text
title, summary, published_at, source, url, extra
```

For typed events, construct `extra` deterministically from the variant. UI types need not change unless tightening them is backward compatible.

Completion criterion: existing API response tests pass and new tests prove projection of every event variant.

### 4. Control-plane seam

The control plane currently launches ingest subprocesses for request-time data. It may continue that deployment shape, but the JSON crossing the process must represent Standard Records or a versioned compatibility DTO produced from them. Document the chosen seam and keep parsing validation explicit.

Completion criterion: control-plane code does not know AKShare columns or vendor exception types and distinguishes typed source failures from successful empty results before applying the user-facing generic error message.

### 5. Cleanup

Remove old mapping functions and tests that patch AKShare calls at use-case level. Keep source payload tests inside Adapter tests.

Completion criterion: direct news/event source calls exist only under Adapter directories.

## Verification

```bash
uv run --directory tools/ingest pytest tests/test_news.py tests/test_events.py tests/test_cli.py
uv run --directory apps/control-plane/core pytest tests/test_http.py tests/test_feature_http.py
pnpm --filter @astock/ui test
pnpm run typecheck
pnpm run check:architecture
```

## Acceptance criteria

- News and Event use cases consume capability interfaces.
- Internal events are typed variants.
- Publication time, units, identity, and errors are normalized.
- Existing CLI/HTTP/UI shapes remain compatible.
- No source-specific mapping remains outside Adapters.

## Handoff

Completed 2026-08-31. News and events now flow through `NewsSource` / `EventSource` with typed Standard Records and legacy compatibility projections at the ingest CLI edge.

### Standard Record serialization / process seam

- **Internal seam:** Adapters return `Dataset[NewsItem]` or `Dataset[MarketEvent]`; use cases depend only on capability interfaces.
- **Subprocess JSON:** Control plane continues to spawn ingest CLI (`stock news` / `stock events`). The trailing JSON payload carries a **versioned compatibility DTO** (not raw Standard Records) produced by `news_item_to_legacy_dict` / `market_event_to_legacy_dict` in `packages/core/src/astock_core/market_data/projections.py`.
- **Validation:** `validate_legacy_news_items` / `validate_legacy_event_items` in `packages/core/src/astock_core/market_data/compat_dto.py` run in control-plane adapters (`apps/control-plane/core/src/astock_control/adapters/news.py`, `events.py`) before items reach queries.
- **Failure vs empty:** Successful empty datasets return `count: 0` with exit code 0; `MarketDataError` / transport failures exit non-zero and surface as typed `RuntimeError` in adapters, which queries map to user-facing `error` strings (empty list + no error remains distinct).

### Stable ID generation rule

Implemented in `tools/ingest/src/astock/providers/akshare/_ids.py`:

1. Use non-empty source ID when the payload supplies one.
2. Otherwise hash source, Instrument ID, publication time, title, URL, and any
   variant discriminator needed to distinguish legitimate same-time events. Block
   trades add price/volume/amount/buyer/seller; holder changes add person/role/share
   change/average price/reason.

Natural keys equal `id`; duplicates raise `InvalidSourcePayload` before the seam.

### Date-only normalization behavior

`tools/ingest/src/astock/providers/akshare/_time.py` parses datetimes with `Asia/Shanghai` when a time component exists. Date-only values normalize to local midnight with a Dataset warning:

```text
published_at for {context} normalized from date-only '{raw}' to local midnight
```

Missing publication time raises `InvalidSourcePayload`. Legacy projection formats midnight as `YYYY-MM-DD`; timed values as `YYYY-MM-DD HH:MM:SS`. ISO timestamps with offsets are preserved and converted to `Asia/Shanghai`; they are not mistaken for date-only values.

### Typed-event-to-`extra` mapping

| Location | Role |
|---|---|
| `packages/core/src/astock_core/market_data/projections.py` → `market_event_extra()` | Deterministic variant → legacy `extra` keys |
| `packages/core/src/astock_core/market_data/projections.py` → `market_event_to_legacy_dict()` | Full CLI/HTTP item including synthesized `summary` |

Legacy key preservation:

- `NoticeEvent` → `notice_type`
- `ResearchReportEvent` → `org`, `rating`
- `BlockTradeEvent` → `deal_price`, `premium_ratio`, `volume`, `amount`, `buyer`, `seller`, `close_price`, `pct_chg`
- `HolderChangeEvent` → `name`, `role`, `change_qty`, `avg_price`, `reason`

### Removed source-shaped paths

Production orchestration no longer calls AKShare directly:

- Removed from `astock/news.py`: `_call`, `ak.stock_news_em`, column mapping loop
- Removed from `astock/events.py`: `_call`, per-kind AKShare fetchers, `_item` dict builder, exchange-specific column mapping

AKShare function names and column handling exist only under `tools/ingest/src/astock/providers/akshare/{news,events}.py` and adapter tests. Use-case tests inject `NewsSource` / `EventSource` fakes instead of monkeypatching `_call`.

Internal Datasets are ascending by publication time. Limit selection keeps the latest N records, and the compatibility presentation edge reverses them so CLI/HTTP retain their historical newest-first order. The five base DTO keys are always present; absent optional values project as empty strings.

### Public import paths

```python
from astock.providers.akshare import AkshareNewsAdapter, AkshareEventAdapter
from astock.providers.protocols import NewsSource, EventSource
from astock.providers.defaults import default_news_source, default_event_source
from astock_core.market_data import (
    news_item_to_legacy_dict,
    market_event_to_legacy_dict,
    market_event_extra,
    validate_news_dataset,
    validate_event_dataset,
    validate_legacy_news_items,
    validate_legacy_event_items,
    NEWS_ITEM_KEYS,
    EVENT_ITEM_KEYS,
)
```

```python
fetch_stock_news(code, *, limit=None, news_source=None)
fetch_stock_events(code, kind, *, limit=None, event_source=None)
```

### Verification

```bash
uv run --directory tools/ingest pytest tests/test_news.py tests/test_events.py tests/test_cli.py
# 15 passed

uv run --directory tools/ingest pytest tests/test_compat_shapes.py tests/providers/test_news_contract.py tests/providers/test_events_contract.py tests/providers/test_akshare_news.py tests/providers/test_akshare_events.py
# 34 passed (focused contracts + shapes, plus use-case projection coverage)

uv run --directory tools/ingest pytest tests/providers/
# provider coverage included in the 140-test full ingest suite

uv run --directory apps/control-plane/core pytest tests/test_http.py tests/test_feature_http.py tests/test_stock_quotes.py
# 31 passed

pnpm --filter @astock/ui test
# 51 passed

pnpm run typecheck
# passed

pnpm run check:architecture
# passed
```

Final full ingest verification after the independent audit fixes: **140 passed**.

### Notes for Plan 08

- Replace `astock.providers.defaults` news/event helpers with the per-capability source registry.
- Do not add persistence for news/events until a separate plan approves it.
