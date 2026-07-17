from abc import ABC, abstractmethod


class MessagingPlugin(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def receive_message(self, raw_webhook_data: dict) -> dict:
        pass

    @abstractmethod
    def send_message(self, user_id: str, text: str):
        pass
