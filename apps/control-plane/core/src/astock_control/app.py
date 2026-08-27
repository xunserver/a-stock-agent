from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from astock_control.adapters.analyze import AnalyzeRunner
from astock_control.adapters.ingest import IngestRunner
from astock_control.adapters.pool import PoolRunner
from astock_control.adapters.stock import StockRunner
from astock_control.config import SettingsRunner
from astock_control.engine import DispatchRunner, Engine
from astock_control.protocol import ProtocolError
from astock_control.queries import handle_query


def create_app(engine: Engine | None = None) -> FastAPI:
    supplied = engine

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        eng = supplied if supplied is not None else Engine(
            DispatchRunner(
                {
                    "quotes.sync": IngestRunner(),
                    "analyze.run": AnalyzeRunner(),
                    "stock.add": StockRunner(),
                    "stock.remove": StockRunner(),
                    "pool.add": PoolRunner(),
                    "pool.set": IngestRunner(),
                    "pool.remove": PoolRunner(),
                    "pool.create": PoolRunner(),
                    "pool.delete": PoolRunner(),
                    "settings.update": SettingsRunner(),
                }
            ),
            handle_query,
        )
        eng.start()
        app.state.engine = eng
        try:
            yield
        finally:
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

    @app.exception_handler(ProtocolError)
    async def protocol_error(_request: Request, exc: ProtocolError) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=400)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "astock-control"}

    @app.post("/api/commands")
    def post_command(body: dict[str, Any], request: Request) -> dict[str, Any]:
        job = _engine(request).submit(body)
        return job.to_dict()

    @app.post("/api/queries")
    def post_query(body: dict[str, Any], request: Request) -> dict[str, Any]:
        try:
            return _engine(request).query(body)
        except ProtocolError:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/jobs")
    def list_jobs(request: Request) -> dict[str, Any]:
        jobs = _engine(request).list_jobs()
        return {"jobs": [job.to_dict(include_log=False) for job in jobs]}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, request: Request) -> dict[str, Any]:
        job = _engine(request).get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"找不到任务: {job_id}")
        return job.to_dict()

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str, request: Request) -> StreamingResponse:
        engine = _engine(request)
        if engine.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail=f"找不到任务: {job_id}")

        async def generate() -> AsyncIterator[str]:
            seen = 0
            while True:
                job = await asyncio.to_thread(engine.wait_for_change, job_id, seen)
                if job is None:
                    yield _sse({"stream": "status", "message": "missing"})
                    return
                for line in job.log[seen:]:
                    yield _sse({"stream": "log", "message": line})
                seen = len(job.log)
                if job.status in {"succeeded", "failed"}:
                    yield _sse(
                        {
                            "stream": "status",
                            "message": job.status,
                            "data": job.to_dict(include_log=False),
                        }
                    )
                    return

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _engine(request: Request) -> Engine:
    return request.app.state.engine


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


app = create_app()
