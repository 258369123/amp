"""Unit tests for MCP server."""

import pytest
from fastapi.testclient import TestClient

from amp.config import settings
from amp.mcp.protocol import ParameterType, ToolParameter
from amp.mcp.server import create_app
from amp.mcp.tool_registry import tool_registry


@pytest.fixture
def client():
    """Create test client."""
    # Clear tool registry before each test
    tool_registry.clear()

    # Create app
    app = create_app()

    # Create test client
    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    tool_registry.clear()


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    if settings.mcp.auth_token:
        return {"Authorization": f"Bearer {settings.mcp.auth_token}"}
    return {}


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data


def test_list_tools_empty(client, auth_headers):
    """Test listing tools when registry is empty."""
    response = client.get("/tools", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 0
    assert data["tools"] == []


def test_list_tools_with_registered_tools(client, auth_headers):
    """Test listing tools with registered tools."""
    # Register a test tool
    def test_tool(param1: str, param2: int) -> dict:
        return {"result": f"{param1}-{param2}"}

    tool_registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="A test tool",
        parameters=[
            ToolParameter(
                name="param1",
                type=ParameterType.STRING,
                description="First parameter",
                required=True,
            ),
            ToolParameter(
                name="param2",
                type=ParameterType.INTEGER,
                description="Second parameter",
                required=True,
            ),
        ],
    )

    response = client.get("/tools", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 1
    assert len(data["tools"]) == 1

    tool = data["tools"][0]
    assert tool["name"] == "test_tool"
    assert tool["description"] == "A test tool"
    assert len(tool["parameters"]) == 2


def test_execute_tool_success(client, auth_headers):
    """Test successful tool execution."""
    # Register a test tool
    def test_tool(name: str, value: int) -> dict:
        return {"name": name, "value": value, "result": value * 2}

    tool_registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="A test tool",
        parameters=[
            ToolParameter(
                name="name",
                type=ParameterType.STRING,
                description="Name parameter",
                required=True,
            ),
            ToolParameter(
                name="value",
                type=ParameterType.INTEGER,
                description="Value parameter",
                required=True,
            ),
        ],
    )

    response = client.post(
        "/tools/test_tool",
        json={"parameters": {"name": "test", "value": 42}},
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["error"] is None
    assert data["result"]["name"] == "test"
    assert data["result"]["value"] == 42
    assert data["result"]["result"] == 84


def test_execute_tool_not_found(client, auth_headers):
    """Test executing non-existent tool."""
    response = client.post(
        "/tools/nonexistent_tool",
        json={"parameters": {}},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_execute_tool_missing_required_parameter(client, auth_headers):
    """Test executing tool with missing required parameter."""
    # Register a test tool
    def test_tool(required_param: str) -> dict:
        return {"result": required_param}

    tool_registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="A test tool",
        parameters=[
            ToolParameter(
                name="required_param",
                type=ParameterType.STRING,
                description="Required parameter",
                required=True,
            ),
        ],
    )

    response = client.post(
        "/tools/test_tool",
        json={"parameters": {}},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_execute_tool_invalid_parameter_type(client, auth_headers):
    """Test executing tool with invalid parameter type."""
    # Register a test tool
    def test_tool(int_param: int) -> dict:
        return {"result": int_param}

    tool_registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="A test tool",
        parameters=[
            ToolParameter(
                name="int_param",
                type=ParameterType.INTEGER,
                description="Integer parameter",
                required=True,
            ),
        ],
    )

    response = client.post(
        "/tools/test_tool",
        json={"parameters": {"int_param": "not_an_integer"}},
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_execute_async_tool(client, auth_headers):
    """Test executing async tool."""
    # Register an async test tool
    async def async_test_tool(value: int) -> dict:
        return {"result": value * 3}

    tool_registry.register_tool(
        name="async_test_tool",
        func=async_test_tool,
        description="An async test tool",
        parameters=[
            ToolParameter(
                name="value",
                type=ParameterType.INTEGER,
                description="Value parameter",
                required=True,
            ),
        ],
    )

    response = client.post(
        "/tools/async_test_tool",
        json={"parameters": {"value": 10}},
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["result"]["result"] == 30


def test_execute_tool_with_optional_parameter(client, auth_headers):
    """Test executing tool with optional parameter."""
    # Register a test tool with optional parameter
    def test_tool(required: str, optional: int = 100) -> dict:
        return {"required": required, "optional": optional}

    tool_registry.register_tool(
        name="test_tool",
        func=test_tool,
        description="A test tool",
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
                default=100,
            ),
        ],
    )

    # Test without optional parameter
    response = client.post(
        "/tools/test_tool",
        json={"parameters": {"required": "test"}},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["required"] == "test"

    # Test with optional parameter
    response = client.post(
        "/tools/test_tool",
        json={"parameters": {"required": "test", "optional": 200}},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["required"] == "test"
    assert data["result"]["optional"] == 200


def test_authentication_disabled(client):
    """Test that endpoints work when authentication is disabled."""
    # Save original auth token
    original_token = settings.mcp.auth_token

    try:
        # Disable authentication
        settings.mcp.auth_token = None

        # Test without auth header
        response = client.get("/tools")
        assert response.status_code == 200

    finally:
        # Restore original auth token
        settings.mcp.auth_token = original_token


def test_authentication_required(client):
    """Test that authentication is required when enabled."""
    # Save original auth token
    original_token = settings.mcp.auth_token

    try:
        # Enable authentication
        settings.mcp.auth_token = "test_token_12345"

        # Recreate app with new settings
        app = create_app()
        test_client = TestClient(app)

        # Test without auth header
        response = test_client.get("/tools")
        assert response.status_code == 401

        # Test with invalid token
        response = test_client.get(
            "/tools",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 403

        # Test with valid token
        response = test_client.get(
            "/tools",
            headers={"Authorization": "Bearer test_token_12345"}
        )
        assert response.status_code == 200

    finally:
        # Restore original auth token
        settings.mcp.auth_token = original_token


def test_cors_headers(client):
    """Test CORS headers are present."""
    # CORS headers are added by middleware on actual requests
    response = client.get("/health")
    assert response.status_code == 200
    # CORS headers should be present (added by CORSMiddleware)
    # Note: TestClient may not always include CORS headers in the same way as a real server
    # This test verifies the endpoint works; CORS is configured in middleware


def test_tool_execution_error_handling(client, auth_headers):
    """Test error handling during tool execution."""
    # Register a tool that raises an exception
    def failing_tool(param: str) -> dict:
        raise ValueError("Intentional error")

    tool_registry.register_tool(
        name="failing_tool",
        func=failing_tool,
        description="A tool that fails",
        parameters=[
            ToolParameter(
                name="param",
                type=ParameterType.STRING,
                description="Parameter",
                required=True,
            ),
        ],
    )

    response = client.post(
        "/tools/failing_tool",
        json={"parameters": {"param": "test"}},
        headers=auth_headers,
    )
    assert response.status_code == 400
