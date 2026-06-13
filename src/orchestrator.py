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

from src.dag_visualizer import AgentDAGTracer
from src.llm_gateway import SovereignLLMGateway
from src.sandbox_firecracker import FirecrackerMicroVM
from plugins.webhook_trigger import ExternalServicePlugin
from plugins.web_search import WebIntelligencePlugin
from plugins.local_files import LocalFileSystemPlugin

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

HIGH_RISK_TOOLS = ["execute_bash", "delete_database", "send_external_email", "request_telegram_approval"]

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
    """Unified routing for local plugins, webhooks, and hardware sandboxing."""
    task_id = str(uuid.uuid4())[:8] 
    
    dag = AgentDAGTracer(task_id=task_id)
    dag.add_step("AgentOrchestrator", "ToolExecutor", f"Requested: {tool_name}")
    
    try:
        # --- 1. WEB INTELLIGENCE PLUGINS ---
        if tool_name == "search_internet":
            dag.add_step("ToolExecutor", "WebPlugin", "Executing DuckDuckGo Search")
            plugin = WebIntelligencePlugin()
            return plugin.search_internet(query=arguments)
            
        elif tool_name == "scrape_website":
            dag.add_step("ToolExecutor", "WebPlugin", "Scraping URL Content")
            plugin = WebIntelligencePlugin()
            return plugin.scrape_website(url=arguments)

        # --- 2. LOCAL RAG / FILE SYSTEM PLUGIN ---
        elif tool_name == "read_file":
            dag.add_step("ToolExecutor", "FileSystemPlugin", "Reading Local File")
            allowed_dirs = os.getenv("ALLOWED_WORKSPACES", "")
            plugin = LocalFileSystemPlugin(allowed_directories_env=allowed_dirs)
            return plugin.read_file(file_path=arguments)

        # --- 3. EXTERNAL WEBHOOKS ---
        elif tool_name == "notify_external_service":
            dag.add_step("ToolExecutor", "WebhookPlugin", "Triggering External API")
            target_url = os.getenv("EXTERNAL_WEBHOOK_URL")
            if not target_url:
                return "ERROR: EXTERNAL_WEBHOOK_URL is not configured in the environment."
            plugin = ExternalServicePlugin(target_url=target_url)
            return plugin.trigger_service(payload={"data": arguments})

        # --- 4. HUMAN-IN-THE-LOOP (HITL) CHECKPOINT ---
        if tool_name in HIGH_RISK_TOOLS:
            dag.add_step("ToolExecutor", "HumanSupervisor", "Triggered HITL Checkpoint")
            
            with tracer.start_as_current_span("hitl_human_checkpoint") as span:
                span.set_attribute("euroclaw.hitl.task_id", task_id)
                span.set_attribute("euroclaw.hitl.tool", tool_name)
                request_human_approval(task_id, user_id, tool_name, arguments)
                
                if not wait_for_approval(task_id):
                    span.set_attribute("euroclaw.hitl.result", "DENIED")
                    dag.add_step("HumanSupervisor", "AgentOrchestrator", "Execution DENIED")
                    return "ERROR: Action rejected by infrastructure supervisor policy rules."
                    
                span.set_attribute("euroclaw.hitl.result", "APPROVED")
                dag.add_step("HumanSupervisor", "ToolExecutor", "Execution APPROVED")

        # --- 5. HARDWARE SANDBOX (Catch-all for executing code/bash) ---
        with tracer.start_as_current_span("sandbox_execution") as span:
            span.set_attribute("euroclaw.sandbox.isolation", "firecracker_microvm")
            span.set_attribute("euroclaw.sandbox.task_id", task_id)
            
            dag.add_step("ToolExecutor", "FirecrackerMicroVM", "Booting Hardware Sandbox")
            vm = FirecrackerMicroVM(task_id=task_id)
            
            try:
                vm.boot()
                result = vm.execute_tool(tool_name, arguments)
                dag.add_step("FirecrackerMicroVM", "AgentOrchestrator", "Tool Execution Success")
                return result
            except Exception as e:
                span.set_status(trace.StatusCode.ERROR, description=str(e))
                dag.add_step("FirecrackerMicroVM", "AgentOrchestrator", "Tool Execution FAILED")
                return f"ERROR: Tool execution failed inside secure boundary. Reason: {e}"
            finally:
                vm.teardown()

    finally:
        # Guarantee the visual DAG is exported regardless of success or failure
        md_file = dag.export_to_markdown()
        logger.info(f"[AUDIT] DAG saved to {md_file}")

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