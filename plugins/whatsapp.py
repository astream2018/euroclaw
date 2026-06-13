import os
import requests
from plugins.base import MessagingPlugin


class WhatsAppPlugin(MessagingPlugin):
    def __init__(self):
        self.api_token = os.getenv("WHATSAPP_API_TOKEN")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_ID")
        self.api_url = (
            f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
        )
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def connect(self):
        pass

    def receive_message(self, raw_webhook_data: dict) -> dict:
        try:
            message = raw_webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]
            return {
                "source": "whatsapp",
                "user_id": message["from"],
                "text": message["text"]["body"],
            }
        except (KeyError, IndexError):
            return None

    def send_message(self, user_id: str, text: str):
        requests.post(
            self.api_url,
            headers=self.headers,
            json={
                "messaging_product": "whatsapp",
                "to": user_id,
                "text": {"body": text},
            },
            timeout=10,
        )
