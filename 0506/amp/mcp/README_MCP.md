# AMP MCP Server

This directory contains the MCP (Model Context Protocol) compliant server implementation for AMP.

## Overview

The MCP server replaces the REST API for Claude Code integration. It implements JSON-RPC 2.0 protocol over stdio transport, following the official MCP specification.

## Architecture

### Files

- **`mcp_server.py`** - Core MCP protocol server implementation
- **`mcp_tools.py`** - Tool adapter that converts AMP tools to MCP format
- **`run_mcp_server.py`** - Server startup script (entry point)
- **`server.py`** - FastAPI REST server (kept for Web UI only)
- **`tool_registry.py`** - Tool registration and management
- **`tools/`** - Individual tool implementations (17 tools total)

### Protocol

- **Transport**: stdio (standard input/output)
- **Protocol**: JSON-RPC 2.0
- **Format**: MCP Tool schema with JSON Schema for parameters

## Available Tools (17 Total)

### Tunnel Management (6 tools)
1. `create_tunnel` - Create a new network tunnel
2. `start_tunnel` - Start an existing tunnel
3. `stop_tunnel` - Stop a running tunnel
4. `delete_tunnel` - Delete a tunnel
5. `list_tunnels` - List all tunnels
6. `get_tunnel_status` - Get tunnel health status

### Shell Management (5 tools)
7. `create_shell` - Create a new shell session
8. `execute_command` - Execute command in shell
9. `close_shell` - Close shell session
10. `list_shells` - List all shells
11. `get_shell_status` - Get shell status

### Context Management (3 tools)
12. `get_relevant_operations` - Get relevant operation history
13. `build_prompt` - Build dynamic prompt with context
14. `compress_context` - Compress context to fit token budget

### Network Topology (3 tools)
15. `visualize_topology` - Generate network topology visualization
16. `find_route` - Find route between network segments
17. `get_affected_segments` - Get segments affected by tunnel failure

## Usage

### Starting the MCP Server

```bash
# Method 1: Using the entry point (after pip install)
amp-mcp

# Method 2: Direct Python execution
python -m amp.mcp.run_mcp_server

# Method 3: Using the script directly
python amp/mcp/run_mcp_server.py
```

### Testing with MCP Client

```bash
# Test initialize request
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python amp/mcp/run_mcp_server.py

# Test tools/list request
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python amp/mcp/run_mcp_server.py

# Test tools/call request
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_tunnels","arguments":{}}}' | python amp/mcp/run_mcp_server.py
```

### Integration with Claude Code

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "amp": {
      "command": "python",
      "args": ["-m", "amp.mcp.run_mcp_server"],
      "cwd": "/path/to/amp"
    }
  }
}
```

Or if installed via pip:

```json
{
  "mcpServers": {
    "amp": {
      "command": "amp-mcp"
    }
  }
}
```

## Configuration

The MCP server uses the same configuration as the REST API server:

- **Database**: Configured via `settings.database.url`
- **Logging**: Logs to `settings.logging.log_file` and stderr
- **Context**: Uses `settings.context.*` for token limits and compression

## Differences from REST API

| Aspect | REST API | MCP Server |
|--------|----------|------------|
| Protocol | HTTP/REST | JSON-RPC 2.0 |
| Transport | HTTP | stdio |
| Tool Format | Custom | MCP Tool schema |
| Response Format | JSON | TextContent |
| Authentication | Token-based | N/A (stdio is local) |
| Web UI | Included | Separate server |

## Web UI

The Web UI is still available via the FastAPI server:

```bash
# Start Web UI server (separate from MCP)
python amp/mcp/run_server.py

# Or using uvicorn
uvicorn amp.mcp.server:create_app --factory --host 127.0.0.1 --port 8000
```

Access at: http://127.0.0.1:8000

## Logging

Logs are written to:
- **File**: `settings.logging.log_file` (default: `data/logs/amp.log`)
- **stderr**: Console output (stdout is reserved for MCP protocol)

## Error Handling

All tool execution errors are returned as TextContent with JSON format:

```json
{
  "success": false,
  "error": "Error message",
  "error_type": "execution_error"
}
```

## Development

### Adding New Tools

1. Implement tool function in `amp/mcp/tools/`
2. Register in `amp/mcp/tools/registry.py`
3. Tool will automatically be exposed via MCP

### Testing

```bash
# Run unit tests
pytest amp/tests/unit/test_mcp_*.py

# Run integration tests
pytest amp/tests/integration/test_mcp_integration.py
```

## Troubleshooting

### Server won't start

- Check database path exists and is writable
- Check log file path is writable
- Verify all dependencies are installed: `pip install -e .`

### Tools not showing up

- Check logs for initialization errors
- Verify managers are initialized correctly
- Run with debug logging: `export LOG_LEVEL=DEBUG`

### Tool execution fails

- Check tool parameters match schema
- Verify managers (tunnel, shell) are initialized
- Check database connection

## References

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Claude Code Documentation](https://docs.anthropic.com/claude/docs)
