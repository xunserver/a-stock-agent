from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from astock_control.engine import JobService
from astock_control.protocol import TERMINAL_JOB_STATUSES


class JobEventStream:
    """Translate durable job changes into the single SSE event protocol."""

    def __init__(self, service: JobService) -> None:
        self.service = service

    async def events(self, job_id: str) -> AsyncIterator[str]:
        seen = 0
        while True:
            job = await asyncio.to_thread(
                self.service.wait_for_change,
                job_id,
                seen,
            )
            if job is None:
                yield encode_sse({"stream": "status", "message": "missing"})
                return
            for line in job.log[seen:]:
                yield encode_sse({"stream": "log", "message": line})
            seen = len(job.log)
            if job.status in TERMINAL_JOB_STATUSES:
                yield encode_sse(
                    {
                        "stream": "status",
                        "message": job.status,
                        "data": job.to_dict(include_log=False),
                    }
                )
                return


def encode_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
