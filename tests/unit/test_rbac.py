from euroclaw import rbac


def test_admin_can_run_anything():
    assert rbac.check_access(["admin"], "delete_database").allowed


def test_analyst_can_search_but_not_execute_bash():
    assert rbac.check_access(["analyst"], "search_internet").allowed
    assert not rbac.check_access(["analyst"], "execute_bash").allowed


def test_unknown_tool_is_denied():
    decision = rbac.check_access(["developer"], "totally_unknown_tool")
    assert not decision.allowed


def test_high_risk_flag():
    assert rbac.is_high_risk("execute_bash")
    assert not rbac.is_high_risk("search_internet")


def test_allowed_tools_scopes_to_roles():
    tools = rbac.allowed_tools(["analyst"])
    assert "search_internet" in tools
    assert "delete_database" not in tools
