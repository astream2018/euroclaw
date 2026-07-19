from euroclaw.toolcall import parse_tool_calls


def test_parses_line_form():
    calls = parse_tool_calls(
        "TOOL_CALL: search_internet | Arguments: euroclaw framework"
    )
    assert len(calls) == 1
    assert calls[0].tool_name == "search_internet"
    assert calls[0].arguments == "euroclaw framework"


def test_parses_json_form():
    calls = parse_tool_calls('{"tool": "read_file", "arguments": "/tmp/x.txt"}')
    assert len(calls) == 1
    assert calls[0].tool_name == "read_file"
    assert calls[0].arguments == "/tmp/x.txt"


def test_json_object_arguments_coerced_to_string():
    calls = parse_tool_calls('{"tool": "q", "arguments": {"k": 1}}')
    assert calls[0].arguments == '{"k": 1}'


def test_plain_text_has_no_tool_calls():
    assert parse_tool_calls("Here is the final answer, no tools needed.") == []


def test_empty_input():
    assert parse_tool_calls("") == []
