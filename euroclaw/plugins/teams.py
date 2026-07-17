import os
import logging

import requests

from euroclaw.plugins.base import MessagingPlugin

logger = logging.getLogger("euroclaw.plugin.teams")


class TeamsPlugin(MessagingPlugin):
    def __init__(self):
        self.app_id = os.getenv("TEAMS_APP_ID")
        self.app_password = os.getenv("TEAMS_APP_PASSWORD")

    def connect(self):
        logger.info("Microsoft Teams Enterprise Integration initialized.")

    def _get_access_token(self) -> str:
        url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.app_id,
            "client_secret": self.app_password,
            "scope": "https://api.botframework.com/.default",
        }
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        return response.json()["access_token"]

    def receive_message(self, raw_webhook_data: dict) -> dict:
        try:
            if raw_webhook_data.get("type") == "message":
                convo_id = raw_webhook_data["conversation"]["id"]
                service_url = raw_webhook_data["serviceUrl"]
                routing_key = f"{convo_id}||{service_url}"
                text = raw_webhook_data.get("text", "").strip()
                return {"source": "teams", "user_id": routing_key, "text": text}
            return None
        except KeyError as exc:
            logger.error("Failed to parse MS Teams payload: %s", exc)
            return None

    def send_message(self, user_id: str, text: str):
        try:
            convo_id, service_url = user_id.split("||")
            token = self._get_access_token()
            url = f"{service_url.rstrip('/')}/v3/conversations/{convo_id}/activities"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {"type": "message", "text": text}
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Dispatched message back to MS Teams.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to transmit to MS Teams: %s", exc)
