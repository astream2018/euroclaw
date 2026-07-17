"""Bounded, auditable multi-agent conversation.

Multi-agent collaboration is modeled as a *bounded DAG of turns*, not a
free-running chat loop. Properties this guarantees:

* **Deterministic termination** — a hard ``max_turns`` ceiling; the round-robin
  order is fixed, so a run can never spin forever.
* **Role specialization** — each participant receives its OWN role-scoped system
  instruction (the previous implementation shared one prompt across all agents).
* **Auditability** — every turn is returned as a structured record and emitted
  as an OpenTelemetry span by the caller.

Tool execution is intentionally NOT performed here: if a turn requests a tool,
the orchestrator routes it through the same RBAC + HITL + sandbox path as any
single-agent action. This module only choreographs the conversation.
"""

from dataclasses import dataclass, field

from euroclaw.tracing import get_tracer

tracer = get_tracer(__name__)


@dataclass
class Turn:
    index: int
    name: str
    role: str
    content: str


@dataclass
class ConversationResult:
    persona: str
    turns: list[Turn] = field(default_factory=list)

    def transcript(self) -> str:
        lines = [f"Roleplay persona: {self.persona}", "Conversation transcript:"]
        for turn in self.turns:
            lines.append(f"{turn.name} ({turn.role}): {turn.content}")
        return "\n\n".join(lines)


def run_conversation(
    gateway,
    persona: str,
    participants: list[dict],
    text: str,
    max_turns: int = 6,
) -> ConversationResult:
    """Run one bounded round-robin over ``participants``.

    ``gateway`` is any object exposing ``query_model(prompt, system_instruction)``.
    """
    result = ConversationResult(persona=persona)
    if not participants:
        return result

    roster = "\n".join(
        f"- {p.get('name', 'agent')} ({p.get('role', 'assistant')})"
        for p in participants
    )

    last_message = text
    # Bound the number of turns; never exceed one pass unless max_turns allows.
    turn_budget = min(len(participants), max(1, max_turns))

    with tracer.start_as_current_span("multi_agent_conversation") as span:
        span.set_attribute("euroclaw.multiagent.persona", persona)
        span.set_attribute("euroclaw.multiagent.participant_count", len(participants))

        for index in range(turn_budget):
            participant = participants[index]
            name = participant.get("name", "agent")
            role = participant.get("role", "assistant")

            system_instruction = (
                f"You are '{name}', acting strictly as: {role}. "
                f"You are one participant in a facilitated multi-agent discussion "
                f"led by a {persona}. The full roster is:\n{roster}\n"
                f"Stay in your role. Respond concisely and build on prior turns. "
                f"Do not impersonate other participants."
            )
            prompt = (
                f"Discussion topic: {text}\n\n"
                f"Most recent contribution:\n{last_message}\n\n"
                f"Provide your ({role}) contribution now."
            )

            with tracer.start_as_current_span("multi_agent_turn") as turn_span:
                turn_span.set_attribute("euroclaw.multiagent.turn", index + 1)
                turn_span.set_attribute("euroclaw.multiagent.agent", name)
                content = gateway.query_model(
                    prompt=prompt, system_instruction=system_instruction
                )

            result.turns.append(
                Turn(index=index + 1, name=name, role=role, content=content)
            )
            last_message = content

    return result
