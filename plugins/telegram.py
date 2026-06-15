import os
import logging
import requests
from plugins.base import MessagingPlugin

logger = logging.getLogger("euroclaw.plugins.telegram")


class TelegramPlugin(MessagingPlugin):
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def connect(self):
        pass

    def receive_message(self, raw_webhook_data: dict) -> dict:
        try:
            message = raw_webhook_data["message"]
            return {
                "source": "telegram",
                "user_id": str(message["chat"]["id"]),
                "text": message["text"],
            }
        except KeyError:
            return None

    def send_message(self, user_id: str, text: str):
        try:
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={"chat_id": user_id, "text": text},
                timeout=10,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"[TelegramPlugin] Failed to send message to {user_id}: {e}")
