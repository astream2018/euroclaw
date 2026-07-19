"""Process-level isolation. Provides a working, auditable execution boundary
(temp working dir, minimized environment, resource limits, wall-clock timeout)
but is NOT a hardware/kernel boundary. For untrusted code in production use the
Firecracker backend on a KVM host.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile

from .base import Sandbox, SandboxResult

logger = logging.getLogger(__name__)

_WINDOWS_LIMITS_WARNED = False

# ~256 MB address space and ~10 MB max file size.
_RLIMIT_AS_BYTES = 256 * 1024 * 1024
_RLIMIT_FSIZE_BYTES = 10 * 1024 * 1024

_BASH_TOOLS = {"execute_bash", "run_bash", "bash"}
_PYTHON_TOOLS = {"execute_python", "python_compiler", "python"}


class SubprocessSandbox(Sandbox):
    """Process-level isolation. Provides a working, auditable execution boundary
    (temp working dir, minimized environment, resource limits, wall-clock
    timeout) but is NOT a hardware/kernel boundary. For untrusted code in
    production use the Firecracker backend on a KVM host.
    """

    isolation_level = "process"

    def _build_env(self, home: str) -> dict[str, str]:
        """Return a minimized environment mapping for the child process."""
        env: dict[str, str] = {"HOME": home}
        path = os.environ.get("PATH")
        if path:
            env["PATH"] = path
        lang = os.environ.get("LANG")
        if lang:
            env["LANG"] = lang
        return env

    def _preexec(self, timeout: int):
        """Build a POSIX preexec_fn applying rlimits and a new session.

        Returns None on non-POSIX platforms or if resource limits are
        unavailable, so callers can pass it straight to ``subprocess.run``.
        """
        if os.name != "posix":
            global _WINDOWS_LIMITS_WARNED
            if not _WINDOWS_LIMITS_WARNED:
                logger.warning(
                    "SubprocessSandbox resource limits are unavailable on "
                    "this platform (%s); running without rlimits.",
                    os.name,
                )
                _WINDOWS_LIMITS_WARNED = True
            return None

        try:
            import resource
        except ImportError:  # pragma: no cover - posix without resource
            return None

        def _apply() -> None:
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (timeout + 1, timeout + 1))
                resource.setrlimit(
                    resource.RLIMIT_AS, (_RLIMIT_AS_BYTES, _RLIMIT_AS_BYTES)
                )
                resource.setrlimit(
                    resource.RLIMIT_FSIZE,
                    (_RLIMIT_FSIZE_BYTES, _RLIMIT_FSIZE_BYTES),
                )
                os.setsid()
            except Exception:
                # Never fail the child just because a limit could not be set.
                pass

        return _apply

    def _build_command(self, tool_name: str, arguments: str) -> list[str]:
        """Map a tool name + arguments to an argv list for the platform."""
        if tool_name in _PYTHON_TOOLS:
            return [sys.executable, "-c", arguments]
        # Bash tools and any unknown tool fall back to a shell command.
        if os.name == "posix":
            return ["/bin/sh", "-c", arguments]
        return ["cmd", "/c", arguments]

    def execute(
        self, tool_name: str, arguments: str, *, timeout: int = 30
    ) -> SandboxResult:
        tmp = tempfile.mkdtemp(prefix="euroclaw-sbx-")
        note = ""
        if tool_name not in _BASH_TOOLS and tool_name not in _PYTHON_TOOLS:
            note = (
                f"note: unrecognized tool {tool_name!r}; "
                f"treated as a shell command\n"
            )
        try:
            cmd = self._build_command(tool_name, arguments)
            env = self._build_env(tmp)
            preexec = self._preexec(timeout)
            kwargs: dict = {}
            if preexec is not None:
                kwargs["preexec_fn"] = preexec
            try:
                completed = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=tmp,
                    env=env,
                    **kwargs,
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    stdout="",
                    stderr=f"execution timed out after {timeout}s",
                    exit_code=124,
                    backend="subprocess",
                    isolation_level=self.isolation_level,
                    timed_out=True,
                )

            return SandboxResult(
                stdout=completed.stdout or "",
                stderr=note + (completed.stderr or ""),
                exit_code=completed.returncode,
                backend="subprocess",
                isolation_level=self.isolation_level,
            )
        except Exception as exc:  # noqa: BLE001 - report, never raise
            return SandboxResult(
                stdout="",
                stderr=f"{note}sandbox execution error: {exc}",
                exit_code=1,
                backend="subprocess",
                isolation_level=self.isolation_level,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
