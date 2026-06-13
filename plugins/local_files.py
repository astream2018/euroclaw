import os
import logging
from opentelemetry import trace

logger = logging.getLogger("euroclaw.plugins.files")
tracer = trace.get_tracer(__name__)

class LocalFileSystemPlugin:
    def __init__(self, allowed_directories_env: str):
        # 1. Parse the comma-separated list from the env var
        raw_dirs = allowed_directories_env.split(",") if allowed_directories_env else []
        
        # 2. Resolve to absolute paths and remove whitespace
        self.allowed_dirs = [os.path.abspath(d.strip()) for d in raw_dirs if d.strip()]
        
        if not self.allowed_dirs:
            logger.warning("No allowed workspaces defined! File reading is disabled.")

    def _get_safe_path(self, target_path: str) -> str | None:
        """Checks if the requested file is inside ANY of the allowed directories."""
        target_abspath = os.path.abspath(target_path)
        
        for base_dir in self.allowed_dirs:
            # If the requested file starts with an allowed base path, it is safe
            if target_abspath.startswith(base_dir):
                return target_abspath
                
        return None # Path traversal attempt

    def read_file(self, file_path: str) -> str:
        """Securely reads a file if it exists within the allowed workspaces."""
        with tracer.start_as_current_span("file_read") as span:
            span.set_attribute("euroclaw.file", file_path)
            
            safe_path = self._get_safe_path(file_path)
            
            if not safe_path:
                span.set_status(trace.StatusCode.ERROR, description="Path Traversal Attempt")
                logger.warning(f"SECURITY ALERT: Agent attempted to read unauthorized path: {file_path}")
                return "ERROR: Access Denied. You are restricted to specific workspace directories."

            if not os.path.exists(safe_path):
                return f"ERROR: File '{file_path}' does not exist."

            try:
                with open(safe_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content
            except Exception as e:
                span.set_status(trace.StatusCode.ERROR, description=str(e))
                return f"ERROR: Failed to read file: {e}"