import os
import logging
import requests
from plugins.base import MessagingPlugin

logger = logging.getLogger("euroclaw.plugin.slack")

class SlackPlugin(MessagingPlugin):
    def __init__(self):
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.api_url = "https://slack.com/api/chat.postMessage"
        self.headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def connect(self):
        logger.info("Slack Enterprise Integration initialized.")

    def receive_message(self, raw_webhook_data: dict) -> dict:
        try:
            if "challenge" in raw_webhook_data:
                return {"type": "url_verification", "challenge": raw_webhook_data["challenge"]}

            event = raw_webhook_data.get("event", {})
            # Negeer berichten van bots om eindeloze loops te voorkomen
            if event.get("type") == "message" and not event.get("bot_id"):
                return {
                    "source": "slack",
                    "user_id": event.get("channel"), 
                    "text": event.get("text")
                }
            return None
        except Exception as e:
            logger.error(f"Failed to parse Slack payload: {e}")
            return None

    def send_message(self, user_id: str, text: str):
        payload = {"channel": user_id, "text": text}
        response = requests.post(self.api_url, headers=self.headers, json=payload)
        response.raise_for_status()