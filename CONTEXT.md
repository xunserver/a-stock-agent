# A-Stock Market Data

This context describes the market data collected, normalized, stored, and consumed by the A-stock tools. It separates source-specific payloads from the stable records used by the rest of the system.

## Language

**Instrument**:
A uniquely identified tradable or reference security, such as an A-share stock, index, or ETF. An Instrument identity includes its exchange; a six-digit symbol alone is not an identity.
_Avoid_: Stock when indexes or ETFs are also possible, code as an identity

**Instrument ID**:
The stable, exchange-qualified identity of an Instrument, written as `{country}.{exchange}.{symbol}`, for example `CN.XSHG.600519`.
_Avoid_: Ticker, six-digit code

**Data Source**:
An external origin of market data, such as Eastmoney or AKShare. A Data Source returns its own payload shape and has no authority over the system's standard records.
_Avoid_: Provider when referring to the external company or library

**Adapter**:
The implementation that translates one Data Source's payloads into standard records at a data capability seam.
_Avoid_: Fetcher, wrapper

**Standard Record**:
A source-independent, validated market-data value consumed by synchronization and persistence. Standard Records carry explicit identity, time, units, and provenance.
_Avoid_: Raw row, DataFrame row

**Dataset**:
The result of one data-source request: zero or more Standard Records plus provenance, fetch time, coverage, completeness, and warnings.
_Avoid_: Response, raw payload

**Bar**:
An OHLCV record for one Instrument and one interval, with explicit adjustment mode and normalized units.
_Avoid_: K-line row, quote

**Quote Snapshot**:
Observed point-in-time trading data such as last price, previous close, limits, and suspension state. Its observation time is part of its identity.
_Avoid_: Profile, latest data

**Instrument Profile**:
Slow-changing descriptive facts about an Instrument, such as name, industry, region, and listing date.
_Avoid_: Quote profile, stock info

**Valuation Snapshot**:
Point-in-time capitalization, share-count, and valuation measures for an Instrument.
_Avoid_: Profile, fundamentals

**Fundamental Period**:
Normalized financial metrics for one reporting period, identified by period end and announcement time.
_Avoid_: Financial snapshot, latest financials

**Financial Statement**:
One balance sheet, income statement, or cash-flow statement for a reporting period, expressed with stable line-item codes.
_Avoid_: Source payload, report summary

**Classification**:
A named grouping in a declared taxonomy, such as an industry, concept, or index.
_Avoid_: Board when referring to all grouping kinds

**Membership**:
The effective-dated relationship between an Instrument and a Classification.
_Avoid_: Constituent list when historical validity matters
