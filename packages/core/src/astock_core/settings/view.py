from __future__ import annotations

from typing import Any

from astock_core.settings.catalog import (
    ANALYZE_GRAPH_KEYS,
    ANALYZE_LLM_KEYS,
    ANALYZE_RUNTIME_KEYS,
    INGEST_QUOTES_KEYS,
    INGEST_SCHEDULE_KEYS,
    live_paths,
)
from astock_core.settings.db import SystemDB
from astock_core.settings.validate import public_values


def paths_payload() -> dict[str, str]:
    payload = live_paths()
    payload["config"] = payload["system"]
    return payload


def settings_catalog_view() -> dict[str, Any]:
    with SystemDB() as db:
        modules = []
        for module in db.list_catalog():
            sections = []
            for section in module["sections"]:
                values = db.get_values(module["id"], section["id"])
                sections.append(
                    {
                        "id": section["id"],
                        "title": section["title"],
                        "description": section["description"],
                        "sort_order": section["sort_order"],
                        "schema": section["schema"],
                        "schema_version": section["schema_version"],
                        "read_only": section["read_only"],
                        "updated_at": section["updated_at"],
                    }
                )
                sections[-1]["values"] = public_values(section["schema"], values)
            modules.append(
                {
                    "id": module["id"],
                    "title": module["title"],
                    "description": module["description"],
                    "sort_order": module["sort_order"],
                    "sections": sections,
                }
            )
        return {"modules": modules, "paths": paths_payload()}


def get_section_view(module_id: str, section_id: str) -> dict[str, Any]:
    with SystemDB() as db:
        section = db.get_section(module_id, section_id)
    return {
        "module": section["module"],
        "module_title": section["module_title"],
        "section": section["section"],
        "title": section["title"],
        "description": section["description"],
        "schema": section["schema"],
        "schema_version": section["schema_version"],
        "read_only": section["read_only"],
        "updated_at": section["updated_at"],
        "values": public_values(section["schema"], section["values"]),
        "paths": paths_payload(),
    }


def update_section(module_id: str, section_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    with SystemDB() as db:
        db.put_values(module_id, section_id, patch)
    return get_section_view(module_id, section_id)


def preview_section(module_id: str, section_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    with SystemDB() as db:
        current = db.get_section(module_id, section_id)
        if current["read_only"]:
            raise ValueError(f"{current['title']}不能修改")
        from astock_core.settings.validate import merge_section_patch

        return merge_section_patch(current["schema"], current["values"], patch)


def load_settings() -> dict[str, Any]:
    with SystemDB() as db:
        quotes = db.get_values("ingest", "quotes")
        schedule = db.get_values("ingest", "schedule")
        llm = db.get_values("analyze", "llm")
        graph = db.get_values("analyze", "graph")
        runtime = db.get_values("analyze", "runtime")
    return {
        "pool": quotes["pool"],
        "adjust": quotes["adjust"],
        "quotes": {
            "sync_enabled": schedule["sync_enabled"],
            "sync_time": schedule["sync_time"],
            "timezone": schedule["timezone"],
            "sleep": quotes["sleep"],
        },
        "analyze": {**llm, **graph, **runtime},
    }


def public_settings(settings: dict[str, Any]) -> dict[str, Any]:
    with SystemDB() as db:
        llm_schema = db.get_section("analyze", "llm")["schema"]
    view = dict(settings)
    analyze = view.get("analyze")
    if isinstance(analyze, dict):
        view["analyze"] = public_values(llm_schema, analyze)
    view["paths"] = paths_payload()
    return view


def settings_view() -> dict[str, Any]:
    return public_settings(load_settings())


def preview_update(patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("settings 必须是对象")
    sections = _legacy_patches(patch)
    assembled = load_settings()
    with SystemDB() as db:
        for module_id, section_id, section_patch in sections:
            current = db.get_section(module_id, section_id)
            from astock_core.settings.validate import merge_section_patch

            merged = merge_section_patch(current["schema"], current["values"], section_patch)
            _apply_section_to_assembled(assembled, module_id, section_id, merged)
    return assembled


def write_settings(settings: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(settings, dict):
        raise ValueError("settings 必须是对象")
    patches = _legacy_patches(settings)
    if not patches:
        return load_settings()
    with SystemDB() as db:
        for module_id, section_id, patch in patches:
            db.put_values(module_id, section_id, patch)
    return load_settings()


def load_analyze_values() -> dict[str, Any]:
    with SystemDB() as db:
        values = {}
        values.update(db.get_values("analyze", "llm"))
        values.update(db.get_values("analyze", "graph"))
        values.update(db.get_values("analyze", "runtime"))
        return values


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return preview_update(settings if settings else {})


def _apply_section_to_assembled(
    assembled: dict[str, Any],
    module_id: str,
    section_id: str,
    values: dict[str, Any],
) -> None:
    if module_id == "ingest" and section_id == "quotes":
        assembled["pool"] = values["pool"]
        assembled["adjust"] = values["adjust"]
        assembled["quotes"]["sleep"] = values["sleep"]
        return
    if module_id == "ingest" and section_id == "schedule":
        assembled["quotes"]["sync_enabled"] = values["sync_enabled"]
        assembled["quotes"]["sync_time"] = values["sync_time"]
        assembled["quotes"]["timezone"] = values["timezone"]
        return
    if module_id == "analyze":
        assembled["analyze"].update(values)


def _legacy_patches(patch: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    patches: list[tuple[str, str, dict[str, Any]]] = []
    quotes: dict[str, Any] = {}
    if "pool" in patch:
        quotes["pool"] = patch["pool"]
    if "adjust" in patch:
        quotes["adjust"] = patch["adjust"]
    quotes_in = patch.get("quotes")
    schedule: dict[str, Any] = {}
    if isinstance(quotes_in, dict):
        for key in INGEST_QUOTES_KEYS:
            if key in quotes_in:
                quotes[key] = quotes_in[key]
        for key in INGEST_SCHEDULE_KEYS:
            if key in quotes_in:
                schedule[key] = quotes_in[key]
    elif quotes_in is not None:
        raise ValueError("quotes 必须是对象")
    if quotes:
        patches.append(("ingest", "quotes", quotes))
    if schedule:
        patches.append(("ingest", "schedule", schedule))

    analyze = patch.get("analyze")
    if analyze is None:
        return patches
    if not isinstance(analyze, dict):
        raise ValueError("analyze 必须是对象")
    llm = {key: analyze[key] for key in ANALYZE_LLM_KEYS if key in analyze}
    graph = {key: analyze[key] for key in ANALYZE_GRAPH_KEYS if key in analyze}
    runtime = {key: analyze[key] for key in ANALYZE_RUNTIME_KEYS if key in analyze}
    unknown = set(analyze) - set(ANALYZE_LLM_KEYS) - set(ANALYZE_GRAPH_KEYS) - set(ANALYZE_RUNTIME_KEYS)
    if unknown:
        raise ValueError(f"未知设置项: {', '.join(sorted(unknown))}")
    if llm:
        patches.append(("analyze", "llm", llm))
    if graph:
        patches.append(("analyze", "graph", graph))
    if runtime:
        patches.append(("analyze", "runtime", runtime))
    return patches
