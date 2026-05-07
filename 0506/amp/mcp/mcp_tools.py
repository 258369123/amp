"""MCP tool adapters - converts AMP tools to MCP format.

This module adapts the existing 17 AMP tools to the MCP Tool schema.
"""

import logging
from typing import Any

from mcp.types import Tool

from amp.mcp.protocol import ParameterType
from amp.mcp.tool_registry import tool_registry
from amp.mcp.tools.registry import initialize_managers, register_all_tools
from amp.storage.database import Database

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    """Adapter to convert AMP tools to MCP format."""

    def __init__(self, database: Database) -> None:
        """Initialize tool adapter.

        Args:
            database: Database instance
        """
        self.database = database
        self.managers: dict[str, Any] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Ensure managers and tools are initialized."""
        if not self._initialized:
            logger.info("Initializing managers and tools")
            self.managers = initialize_managers(self.database)
            register_all_tools(self.managers)
            self._initialized = True
            logger.info(f"Initialized {len(tool_registry.list_tools())} tools")

    def get_all_tools(self) -> list[Tool]:
        """Get all tools in MCP format.

        Returns:
            List of MCP Tool definitions
        """
        self._ensure_initialized()

        amp_tools = tool_registry.list_tools()
        mcp_tools = []

        for amp_tool in amp_tools:
            mcp_tool = self._convert_to_mcp_tool(amp_tool)
            mcp_tools.append(mcp_tool)

        return mcp_tools

    def _convert_to_mcp_tool(self, amp_tool: Any) -> Tool:
        """Convert AMP tool definition to MCP Tool.

        Args:
            amp_tool: AMP ToolDefinition

        Returns:
            MCP Tool
        """
        # Build JSON Schema for input parameters
        properties = {}
        required = []

        for param in amp_tool.parameters:
            # Convert parameter type to JSON Schema type
            json_type = self._convert_parameter_type(param.type)

            param_schema: dict[str, Any] = {
                "type": json_type,
                "description": param.description,
            }

            # Add default value if present
            if hasattr(param, 'default') and param.default is not None:
                param_schema["default"] = param.default

            properties[param.name] = param_schema

            if param.required:
                required.append(param.name)

        # Build input schema
        input_schema = {
            "type": "object",
            "properties": properties,
        }

        if required:
            input_schema["required"] = required

        return Tool(
            name=amp_tool.name,
            description=amp_tool.description,
            inputSchema=input_schema
        )

    def _convert_parameter_type(self, param_type: ParameterType) -> str:
        """Convert AMP ParameterType to JSON Schema type.

        Args:
            param_type: AMP ParameterType

        Returns:
            JSON Schema type string
        """
        type_mapping = {
            ParameterType.STRING: "string",
            ParameterType.INTEGER: "integer",
            ParameterType.BOOLEAN: "boolean",
            ParameterType.OBJECT: "object",
            ParameterType.ARRAY: "array",
        }
        return type_mapping.get(param_type, "string")

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        self._ensure_initialized()

        try:
            result = await tool_registry.execute_tool(name, arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "execution_error"
            }
