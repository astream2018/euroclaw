import asyncio
import json
import logging
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("euroclaw.plugins.mcp")

# Minimal env passed to the MCP subprocess. The previous version used env=None,
# which inherited the ENTIRE parent environment (all secrets) into an external
# npm-fetched process. We now pass an explicit allowlist only.
_DEFAULT_ENV_ALLOWLIST = ("PATH", "HOME", "SystemRoot", "TEMP", "TMP", "DATABASE_URL")


class ModelContextProtocolPlugin:
    """Connects EuroClaw to external MCP servers via stdio with a scoped env."""

    def __init__(
        self,
        server_command: str,
        server_args: list | None = None,
        env: dict | None = None,
    ):
        self.server_command = server_command
        self.server_args = server_args or []
        if env is None:
            env = {k: os.environ[k] for k in _DEFAULT_ENV_ALLOWLIST if k in os.environ}
        self.env = env

    async def _execute_mcp_request(self, tool_name: str, arguments: dict) -> str:
        server_params = StdioServerParameters(
            command=self.server_command, args=self.server_args, env=self.env
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if result.content and len(result.content) > 0:
                    return result.content[0].text
                return "MCP Execution Success: No content returned."

    def execute_mcp_tool(self, tool_name: str, arguments_json: str) -> str:
        try:
            args_dict = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError:
            return "ERROR: Invalid JSON arguments provided to MCP tool."
        try:
            return asyncio.run(self._execute_mcp_request(tool_name, args_dict))
        except Exception as exc:  # noqa: BLE001
            logger.error("[MCP] Failed to execute %s: %s", tool_name, exc)
            return f"ERROR: MCP Server execution failed. Reason: {exc}"
