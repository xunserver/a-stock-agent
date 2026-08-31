from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from astock_core.automation import AutomationStore

from astock_control.adapters.analyze import AnalyzeRunner
from astock_control.adapters.ingest import IngestRunner
from astock_control.adapters.pool import PoolRunner
from astock_control.adapters.qlib import QlibRunner
from astock_control.adapters.stock import StockRunner
from astock_control.automation_api import router as automation_router
from astock_control.automations import AutomationManager
from astock_control.config import SettingsRunner
from astock_control.engine import JobService
from astock_control.feature_api import router as feature_router
from astock_control.job_api import router as job_router
from astock_control.protocol import ProtocolError
from astock_control.scheduler import Scheduler
from astock_control.task_registry import TaskDefinition, TaskRegistry


def create_app(
    engine: JobService | None = None,
    automation_store: AutomationStore | None = None,
) -> FastAPI:
    supplied = engine

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = automation_store or AutomationStore()
        eng = supplied or JobService(_task_registry(), repository=store)
        eng.start()
        app.state.engine = eng
        manager = AutomationManager(store, eng)
        manager.seed_legacy_quotes()
        app.state.automation_manager = manager
        scheduler = None if supplied is not None else Scheduler(eng, store)
        if scheduler is not None:
            scheduler.start()
        app.state.scheduler = scheduler
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.stop()
            eng.stop()

    app = FastAPI(title="astock-control", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
            "null",
        ],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(automation_router)
    app.include_router(feature_router)
    app.include_router(job_router)

    @app.exception_handler(ProtocolError)
    async def protocol_error(_request: Request, exc: ProtocolError) -> JSONResponse:
        return _error_response("protocol_error", str(exc), status_code=400)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return _error_response(f"http_{exc.status_code}", detail, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        message = str(first.get("msg") or "请求参数不合法")
        return _error_response("validation_error", message, status_code=422)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "astock-control"}

    return app


def _task_registry() -> TaskRegistry:
    ingest = IngestRunner()
    qlib = QlibRunner()
    pool = PoolRunner()
    stock = StockRunner()
    settings = SettingsRunner()
    definitions = (
        *(
            TaskDefinition(task_type, ingest)
            for task_type in (
                "quotes.sync",
                "boards.sync",
                "stock.sync",
                "pool.set",
            )
        ),
        TaskDefinition("analyze.run", AnalyzeRunner()),
        *(
            TaskDefinition(task_type, qlib)
            for task_type in ("qlib.run", "qlib.dump", "qlib.workflow.update")
        ),
        *(
            TaskDefinition(task_type, stock)
            for task_type in ("stock.add", "stock.remove")
        ),
        *(
            TaskDefinition(task_type, pool)
            for task_type in (
                "pool.add",
                "pool.remove",
                "pool.reorder",
                "pool.create",
                "pool.delete",
            )
        ),
        TaskDefinition("settings.update", settings),
    )
    return TaskRegistry(definitions)


def _error_response(code: str, message: str, *, status_code: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message}},
        status_code=status_code,
    )


app = create_app()
