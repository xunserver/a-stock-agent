from __future__ import annotations

from collections.abc import Callable
from typing import Any

from astock_core.paths import system_db_path
from astock_core.settings import (
    get_section_view,
    load_settings,
    preview_section,
    preview_update,
    public_settings,
    settings_catalog_view,
    settings_view,
    update_section,
    write_settings,
)
from astock_core.settings.view import validate_settings

CONFIG_ENV = "ASTOCK_CONTROL_CONFIG"
API_KEY_CLEAR = "__clear__"
API_KEY_HINT = "••••"

config_path = system_db_path


class SettingsRunner:
    def run(
        self,
        command: dict[str, Any],
        on_log: Callable[[str], None],
        *,
        timeout: float | None = None,
        cancel_event=None,
    ) -> dict[str, Any]:
        del timeout, cancel_event
        if command.get("type") != "settings.update":
            raise ValueError(f"设置执行器不支持命令: {command.get('type')}")
        module = str(command.get("module") or "").strip()
        section = str(command.get("section") or "").strip()
        if module and section:
            on_log(f"写入设置 {module}.{section}")
            written = update_section(module, section, command.get("values") or {})
            on_log(f"已保存 {system_db_path()}")
            return written
        on_log("写入系统设置")
        written = write_settings(command.get("settings") or {})
        on_log(f"已保存 {system_db_path()}")
        return public_settings(written)
