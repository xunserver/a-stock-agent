from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from astock_control.protocol import Runner


@dataclass(frozen=True)
class TaskDefinition:
    """A stable task type and the adapter that executes it."""

    type: str
    runner: Runner


class TaskRegistry:
    """Typed task lookup with duplicate and missing-registration checks."""

    def __init__(self, definitions: Iterable[TaskDefinition]) -> None:
        self._runners: dict[str, Runner] = {}
        for definition in definitions:
            task_type = definition.type.strip()
            if not task_type:
                raise ValueError("任务类型不能为空")
            if task_type in self._runners:
                raise ValueError(f"任务类型重复注册: {task_type}")
            self._runners[task_type] = definition.runner

    @property
    def task_types(self) -> frozenset[str]:
        return frozenset(self._runners)

    def run(
        self,
        command: dict[str, Any],
        on_log: Callable[[str], None],
        *,
        timeout: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        task_type = str(command.get("type") or "")
        runner = self._runners.get(task_type)
        if runner is None:
            raise ValueError(f"没有执行器: {task_type}")
        return runner.run(
            command,
            on_log,
            timeout=timeout,
            cancel_event=cancel_event,
        )
