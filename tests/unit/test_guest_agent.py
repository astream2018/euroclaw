from euroclaw.sandbox.guest_agent import run_tool


def test_run_python_tool():
    result = run_tool("execute_python", "print(6*7)")
    assert result["exit_code"] == 0
    assert "42" in result["stdout"]


def test_run_python_error_exit_code():
    result = run_tool("execute_python", "import sys; sys.exit(3)")
    assert result["exit_code"] == 3


def test_run_tool_timeout():
    result = run_tool("execute_python", "import time; time.sleep(5)", timeout=1)
    assert result["exit_code"] == 124
    assert "timed out" in result["stderr"]
