# MCP Server Module

The MCP (Model Context Protocol) server module provides a FastAPI-based HTTP API for exposing AMP functionality to Claude Code and other AI agents.

## Architecture

The MCP server consists of four main components:

1. **Server (`server.py`)** - FastAPI application with routes and middleware
2. **Protocol (`protocol.py`)** - Pydantic models for request/response schemas
3. **Tools (`tools.py`)** - Tool registry and execution engine
4. **Auth (`auth.py`)** - Authentication and request logging middleware

## Features

- **Tool Discovery** - List all available tools via `GET /tools`
- **Tool Execution** - Execute tools via `POST /tools/{tool_name}`
- **Health Check** - Server health status via `GET /health`
- **Authentication** - Token-based authentication (optional)
- **CORS Support** - Configurable CORS for cross-origin requests
- **Request Logging** - Automatic logging of all API requests
- **Error Handling** - Comprehensive error handling with detailed messages
- **Async Support** - Both sync and async tool functions supported

## Quick Start

### 1. Register Tools

```python
from amp.mcp.protocol import ParameterType, ToolParameter
from amp.mcp.tools import tool_registry

# Define a tool function
def create_tunnel(name: str, tunnel_type: str, local_port: int) -> dict:
    return {"tunnel_id": "abc123", "status": "active"}

# Register the tool
tool_registry.register_tool(
    name="create_tunnel",
    func=create_tunnel,
    description="Create a new network tunnel",
    parameters=[
        ToolParameter(
            name="name",
            type=ParameterType.STRING,
            description="Tunnel name",
            required=True,
        ),
        ToolParameter(
            name="tunnel_type",
            type=ParameterType.STRING,
            description="Tunnel type (chisel or ligolo)",
            required=True,
        ),
        ToolParameter(
            name="local_port",
            type=ParameterType.INTEGER,
            description="Local port to bind",
            required=True,
        ),
    ],
)
```

### 2. Start the Server

```bash
# Using uvicorn directly
uvicorn amp.mcp.server:create_app --factory --host 127.0.0.1 --port 8000

# Or with reload for development
uvicorn amp.mcp.server:create_app --factory --reload --host 127.0.0.1 --port 8000
```

### 3. Access the API

- **Health Check**: `GET http://127.0.0.1:8000/health`
- **List Tools**: `GET http://127.0.0.1:8000/tools`
- **Execute Tool**: `POST http://127.0.0.1:8000/tools/create_tunnel`
- **API Docs**: `http://127.0.0.1:8000/docs`

## Configuration

Configure the MCP server via environment variables or `.env` file:

```bash
# Server settings
AMP_MCP__HOST=127.0.0.1
AMP_MCP__PORT=8000

# Authentication (optional)
AMP_MCP__AUTH_TOKEN=your_secret_token_here

# CORS origins (comma-separated)
AMP_MCP__CORS_ORIGINS=*
```

## API Reference

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-05-07T12:00:00Z"
}
```

### List Tools

```http
GET /tools
```

**Response:**
```json
{
  "tools": [
    {
      "name": "create_tunnel",
      "description": "Create a new network tunnel",
      "parameters": [
        {
          "name": "name",
          "type": "string",
          "description": "Tunnel name",
          "required": true
        }
      ]
    }
  ],
  "count": 1
}
```

### Execute Tool

```http
POST /tools/{tool_name}
Content-Type: application/json

{
  "parameters": {
    "name": "dmz-tunnel",
    "tunnel_type": "chisel",
    "local_port": 8080
  }
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "tunnel_id": "abc123",
    "status": "active"
  },
  "error": null
}
```

## Authentication

When authentication is enabled, include the token in the `Authorization` header:

```http
Authorization: Bearer your_secret_token_here
```

Exempt paths (no authentication required):
- `/health`
- `/docs`
- `/redoc`
- `/openapi.json`

## Tool Development

### Synchronous Tools

```python
def my_tool(param1: str, param2: int) -> dict:
    """Synchronous tool function."""
    return {"result": f"{param1}-{param2}"}

tool_registry.register_tool(
    name="my_tool",
    func=my_tool,
    description="My synchronous tool",
    parameters=[...],
)
```

### Asynchronous Tools

```python
async def my_async_tool(param1: str) -> dict:
    """Asynchronous tool function."""
    await asyncio.sleep(1)
    return {"result": param1}

tool_registry.register_tool(
    name="my_async_tool",
    func=my_async_tool,
    description="My asynchronous tool",
    parameters=[...],
)
```

### Parameter Types

- `ParameterType.STRING` - String values
- `ParameterType.INTEGER` - Integer values
- `ParameterType.BOOLEAN` - Boolean values
- `ParameterType.OBJECT` - Dictionary/object values
- `ParameterType.ARRAY` - List/array values

### Optional Parameters

```python
ToolParameter(
    name="timeout",
    type=ParameterType.INTEGER,
    description="Timeout in seconds",
    required=False,
    default=30,
)
```

## Error Handling

The server returns appropriate HTTP status codes:

- `200 OK` - Successful request
- `400 Bad Request` - Invalid parameters or tool execution failed
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Invalid authentication token
- `404 Not Found` - Tool not found
- `500 Internal Server Error` - Unexpected server error

Error response format:
```json
{
  "error": "Error message",
  "details": {
    "additional": "context"
  }
}
```

## Testing

Run the test suite:

```bash
# Run all MCP tests
pytest amp/tests/unit/test_mcp_server.py amp/tests/unit/test_mcp_tools.py -v

# Run with coverage
pytest amp/tests/unit/test_mcp_server.py amp/tests/unit/test_mcp_tools.py --cov=amp/mcp
```

## Example

See `examples/mcp_server_example.py` for a complete working example.

## Integration with AMP

The MCP server is designed to integrate with other AMP components:

- **Tunnel Manager** - Expose tunnel creation/management tools
- **Shell Manager** - Expose shell session and command execution tools
- **Context Engine** - Expose context query and compression tools
- **Network Topology** - Expose network visualization and routing tools

Example integration:

```python
from amp.core.tunnel.manager import TunnelManager
from amp.storage.database import Database
from amp.mcp.tools import tool_registry

# Initialize managers
db = Database()
tunnel_manager = TunnelManager(db)

# Register tunnel tools
tool_registry.register_tool(
    name="create_tunnel",
    func=tunnel_manager.create_tunnel,
    description="Create a new network tunnel",
    parameters=[...],
)
```

## Security Considerations

1. **Authentication** - Always enable authentication in production
2. **CORS** - Restrict CORS origins to trusted domains
3. **Rate Limiting** - Consider enabling rate limiting for production
4. **Input Validation** - All parameters are validated before execution
5. **Error Messages** - Avoid exposing sensitive information in errors

## Performance

- Async tool execution for non-blocking operations
- Connection pooling for database operations
- Efficient parameter validation
- Minimal middleware overhead

## Troubleshooting

### Server won't start

Check that the port is not already in use:
```bash
lsof -i :8000
```

### Authentication fails

Verify the token is correctly set:
```bash
echo $AMP_MCP__AUTH_TOKEN
```

### Tool not found

List all registered tools:
```python
from amp.mcp.tools import tool_registry
print([t.name for t in tool_registry.list_tools()])
```

## License

MIT License - See LICENSE file for details.
