"""Declarative agent profiles loaded from ``agents.yaml``.

This is what makes the Quickstart real: define agents in YAML, load them, and
hand a profile to :class:`~euroclaw.orchestrator.EuroclawOrchestrator`.
"""

import logging
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger("euroclaw.agent_loader")


@dataclass
class AgentProfile:
    name: str
    role: str = ""
    goal: str = ""
    backstory: str = ""
    llm_config: dict = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    cron_schedule: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentProfile":
        if "name" not in data:
            raise ValueError("agent entry is missing required field 'name'")
        return cls(
            name=data["name"],
            role=data.get("role", ""),
            goal=data.get("goal", ""),
            backstory=data.get("backstory", ""),
            llm_config=data.get("llm_config", {}) or {},
            allowed_tools=list(data.get("allowed_tools", []) or []),
            cron_schedule=list(data.get("cron_schedule", []) or []),
        )


def load_agents_from_yaml(path: str) -> dict:
    """Load and validate an agents.yaml file.

    Returns ``{"agents": [AgentProfile, ...], "raw": <parsed yaml>}``.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    entries = raw.get("agents", [])
    if not isinstance(entries, list):
        raise ValueError("'agents' must be a list in agents.yaml")

    profiles = [AgentProfile.from_dict(entry) for entry in entries]
    names = [p.name for p in profiles]
    if len(names) != len(set(names)):
        raise ValueError("duplicate agent names detected in agents.yaml")

    logger.info("Loaded %d agent profile(s) from %s", len(profiles), path)
    return {"agents": profiles, "raw": raw}


def get_profile(loaded: dict, name: str) -> AgentProfile:
    for profile in loaded["agents"]:
        if profile.name == name:
            return profile
    raise KeyError(f"agent '{name}' not found")
