from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from astock_control.automations import AutomationManager

router = APIRouter(prefix="/api/automations", tags=["automations"])


def _manager(request: Request) -> AutomationManager:
    return request.app.state.automation_manager


@router.get("/catalog")
def automation_catalog(request: Request) -> dict[str, Any]:
    return _manager(request).catalog()


@router.get("")
def list_automations(
    request: Request,
    include_archived: bool = False,
) -> dict[str, Any]:
    items = _manager(request).list(include_archived=include_archived)
    return {"automations": items, "count": len(items)}


@router.post("", status_code=201)
def create_automation(body: dict[str, Any], request: Request) -> dict[str, Any]:
    return _manager(request).create(body)


@router.get("/{automation_id}")
def get_automation(automation_id: str, request: Request) -> dict[str, Any]:
    item = _manager(request).get(automation_id, include_archived=True)
    if item is None:
        raise HTTPException(status_code=404, detail=f"找不到自动任务: {automation_id}")
    return item


@router.patch("/{automation_id}")
def update_automation(
    automation_id: str,
    body: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    item = _manager(request).update(automation_id, body)
    if item is None:
        raise HTTPException(status_code=404, detail=f"找不到自动任务: {automation_id}")
    return item


@router.delete("/{automation_id}")
def archive_automation(automation_id: str, request: Request) -> dict[str, Any]:
    item = _manager(request).archive(automation_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"找不到自动任务: {automation_id}")
    return item


@router.post("/{automation_id}/run")
def run_automation(automation_id: str, request: Request) -> dict[str, Any]:
    job = _manager(request).run_now(automation_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"找不到自动任务: {automation_id}")
    return job.to_dict()


@router.get("/{automation_id}/runs")
def list_automation_runs(
    automation_id: str,
    request: Request,
    date: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    manager = _manager(request)
    if manager.get(automation_id, include_archived=True) is None:
        raise HTTPException(status_code=404, detail=f"找不到自动任务: {automation_id}")
    jobs = manager.store.list_jobs(
        automation_id=automation_id,
        date=date,
        limit=limit,
        offset=offset,
    )
    return {
        "jobs": jobs,
        "count": manager.store.count_jobs(automation_id=automation_id, date=date),
        "limit": limit,
        "offset": offset,
    }
