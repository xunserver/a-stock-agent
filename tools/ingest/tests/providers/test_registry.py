from __future__ import annotations

import json

import pytest

from astock.providers.registry import (
    DEFAULT_SOURCE_ORDER,
    RegistryValidationError,
    build_registry,
    serialize_source_order,
    validate_source_order_config,
)
from astock_core.settings.catalog import ingest_sources_defaults
from astock_core.settings.db import SystemDB
from astock_core.settings.validate import merge_section_patch


def test_default_source_order_matches_spec() -> None:
    normalized = validate_source_order_config(ingest_sources_defaults())
    assert normalized == {key: tuple(value) for key, value in DEFAULT_SOURCE_ORDER.items()}


def test_validate_rejects_unknown_source() -> None:
    config = ingest_sources_defaults()
    config["bars"] = ["eastmoney", "unknown"]
    with pytest.raises(RegistryValidationError, match="unknown source"):
        validate_source_order_config(config)


def test_validate_rejects_unknown_capability() -> None:
    config = ingest_sources_defaults()
    config["extra"] = ["akshare"]
    with pytest.raises(RegistryValidationError, match="unknown capability"):
        validate_source_order_config(config)


def test_validate_rejects_missing_capability() -> None:
    config = ingest_sources_defaults()
    del config["news"]
    with pytest.raises(RegistryValidationError, match="missing required"):
        validate_source_order_config(config)


def test_validate_rejects_empty_source_order() -> None:
    config = ingest_sources_defaults()
    config["calendar"] = []
    with pytest.raises(RegistryValidationError, match="cannot be empty"):
        validate_source_order_config(config)


def test_validate_rejects_duplicate_source() -> None:
    config = ingest_sources_defaults()
    config["bars"] = ["eastmoney", "eastmoney"]
    with pytest.raises(RegistryValidationError, match="duplicate source"):
        validate_source_order_config(config)


def test_validate_rejects_unsupported_schema_version() -> None:
    config = ingest_sources_defaults()
    config["schema_version"] = 2
    with pytest.raises(RegistryValidationError, match="schema_version"):
        validate_source_order_config(config)


def test_defaults_are_independent_copies() -> None:
    first = ingest_sources_defaults()
    first["bars"].append("akshare")
    assert ingest_sources_defaults()["bars"] == ["eastmoney", "akshare"]


def test_build_registry_exposes_all_capabilities() -> None:
    registry = build_registry(retries=1)
    assert registry.bar_source() is not None
    assert registry.calendar_source() is not None
    assert registry.instrument_source() is not None
    assert registry.profile_source() is not None
    assert registry.quote_snapshot_source() is not None
    assert registry.valuation_source() is not None
    assert registry.fundamental_source() is not None
    assert registry.statement_source() is not None
    assert registry.classification_source() is not None
    assert registry.membership_source() is not None
    assert registry.news_source() is not None
    assert registry.event_source() is not None


def test_serialize_source_order_is_secret_free() -> None:
    payload = serialize_source_order(validate_source_order_config(ingest_sources_defaults()))
    text = json.dumps(payload)
    assert "api_key" not in text
    assert "token" not in text


def test_settings_merge_partial_patch(tmp_path) -> None:
    with SystemDB(tmp_path / "system.db") as db:
        section = db.get_section("ingest", "sources")
        merged = merge_section_patch(section["schema"], section["values"], {"bars": ["akshare", "eastmoney"]})
        assert merged["bars"] == ["akshare", "eastmoney"]
        assert merged["calendar"] == section["values"]["calendar"]


def test_settings_schema_rejects_invalid_source_and_capability(tmp_path) -> None:
    with SystemDB(tmp_path / "system.db") as db:
        section = db.get_section("ingest", "sources")
        with pytest.raises(ValueError, match="不合法"):
            merge_section_patch(
                section["schema"],
                section["values"],
                {"bars": ["unknown"]},
            )
        with pytest.raises(ValueError, match="未知设置项"):
            merge_section_patch(
                section["schema"],
                section["values"],
                {"unknown_capability": ["akshare"]},
            )
