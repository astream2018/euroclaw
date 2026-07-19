from unittest.mock import MagicMock

from euroclaw.multi_agent import run_conversation


def test_bounded_conversation_calls_once_per_participant():
    gateway = MagicMock()
    gateway.query_model.side_effect = ["a", "b"]
    participants = [
        {"name": "analyst", "role": "strategist"},
        {"name": "reviewer", "role": "risk"},
    ]

    result = run_conversation(gateway, "lead", participants, "topic", max_turns=6)

    assert gateway.query_model.call_count == 2
    assert len(result.turns) == 2
    assert "lead" in result.transcript().lower()
    assert "analyst (strategist): a" in result.transcript()


def test_max_turns_bounds_iterations():
    gateway = MagicMock()
    gateway.query_model.return_value = "x"
    participants = [{"name": f"a{i}", "role": "r"} for i in range(10)]

    result = run_conversation(gateway, "lead", participants, "topic", max_turns=3)

    assert gateway.query_model.call_count == 3
    assert len(result.turns) == 3


def test_each_agent_gets_its_own_role_instruction():
    gateway = MagicMock()
    gateway.query_model.return_value = "ok"
    participants = [{"name": "analyst", "role": "risk analyst"}]

    run_conversation(gateway, "lead", participants, "topic")

    _, kwargs = gateway.query_model.call_args
    assert "risk analyst" in kwargs["system_instruction"]


def test_no_participants_returns_empty():
    gateway = MagicMock()
    result = run_conversation(gateway, "lead", [], "topic")
    assert result.turns == []
    gateway.query_model.assert_not_called()
