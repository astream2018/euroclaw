import os
import logging
import json
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from starlette.responses import JSONResponse

from src.config import validate_settings, get_settings
from src.orchestrator import process_inbound_message, r
from src.security import get_current_user
from plugins.whatsapp import WhatsAppPlugin
from plugins.telegram import TelegramPlugin
from plugins.slack import SlackPlugin
from plugins.teams import TeamsPlugin

logger = logging.getLogger("euroclaw.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
)
settings = get_settings()
rate_limit_store: dict[str, tuple[int, float]] = {}
hitl_store: dict[str, dict] = {}


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = getattr(record, "request_id", "") or "-"
        record.request_id = request_id
        return True


logging.getLogger().addFilter(ContextFilter())

# =====================================================================
# CRUCIAAL: Initialiseer de plugins in de globale scope (Boven de functies)
# =====================================================================
whatsapp_plugin = WhatsAppPlugin()
telegram_plugin = TelegramPlugin()
slack_plugin = SlackPlugin()
teams_plugin = TeamsPlugin()


# =====================================================================
# Lifespan / Startup Logica
# =====================================================================
@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Startup Logic: Verbind alle enterprise messaging plugins
    whatsapp_plugin.connect()
    telegram_plugin.connect()
    slack_plugin.connect()
    teams_plugin.connect()
    logger.info(
        "EuroClaw Orchestration Core fully initialized via modern Lifespan pipeline."
    )

    yield  # De applicatie draait terwijl deze hier gepauzeerd is

    # Shutdown Logic: Wordt uitgevoerd als je de server stopt (Ctrl+C)
    logger.info("EuroClaw Orchestration Core gracefully shutting down.")


# Initialiseer FastAPI met de lifespan manager
app = FastAPI(
    title="EuroClaw Sovereign Orchestration Engine API",
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("LOCAL_UI_URL", "http://localhost:3000").strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description="Sovereign orchestration API with enterprise authentication and auditability.",
        routes=app.routes,
    )
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "BearerAuth"
    ] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = None
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response
    finally:
        logger.info(
            "request completed",
            extra={"request_id": request_id},
        )


@app.middleware("http")
async def enforce_rate_limit(request: Request, call_next):
    if request.url.path.startswith("/healthz") or request.url.path in {
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
    }:
        return await call_next(request)

    limit = settings.rate_limit_requests
    window_seconds = settings.rate_limit_window_seconds
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate-limit:{client_ip}"
    now = time.time()
    current = rate_limit_store.get(key)

    if current is not None and current[1] <= now:
        rate_limit_store.pop(key, None)
        current = None

    if current is None:
        rate_limit_store[key] = (1, now + window_seconds)
    else:
        current_count = current[0]
        if current_count >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )
        rate_limit_store[key] = (current_count + 1, current[1])

    return await call_next(request)


@app.get("/healthz/liveness")
def liveness() -> dict:
    return {"status": "ok"}


@app.get("/healthz/readiness")
def readiness() -> dict:
    try:
        validate_settings()
        return {"status": "ok"}
    except ValueError:
        return {"status": "ok", "detail": "Configuration defaults are active"}


class ApprovalDecision(BaseModel):
    task_id: str
    approved: bool


def _get_hitl_payload(task_id: str) -> dict | None:
    redis_key = f"hitl:{task_id}"
    try:
        raw_data = r.get(redis_key)
    except Exception as exc:
        logger.warning(
            "Redis unavailable for HITL state; using in-memory fallback: %s", exc
        )
        return hitl_store.get(redis_key)

    if not raw_data:
        return None

    if isinstance(raw_data, str):
        return json.loads(raw_data)
    return raw_data


def _set_hitl_payload(task_id: str, payload: dict, ttl_seconds: int = 300) -> None:
    redis_key = f"hitl:{task_id}"
    try:
        r.set(redis_key, json.dumps(payload), ex=ttl_seconds)
    except Exception as exc:
        logger.warning(
            "Redis unavailable for HITL persistence; using in-memory fallback: %s", exc
        )
        hitl_store[redis_key] = payload


# =====================================================================
# API & Webhook Endpoints
# =====================================================================


@app.post("/api/v1/orchestrate")
async def secure_orchestration_endpoint(
    request: Request, current_user: dict = Depends(get_current_user)
):
    """Secure OIDC endpoint for API-driven enterprise workflows."""
    payload = await request.json()
    logger.info(
        "orchestration request received",
        extra={"request_id": getattr(request.state, "request_id", "-")},
    )
    payload["user_id"] = current_user["user_id"]
    payload["roles"] = current_user["roles"]

    response = process_inbound_message(payload)
    return {"status": "processed", "result": response}


@app.post("/api/v1/hitl/callback")
def handle_hitl_decision(decision: ApprovalDecision):
    data = _get_hitl_payload(decision.task_id)

    if not data:
        data = {
            "task_id": decision.task_id,
            "status": "APPROVED" if decision.approved else "DENIED",
            "approved": decision.approved,
        }
    else:
        data["status"] = "APPROVED" if decision.approved else "DENIED"
        data["approved"] = decision.approved

    _set_hitl_payload(decision.task_id, data)
    return {
        "status": "success",
        "message": f"Task {decision.task_id} updated to {data['status']}",
    }


@app.post("/webhook/slack")
async def handle_slack_webhook(request: Request):
    payload = await request.json()
    standardized_msg = slack_plugin.receive_message(payload)

    if standardized_msg and standardized_msg.get("type") == "url_verification":
        return {"challenge": standardized_msg["challenge"]}

    if standardized_msg:
        response = process_inbound_message(standardized_msg)
        slack_plugin.send_message(standardized_msg["user_id"], response)
        return {"status": "processed"}
    return {"status": "ignored"}


@app.post("/webhook/whatsapp")
async def handle_whatsapp_webhook(request: Request):
    payload = await request.json()
    standardized_msg = whatsapp_plugin.receive_message(payload)
    if standardized_msg:
        response = process_inbound_message(standardized_msg)
        whatsapp_plugin.send_message(standardized_msg["user_id"], response)
        return {"status": "processed"}
    return {"status": "ignored"}


@app.post("/webhook/telegram")
async def handle_telegram_webhook(request: Request):
    payload = await request.json()
    standardized_msg = telegram_plugin.receive_message(payload)
    if standardized_msg:
        response = process_inbound_message(standardized_msg)
        telegram_plugin.send_message(standardized_msg["user_id"], response)
        return {"status": "processed"}
    return {"status": "ignored"}


@app.post("/api/messages")
async def handle_teams_webhook(request: Request):
    """Web endpoint capturing incoming event telemetry streams from MS Teams."""
    payload = await request.json()
    standardized_msg = teams_plugin.receive_message(payload)

    if standardized_msg:
        response = process_inbound_message(standardized_msg)
        teams_plugin.send_message(standardized_msg["user_id"], response)
        return {"status": "processed"}

    return {"status": "ignored"}
