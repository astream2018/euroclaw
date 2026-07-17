"""Deterministic parser that extracts tool calls from LLM output.

Two formats are recognized:

1. Line form (the model is instructed to emit this):
   ``TOOL_CALL: <tool_name> | Arguments: <arguments>``
2. Fenced JSON:
   ``{"tool": "<name>", "arguments": "<args>"}`` (also accepts ``tool_calls``: [...]).

Parsing is intentionally strict and side-effect free. If nothing matches, an
empty list is returned and the caller treats the text as a final answer.
"""

import json
import re
from dataclasses import dataclass

_LINE_RE = re.compile(
    r"TOOL_CALL:\s*(?P<tool>[a-zA-Z0-9_\-]+)\s*\|\s*Arguments:\s*(?P<args>.*)",
    re.IGNORECASE,
)


def _extract_json_objects(text: str) -> list[str]:
    """Extract top-level, brace-balanced JSON object substrings (handles nesting)."""
    objects: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    objects.append(text[start : i + 1])
                    start = -1
    return objects


@dataclass(frozen=True)
class ToolCall:
    tool_name: str
    arguments: str


def _coerce_args(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


def parse_tool_calls(text: str) -> list[ToolCall]:
    if not text:
        return []

    calls: list[ToolCall] = []

    # 1) Line form (handle each matching line).
    for match in _LINE_RE.finditer(text):
        tool = match.group("tool").strip()
        args = match.group("args").strip()
        calls.append(ToolCall(tool_name=tool, arguments=args))
    if calls:
        return calls

    # 2) JSON object(s).
    for block in _extract_json_objects(text):
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "tool" in obj:
            calls.append(
                ToolCall(
                    tool_name=str(obj["tool"]).strip(),
                    arguments=_coerce_args(obj.get("arguments", "")),
                )
            )
        elif isinstance(obj, dict) and isinstance(obj.get("tool_calls"), list):
            for tc in obj["tool_calls"]:
                if isinstance(tc, dict) and "tool" in tc:
                    calls.append(
                        ToolCall(
                            tool_name=str(tc["tool"]).strip(),
                            arguments=_coerce_args(tc.get("arguments", "")),
                        )
                    )
    return calls
