"""Unit tests for tool registry."""

import pytest

from amp.exceptions import MCPToolExecutionFailed
from amp.mcp.protocol import ParameterType, ToolParameter
from amp.mcp.tool_registry import ToolRegistry


@pytest.fixture
def registry():
    """Create a fresh tool registry."""
    reg = ToolRegistry()
    yield reg
    reg.clear()


def test_register_tool(registry):
    """Test registering a tool."""
    def test_func(param: str) -> str:
        return f"result: {param}"

    registry.register_tool(
        name="test_tool",
        func=test_func,
        description="Test tool",
        parameters=[
            ToolParameter(
                name="param",
                type=ParameterType.STRING,
                description="Test parameter",
                required=True,
            )
        ],
    )

    tool = registry.get_tool("test_tool")
    assert tool is not None
    assert tool["description"] == "Test tool"
    assert tool["is_async"] is False


def test_register_async_tool(registry):
    """Test registering an async tool."""
    async def async_func(param: int) -> int:
        return param * 2

    registry.register_tool(
        name="async_tool",
        func=async_func,
        description="Async tool",
        parameters=[
            ToolParameter(
                name="param",
                type=ParameterType.INTEGER,
                description="Test parameter",
                required=True,
            )
        ],
    )

    tool = registry.get_tool("async_tool")
    assert tool is not None
    assert tool["is_async"] is True


def test_get_nonexistent_tool(registry):
    """Test getting a tool that doesn't exist."""
    tool = registry.get_tool("nonexistent")
    assert tool is None


def test_list_tools(registry):
    """Test listing all tools."""
    def tool1(p: str) -> str:
        return p

    def tool2(p: int) -> int:
        return p

    registry.register_tool(
        name="tool1",
        func=tool1,
        description="Tool 1",
        parameters=[],
    )

    registry.register_tool(
        name="tool2",
        func=tool2,
        description="Tool 2",
        parameters=[],
    )

    tools = registry.list_tools()
    assert len(tools) == 2
    assert any(t.name == "tool1" for t in tools)
    assert any(t.name == "tool2" for t in tools)


@pytest.mark.asyncio
async def test_execute_sync_tool(registry):
    """Test executing a synchronous tool."""
    def add_tool(a: int, b: int) -> int:
        return a + b

    registry.register_tool(
        name="add",
        func=add_tool,
        description="Add two numbers",
        parameters=[
            ToolParameter(
                name="a",
                type=ParameterType.INTEGER,
                description="First number",
                required=True,
            ),
            ToolParameter(
                name="b",
                type=ParameterType.INTEGER,
                description="Second number",
                required=True,
            ),
        ],
    )

    result = await registry.execute_tool("add", {"a": 5, "b": 3})
    assert result == 8


@pytest.mark.asyncio
async def test_execute_async_tool(registry):
    """Test executing an async tool."""
    async def multiply_tool(a: int, b: int) -> int:
        return a * b

    registry.register_tool(
        name="multiply",
        func=multiply_tool,
        description="Multiply two numbers",
        parameters=[
            ToolParameter(
                name="a",
                type=ParameterType.INTEGER,
                description="First number",
                required=True,
            ),
            ToolParameter(
                name="b",
                type=ParameterType.INTEGER,
                description="Second number",
                required=True,
            ),
        ],
    )

    result = await registry.execute_tool("multiply", {"a": 4, "b": 7})
    assert result == 28


@pytest.mark.asyncio
async def test_execute_nonexistent_tool(registry):
    """Test executing a tool that doesn't exist."""
    with pytest.raises(MCPToolExecutionFailed) as exc_info:
        await registry.execute_tool("nonexistent", {})

    assert "Tool not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_tool_missing_required_param(registry):
    """Test executing a tool with missing required parameter."""
    def test_tool(required_param: str) -> str:
        return required_param

    registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="Test tool",
        parameters=[
            ToolParameter(
                name="required_param",
                type=ParameterType.STRING,
                description="Required parameter",
                required=True,
            ),
        ],
    )

    with pytest.raises(MCPToolExecutionFailed) as exc_info:
        await registry.execute_tool("test_tool", {})

    assert "Parameter validation failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_tool_invalid_type(registry):
    """Test executing a tool with invalid parameter type."""
    def test_tool(int_param: int) -> int:
        return int_param

    registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="Test tool",
        parameters=[
            ToolParameter(
                name="int_param",
                type=ParameterType.INTEGER,
                description="Integer parameter",
                required=True,
            ),
        ],
    )

    with pytest.raises(MCPToolExecutionFailed) as exc_info:
        await registry.execute_tool("test_tool", {"int_param": "not_an_int"})

    assert "Parameter validation failed" in str(exc_info.value)


def test_validate_string_type(registry):
    """Test string type validation."""
    assert registry._validate_type("hello", ParameterType.STRING) is True
    assert registry._validate_type(123, ParameterType.STRING) is False


def test_validate_integer_type(registry):
    """Test integer type validation."""
    assert registry._validate_type(42, ParameterType.INTEGER) is True
    assert registry._validate_type("42", ParameterType.INTEGER) is False
    assert registry._validate_type(True, ParameterType.INTEGER) is False  # bool is not int


def test_validate_boolean_type(registry):
    """Test boolean type validation."""
    assert registry._validate_type(True, ParameterType.BOOLEAN) is True
    assert registry._validate_type(False, ParameterType.BOOLEAN) is True
    assert registry._validate_type(1, ParameterType.BOOLEAN) is False


def test_validate_object_type(registry):
    """Test object type validation."""
    assert registry._validate_type({"key": "value"}, ParameterType.OBJECT) is True
    assert registry._validate_type([], ParameterType.OBJECT) is False


def test_validate_array_type(registry):
    """Test array type validation."""
    assert registry._validate_type([1, 2, 3], ParameterType.ARRAY) is True
    assert registry._validate_type({}, ParameterType.ARRAY) is False


def test_unregister_tool(registry):
    """Test unregistering a tool."""
    def test_tool(p: str) -> str:
        return p

    registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="Test tool",
        parameters=[],
    )

    assert registry.get_tool("test_tool") is not None

    registry.unregister_tool("test_tool")
    assert registry.get_tool("test_tool") is None


def test_clear_registry(registry):
    """Test clearing all tools."""
    def tool1(p: str) -> str:
        return p

    def tool2(p: int) -> int:
        return p

    registry.register_tool("tool1", tool1, "Tool 1", [])
    registry.register_tool("tool2", tool2, "Tool 2", [])

    assert len(registry.list_tools()) == 2

    registry.clear()
    assert len(registry.list_tools()) == 0


@pytest.mark.asyncio
async def test_execute_tool_with_optional_param(registry):
    """Test executing a tool with optional parameter."""
    def test_tool(required: str, optional: int = 10) -> dict:
        return {"required": required, "optional": optional}

    registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="Test tool",
        parameters=[
            ToolParameter(
                name="required",
                type=ParameterType.STRING,
                description="Required parameter",
                required=True,
            ),
            ToolParameter(
                name="optional",
                type=ParameterType.INTEGER,
                description="Optional parameter",
                required=False,
                default=10,
            ),
        ],
    )

    # Execute without optional parameter
    result = await registry.execute_tool("test_tool", {"required": "test"})
    assert result["required"] == "test"

    # Execute with optional parameter
    result = await registry.execute_tool("test_tool", {"required": "test", "optional": 20})
    assert result["required"] == "test"
    assert result["optional"] == 20


@pytest.mark.asyncio
async def test_execute_tool_with_extra_params(registry):
    """Test executing a tool with extra unknown parameters."""
    def test_tool(param: str) -> str:
        return param

    registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="Test tool",
        parameters=[
            ToolParameter(
                name="param",
                type=ParameterType.STRING,
                description="Parameter",
                required=True,
            ),
        ],
    )

    # Should not fail with extra parameters (they are just ignored)
    result = await registry.execute_tool(
        "test_tool",
        {"param": "test", "extra": "ignored"}
    )
    assert result == "test"


@pytest.mark.asyncio
async def test_execute_tool_exception_handling(registry):
    """Test that tool exceptions are properly wrapped."""
    def failing_tool(param: str) -> str:
        raise ValueError("Tool failed")

    registry.register_tool(
        name="failing_tool",
        func=failing_tool,
        description="Failing tool",
        parameters=[
            ToolParameter(
                name="param",
                type=ParameterType.STRING,
                description="Parameter",
                required=True,
            ),
        ],
    )

    with pytest.raises(MCPToolExecutionFailed) as exc_info:
        await registry.execute_tool("failing_tool", {"param": "test"})

    assert "Tool failed" in str(exc_info.value)
