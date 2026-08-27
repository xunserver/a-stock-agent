from __future__ import annotations

import math
import re
from typing import Any


def secret_fields(schema: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return fields
    for name, spec in properties.items():
        if isinstance(spec, dict) and spec.get("x-secret"):
            fields.append(str(name))
    return fields


def public_values(schema: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    view = dict(values)
    for key in secret_fields(schema):
        secret = str(view.pop(key, "") or "")
        view[f"{key}_set"] = bool(secret)
        view[f"{key}_hint"] = "••••" if secret else ""
    return view


def merge_section_patch(
    schema: dict[str, Any],
    current: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("取值必须是对象")
    merged = dict(current)
    secrets = set(secret_fields(schema))
    for key, value in patch.items():
        if key in secrets:
            if value is None or value == "":
                continue
            if value == "__clear__":
                merged[key] = ""
            else:
                merged[key] = value
            continue
        merged[key] = value
    return validate_against_schema(schema, merged)


def validate_against_schema(schema: dict[str, Any], data: Any) -> dict[str, Any]:
    if schema.get("type") != "object":
        raise ValueError("设置 schema 必须是对象")
    if not isinstance(data, dict):
        raise ValueError("取值必须是对象")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("设置 schema 缺少 properties")
    extra = set(data) - set(properties)
    if extra and schema.get("additionalProperties") is False:
        raise ValueError(f"未知设置项: {', '.join(sorted(extra))}")
    required = schema.get("required") or []
    missing = [name for name in required if name not in data]
    if missing:
        titles = [_title(properties.get(name), name) for name in missing]
        raise ValueError(f"{'、'.join(titles)}不能为空")
    out: dict[str, Any] = {}
    for name, spec in properties.items():
        if name not in data:
            continue
        if not isinstance(spec, dict):
            raise ValueError(f"{name} 的 schema 不合法")
        out[name] = _validate_value(spec, data[name], _title(spec, name))
    return out


def _title(spec: Any, fallback: str) -> str:
    if isinstance(spec, dict) and spec.get("title"):
        return str(spec["title"])
    return fallback


def _validate_value(spec: dict[str, Any], value: Any, title: str) -> Any:
    allowed = spec.get("type")
    types = [allowed] if isinstance(allowed, str) else list(allowed or [])
    if value is None:
        if "null" in types or allowed is None:
            return None
        raise ValueError(f"{title}不能为空")
    if "integer" in types and "number" not in types:
        value = _as_int(value, title)
    elif "number" in types:
        value = _as_number(value, title)
    elif "boolean" in types:
        if not isinstance(value, bool):
            raise ValueError(f"{title}必须是布尔值")
    elif "array" in types:
        value = _as_array(spec, value, title)
    elif "string" in types:
        value = _as_string(spec, value, title)
    else:
        raise ValueError(f"{title}类型不支持")

    enum = spec.get("enum")
    if isinstance(enum, list) and value not in enum:
        raise ValueError(f"{title}不合法")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in spec and value < spec["minimum"]:
            raise ValueError(f"{title}不能小于 {spec['minimum']}")
        if "maximum" in spec and value > spec["maximum"]:
            raise ValueError(f"{title}不能大于 {spec['maximum']}")
    return value


def _as_string(spec: dict[str, Any], value: Any, title: str) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bool) or isinstance(value, (int, float)):
        raise ValueError(f"{title}必须是字符串")
    else:
        text = str(value)
    if spec.get("x-widget") == "time" and len(text) >= 5:
        text = text[:5]
    if spec.get("minLength") and len(text) < int(spec["minLength"]):
        raise ValueError(f"{title}不能为空")
    pattern = spec.get("pattern")
    if pattern and not re.match(pattern, text):
        raise ValueError(f"{title}格式不正确")
    return text


def _as_number(value: Any, title: str) -> float:
    if isinstance(value, bool) or isinstance(value, str) and value.strip() == "":
        raise ValueError(f"{title}必须是数字")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{title}必须是数字") from exc
    if not math.isfinite(number):
        raise ValueError(f"{title}必须是数字")
    return number


def _as_int(value: Any, title: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{title}必须是整数")
    try:
        if isinstance(value, float):
            if not math.isfinite(value) or value != int(value):
                raise ValueError(f"{title}必须是整数")
            return int(value)
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{title}必须是整数") from exc


def _as_array(spec: dict[str, Any], value: Any, title: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{title}必须是数组")
    items_spec = spec.get("items")
    out: list[Any] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(items_spec, dict):
            item = _validate_value(items_spec, item, title)
        text = str(item)
        if spec.get("uniqueItems") and text in seen:
            continue
        seen.add(text)
        out.append(item)
    min_items = spec.get("minItems")
    if min_items is not None and len(out) < int(min_items):
        raise ValueError(f"{title}列表不能为空")
    max_items = spec.get("maxItems")
    if max_items is not None and len(out) > int(max_items):
        raise ValueError(f"{title}数量过多")
    return out
