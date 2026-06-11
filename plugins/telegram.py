import os
import requests
from plugins.base import MessagingPlugin

class TelegramPlugin(MessagingPlugin):
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def connect(self): pass

    def receive_message(self, raw_webhook_data: dict) -> dict:
        try:
            message = raw_webhook_data["message"]
            return {"source": "telegram", "user_id": str(message["chat"]["id"]), "text": message["text"]}
        except KeyError: return None

    def send_message(self, user_id: str, text: str):
        requests.post(f"{self.api_url}/sendMessage", json={"chat_id": user_id, "text": text})