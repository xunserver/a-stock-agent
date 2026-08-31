"""Per-capability source registry and validated composition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, Literal
from zoneinfo import ZoneInfo

from astock.providers.akshare import (
    AkshareBarAdapter,
    AkshareCalendarAdapter,
    AkshareClassificationAdapter,
    AkshareEventAdapter,
    AkshareFundamentalAdapter,
    AkshareInstrumentAdapter,
    AkshareMembershipAdapter,
    AkshareNewsAdapter,
    AkshareSnapshotAdapter,
    AkshareStatementAdapter,
)
from astock.providers.eastmoney import EastmoneyBarAdapter, EastmoneySnapshotAdapter
from astock.providers.eastmoney.snapshots import CN_TIMEZONE
from astock.providers.fallback import FallbackCapability
from astock.providers.protocols import (
    BarSource,
    CalendarSource,
    ClassificationSource,
    EventSource,
    FundamentalSource,
    InstrumentProfileSource,
    InstrumentSource,
    MembershipSource,
    NewsSource,
    QuoteSnapshotSource,
    StatementSource,
    ValuationSource,
)
from astock_core.market_data import (
    Dataset,
    InstrumentQuery,
    MarketDataError,
    SnapshotQuery,
    ValuationQuery,
    to_legacy_symbol,
)

CapabilityKey = Literal[
    "instruments",
    "calendar",
    "bars",
    "quote_snapshots",
    "valuations",
    "fundamentals",
    "statements",
    "classifications",
    "memberships",
    "news",
    "events",
]

KNOWN_SOURCES: frozenset[str] = frozenset({"eastmoney", "akshare"})
REQUIRED_CAPABILITIES: tuple[CapabilityKey, ...] = (
    "instruments",
    "calendar",
    "bars",
    "quote_snapshots",
    "valuations",
    "fundamentals",
    "statements",
    "classifications",
    "memberships",
    "news",
    "events",
)
DEFAULT_SOURCE_ORDER: dict[CapabilityKey, tuple[str, ...]] = {
    "bars": ("eastmoney", "akshare"),
    "calendar": ("akshare",),
    "instruments": ("akshare",),
    "quote_snapshots": ("eastmoney", "akshare"),
    "valuations": ("eastmoney", "akshare"),
    "fundamentals": ("akshare",),
    "statements": ("akshare",),
    "classifications": ("akshare",),
    "memberships": ("akshare",),
    "news": ("akshare",),
    "events": ("akshare",),
}
SOURCES_SETTINGS_SECTION = ("ingest", "sources")


class RegistryValidationError(ValueError):
    """Invalid registry configuration."""


def default_source_order() -> dict[str, tuple[str, ...]]:
    return {key: tuple(value) for key, value in DEFAULT_SOURCE_ORDER.items()}


def validate_source_order_config(config: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    if not isinstance(config, Mapping):
        raise RegistryValidationError("source order must be an object")
    schema_version = config.get("schema_version", 1)
    if isinstance(schema_version, bool) or schema_version != 1:
        raise RegistryValidationError(
            f"unsupported source-order schema_version: {schema_version!r}"
        )

    unknown_keys = sorted(set(config) - set(REQUIRED_CAPABILITIES) - {"schema_version"})
    if unknown_keys:
        raise RegistryValidationError(f"unknown capability keys: {', '.join(unknown_keys)}")

    missing = [key for key in REQUIRED_CAPABILITIES if key not in config]
    if missing:
        raise RegistryValidationError(f"missing required capabilities: {', '.join(missing)}")

    normalized: dict[str, tuple[str, ...]] = {}
    for capability in REQUIRED_CAPABILITIES:
        raw = config[capability]
        if not isinstance(raw, (list, tuple)):
            raise RegistryValidationError(f"{capability} source order must be an array")
        if not raw:
            raise RegistryValidationError(f"{capability} source order cannot be empty")
        seen: set[str] = set()
        order: list[str] = []
        for item in raw:
            source = str(item)
            if source not in KNOWN_SOURCES:
                raise RegistryValidationError(f"unknown source '{source}' for {capability}")
            if source in seen:
                raise RegistryValidationError(f"duplicate source '{source}' in {capability}")
            seen.add(source)
            order.append(source)
        normalized[capability] = tuple(order)
    return normalized


def serialize_source_order(config: Mapping[str, tuple[str, ...]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        **{key: list(config[key]) for key in REQUIRED_CAPABILITIES},
    }


class StockInfoComposite:
    """Eastmoney primary records with AKShare ST/suspend overlay."""

    def __init__(
        self,
        *,
        primary: EastmoneySnapshotAdapter,
        overlay: AkshareSnapshotAdapter,
    ) -> None:
        self._primary = primary
        self._overlay = overlay

    def fetch_profiles(self, query: InstrumentQuery) -> Dataset:
        dataset = self._primary.fetch_profiles(query)
        try:
            st_codes = self._overlay.st_codes()
        except MarketDataError:
            return dataset
        items = []
        for profile in dataset.items:
            code = to_legacy_symbol(profile.instrument_id)
            if profile.is_st or code not in st_codes:
                items.append(profile)
                continue
            items.append(replace(profile, is_st=True))
        return Dataset(
            items=tuple(items),
            source=dataset.source,
            fetched_at=dataset.fetched_at,
            coverage_start=dataset.coverage_start,
            coverage_end=dataset.coverage_end,
            complete=dataset.complete,
            warnings=dataset.warnings,
        )

    def fetch_snapshots(self, query: SnapshotQuery) -> Dataset:
        dataset = self._primary.fetch_snapshots(query)
        try:
            mapping = self._overlay.suspend_reasons(
                dataset.fetched_at.astimezone(ZoneInfo(CN_TIMEZONE)).date()
            )
        except MarketDataError:
            return dataset
        items = []
        for snapshot in dataset.items:
            code = to_legacy_symbol(snapshot.instrument_id)
            reason = mapping.get(code)
            if not reason:
                items.append(snapshot)
                continue
            items.append(replace(snapshot, is_suspended=True, suspend_reason=reason))
        return Dataset(
            items=tuple(items),
            source=dataset.source,
            fetched_at=dataset.fetched_at,
            coverage_start=dataset.coverage_start,
            coverage_end=dataset.coverage_end,
            complete=dataset.complete,
            warnings=dataset.warnings,
        )

    def fetch_valuations(self, query: ValuationQuery) -> Dataset:
        return self._primary.fetch_valuations(query)


class _FallbackBarSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_bars(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackCalendarSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_calendar(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackInstrumentSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_instruments(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackQuoteSnapshotSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_snapshots(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackValuationSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_valuations(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackFundamentalSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_fundamentals(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackStatementSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_statements(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackClassificationSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_classifications(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackMembershipSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_memberships(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackNewsSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_news(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class _FallbackEventSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_events(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


class CapabilityRegistry:
    """Validated per-capability source registry with typed fallback."""

    def __init__(
        self,
        source_order: Mapping[str, tuple[str, ...]],
        *,
        retries: int,
        pause: float = 0.0,
    ) -> None:
        self._order = validate_source_order_config(source_order)
        self._retries = retries
        self._pause = pause
        self._adapters = self._build_adapters()

    @classmethod
    def from_settings(cls, *, pause: float = 0.0) -> CapabilityRegistry:
        from astock.config import request_retries, sources_settings

        return cls(sources_settings(), retries=request_retries(), pause=pause)

    def source_order(self) -> dict[str, tuple[str, ...]]:
        return dict(self._order)

    def bar_source(self) -> BarSource:
        return _FallbackBarSource(self._fallback("bars", lambda adapter, query: adapter.fetch_bars(query)))

    def calendar_source(self) -> CalendarSource:
        return _FallbackCalendarSource(
            self._fallback("calendar", lambda adapter, query: adapter.fetch_calendar(query))
        )

    def instrument_source(self) -> InstrumentSource:
        return _FallbackInstrumentSource(
            self._fallback("instruments", lambda adapter, query: adapter.fetch_instruments(query))
        )

    def profile_source(self) -> InstrumentProfileSource:
        return _FallbackProfileSource(
            self._fallback("quote_snapshots", lambda adapter, query: adapter.fetch_profiles(query))
        )

    def quote_snapshot_source(self) -> QuoteSnapshotSource:
        return _FallbackQuoteSnapshotSource(
            self._fallback("quote_snapshots", lambda adapter, query: adapter.fetch_snapshots(query))
        )

    def valuation_source(self) -> ValuationSource:
        return _FallbackValuationSource(
            self._fallback("valuations", lambda adapter, query: adapter.fetch_valuations(query))
        )

    def fundamental_source(self) -> FundamentalSource:
        return _FallbackFundamentalSource(
            self._fallback("fundamentals", lambda adapter, query: adapter.fetch_fundamentals(query))
        )

    def statement_source(self) -> StatementSource:
        return _FallbackStatementSource(
            self._fallback("statements", lambda adapter, query: adapter.fetch_statements(query))
        )

    def classification_source(self) -> ClassificationSource:
        return _FallbackClassificationSource(
            self._fallback("classifications", lambda adapter, query: adapter.fetch_classifications(query))
        )

    def membership_source(self) -> MembershipSource:
        return _FallbackMembershipSource(
            self._fallback("memberships", lambda adapter, query: adapter.fetch_memberships(query))
        )

    def news_source(self) -> NewsSource:
        return _FallbackNewsSource(
            self._fallback("news", lambda adapter, query: adapter.fetch_news(query))
        )

    def event_source(self) -> EventSource:
        return _FallbackEventSource(
            self._fallback("events", lambda adapter, query: adapter.fetch_events(query))
        )

    def _fallback(self, capability: CapabilityKey, fetch):
        names = self._order[capability]
        adapters = tuple(self._adapters[capability][name] for name in names)
        return FallbackCapability(
            capability=capability,
            source_names=names,
            sources=adapters,
            fetch=fetch,
        )

    def _build_adapters(self) -> dict[str, dict[str, Any]]:
        built: dict[str, dict[str, Any]] = {capability: {} for capability in REQUIRED_CAPABILITIES}
        for capability in REQUIRED_CAPABILITIES:
            for source in self._order[capability]:
                if source in built[capability]:
                    continue
                built[capability][source] = _create_adapter(
                    capability,
                    source,
                    retries=self._retries,
                    pause=self._pause,
                    overlay=self._overlay_adapter(),
                )
        return built

    def _overlay_adapter(self) -> AkshareSnapshotAdapter | None:
        if "akshare" not in self._order["quote_snapshots"]:
            return None
        return AkshareSnapshotAdapter(retries=self._retries, pause=self._pause)


class _FallbackProfileSource:
    def __init__(self, inner: FallbackCapability[Any]) -> None:
        self._inner = inner

    def fetch_profiles(self, query: Any) -> Dataset:
        return self._inner.fetch(query)


def _create_adapter(
    capability: CapabilityKey,
    source: str,
    *,
    retries: int,
    pause: float,
    overlay: AkshareSnapshotAdapter | None = None,
) -> Any:
    if source == "eastmoney":
        if capability == "bars":
            return EastmoneyBarAdapter(retries=retries)
        if capability in {"quote_snapshots", "valuations"}:
            primary = EastmoneySnapshotAdapter(retries=retries, pause=pause)
            if overlay is not None:
                return StockInfoComposite(primary=primary, overlay=overlay)
            return primary
        raise RegistryValidationError(f"eastmoney does not support {capability}")

    if source != "akshare":
        raise RegistryValidationError(f"unknown source '{source}'")

    factory = {
        "instruments": AkshareInstrumentAdapter,
        "calendar": AkshareCalendarAdapter,
        "bars": AkshareBarAdapter,
        "quote_snapshots": AkshareSnapshotAdapter,
        "valuations": AkshareSnapshotAdapter,
        "fundamentals": AkshareFundamentalAdapter,
        "statements": AkshareStatementAdapter,
        "classifications": AkshareClassificationAdapter,
        "memberships": AkshareMembershipAdapter,
        "news": AkshareNewsAdapter,
        "events": AkshareEventAdapter,
    }
    adapter_type = factory.get(capability)
    if adapter_type is None:
        raise RegistryValidationError(f"akshare does not support {capability}")
    if capability in {"quote_snapshots", "valuations"}:
        return adapter_type(retries=retries, pause=pause)
    return adapter_type(retries=retries)


def build_registry(
  source_order: Mapping[str, Any] | None = None,
  *,
  retries: int | None = None,
  pause: float = 0.0,
) -> CapabilityRegistry:
    from astock.config import request_retries, sources_settings

    order = sources_settings() if source_order is None else validate_source_order_config(source_order)
    return CapabilityRegistry(order, retries=request_retries() if retries is None else retries, pause=pause)


def resolve_capability(
    capability: CapabilityKey,
    *,
    pause: float = 0.0,
) -> Any:
    """Resolve one capability through the configured registry.

    Production composition roots should build one registry and inject its sources.
    This resolver keeps direct library/debug use explicit and registry-backed.
    """
    registry = build_registry(pause=pause)
    resolvers = {
        "instruments": registry.instrument_source,
        "calendar": registry.calendar_source,
        "bars": registry.bar_source,
        "quote_snapshots": registry.quote_snapshot_source,
        "valuations": registry.valuation_source,
        "fundamentals": registry.fundamental_source,
        "statements": registry.statement_source,
        "classifications": registry.classification_source,
        "memberships": registry.membership_source,
        "news": registry.news_source,
        "events": registry.event_source,
    }
    try:
        return resolvers[capability]()
    except KeyError as exc:
        raise RegistryValidationError(f"unknown capability key: {capability}") from exc
