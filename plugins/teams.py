import os
import logging
import requests
from plugins.base import MessagingPlugin

logger = logging.getLogger("euroclaw.plugin.teams")

class TeamsPlugin(MessagingPlugin):
    def __init__(self):
        self.app_id = os.getenv("TEAMS_APP_ID")
        self.app_password = os.getenv("TEAMS_APP_PASSWORD")

    def connect(self):
        logger.info("Microsoft Teams Enterprise Integration initialized.")

    def _get_access_token(self) -> str:
        """Retrieves the OAuth2 bearer token required to reply to Teams."""
        url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.app_id,
            "client_secret": self.app_password,
            "scope": "https://api.botframework.com/.default"
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()["access_token"]

    def receive_message(self, raw_webhook_data: dict) -> dict:
        """Parses the incoming Bot Framework Activity payload."""
        try:
            # We only process actual user messages, ignoring typing indicators or status updates
            if raw_webhook_data.get("type") == "message":
                convo_id = raw_webhook_data["conversation"]["id"]
                service_url = raw_webhook_data["serviceUrl"]
                
                # We combine the conversation ID and service URL so send_message knows where to route the reply
                routing_key = f"{convo_id}||{service_url}"
                
                # Clean up the text (Teams often includes HTML tags or @mention artifacts)
                text = raw_webhook_data.get("text", "").strip()
                
                return {
                    "source": "teams",
                    "user_id": routing_key,
                    "text": text
                }
            return None
        except KeyError as e:
            logger.error(f"Failed to parse MS Teams payload: {e}")
            return None

    def send_message(self, user_id: str, text: str):
        """Dispatches the message back to the correct Microsoft Azure regional endpoint."""
        try:
            convo_id, service_url = user_id.split("||")
            token = self._get_access_token()
            
            url = f"{service_url.rstrip('/')}/v3/conversations/{convo_id}/activities"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {
                "type": "message",
                "text": text
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info("Successfully dispatched message trace back to MS Teams.")
            
        except Exception as e:
            logger.error(f"Failed to transmit data metrics to MS Teams: {e}")