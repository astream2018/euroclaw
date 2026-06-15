import os
import logging
from celery import Celery

# We import the execution logic from your orchestrator
from src.orchestrator import execute_agent_tool

logger = logging.getLogger("euroclaw.worker")

# Initialize the Celery App, pointing it to the central Redis server
redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
backend_url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery("euroclaw_workers", broker=redis_url, backend=backend_url)

@celery_app.task(name="execute_remote_tool", bind=True)
def execute_remote_tool(self, user_id: str, tool_name: str, arguments: str) -> str:
    """
    This function physically executes on whichever server picks it up from the queue.
    """
    logger.info(f"[WORKER] Picked up task {self.request.id}: {tool_name}")
    
    # Run the exact same secure execution logic you already built
    result = execute_agent_tool(user_id=user_id, tool_name=tool_name, arguments=arguments)
    
    logger.info(f"[WORKER] Completed task {self.request.id}.")
    return result