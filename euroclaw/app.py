"""EuroClaw HTTP API (FastAPI).

Design notes vs. the previous version:

* The orchestrate endpoint is **non-blocking**: it creates a run, schedules
  execution in a worker thread, and returns a ``run_id`` immediately. Clients
  poll ``/api/v1/runs/{id}`` or subscribe to the SSE stream. A ``?wait=true``
  convenience mode is available for scripts/tests.
* Rate-limit and HITL state live in Redis (``euroclaw.state``), so limits and
  approvals are correct across replicas.
* Readiness can actually FAIL (503) so Kubernetes rollouts are gated.
* CORS origins come from configuration, not a wildcard.
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, StreamingResponse

from euroclaw import state
from euroclaw.llm_gateway import LLMUnavailableError
from euroclaw.orchestrator import process_inbound_message
from euroclaw.security import get_current_user
from euroclaw.settings import current_settings, get_settings, validate_settings
from euroclaw.tracing import configure_tracing
from euroclaw.plugins.slack import SlackPlugin
from euroclaw.plugins.teams import TeamsPlugin
from euroclaw.plugins.telegram import TelegramPlugin
from euroclaw.plugins.whatsapp import WhatsAppPlugin

logger = logging.getLogger("euroclaw.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", "") or "-"
        return True


logging.getLogger().addFilter(ContextFilter())

settings = current_settings()

whatsapp_plugin = WhatsAppPlugin()
telegram_plugin = TelegramPlugin()
slack_plugin = SlackPlugin()
teams_plugin = TeamsPlugin()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_tracing("euroclaw-api")
    for plugin in (whatsapp_plugin, telegram_plugin, slack_plugin, teams_plugin):
        try:
            plugin.connect()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Plugin connect failed: %s", exc)
    logger.info("EuroClaw Orchestration Core initialized.")
    yield
    logger.info("EuroClaw Orchestration Core shutting down.")


app = FastAPI(
    title="EuroClaw Sovereign Orchestration Engine API",
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description="Sovereign orchestration API with enterprise auth and audit.",
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "BearerAuth"
    ] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

_PUBLIC_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    finally:
        logger.info("request completed", extra={"request_id": request_id})
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.middleware("http")
async def enforce_rate_limit(request: Request, call_next):
    if request.url.path.startswith("/healthz") or request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    s = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    if not state.rate_limit_hit(
        client_ip, s.rate_limit_requests, s.rate_limit_window_seconds
    ):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    return await call_next(request)


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@app.get("/healthz/liveness")
def liveness() -> dict:
    return {"status": "ok"}


@app.get("/healthz/readiness")
def readiness():
    try:
        s = validate_settings()
    except ValueError as exc:
        return JSONResponse(
            status_code=503, content={"status": "error", "detail": str(exc)}
        )
    if s.execution_mode == "distributed" and state.get_client() is None:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "Redis required but unavailable"},
        )
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Orchestration (async run model)
# --------------------------------------------------------------------------- #
def _run_orchestration(run_id: str, payload: dict) -> None:
    state.run_update(run_id, status="running")
    try:
        result = process_inbound_message(payload)
        state.run_update(run_id, status="completed", result=result)
        state.run_append_event(run_id, {"type": "completed"})
    except LLMUnavailableError as exc:
        state.run_update(run_id, status="failed", error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("run %s failed", run_id)
        state.run_update(run_id, status="failed", error=str(exc))


@app.post("/api/v1/orchestrate")
async def orchestrate(
    request: Request,
    background: BackgroundTasks,
    wait: bool = False,
    current_user: dict = Depends(get_current_user),
):
    payload = await request.json()
    payload["user_id"] = current_user["user_id"]
    payload["roles"] = current_user["roles"]

    run_id = uuid.uuid4().hex
    state.run_create(
        run_id,
        {
            "run_id": run_id,
            "status": "queued",
            "user_id": current_user["user_id"],
            "result": None,
        },
    )

    if wait:
        await run_in_threadpool(_run_orchestration, run_id, payload)
        return state.run_get(run_id)

    background.add_task(_run_orchestration, run_id, payload)
    return {"run_id": run_id, "status": "queued"}


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str):
    run = state.run_get(run_id)
    if run is None:
        return JSONResponse(status_code=404, content={"detail": "run not found"})
    return run


@app.get("/api/v1/runs/{run_id}/events")
async def stream_run_events(run_id: str):
    async def event_generator():
        seen = 0
        for _ in range(600):  # ~5 min ceiling at 0.5s poll
            run = state.run_get(run_id)
            if run is None:
                yield f"data: {json.dumps({'error': 'run not found'})}\n\n"
                return
            events = run.get("events", [])
            while seen < len(events):
                yield f"data: {json.dumps(events[seen])}\n\n"
                seen += 1
            if run.get("status") in {"completed", "failed"}:
                yield f"data: {json.dumps({'type': 'final', 'run': run})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class ApprovalDecision(BaseModel):
    task_id: str
    approved: bool


@app.post("/api/v1/hitl/callback")
def handle_hitl_decision(decision: ApprovalDecision):
    data = state.hitl_get(decision.task_id) or {"task_id": decision.task_id}
    data["status"] = "APPROVED" if decision.approved else "DENIED"
    data["approved"] = decision.approved
    state.hitl_set(decision.task_id, data)
    return {
        "status": "success",
        "message": f"Task {decision.task_id} -> {data['status']}",
    }


# --------------------------------------------------------------------------- #
# Messaging webhooks
# --------------------------------------------------------------------------- #
def _handle_webhook(plugin, payload: dict):
    msg = plugin.receive_message(payload)
    if msg and msg.get("type") == "url_verification":
        return {"challenge": msg["challenge"]}
    if msg:
        response = process_inbound_message(msg)
        plugin.send_message(msg["user_id"], response)
        return {"status": "processed"}
    return {"status": "ignored"}


@app.post("/webhook/slack")
async def handle_slack_webhook(request: Request):
    return await run_in_threadpool(_handle_webhook, slack_plugin, await request.json())


@app.post("/webhook/whatsapp")
async def handle_whatsapp_webhook(request: Request):
    return await run_in_threadpool(
        _handle_webhook, whatsapp_plugin, await request.json()
    )


@app.post("/webhook/telegram")
async def handle_telegram_webhook(request: Request):
    return await run_in_threadpool(
        _handle_webhook, telegram_plugin, await request.json()
    )


@app.post("/api/messages")
async def handle_teams_webhook(request: Request):
    return await run_in_threadpool(_handle_webhook, teams_plugin, await request.json())
