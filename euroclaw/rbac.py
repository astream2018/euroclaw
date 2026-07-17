"""Role-Based tool access control.

Every tool belongs to a *capability group* with a risk class. A caller may only
invoke a tool if one of their SSO-mapped roles is granted that tool. High-risk
tools additionally require a HITL approval regardless of role (enforced in the
orchestrator). The default policy is deliberately restrictive; override per
deployment via the ``RBAC_POLICY`` env var (see ``settings.py``).
"""

from dataclasses import dataclass

from euroclaw.settings import current_settings

# Tools considered high-risk: always routed through HITL even if RBAC allows.
HIGH_RISK_TOOLS = frozenset(
    {
        "execute_bash",
        "run_bash",
        "delete_database",
        "send_external_email",
        "request_telegram_approval",
        "post_to_instagram",
    }
)

# Default capability -> allowed roles. "admin" is granted everything implicitly.
_DEFAULT_POLICY: dict[str, frozenset[str]] = {
    "search_internet": frozenset({"analyst", "operator", "developer"}),
    "scrape_website": frozenset({"analyst", "operator", "developer"}),
    "read_file": frozenset({"analyst", "operator", "developer"}),
    "notify_external_service": frozenset({"operator", "developer"}),
    "query_database_mcp": frozenset({"operator", "developer"}),
    "execute_bash": frozenset({"developer"}),
    "run_bash": frozenset({"developer"}),
    "execute_python": frozenset({"developer"}),
    "python_compiler": frozenset({"developer"}),
    "delete_database": frozenset(),  # admin-only
    "send_external_email": frozenset({"operator"}),
    "request_telegram_approval": frozenset({"operator", "developer"}),
    "post_to_instagram": frozenset({"operator"}),
}

ADMIN_ROLE = "admin"


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str


def _effective_policy() -> dict[str, frozenset[str]]:
    policy = dict(_DEFAULT_POLICY)
    for tool, roles in current_settings().rbac_policy:
        policy[tool] = frozenset(roles)
    return policy


def is_high_risk(tool_name: str) -> bool:
    return tool_name in HIGH_RISK_TOOLS


def check_access(roles, tool_name: str) -> AccessDecision:
    roles = set(roles or [])
    if ADMIN_ROLE in roles:
        return AccessDecision(True, "admin override")

    policy = _effective_policy()
    if tool_name not in policy:
        return AccessDecision(
            False, f"tool '{tool_name}' is not registered in the RBAC policy"
        )

    granted = policy[tool_name]
    if roles & granted:
        return AccessDecision(True, "role grant")
    return AccessDecision(
        False,
        f"none of roles {sorted(roles)} may invoke '{tool_name}' "
        f"(requires one of {sorted(granted) or ['admin']})",
    )


def allowed_tools(roles) -> list[str]:
    """Tools this caller may invoke — used to scope what the LLM is told about."""
    roles = set(roles or [])
    if ADMIN_ROLE in roles:
        return sorted(_effective_policy().keys())
    return sorted(
        tool for tool, granted in _effective_policy().items() if roles & granted
    )
