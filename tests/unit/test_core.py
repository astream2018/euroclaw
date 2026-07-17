from unittest.mock import MagicMock, patch

from euroclaw import state
from euroclaw.orchestrator import (
    execute_agent_tool,
    process_inbound_message,
    run_agent_loop,
)


def setup_function():
    state.reset_for_tests()


@patch("euroclaw.orchestrator.WebIntelligencePlugin")
def test_orchestrator_routes_web_search(MockWebPlugin):
    instance = MockWebPlugin.return_value
    instance.search_internet.return_value = "Mocked Search Result"

    result = execute_agent_tool(
        "user_123", "search_internet", "EuroClaw framework", roles=["analyst"]
    )

    instance.search_internet.assert_called_once_with(query="EuroClaw framework")
    assert result == "Mocked Search Result"


def test_rbac_denies_unauthorized_tool():
    result = execute_agent_tool(
        "user_123", "delete_database", "drop table users", roles=["analyst"]
    )
    assert "Access denied by RBAC policy" in result


@patch("euroclaw.orchestrator.get_sandbox")
def test_unknown_tool_routes_to_sandbox(mock_get_sandbox):
    sandbox = MagicMock()
    sandbox.isolation_level = "process"
    sandbox.__enter__.return_value = sandbox
    sandbox.__exit__.return_value = False
    exec_result = MagicMock()
    exec_result.as_text.return_value = "sandboxed output"
    sandbox.execute.return_value = exec_result
    mock_get_sandbox.return_value = sandbox

    # 'developer' role may run python in the sandbox.
    result = execute_agent_tool(
        "user_123", "python_compiler", "print('hi')", roles=["developer"]
    )

    sandbox.execute.assert_called_once_with("python_compiler", "print('hi')")
    assert result == "sandboxed output"


@patch("euroclaw.orchestrator.gateway.query_model")
def test_process_inbound_message_supports_multi_agent_roleplay(mock_query_model):
    mock_query_model.side_effect = ["Analyst summary", "Reviewer critique"]

    payload = {
        "user_id": "user_123",
        "text": "Draft a launch plan for the new feature",
        "roleplay": {"persona": "executive sponsor"},
        "conversation": {
            "participants": [
                {"name": "analyst", "role": "product strategist"},
                {"name": "reviewer", "role": "risk reviewer"},
            ]
        },
    }

    result = process_inbound_message(payload)

    assert mock_query_model.call_count == 2
    assert "analyst" in result.lower()
    assert "reviewer" in result.lower()
    assert "executive sponsor" in result.lower()


@patch("euroclaw.orchestrator.dispatch_agent_tool")
@patch("euroclaw.orchestrator.gateway.query_model")
def test_agent_loop_executes_tool_then_returns_final(mock_query, mock_dispatch):
    # First turn asks for a tool, second turn returns a plain final answer.
    mock_query.side_effect = [
        "TOOL_CALL: search_internet | Arguments: euroclaw",
        "Final answer based on the search.",
    ]
    mock_dispatch.return_value = "search results"

    result = run_agent_loop("user_1", "look it up", "agent", roles=["analyst"])

    mock_dispatch.assert_called_once_with(
        "user_1", "search_internet", "euroclaw", ["analyst"]
    )
    assert result == "Final answer based on the search."


@patch("euroclaw.orchestrator.gateway.query_model")
def test_agent_loop_returns_direct_answer_without_tools(mock_query):
    mock_query.return_value = "Just a plain answer."
    result = run_agent_loop("user_1", "hello", "agent", roles=["analyst"])
    assert result == "Just a plain answer."
