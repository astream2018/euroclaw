"""EuroClaw orchestration core.

Responsibilities:

* Turn an inbound request into a bounded reasoning loop that ACTUALLY executes
  tools (the previous version returned raw text and never dispatched anything).
* Enforce RBAC on every tool call and route high-risk / MCP tools through a
  Human-in-the-Loop checkpoint before execution.
* Execute tools locally (synchronous) or fan out to distributed Celery workers.
* Run untrusted code inside the configured sandbox backend.
* Emit OpenTelemetry spans and append-only audit records for every step.
"""

import logging
import time
import uuid

from celery import Celery
from opentelemetry import trace

from euroclaw import audit, rbac
from euroclaw import state
from euroclaw.dag_visualizer import AgentDAGTracer
from euroclaw.llm_gateway import SovereignLLMGateway
from euroclaw.multi_agent import run_conversation
from euroclaw.sandbox import get_sandbox
from euroclaw.settings import current_settings
from euroclaw.toolcall import parse_tool_calls
from euroclaw.tracing import configure_tracing, get_tracer
from euroclaw.plugins.web_search import WebIntelligencePlugin
from euroclaw.plugins.local_files import LocalFileSystemPlugin
from euroclaw.plugins.webhook_trigger import ExternalServicePlugin
from euroclaw.plugins.mcp_client import ModelContextProtocolPlugin

logger = logging.getLogger("euroclaw.orchestrator")

configure_tracing("euroclaw-orchestrator")
tracer = get_tracer(__name__)

settings = current_settings()
gateway = SovereignLLMGateway()

celery_app = Celery(
    "euroclaw_dispatch",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Tools that reach external systems and must be gated by HITL in addition to RBAC.
_HITL_REQUIRED = rbac.HIGH_RISK_TOOLS | {"query_database_mcp"}


# --------------------------------------------------------------------------- #
# Human-in-the-loop
# --------------------------------------------------------------------------- #
def request_human_approval(
    task_id: str, user_id: str, tool_name: str, arguments: str
) -> None:
    state.hitl_set(
        task_id,
        {
            "status": "AWAITING_APPROVAL",
            "user_id": user_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "timestamp": time.time(),
        },
        ttl_seconds=7200,
    )
    audit.record("hitl.requested", task_id=task_id, user_id=user_id, tool=tool_name)
    logger.warning(
        "[HITL PENDING] '%s' awaiting approval (task %s)", tool_name, task_id
    )


def wait_for_approval(task_id: str, timeout: int | None = None) -> bool:
    """Poll the shared HITL store. Runs off the API event loop (worker/thread)."""
    timeout = timeout or current_settings().hitl_timeout_seconds
    start = time.time()
    while time.time() - start < timeout:
        data = state.hitl_get(task_id)
        if not data:
            return False
        if data.get("status") == "APPROVED":
            return True
        if data.get("status") == "DENIED":
            return False
        time.sleep(2)
    return False


# --------------------------------------------------------------------------- #
# Tool execution
# --------------------------------------------------------------------------- #
def execute_agent_tool(user_id: str, tool_name: str, arguments: str, roles=None) -> str:
    """Execute a single tool with RBAC + HITL + sandbox + audit."""
    task_id = uuid.uuid4().hex[:8]
    dag = AgentDAGTracer(task_id=task_id)
    dag.add_step("AgentOrchestrator", "ToolExecutor", f"Requested: {tool_name}")

    # 1) RBAC — fail closed.
    decision = rbac.check_access(roles, tool_name)
    if not decision.allowed:
        audit.record(
            "rbac.denied",
            task_id=task_id,
            user_id=user_id,
            tool=tool_name,
            reason=decision.reason,
        )
        dag.add_step("ToolExecutor", "AgentOrchestrator", "RBAC DENIED")
        dag.export_to_markdown(current_settings().audit_dir)
        return f"ERROR: Access denied by RBAC policy — {decision.reason}"

    try:
        # 2) HITL for high-risk / external tools.
        if tool_name in _HITL_REQUIRED:
            with tracer.start_as_current_span("hitl_human_checkpoint") as span:
                span.set_attribute("euroclaw.hitl.task_id", task_id)
                span.set_attribute("euroclaw.hitl.tool", tool_name)
                request_human_approval(task_id, user_id, tool_name, arguments)
                dag.add_step("ToolExecutor", "HumanSupervisor", "HITL Checkpoint")
                if not wait_for_approval(task_id):
                    span.set_attribute("euroclaw.hitl.result", "DENIED")
                    audit.record("hitl.denied", task_id=task_id, tool=tool_name)
                    dag.add_step("HumanSupervisor", "AgentOrchestrator", "DENIED")
                    return "ERROR: Action rejected by supervisor policy."
                span.set_attribute("euroclaw.hitl.result", "APPROVED")
                audit.record("hitl.approved", task_id=task_id, tool=tool_name)
                dag.add_step("HumanSupervisor", "ToolExecutor", "APPROVED")

        result = _route_tool(dag, task_id, tool_name, arguments)
        audit.record("tool.executed", task_id=task_id, user_id=user_id, tool=tool_name)
        return result
    finally:
        md = dag.export_to_markdown(current_settings().audit_dir)
        logger.info("[AUDIT] DAG saved to %s", md)


def _route_tool(dag, task_id, tool_name, arguments) -> str:
    s = current_settings()

    if tool_name in {"search_internet"}:
        dag.add_step("ToolExecutor", "WebPlugin", "Web search")
        return WebIntelligencePlugin().search_internet(query=arguments)

    if tool_name in {"scrape_website"}:
        dag.add_step("ToolExecutor", "WebPlugin", "Scrape URL")
        return WebIntelligencePlugin().scrape_website(url=arguments)

    if tool_name == "read_file":
        dag.add_step("ToolExecutor", "FileSystemPlugin", "Read file")
        plugin = LocalFileSystemPlugin(
            allowed_directories_env=",".join(s.allowed_workspaces)
        )
        return plugin.read_file(file_path=arguments)

    if tool_name == "notify_external_service":
        dag.add_step("ToolExecutor", "WebhookPlugin", "Trigger external API")
        import os

        target = os.getenv("EXTERNAL_WEBHOOK_URL")
        if not target:
            return "ERROR: EXTERNAL_WEBHOOK_URL is not configured."
        return ExternalServicePlugin(target_url=target).trigger_service(
            payload={"data": arguments}
        )

    if tool_name == "query_database_mcp":
        import os

        dag.add_step("ToolExecutor", "MCPClientPlugin", "MCP stdio server")
        with tracer.start_as_current_span("mcp_server_execution") as span:
            span.set_attribute("euroclaw.mcp.tool", tool_name)
            plugin = ModelContextProtocolPlugin(
                server_command="npx",
                server_args=[
                    "-y",
                    "@modelcontextprotocol/server-postgres",
                    os.getenv("DATABASE_URL", "postgresql://localhost/mydb"),
                ],
            )
            return plugin.execute_mcp_tool(
                tool_name="query_database", arguments_json=arguments
            )

    # Default: run inside the configured sandbox backend.
    with tracer.start_as_current_span("sandbox_execution") as span:
        sandbox = get_sandbox(s.sandbox_backend, task_id=task_id)
        span.set_attribute("euroclaw.sandbox.isolation", sandbox.isolation_level)
        span.set_attribute("euroclaw.sandbox.task_id", task_id)
        dag.add_step("ToolExecutor", "Sandbox", f"Execute in {sandbox.isolation_level}")
        try:
            with sandbox:
                result = sandbox.execute(tool_name, arguments)
            dag.add_step("Sandbox", "AgentOrchestrator", "Execution complete")
            return result.as_text()
        except Exception as exc:  # noqa: BLE001
            span.set_status(trace.StatusCode.ERROR, description=str(exc))
            dag.add_step("Sandbox", "AgentOrchestrator", "Execution FAILED")
            return f"ERROR: Tool execution failed inside secure boundary: {exc}"


def dispatch_agent_tool(
    user_id: str, tool_name: str, arguments: str, roles=None
) -> str:
    """Route execution locally (sync) or to the distributed worker pool."""
    mode = current_settings().execution_mode
    if mode == "local":
        logger.info("[LOCAL] executing %s", tool_name)
        return execute_agent_tool(user_id, tool_name, arguments, roles)

    logger.info("[DISTRIBUTED] dispatching %s", tool_name)
    async_task = celery_app.send_task(
        "execute_remote_tool", args=[user_id, tool_name, arguments, roles or []]
    )
    try:
        return async_task.get(timeout=current_settings().hitl_timeout_seconds + 60)
    except Exception as exc:  # noqa: BLE001
        logger.error("[DISTRIBUTED] remote execution failed: %s", exc)
        return f"ERROR: Remote worker failed to complete task. Reason: {exc}"


# --------------------------------------------------------------------------- #
# Reasoning loop
# --------------------------------------------------------------------------- #
def _tool_system_prompt(persona: str, roles) -> str:
    tools = rbac.allowed_tools(roles)
    tool_list = ", ".join(tools) if tools else "(none — you may only answer directly)"
    return (
        f"You are a {persona}. You may call tools you are authorized for.\n"
        f"Authorized tools: {tool_list}.\n"
        "To call a tool, emit EXACTLY one line:\n"
        "TOOL_CALL: <tool_name> | Arguments: <arguments>\n"
        "When you have the final answer and need no tool, reply in plain text "
        "with no TOOL_CALL line."
    )


def run_agent_loop(user_id: str, text: str, persona: str, roles) -> str:
    """Bounded reason -> act -> observe loop that really executes tools."""
    system_prompt = _tool_system_prompt(persona, roles)
    max_iters = current_settings().max_tool_iterations
    conversation = text
    final_text = ""

    for iteration in range(max_iters):
        with tracer.start_as_current_span("llm_inference") as span:
            span.set_attribute("euroclaw.loop.iteration", iteration + 1)
            response = gateway.query_model(
                prompt=conversation, system_instruction=system_prompt
            )
        final_text = response
        calls = parse_tool_calls(response)
        if not calls:
            return response

        observations = []
        for call in calls:
            result = dispatch_agent_tool(user_id, call.tool_name, call.arguments, roles)
            observations.append(f"[{call.tool_name}] -> {result}")
        conversation = (
            f"Previous reasoning:\n{response}\n\n"
            f"Tool results:\n" + "\n".join(observations) + "\n\n"
            "Continue. If done, provide the final answer with no TOOL_CALL line."
        )

    logger.warning("Agent loop hit max iterations (%s)", max_iters)
    return final_text or "ERROR: Agent loop reached iteration limit."


def process_inbound_message(message_payload: dict) -> str:
    user_id = message_payload.get("user_id", "unknown")
    roles = message_payload.get("roles")
    roleplay = message_payload.get("roleplay") or {}
    conversation = message_payload.get("conversation") or {}
    participants = conversation.get("participants", [])
    persona = roleplay.get("persona", "secure EuroClaw Linux automation agent")
    text = message_payload["text"]

    with tracer.start_as_current_span("agent_reasoning_loop") as span:
        span.set_attribute("euroclaw.user_id", str(user_id))
        span.set_attribute(
            "euroclaw.source", str(message_payload.get("source") or "unknown")
        )

        if participants:
            result = run_conversation(
                gateway,
                persona=persona,
                participants=participants,
                text=text,
                max_turns=current_settings().max_agent_turns,
            )
            audit.record(
                "conversation.completed",
                user_id=user_id,
                turns=len(result.turns),
            )
            return result.transcript()

        return run_agent_loop(user_id, text, persona, roles)


# --------------------------------------------------------------------------- #
# Public facade
# --------------------------------------------------------------------------- #
class EuroclawOrchestrator:
    """Programmatic entry point for embedding EuroClaw in an application."""

    def __init__(self, name: str = "EuroClaw", default_roles=("developer", "operator")):
        self.name = name
        self.default_roles = list(default_roles)

    def handle_request(self, text: str, user_id: str = "local", roles=None) -> str:
        payload = {
            "user_id": user_id,
            "text": text,
            "roles": list(roles) if roles is not None else self.default_roles,
            "source": "sdk",
        }
        return process_inbound_message(payload)

    def run_conversation(
        self, text: str, persona: str, participants: list[dict]
    ) -> str:
        payload = {
            "user_id": "local",
            "text": text,
            "roleplay": {"persona": persona},
            "conversation": {"participants": participants},
        }
        return process_inbound_message(payload)


# Kept for backward compatibility with existing imports/tests.
r = None  # deprecated: use euroclaw.state
HIGH_RISK_TOOLS = sorted(rbac.HIGH_RISK_TOOLS)

__all__ = [
    "EuroclawOrchestrator",
    "execute_agent_tool",
    "dispatch_agent_tool",
    "process_inbound_message",
    "run_agent_loop",
    "request_human_approval",
    "wait_for_approval",
    "gateway",
    "celery_app",
]
