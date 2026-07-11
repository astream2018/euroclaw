from plugins.base import MessagingPlugin


class DummyPlugin(MessagingPlugin):
    def connect(self):
        return None

    def receive_message(self, raw_webhook_data: dict) -> dict:
        return raw_webhook_data

    def send_message(self, user_id: str, text: str):
        return None


def test_messaging_plugin_contract_is_implementable():
    plugin = DummyPlugin()

    assert plugin.connect() is None
    assert plugin.receive_message({"hello": "world"}) == {"hello": "world"}
    assert plugin.send_message("user", "hi") is None
