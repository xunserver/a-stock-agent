from __future__ import annotations

from typing import Any, Protocol


class JobRepository(Protocol):
    """Persistence contract required by the job service and scheduler."""

    def recover_open_jobs(self) -> int: ...

    def record_job(self, job: dict[str, Any]) -> bool: ...

    def update_job(self, job: dict[str, Any]) -> None: ...

    def append_job_log(self, job_id: str, seq: int, line: str) -> None: ...

    def get_job(self, job_id: str) -> dict[str, Any] | None: ...

    def list_jobs(
        self,
        *,
        automation_id: str | None = None,
        date: str | None = None,
        trigger: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]: ...

    def count_jobs(
        self,
        *,
        automation_id: str | None = None,
        date: str | None = None,
        trigger: str | None = None,
    ) -> int: ...
