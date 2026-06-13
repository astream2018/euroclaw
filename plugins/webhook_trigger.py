import os
import requests
import opentelemetry.trace as trace


tracer = trace.get_tracer(__name__)


class ExternalServicePlugin:
    def __init__(self, target_url: str):
        self.target_url = target_url
        # Securely load the API key from the environment
        self.api_key = os.getenv("EXTERNAL_WEBHOOK_API_KEY")

    def trigger_service(self, payload: dict) -> str:
        with tracer.start_as_current_span("external_api_trigger") as span:
            span.set_attribute("http.url", self.target_url)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            }

            try:
                response = requests.post(
                    self.target_url,
                    json=payload,
                    headers=headers,  # Inject the secure headers here
                    timeout=10,
                )
                response.raise_for_status()
                return f"SUCCESS: External service triggered. Status: {response.status_code}"

            except requests.exceptions.RequestException as e:
                span.set_status(trace.StatusCode.ERROR, description=str(e))
                return f"ERROR: Failed to reach external service. Reason: {e}"
