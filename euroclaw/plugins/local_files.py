import os
import logging

from euroclaw.tracing import get_tracer

logger = logging.getLogger("euroclaw.plugins.files")
tracer = get_tracer(__name__)


class LocalFileSystemPlugin:
    def __init__(self, allowed_directories_env: str):
        raw_dirs = allowed_directories_env.split(",") if allowed_directories_env else []
        self.allowed_dirs = [os.path.abspath(d.strip()) for d in raw_dirs if d.strip()]
        if not self.allowed_dirs:
            logger.warning("No allowed workspaces defined! File reading is disabled.")

    def _get_safe_path(self, target_path: str) -> str | None:
        """Resolve symlinks and confine to an allowed directory (no traversal)."""
        target_abspath = os.path.realpath(os.path.abspath(target_path))
        for base_dir in self.allowed_dirs:
            base_real = os.path.realpath(base_dir)
            # Use commonpath to avoid the "/foo" vs "/foobar" prefix bug.
            try:
                if os.path.commonpath([target_abspath, base_real]) == base_real:
                    return target_abspath
            except ValueError:
                continue
        return None

    def read_file(self, file_path: str) -> str:
        with tracer.start_as_current_span("file_read") as span:
            span.set_attribute("euroclaw.file", file_path)
            safe_path = self._get_safe_path(file_path)
            if not safe_path:
                from opentelemetry import trace

                span.set_status(trace.StatusCode.ERROR, description="Path Traversal")
                logger.warning("SECURITY: blocked unauthorized read: %s", file_path)
                return (
                    "ERROR: Access Denied. You are restricted to workspace "
                    "directories."
                )
            if not os.path.exists(safe_path):
                return f"ERROR: File '{file_path}' does not exist."
            try:
                with open(safe_path, "r", encoding="utf-8") as fh:
                    return fh.read()
            except Exception as exc:  # noqa: BLE001
                return f"ERROR: Failed to read file: {exc}"
