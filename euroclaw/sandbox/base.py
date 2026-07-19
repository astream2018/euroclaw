"""Core abstractions for the EuroClaw sandbox subsystem.

Defines the common result type, the unavailability error, and the abstract
``Sandbox`` interface that every backend implements.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


class SandboxUnavailable(RuntimeError):
    """Raised when a requested sandbox backend cannot run in this environment.

    For example, the Firecracker backend raises this on a host without KVM.
    """


@dataclass
class SandboxResult:
    """Outcome of a single sandboxed execution.

    Attributes:
        stdout: Captured standard output.
        stderr: Captured standard error.
        exit_code: Process exit code (124 conventionally means timeout).
        backend: Name of the backend that produced this result.
        isolation_level: Isolation guarantee of the backend, e.g. "process".
        timed_out: True if execution was killed for exceeding its timeout.
    """

    stdout: str
    stderr: str = ""
    exit_code: int = 0
    backend: str = ""
    isolation_level: str = ""
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        """True only if the process exited cleanly and did not time out."""
        return self.exit_code == 0 and not self.timed_out

    def as_text(self) -> str:
        """Return a concise, human/LLM-friendly summary of this result."""
        if self.timed_out:
            status = "TIMED OUT"
        elif self.ok:
            status = "OK"
        else:
            status = f"FAILED (exit {self.exit_code})"

        parts = [f"[{status}]"]
        stdout = self.stdout.strip()
        stderr = self.stderr.strip()
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(f"stderr: {stderr}")
        return "\n".join(parts)


class Sandbox(abc.ABC):
    """Abstract base class for pluggable code-execution sandboxes.

    Subclasses declare their real isolation guarantee via ``isolation_level``
    and implement :meth:`execute`. Lifecycle hooks ``boot`` and ``teardown``
    default to no-ops and are also driven by the context-manager protocol.
    """

    isolation_level: str = "none"

    @abc.abstractmethod
    def execute(
        self, tool_name: str, arguments: str, *, timeout: int = 30
    ) -> SandboxResult:
        """Execute ``arguments`` for ``tool_name`` and return a result."""
        raise NotImplementedError

    def boot(self) -> None:
        """Prepare the sandbox. No-op by default; backends may override."""

    def teardown(self) -> None:
        """Release sandbox resources. No-op by default; backends override."""

    def __enter__(self) -> "Sandbox":
        self.boot()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.teardown()
