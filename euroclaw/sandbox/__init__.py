"""EuroClaw sandbox subsystem.

A pluggable, honest code-execution sandbox layer. Each backend advertises its
real isolation guarantee rather than pretending to be stronger than it is.
"""

from __future__ import annotations

import os
import uuid

from .base import Sandbox, SandboxResult, SandboxUnavailable

__all__ = ["Sandbox", "SandboxResult", "SandboxUnavailable", "get_sandbox"]


def get_sandbox(backend: str | None = None, *, task_id: str | None = None) -> Sandbox:
    """Construct a sandbox backend by name.

    Args:
        backend: Backend name. Falls back to the ``SANDBOX_BACKEND`` env var,
            then to ``"subprocess"``.
        task_id: Optional identifier for the task. Generated if omitted.

    Returns:
        An instantiated :class:`Sandbox` subclass.

    Raises:
        ValueError: If the backend name is not recognized.
    """
    # Imported lazily so importing this package never hard-requires optional
    # backend dependencies (e.g. requests_unixsocket for Firecracker).
    from .firecracker import FirecrackerMicroVM
    from .subprocess_sandbox import SubprocessSandbox

    if backend is None:
        backend = os.getenv("SANDBOX_BACKEND", "subprocess")

    if task_id is None:
        task_id = uuid.uuid4().hex[:8]

    registry = {
        "subprocess": SubprocessSandbox,
        "firecracker": FirecrackerMicroVM,
    }

    if backend not in registry:
        raise ValueError(
            f"unknown sandbox backend {backend!r}; "
            f"valid choices: {sorted(registry)}"
        )

    cls = registry[backend]
    if backend == "firecracker":
        return cls(task_id=task_id)
    return cls()
