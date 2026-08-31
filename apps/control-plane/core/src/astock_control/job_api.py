from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from astock_control.engine import JobService
from astock_control.http_models import JobListResponse, JobResponse, TaskSubmission
from astock_control.job_events import JobEventStream

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _service(request: Request) -> JobService:
    return request.app.state.engine


@router.post("", status_code=202, response_model=JobResponse)
def submit_job(body: TaskSubmission, request: Request) -> dict[str, Any]:
    return _service(request).submit(body.command_payload()).to_dict()


@router.get("", response_model=JobListResponse)
def list_jobs(
    request: Request,
    automation_id: str | None = None,
    date: str | None = None,
    trigger: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    service = _service(request)
    jobs = service.list_jobs(
        automation_id=automation_id,
        date=date,
        trigger=trigger,
        limit=limit,
        offset=offset,
    )
    return {
        "jobs": [job.to_dict(include_log=False) for job in jobs],
        "count": service.repository.count_jobs(
            automation_id=automation_id,
            date=date,
            trigger=trigger,
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, request: Request) -> dict[str, Any]:
    job = _service(request).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"找不到任务: {job_id}")
    return job.to_dict()


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, request: Request) -> dict[str, Any]:
    job = _service(request).cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"找不到任务: {job_id}")
    return job.to_dict()


@router.get("/{job_id}/events")
def job_events(job_id: str, request: Request) -> StreamingResponse:
    service = _service(request)
    if service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail=f"找不到任务: {job_id}")
    return StreamingResponse(
        JobEventStream(service).events(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
