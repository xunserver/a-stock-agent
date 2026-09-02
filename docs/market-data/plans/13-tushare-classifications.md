# Plan 13: Tushare Classifications and Memberships

Status: not started

Release boundary: internal work package; not independently deployable

## Objective

Implement Tushare index, industry, and concept Classification/Membership Adapters
with stable versioned taxonomies, weights, and trustworthy effective dates. Do
not register or enable them.

## Required reading

1. [`../tushare-migration-spec.md`](../tushare-migration-spec.md), section 6.7
2. [`../spec.md`](../spec.md), Classification and Membership sections
3. [`../../../CONTEXT.md`](../../../CONTEXT.md)
4. Plan 09 handoff
5. Current AKShare classification Adapter, taxonomy constants, pool/universe use cases

## Dependencies

Plan 09 complete. May run in parallel with Plans 10, 11, 12, and 14.

## File ownership

```text
tools/ingest/src/astock/providers/tushare/classifications.py
tools/ingest/tests/providers/tushare/fixtures/classifications/
tools/ingest/tests/providers/test_tushare_classifications.py
```

Core taxonomy additions may be made only when source-independent and coordinated.
Do not edit pool persistence, registry, or defaults.

## Deliverables

- Implement index catalogs and members/weights from the appropriate Tushare APIs.
- Implement current entitled Shenwan classification/version and members.
- Implement THS and DC concept catalogs/members where required by the production
  account; absence of a required entitlement blocks release evidence.
- Use stable taxonomies such as `tushare.csindex`, `tushare.sw2021`,
  `tushare.ths`, and `tushare.dc`; never identify a taxonomy by display name.
- Map classification codes independently of names and normalize members to
  `InstrumentId`.
- Map weight to percentage points.
- Use source in/out dates as effective bounds. Keep monthly weight observation
  dates distinct from effective membership dates; never invent history.
- Support classification-id, kind, taxonomy, Instrument, and as-of query filters.
- Provide conclusive-empty semantics for valid groups with no members.

## Required fixtures/tests

- HS300 weighted membership over two dates;
- SW2021 hierarchy and component changes;
- THS and DC concepts with colliding display names but distinct IDs/taxonomies;
- member in/out dates, missing weights, duplicates, malformed codes;
- latest-only source data marked with correct completeness/warnings;
- shared Classification and Membership contracts;
- pool/universe legacy projection compatibility.

## Verification

```bash
uv run --directory tools/ingest pytest \
  tests/providers/test_tushare_classifications.py \
  tests/providers/test_classification_contract.py \
  tests/providers/test_membership_contract.py
uv run --directory apps/control-plane/core pytest tests/test_pool_members.py
git diff --check
```

Adjust contract filenames only to match existing repository names; record the
actual commands in Handoff.

## Acceptance criteria

- Index, industry, and concept queries are covered in one Adapter family.
- Taxonomy versions cannot collide or silently merge.
- Historical/effective semantics are honest and tested.
- No registration/default change occurs.
- Verification passes.

## Handoff

Record API-to-taxonomy mapping, hierarchy/effective-date rules, entitlements,
fixture inventory, pool compatibility, actual verification commands, and counts.

## Cursor subagent invocation

```text
Implement docs/market-data/plans/13-tushare-classifications.md after Plan 09.
Read all required material, stay within ownership, do not register/enable the
source, run the actual available contract tests, and append evidence to Handoff.
```

