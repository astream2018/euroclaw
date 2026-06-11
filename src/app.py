import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from pydantic import BaseModel

from src.orchestrator import process_inbound_message, r
from src.security import get_current_user
from plugins.whatsapp import WhatsAppPlugin
from plugins.telegram import TelegramPlugin
from plugins.slack import SlackPlugin
from plugins.teams import TeamsPlugin

logger = logging.getLogger("euroclaw.api")

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
    logger.info("EuroClaw Orchestration Core fully initialized via modern Lifespan pipeline.")
    
    yield  # De applicatie draait terwijl deze hier gepauzeerd is
    
    # Shutdown Logic: Wordt uitgevoerd als je de server stopt (Ctrl+C)
    logger.info("EuroClaw Orchestration Core gracefully shutting down.")

# Initialiseer FastAPI met de lifespan manager
app = FastAPI(
    title="EuroClaw Sovereign Orchestration Engine API",
    lifespan=lifespan
)

class ApprovalDecision(BaseModel):
    task_id: str
    approved: bool

# =====================================================================
# API & Webhook Endpoints
# =====================================================================

@app.post("/api/v1/orchestrate")
async def secure_orchestration_endpoint(request: Request, current_user: dict = Depends(get_current_user)):
    """Secure OIDC endpoint for API-driven enterprise workflows."""
    payload = await request.json()
    payload["user_id"] = current_user["user_id"]
    payload["roles"] = current_user["roles"]
    
    response = process_inbound_message(payload)
    return {"status": "processed", "result": response}

@app.post("/api/v1/hitl/callback")
def handle_hitl_decision(decision: ApprovalDecision):
    redis_key = f"hitl:{decision.task_id}"
    raw_data = r.get(redis_key)
    
    if not raw_data: 
        raise HTTPException(status_code=404, detail="Task ID not found or expired.")
        
    data = json.loads(raw_data)
    data["status"] = "APPROVED" if decision.approved else "DENIED"
    r.set(redis_key, json.dumps(data), ex=300) 
    return {"status": "success", "message": f"Task {decision.task_id} updated to {data['status']}"}

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