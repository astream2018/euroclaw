import json
import asyncio
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("euroclaw.plugins.mcp")


class ModelContextProtocolPlugin:
    """
    Connects EuroClaw to external Model Context Protocol (MCP) servers via stdio.
    This allows the sovereign LLM to securely access external databases and APIs.
    """

    def __init__(self, server_command: str, server_args: list = None):
        """
        Args:
            server_command: The executable command (e.g., 'npx', 'python', 'docker')
            server_args: The arguments to boot the MCP server (e.g., ['-y', '@modelcontextprotocol/server-postgres'])
        """
        self.server_command = server_command
        self.server_args = server_args or []

    async def _execute_mcp_request(self, tool_name: str, arguments: dict) -> str:
        server_params = StdioServerParameters(
            command=self.server_command,
            args=self.server_args,
            env=None,  # Inherits current environment variables securely
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize connection with the MCP Server
                    await session.initialize()

                    # Execute the requested tool on the MCP server
                    result = await session.call_tool(tool_name, arguments)

                    # MCP returns a list of content blocks, we extract the text
                    if result.content and len(result.content) > 0:
                        return result.content[0].text
                    return "MCP Execution Success: No content returned."

        except Exception as e:
            logger.error(f"[MCP Plugin] Async execution failed: {e}")
            raise

    def execute_mcp_tool(self, tool_name: str, arguments_json: str) -> str:
        """
        Synchronous wrapper to fit into the existing DAG routing architecture.
        """
        try:
            # Parse the stringified JSON arguments from the LLM
            args_dict = json.loads(arguments_json) if arguments_json else {}

            # Block the current thread to run the async MCP lifecycle
            result = asyncio.run(self._execute_mcp_request(tool_name, args_dict))
            return result

        except json.JSONDecodeError:
            return "ERROR: Invalid JSON arguments provided to MCP tool."
        except Exception as e:
            logger.error(f"[MCP Plugin] Failed to execute {tool_name}: {e}")
            return f"ERROR: MCP Server execution failed. Reason: {str(e)}"
