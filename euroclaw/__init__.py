"""EuroClaw — sovereign, zero-trust, enterprise agentic AI framework.

Public entry points::

    from euroclaw import EuroclawOrchestrator, __version__
    from euroclaw.agent_loader import load_agents_from_yaml
"""

__version__ = "0.2.0"


def __getattr__(name):
    # Lazy re-exports so importing the package never triggers heavy imports
    # (redis/celery/otel) unless the orchestrator is actually used.
    if name in {
        "EuroclawOrchestrator",
        "execute_agent_tool",
        "dispatch_agent_tool",
        "process_inbound_message",
    }:
        from euroclaw import orchestrator

        return getattr(orchestrator, name)
    raise AttributeError(f"module 'euroclaw' has no attribute {name!r}")


__all__ = [
    "EuroclawOrchestrator",
    "execute_agent_tool",
    "dispatch_agent_tool",
    "process_inbound_message",
    "__version__",
]
