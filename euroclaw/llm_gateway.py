"""Sovereign LLM gateway.

Routes reasoning to a local, self-hosted model (Ollama-compatible ``/api/chat``)
so no prompt data leaves the sovereign boundary. On failure it FAILS CLOSED with
an explicit error — it never fabricates a tool call or an action.
"""

import logging

import requests

from euroclaw.settings import current_settings
from euroclaw.tracing import get_tracer

logger = logging.getLogger("euroclaw.llm_gateway")
tracer = get_tracer(__name__)


class LLMUnavailableError(RuntimeError):
    """Raised when the sovereign inference endpoint cannot be reached."""


class SovereignLLMGateway:
    def __init__(self, endpoint: str | None = None, model: str | None = None):
        settings = current_settings()
        self.ollama_url = (endpoint or settings.llm_endpoint).rstrip("/")
        self.default_model = model or settings.llm_model

    def query_model(
        self,
        prompt: str,
        system_instruction: str | None = None,
        model_name: str | None = None,
        timeout: int = 60,
    ) -> str:
        selected_model = model_name or self.default_model
        endpoint = f"{self.ollama_url}/api/chat"

        with tracer.start_as_current_span("llm_local_inference") as span:
            span.set_attribute("euroclaw.llm.model", selected_model)
            span.set_attribute("euroclaw.llm.endpoint", self.ollama_url)

            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": selected_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2, "top_p": 0.9},
            }

            try:
                response = requests.post(endpoint, json=payload, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                if "eval_count" in data:
                    span.set_attribute("euroclaw.llm.tokens.output", data["eval_count"])
                return data.get("message", {}).get("content", "")
            except requests.exceptions.RequestException as exc:
                from opentelemetry import trace as _trace

                span.set_status(_trace.StatusCode.ERROR, description=str(exc))
                logger.error("Local model routing failed: %s", exc)
                # FAIL CLOSED. Never fabricate a command or tool call on failure.
                raise LLMUnavailableError(
                    "Sovereign inference endpoint unreachable at "
                    f"{self.ollama_url}. Refusing to fabricate a response."
                ) from exc
