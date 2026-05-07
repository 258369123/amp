"""Tool registry and execution for MCP server."""

import inspect
import logging
from collections.abc import Callable
from typing import Any

from amp.exceptions import MCPToolExecutionFailed
from amp.mcp.protocol import ParameterType, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for MCP tools."""

    def __init__(self) -> None:
        """Initialize tool registry."""
        self._tools: dict[str, dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        func: Callable[..., Any],
        description: str,
        parameters: list[ToolParameter],
    ) -> None:
        """Register a tool.

        Args:
            name: Tool name
            func: Tool function (sync or async)
            description: Tool description
            parameters: Tool parameters
        """
        self._tools[name] = {
            "func": func,
            "description": description,
            "parameters": parameters,
            "is_async": inspect.iscoroutinefunction(func),
        }
        logger.info(f"Registered tool: {name}")

    def get_tool(self, name: str) -> dict[str, Any] | None:
        """Get tool by name.

        Args:
            name: Tool name

        Returns:
            Tool metadata or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools.

        Returns:
            List of tool definitions
        """
        tools = []
        for name, tool_data in self._tools.items():
            tools.append(
                ToolDefinition(
                    name=name,
                    description=tool_data["description"],
                    parameters=tool_data["parameters"],
                )
            )
        return tools

    async def execute_tool(self, name: str, params: dict[str, Any]) -> Any:
        """Execute a tool.

        Args:
            name: Tool name
            params: Tool parameters

        Returns:
            Tool execution result

        Raises:
            MCPToolExecutionFailed: If tool not found or execution fails
        """
        tool = self.get_tool(name)
        if not tool:
            raise MCPToolExecutionFailed(name, "Tool not found")

        # Validate parameters
        try:
            self.validate_parameters(name, params)
        except ValueError as e:
            raise MCPToolExecutionFailed(name, f"Parameter validation failed: {e}") from e

        # Filter parameters to only include those defined in tool parameters
        tool_param_names = {p.name for p in tool["parameters"]}
        filtered_params = {k: v for k, v in params.items() if k in tool_param_names}

        # Execute tool
        try:
            func = tool["func"]
            if tool["is_async"]:
                result = await func(**filtered_params)
            else:
                result = func(**filtered_params)
            return result
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {e}")
            raise MCPToolExecutionFailed(name, str(e)) from e

    def validate_parameters(self, tool_name: str, params: dict[str, Any]) -> None:
        """Validate tool parameters.

        Args:
            tool_name: Tool name
            params: Parameters to validate

        Raises:
            ValueError: If validation fails
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")

        tool_params = tool["parameters"]

        # Check required parameters
        for param in tool_params:
            if param.required and param.name not in params:
                raise ValueError(f"Required parameter '{param.name}' missing")

        # Check parameter types
        for param_name, param_value in params.items():
            # Find parameter definition
            param_def = next(
                (p for p in tool_params if p.name == param_name),
                None
            )
            if not param_def:
                logger.warning(f"Unknown parameter '{param_name}' for tool {tool_name}")
                continue

            # Validate type
            if not self._validate_type(param_value, param_def.type):
                raise ValueError(
                    f"Parameter '{param_name}' has invalid type. "
                    f"Expected {param_def.type}, got {type(param_value).__name__}"
                )

    def _validate_type(self, value: Any, expected_type: ParameterType) -> bool:
        """Validate parameter type.

        Args:
            value: Parameter value
            expected_type: Expected parameter type

        Returns:
            True if type is valid
        """
        if expected_type == ParameterType.STRING:
            return isinstance(value, str)
        elif expected_type == ParameterType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        elif expected_type == ParameterType.BOOLEAN:
            return isinstance(value, bool)
        elif expected_type == ParameterType.OBJECT:
            return isinstance(value, dict)
        elif expected_type == ParameterType.ARRAY:
            return isinstance(value, list)
        return False

    def unregister_tool(self, name: str) -> None:
        """Unregister a tool.

        Args:
            name: Tool name
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        logger.info("Cleared all tools")


# Global tool registry instance
tool_registry = ToolRegistry()
