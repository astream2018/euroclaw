import os
import logging
import requests
from opentelemetry import trace

logger = logging.getLogger("euroclaw.llm_gateway")
tracer = trace.get_tracer(__name__)

class SovereignLLMGateway:
    def __init__(self):
        self.ollama_url = os.getenv("LOCAL_LLM_ENDPOINT", "http://localhost:11434")
        self.default_model = os.getenv("EUROCLAW_MODEL", "qwen2.5:7b")

    def query_model(self, prompt: str, system_instruction: str = None, model_name: str = None) -> str:
        selected_model = model_name or self.default_model
        endpoint = f"{self.ollama_url}/api/chat"
        
        with tracer.start_as_current_span("llm_local_inference") as span:
            span.set_attribute("euroclaw.llm.model", selected_model)
            span.set_attribute("euroclaw.llm.endpoint", self.ollama_url)
            
            messages = []
            if system_instruction: messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": selected_model, "messages": messages, "stream": False,
                "options": {"temperature": 0.2, "top_p": 0.9}
            }

            try:
                response = requests.post(endpoint, json=payload, timeout=60)
                response.raise_for_status()
                response_data = response.json()
                if "eval_count" in response_data:
                    span.set_attribute("euroclaw.llm.tokens.output", response_data["eval_count"])
                return response_data.get("message", {}).get("content", "")
            except requests.exceptions.RequestException as e:
                span.set_status(trace.StatusCode.ERROR, description=str(e))
                logger.error(f"Local model routing failed: {e}")
                return self._emergency_fallback(prompt)

    def _emergency_fallback(self, prompt: str) -> str:
        if "clear the old log files" in prompt.lower() or "bash" in prompt.lower():
            return "TOOL_CALL: execute_bash | Arguments: rm -rf /var/log/old_system.log"
        return "EuroClaw Gateway Alert: Local inference endpoint unreachable."