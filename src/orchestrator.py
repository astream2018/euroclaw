import os
import time
import uuid
import json
import logging
import redis
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from src.llm_gateway import SovereignLLMGateway
from src.sandbox_firecracker import FirecrackerMicroVM

logger = logging.getLogger("euroclaw.orchestrator")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
)

r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, decode_responses=True)
gateway = SovereignLLMGateway()

HIGH_RISK_TOOLS = ["execute_bash", "delete_database", "send_external_email"]

def request_human_approval(task_id: str, user_id: str, tool_name: str, arguments: str):
    task_payload = {
        "status": "AWAITING_APPROVAL",
        "user_id": user_id,
        "tool_name": tool_name,
        "arguments": arguments,
        "timestamp": time.time()
    }
    r.set(f"hitl:{task_id}", json.dumps(task_payload), ex=7200) 
    logger.warning(f"[HITL PENDING] Intercepted high-risk execution '{tool_name}' on Task ID: {task_id}.")

def wait_for_approval(task_id: str, timeout: int = 300) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        raw_data = r.get(f"hitl:{task_id}")
        if not raw_data: return False
        data = json.loads(raw_data)
        if data["status"] == "APPROVED": return True
        elif data["status"] == "DENIED": return False
        time.sleep(2) 
    return False

def execute_agent_tool(user_id: str, tool_name: str, arguments: str) -> str:
    task_id = str(uuid.uuid4())
    
    if tool_name in HIGH_RISK_TOOLS:
        with tracer.start_as_current_span("hitl_human_checkpoint") as span:
            span.set_attribute("euroclaw.hitl.task_id", task_id)
            span.set_attribute("euroclaw.hitl.tool", tool_name)
            request_human_approval(task_id, user_id, tool_name, arguments)
            
            if not wait_for_approval(task_id):
                span.set_attribute("euroclaw.hitl.result", "DENIED")
                return "ERROR: Action rejected by infrastructure supervisor policy rules."
            span.set_attribute("euroclaw.hitl.result", "APPROVED")

    with tracer.start_as_current_span("sandbox_execution") as span:
        span.set_attribute("euroclaw.sandbox.isolation", "firecracker_microvm")
        span.set_attribute("euroclaw.sandbox.task_id", task_id)
        
        vm = FirecrackerMicroVM(task_id=task_id)
        try:
            vm.boot()
            return vm.execute_tool(tool_name, arguments)
        except Exception as e:
            span.set_status(trace.StatusCode.ERROR, description=str(e))
            return f"ERROR: Tool execution failed inside secure boundary. Reason: {e}"
        finally:
            vm.teardown()

def process_inbound_message(message_payload: dict) -> str:
    user_id = message_payload.get("user_id", "unknown")
    
    with tracer.start_as_current_span("agent_reasoning_loop") as parent_span:
        parent_span.set_attribute("euroclaw.user_id", user_id)
        parent_span.set_attribute("euroclaw.source", message_payload.get("source"))

        with tracer.start_as_current_span("context_retrieval"):
            pass 
            
        with tracer.start_as_current_span("llm_inference"):
            system_prompt = "You are a secure EuroClaw Linux Automation Agent. Return standard tool calling blocks for required changes."
            response = gateway.query_model(prompt=message_payload["text"], system_instruction=system_prompt)
            
        return response