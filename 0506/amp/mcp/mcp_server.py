"""MCP (Model Context Protocol) compliant server implementation.

This module implements a JSON-RPC 2.0 server following the MCP protocol specification.
It replaces the REST API for Claude Code integration.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from amp.mcp.mcp_tools import MCPToolAdapter
from amp.storage.database import Database

logger = logging.getLogger(__name__)


class AMPMCPServer:
    """AMP MCP Protocol Server.

    Implements the Model Context Protocol (MCP) for Claude Code integration.
    Uses JSON-RPC 2.0 over stdio transport.
    """

    def __init__(self, database: Database) -> None:
        """Initialize MCP server.

        Args:
            database: Database instance for storage
        """
        self.database = database
        self.server = Server("amp")
        self.tool_adapter = MCPToolAdapter(database)

        # Register MCP protocol handlers
        self._register_handlers()

        logger.info("AMP MCP Server initialized")

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List all available tools.

            Returns:
                List of MCP Tool definitions
            """
            try:
                tools = self.tool_adapter.get_all_tools()
                logger.debug(f"Listed {len(tools)} tools")
                return tools
            except Exception as e:
                logger.error(f"Error listing tools: {e}")
                raise

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Execute a tool.

            Args:
                name: Tool name
                arguments: Tool arguments

            Returns:
                List of TextContent with execution result
            """
            try:
                logger.info(f"Executing tool: {name}")
                logger.debug(f"Tool arguments: {arguments}")

                result = await self.tool_adapter.execute_tool(name, arguments)

                # Convert result to JSON string
                result_json = json.dumps(result, indent=2, default=str)

                logger.debug(f"Tool {name} executed successfully")

                return [
                    TextContent(
                        type="text",
                        text=result_json
                    )
                ]
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                # Return error as TextContent
                error_result = {
                    "success": False,
                    "error": str(e),
                    "error_type": "execution_error"
                }
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(error_result, indent=2)
                    )
                ]

    def get_server(self) -> Server:
        """Get the MCP server instance.

        Returns:
            MCP Server instance
        """
        return self.server


def create_mcp_server(database: Database) -> Server:
    """Create and configure MCP server.

    Args:
        database: Database instance

    Returns:
        Configured MCP Server instance
    """
    amp_server = AMPMCPServer(database)
    return amp_server.get_server()
