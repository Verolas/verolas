"""The main poll loop.

The runner:

1. Polls `/v1/bridges/poll`. The cloud claims up to ten queued jobs
   and marks them in_progress.
2. For each job, looks up a tool handler by class_id and invokes it.
3. Posts the result (or the error) back via `/v1/bridges/jobs/{id}/result`.

If no handler is registered for a class_id, the job is failed with a
"tool not supported" message so the admin sees a clear signal that the
bridge needs a newer build.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from verolas_bridge.client import BridgeClient
from verolas_bridge.tools import handler_for

log = structlog.get_logger(__name__)


async def run_forever(client: BridgeClient, poll_interval: float) -> None:
    """Block the calling task indefinitely, polling + dispatching jobs."""
    while True:
        try:
            await _tick(client)
        except Exception as exc:
            log.exception("poll_tick_failed", error=str(exc))
        await asyncio.sleep(poll_interval)


async def _tick(client: BridgeClient) -> None:
    jobs = await client.poll()
    if not jobs:
        log.debug("no_jobs")
        return
    log.info("claimed_jobs", count=len(jobs))
    for job in jobs:
        await _dispatch(client, job)


async def _dispatch(client: BridgeClient, job: dict[str, Any]) -> None:
    job_id = job.get("id")
    class_id = job.get("class_id")
    if not isinstance(job_id, str) or not isinstance(class_id, str):
        log.warning("malformed_job", job=job)
        return

    handler = handler_for(class_id)
    if handler is None:
        log.warning("no_handler", class_id=class_id, job_id=job_id)
        await client.submit_result(
            job_id,
            status="failed",
            error=f"Bridge has no handler for class_id={class_id}",
        )
        return

    log.info("running_job", class_id=class_id, job_id=job_id)
    try:
        result = await handler(job.get("payload") or {})
    except Exception as exc:
        log.exception("tool_failed", class_id=class_id, job_id=job_id)
        await client.submit_result(job_id, status="failed", error=str(exc))
        return

    await client.submit_result(job_id, status="completed", result=result)
    log.info("job_done", class_id=class_id, job_id=job_id)
