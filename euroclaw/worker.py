"""Distributed execution worker.

Boot on any node connected to the shared Redis broker::

    celery -A euroclaw.worker celery_app worker --loglevel=info --concurrency=4

Each worker runs the identical RBAC + HITL + sandbox execution path as local
mode, so security guarantees do not weaken when scaling out.
"""

import logging

from celery import Celery

from euroclaw.orchestrator import execute_agent_tool
from euroclaw.settings import current_settings

logger = logging.getLogger("euroclaw.worker")

_settings = current_settings()
celery_app = Celery(
    "euroclaw_workers",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
)


@celery_app.task(name="execute_remote_tool", bind=True)
def execute_remote_tool(
    self, user_id: str, tool_name: str, arguments: str, roles=None
) -> str:
    logger.info("[WORKER] picked up task %s: %s", self.request.id, tool_name)
    result = execute_agent_tool(
        user_id=user_id, tool_name=tool_name, arguments=arguments, roles=roles or []
    )
    logger.info("[WORKER] completed task %s", self.request.id)
    return result
