import os

import requests

from euroclaw.tracing import get_tracer

tracer = get_tracer(__name__)


class ExternalServicePlugin:
    def __init__(self, target_url: str):
        self.target_url = target_url
        self.api_key = os.getenv("EXTERNAL_WEBHOOK_API_KEY")

    def trigger_service(self, payload: dict) -> str:
        with tracer.start_as_current_span("external_api_trigger") as span:
            span.set_attribute("http.url", self.target_url)
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            try:
                response = requests.post(
                    self.target_url, json=payload, headers=headers, timeout=10
                )
                response.raise_for_status()
                return f"SUCCESS: External service triggered. Status: {response.status_code}"
            except requests.exceptions.RequestException as exc:
                from opentelemetry import trace

                span.set_status(trace.StatusCode.ERROR, description=str(exc))
                return f"ERROR: Failed to reach external service. Reason: {exc}"
