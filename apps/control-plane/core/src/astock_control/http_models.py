from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskSubmission(BaseModel):
    """HTTP task DTO; task-specific fields are validated by the registry protocol."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=1)
    background: bool | None = None
    timeout: float | None = Field(default=None, gt=0)

    def command_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class JobSummaryResponse(BaseModel):
    """Stable JSON representation shared by job HTTP endpoints and OpenAPI."""

    id: str
    type: str
    name: str
    status: str
    command: dict[str, Any]
    background: bool
    timeout_seconds: int
    trigger: str
    automation_id: str | None = None
    scheduled_for: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    log_count: int


class JobResponse(JobSummaryResponse):
    log: list[str]


class JobListResponse(BaseModel):
    jobs: list[JobSummaryResponse]
    count: int
    limit: int
    offset: int
