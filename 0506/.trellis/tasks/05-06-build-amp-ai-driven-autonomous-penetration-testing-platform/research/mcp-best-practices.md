# Research: MCP Best Practices

- **Query**: MCP (Model Context Protocol) best practices for building MCP servers that integrate with Claude Code
- **Scope**: External knowledge + protocol specifications
- **Date**: 2026-05-06

## Overview of MCP Protocol

The Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to Large Language Models (LLMs). It enables AI assistants like Claude Code to securely interact with external tools, data sources, and services through a client-server architecture.

### Core Concepts

**Architecture**: MCP uses a client-server model where:
- **MCP Host**: The application embedding the LLM (e.g., Claude Code CLI)
- **MCP Client**: Protocol client inside the host that maintains 1:1 server connections
- **MCP Server**: Lightweight programs that expose specific capabilities via standardized protocol
- **Local Data Sources**: Resources that MCP servers can securely access

**Communication**: MCP servers communicate via JSON-RPC 2.0 over stdio (standard input/output) or HTTP with Server-Sent Events (SSE).

**Key Features**:
- **Tools**: Expose executable functions that the LLM can invoke
- **Resources**: Provide data/content that the LLM can read (files, API data, database records)
- **Prompts**: Pre-written prompt templates with arguments
- **Sampling**: Allow servers to request LLM completions through the client

// __CONTINUE_HERE__

## Architecture Patterns

### 1. Server Structure

**Single Responsibility Principle**: Each MCP server should focus on one domain or capability set.
- Good: `mcp-server-filesystem` (file operations only)
- Good: `mcp-server-postgres` (database operations only)
- Bad: `mcp-server-everything` (files + database + network + shell)

**Recommended Project Structure**:
```
mcp-server-name/
├── src/
│   ├── index.ts/main.py          # Entry point, server initialization
│   ├── tools/                     # Tool implementations
│   │   ├── tool1.ts
│   │   └── tool2.ts
│   ├── resources/                 # Resource providers (optional)
│   ├── prompts/                   # Prompt templates (optional)
│   └── utils/                     # Shared utilities
├── tests/
├── package.json/pyproject.toml
└── README.md
```

### 2. Connection Modes

**stdio (Standard Input/Output)**:
- **Use case**: Local servers, command-line tools, trusted environments
- **Pros**: Simple, no network overhead, automatic process lifecycle
- **Cons**: Single connection only, no remote access
- **Security**: Inherits parent process permissions

**HTTP + SSE (Server-Sent Events)**:
- **Use case**: Remote servers, multi-client scenarios, web services
- **Pros**: Multiple connections, network-accessible, standard HTTP tooling
- **Cons**: More complex setup, requires authentication layer
- **Security**: Must implement authentication, TLS, CORS policies

**Recommendation for AMP**: Use stdio for local MCP server (simpler, more secure for single-user deployment).

### 3. State Management

**Stateless vs Stateful**:
- **Stateless**: Each tool call is independent (e.g., file read, API query)
- **Stateful**: Server maintains session state (e.g., database connections, tunnel sessions)

**For Stateful Servers** (like AMP):
- Store state in persistent storage (SQLite, Redis)
- Implement session recovery on restart
- Clean up resources on shutdown (use signal handlers)
- Provide tools to query current state (`get_tunnels`, `list_shells`)


### 4. Error Handling Strategy

**Error Categories**:
1. **Validation Errors**: Invalid parameters, missing required fields
2. **Execution Errors**: Tool execution failed (network timeout, command error)
3. **System Errors**: Server internal errors (database connection lost)

**Best Practices**:
- Return structured error responses with error codes
- Include actionable error messages (what went wrong + how to fix)
- Log errors internally but sanitize sensitive data in responses
- Use exponential backoff for retryable operations
- Implement circuit breakers for external dependencies

**Example Error Response**:
```json
{
  "error": {
    "code": "TUNNEL_CONNECTION_FAILED",
    "message": "Failed to establish tunnel to 192.168.1.10:8080",
    "details": "Connection timeout after 30s",
    "retryable": true,
    "suggested_action": "Check if target host is reachable and port is open"
  }
}
```

### 5. Concurrency Model

**For Python MCP Servers**:
- Use `asyncio` for I/O-bound operations (network, file I/O)
- Use `ThreadPoolExecutor` for CPU-bound operations
- Implement proper locking for shared state (tunnels, shells)
- Set resource limits (max concurrent operations)

**For TypeScript MCP Servers**:
- Use async/await for all I/O operations
- Implement request queuing for rate-limited operations
- Use worker threads for CPU-intensive tasks


## Tool Design Guidelines

### 1. Tool Naming Conventions

**Format**: `verb_noun` or `verb_noun_modifier`
- Good: `create_tunnel`, `execute_command`, `list_shells`, `get_tunnel_status`
- Bad: `tunnel`, `cmd`, `do_stuff`, `helper_function_1`

**Consistency**: Use consistent verb patterns across related tools
- Create/Delete: `create_tunnel` / `delete_tunnel`
- Get/List: `get_tunnel` (single) / `list_tunnels` (multiple)
- Start/Stop: `start_shell` / `stop_shell`

### 2. Parameter Design

**Required vs Optional**:
- Mark parameters as required only if truly necessary
- Provide sensible defaults for optional parameters
- Use enums for parameters with fixed choices

**Parameter Validation**:
- Validate all inputs before execution
- Return validation errors immediately (don't start execution)
- Use JSON Schema for complex parameter structures

**Example Tool Schema**:
```json
{
  "name": "create_tunnel",
  "description": "Create a network tunnel using Chisel or Ligolo-ng",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target_host": {
        "type": "string",
        "description": "Target host IP or hostname",
        "pattern": "^[a-zA-Z0-9.-]+$"
      },
      "target_port": {
        "type": "integer",
        "description": "Target port number",
        "minimum": 1,
        "maximum": 65535
      },
      "tunnel_type": {
        "type": "string",
        "enum": ["chisel", "ligolo"],
        "default": "chisel",
        "description": "Tunnel technology to use"
      },
      "local_port": {
        "type": "integer",
        "description": "Local port for tunnel (auto-assigned if not specified)",
        "minimum": 1024,
        "maximum": 65535
      }
    },
    "required": ["target_host", "target_port"]
  }
}
```

### 3. Response Design

**Structured Responses**: Always return structured data (JSON), not plain text
- Include operation status (success/failure)
- Return relevant identifiers (tunnel_id, shell_id)
- Include metadata (timestamp, duration, resource usage)

**Example Response**:
```json
{
  "success": true,
  "tunnel_id": "tunnel_abc123",
  "local_port": 8080,
  "target": "192.168.1.10:22",
  "status": "connected",
  "created_at": "2026-05-06T10:30:00Z",
  "metadata": {
    "tunnel_type": "chisel",
    "connection_time_ms": 1250
  }
}
```


### 4. Timeout Handling

**Set Appropriate Timeouts**:
- Short operations (< 5s): File reads, database queries
- Medium operations (5-30s): Network requests, command execution
- Long operations (30s-5min): Network scans, large file transfers
- Very long operations (> 5min): Consider breaking into smaller tasks or using async patterns

**Timeout Strategies**:
1. **Hard timeout**: Kill operation after timeout (use for safety)
2. **Soft timeout**: Return partial results after timeout (use for scans)
3. **Progress updates**: Stream progress for long operations (if MCP supports)

**Implementation Pattern**:
```python
import asyncio

async def execute_command_with_timeout(cmd: str, timeout: int = 30):
    try:
        result = await asyncio.wait_for(
            run_command(cmd),
            timeout=timeout
        )
        return {"success": True, "output": result}
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "TIMEOUT",
            "message": f"Command exceeded {timeout}s timeout"
        }
```

### 5. Streaming Responses

**When to Stream**:
- Long-running operations with incremental output (shell commands, scans)
- Large data transfers (file downloads, log tails)
- Real-time monitoring (tunnel status, shell output)

**MCP Streaming Support**:
- MCP protocol supports streaming via Server-Sent Events (SSE) in HTTP mode
- stdio mode: Return chunked responses or use progress callbacks

**Pattern for Long Operations**:
```python
# Option 1: Return operation ID, provide separate status tool
{
  "operation_id": "scan_xyz789",
  "status": "running",
  "message": "Use get_operation_status(operation_id) to check progress"
}

# Option 2: Return final result with summary
{
  "success": true,
  "duration_seconds": 45,
  "results_summary": "Found 12 hosts, 45 open ports",
  "full_results": {...}
}
```

### 6. Idempotency

**Design Idempotent Tools** where possible:
- `create_tunnel(host, port)` → if tunnel exists, return existing tunnel_id
- `delete_tunnel(tunnel_id)` → if already deleted, return success
- `execute_command(shell_id, cmd)` → each execution is unique (not idempotent by nature)

**Benefits**:
- Safer retries on network failures
- Easier for LLM to reason about (can retry without side effects)
- Reduces error handling complexity


## Handling Long-Running Operations

### Pattern 1: Synchronous with Timeout
**Use case**: Operations that complete within 30-60 seconds
```python
async def scan_network(target: str, timeout: int = 60):
    result = await asyncio.wait_for(nmap_scan(target), timeout=timeout)
    return result
```
**Pros**: Simple, immediate results
**Cons**: Blocks tool call, may timeout

### Pattern 2: Async with Operation ID
**Use case**: Operations that take minutes or hours
```python
# Tool 1: Start operation
async def start_network_scan(target: str):
    operation_id = generate_id()
    asyncio.create_task(run_scan_background(operation_id, target))
    return {"operation_id": operation_id, "status": "started"}

# Tool 2: Check status
async def get_operation_status(operation_id: str):
    status = await db.get_operation(operation_id)
    return {"status": status.state, "progress": status.progress}
```
**Pros**: Non-blocking, supports very long operations
**Cons**: Requires multiple tool calls, more complex state management

### Pattern 3: Callback/Webhook (HTTP mode only)
**Use case**: Operations where client needs real-time updates
```python
async def start_scan_with_callback(target: str, callback_url: str):
    operation_id = generate_id()
    asyncio.create_task(run_scan_with_updates(operation_id, target, callback_url))
    return {"operation_id": operation_id}
```
**Pros**: Real-time updates, efficient
**Cons**: Only works in HTTP mode, requires callback endpoint

**Recommendation for AMP**: Use Pattern 2 (async with operation ID) for network scans and long-running commands.

## Security Considerations

### 1. Input Validation

**Prevent Command Injection**:
```python
# BAD: Direct string interpolation
cmd = f"ping {user_input}"  # Vulnerable to injection

# GOOD: Use parameterized commands or allowlists
import shlex
cmd = ["ping", "-c", "4", shlex.quote(user_input)]
```

**Validate IP Addresses and Hostnames**:
```python
import ipaddress
import re

def validate_host(host: str) -> bool:
    # Try parsing as IP
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    
    # Validate hostname format
    hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    return bool(re.match(hostname_pattern, host))
```

### 2. Authentication & Authorization

**For stdio mode** (AMP use case):
- Authentication inherited from parent process (Claude Code CLI)
- No additional auth needed (single-user, local deployment)
- Use file system permissions to protect state files

**For HTTP mode**:
- Implement token-based authentication (Bearer tokens)
- Use TLS for all connections
- Implement rate limiting per client
- Consider OAuth2 for multi-user scenarios


### 3. Resource Limits

**Prevent Resource Exhaustion**:
```python
class ResourceLimits:
    MAX_CONCURRENT_TUNNELS = 20
    MAX_CONCURRENT_SHELLS = 50
    MAX_COMMAND_OUTPUT_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_OPERATION_DURATION = 3600  # 1 hour
    
    @staticmethod
    async def check_tunnel_limit():
        active_tunnels = await db.count_active_tunnels()
        if active_tunnels >= ResourceLimits.MAX_CONCURRENT_TUNNELS:
            raise ResourceLimitError("Maximum tunnel limit reached")
```

**Implement Cleanup**:
- Automatic cleanup of stale resources (tunnels inactive > 1 hour)
- Graceful shutdown handler to close all connections
- Zombie process detection and termination

### 4. Secrets Management

**Never Log Secrets**:
```python
# BAD
logger.info(f"Connecting with password: {password}")

# GOOD
logger.info("Connecting to database (credentials redacted)")
```

**Store Secrets Securely**:
- Use environment variables for API keys, tokens
- Encrypt sensitive data in SQLite (use SQLCipher or application-level encryption)
- Never return secrets in tool responses

### 5. Sandboxing & Isolation

**For AMP (Docker-based isolation)**:
- Run MCP server inside Docker container
- Use network namespaces to isolate tunnel traffic
- Mount only necessary directories (read-only where possible)
- Drop unnecessary capabilities (CAP_NET_ADMIN only if needed)

**Docker Compose Example**:
```yaml
services:
  amp-mcp-server:
    image: amp-mcp:latest
    cap_drop:
      - ALL
    cap_add:
      - NET_ADMIN  # Required for tunnel management
    read_only: true
    volumes:
      - ./data:/data  # State persistence
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
```

## Reference Implementations

### Well-Designed MCP Servers

1. **@modelcontextprotocol/server-filesystem** (TypeScript)
   - **Domain**: File system operations
   - **Tools**: read_file, write_file, list_directory, search_files
   - **Strengths**: Clean parameter validation, comprehensive error handling
   - **Link**: https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem

2. **@modelcontextprotocol/server-postgres** (TypeScript)
   - **Domain**: PostgreSQL database operations
   - **Tools**: query, list_tables, describe_table
   - **Strengths**: Connection pooling, SQL injection prevention, transaction support
   - **Link**: https://github.com/modelcontextprotocol/servers/tree/main/src/postgres

3. **@modelcontextprotocol/server-brave-search** (TypeScript)
   - **Domain**: Web search via Brave Search API
   - **Tools**: brave_web_search, brave_local_search
   - **Strengths**: API key management, rate limiting, structured results
   - **Link**: https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search


4. **mcp-server-docker** (Python)
   - **Domain**: Docker container management
   - **Tools**: list_containers, start_container, stop_container, exec_command
   - **Strengths**: Async operations, resource cleanup, status monitoring
   - **Relevance**: Similar to AMP's shell/tunnel management patterns

5. **mcp-server-kubernetes** (Python)
   - **Domain**: Kubernetes cluster operations
   - **Tools**: get_pods, apply_manifest, get_logs
   - **Strengths**: Long-running operation handling, streaming logs
   - **Relevance**: Good patterns for infrastructure automation

### Python MCP SDK Examples

**Basic Server Setup**:
```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("amp-mcp-server")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_tunnel",
            description="Create a network tunnel to a target host",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_host": {"type": "string"},
                    "target_port": {"type": "integer"}
                },
                "required": ["target_host", "target_port"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "create_tunnel":
        result = await create_tunnel_impl(
            arguments["target_host"],
            arguments["target_port"]
        )
        return [TextContent(type="text", text=json.dumps(result))]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**Error Handling Pattern**:
```python
from mcp.types import TextContent
import json

async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        # Validate inputs
        validate_tool_arguments(name, arguments)
        
        # Execute tool
        result = await execute_tool(name, arguments)
        
        # Return success response
        return [TextContent(
            type="text",
            text=json.dumps({"success": True, "data": result})
        )]
        
    except ValidationError as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": str(e)
            })
        )]
    except TimeoutError as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "TIMEOUT",
                "message": "Operation timed out",
                "retryable": True
            })
        )]
    except Exception as e:
        logger.exception("Unexpected error in tool execution")
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            })
        )]
```


## AMP-Specific Recommendations

### 1. Tool Design for AMP

**Core Tools** (7 tools as per PRD):

1. **create_tunnel**
   - Parameters: target_host, target_port, tunnel_type (chisel/ligolo), local_port (optional)
   - Returns: tunnel_id, local_port, status
   - Idempotent: Yes (return existing if duplicate)

2. **execute_command**
   - Parameters: shell_id, command, timeout (default 30s)
   - Returns: exit_code, stdout, stderr, duration
   - Idempotent: No (each execution is unique)

3. **get_context**
   - Parameters: task_type (optional), max_tokens (default 8000)
   - Returns: network_topology, active_tunnels, active_shells, relevant_history
   - Idempotent: Yes (read-only)

4. **scan_network**
   - Parameters: target, scan_type (quick/full), timeout (default 300s)
   - Returns: operation_id (for async pattern)
   - Follow-up: get_operation_status(operation_id)

5. **create_shell**
   - Parameters: target_host, target_port, shell_type (reverse/bind/ssh), tunnel_id (optional)
   - Returns: shell_id, status, connection_info
   - Idempotent: No (each shell is unique)

6. **upload_file**
   - Parameters: shell_id, local_path, remote_path, timeout (default 60s)
   - Returns: success, bytes_transferred, duration
   - Idempotent: Yes (overwrite if exists)

7. **visualize_topology**
   - Parameters: format (mermaid/json)
   - Returns: topology_diagram (Mermaid syntax or JSON graph)
   - Idempotent: Yes (read-only)

### 2. State Management for AMP

**SQLite Schema Design**:
```sql
CREATE TABLE tunnels (
    tunnel_id TEXT PRIMARY KEY,
    target_host TEXT NOT NULL,
    target_port INTEGER NOT NULL,
    local_port INTEGER NOT NULL,
    tunnel_type TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'connected', 'disconnected', 'error'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_health_check TIMESTAMP,
    parent_tunnel_id TEXT,  -- For nested tunnels
    FOREIGN KEY (parent_tunnel_id) REFERENCES tunnels(tunnel_id)
);

CREATE TABLE shells (
    shell_id TEXT PRIMARY KEY,
    target_host TEXT NOT NULL,
    shell_type TEXT NOT NULL,
    tunnel_id TEXT,
    status TEXT NOT NULL,
    working_directory TEXT,
    environment TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP,
    FOREIGN KEY (tunnel_id) REFERENCES tunnels(tunnel_id)
);

CREATE TABLE operations (
    operation_id TEXT PRIMARY KEY,
    operation_type TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    progress INTEGER DEFAULT 0,
    result TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 3. Context Engine Integration

**Progressive Disclosure Pattern**:
```python
async def get_context(task_type: str = None, max_tokens: int = 8000):
    # 1. Always include: Current network topology summary
    topology = await build_topology_summary()
    
    # 2. Filter tunnels/shells by relevance
    if task_type == "lateral_movement":
        relevant_tunnels = await get_tunnels_to_internal_network()
        relevant_shells = await get_shells_with_high_privilege()
    else:
        relevant_tunnels = await get_active_tunnels(limit=5)
        relevant_shells = await get_active_shells(limit=5)
    
    # 3. Retrieve relevant history from ChromaDB
    if task_type:
        history = await vector_search(task_type, limit=3)
    else:
        history = []
    
    # 4. Assemble context and compress if needed
    context = {
        "topology": topology,
        "tunnels": relevant_tunnels,
        "shells": relevant_shells,
        "history": history
    }
    
    # 5. Token-based compression
    context_text = json.dumps(context)
    if count_tokens(context_text) > max_tokens:
        context = compress_context(context, max_tokens)
    
    return context
```


### 4. Health Monitoring & Recovery

**Tunnel Health Check Pattern**:
```python
import asyncio

async def tunnel_health_monitor():
    """Background task to monitor tunnel health"""
    while True:
        tunnels = await db.get_active_tunnels()
        
        for tunnel in tunnels:
            try:
                # Check if tunnel is responsive
                is_alive = await check_tunnel_connection(tunnel.tunnel_id)
                
                if not is_alive:
                    logger.warning(f"Tunnel {tunnel.tunnel_id} is down, attempting recovery")
                    await recover_tunnel(tunnel)
                else:
                    await db.update_tunnel_health(tunnel.tunnel_id)
                    
            except Exception as e:
                logger.error(f"Health check failed for {tunnel.tunnel_id}: {e}")
        
        await asyncio.sleep(30)  # Check every 30 seconds

async def recover_tunnel(tunnel):
    """Attempt to recover a failed tunnel"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await recreate_tunnel(tunnel)
            logger.info(f"Tunnel {tunnel.tunnel_id} recovered on attempt {attempt + 1}")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"Failed to recover tunnel {tunnel.tunnel_id} after {max_retries} attempts")
                await db.update_tunnel_status(tunnel.tunnel_id, "error")
```

### 5. Logging & Observability

**Structured Logging**:
```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
    def log_tool_call(self, tool_name: str, arguments: dict, result: dict, duration_ms: float):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "tool_call",
            "tool_name": tool_name,
            "arguments": self._sanitize(arguments),
            "success": result.get("success", False),
            "duration_ms": duration_ms
        }
        self.logger.info(json.dumps(log_entry))
    
    def _sanitize(self, data: dict) -> dict:
        """Remove sensitive fields from logs"""
        sensitive_keys = ["password", "token", "api_key", "secret"]
        sanitized = data.copy()
        for key in sensitive_keys:
            if key in sanitized:
                sanitized[key] = "***REDACTED***"
        return sanitized
```

## Testing Strategies

### 1. Unit Tests

**Test Tool Parameter Validation**:
```python
import pytest

@pytest.mark.asyncio
async def test_create_tunnel_validation():
    # Test missing required parameter
    with pytest.raises(ValidationError):
        await create_tunnel(target_host="192.168.1.10")  # Missing target_port
    
    # Test invalid port range
    with pytest.raises(ValidationError):
        await create_tunnel(target_host="192.168.1.10", target_port=70000)
    
    # Test invalid host format
    with pytest.raises(ValidationError):
        await create_tunnel(target_host="invalid host!", target_port=22)
```

### 2. Integration Tests

**Test End-to-End Workflow**:
```python
@pytest.mark.asyncio
async def test_tunnel_shell_command_workflow():
    # 1. Create tunnel
    tunnel_result = await create_tunnel(
        target_host="test-target",
        target_port=22
    )
    assert tunnel_result["success"]
    tunnel_id = tunnel_result["tunnel_id"]
    
    # 2. Create shell through tunnel
    shell_result = await create_shell(
        target_host="test-target",
        target_port=22,
        shell_type="ssh",
        tunnel_id=tunnel_id
    )
    assert shell_result["success"]
    shell_id = shell_result["shell_id"]
    
    # 3. Execute command
    cmd_result = await execute_command(
        shell_id=shell_id,
        command="whoami"
    )
    assert cmd_result["success"]
    assert cmd_result["exit_code"] == 0
    
    # 4. Cleanup
    await delete_shell(shell_id)
    await delete_tunnel(tunnel_id)
```


### 3. Mock Testing

**Mock External Dependencies**:
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
@patch('amp.tunnel.chisel.ChiselClient')
async def test_create_tunnel_with_mock(mock_chisel):
    # Setup mock
    mock_instance = AsyncMock()
    mock_instance.connect.return_value = True
    mock_chisel.return_value = mock_instance
    
    # Test
    result = await create_tunnel(target_host="192.168.1.10", target_port=22)
    
    # Verify
    assert result["success"]
    mock_instance.connect.assert_called_once()
```

## Performance Optimization

### 1. Connection Pooling

**Reuse Connections**:
```python
from asyncio import Queue

class ShellPool:
    def __init__(self, max_size: int = 10):
        self.pool: Queue = Queue(maxsize=max_size)
        self.active_connections = {}
    
    async def get_shell(self, shell_id: str):
        if shell_id in self.active_connections:
            return self.active_connections[shell_id]
        
        # Create new shell if not in pool
        shell = await create_new_shell(shell_id)
        self.active_connections[shell_id] = shell
        return shell
    
    async def release_shell(self, shell_id: str):
        if shell_id in self.active_connections:
            shell = self.active_connections.pop(shell_id)
            await shell.close()
```

### 2. Caching

**Cache Expensive Operations**:
```python
from functools import lru_cache
import asyncio

class ContextCache:
    def __init__(self, ttl: int = 60):
        self.cache = {}
        self.ttl = ttl
    
    async def get_topology(self) -> dict:
        cache_key = "topology"
        
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.ttl:
                return cached_data
        
        # Compute fresh data
        topology = await build_topology()
        self.cache[cache_key] = (topology, time.time())
        return topology
```

## Documentation Best Practices

### 1. Tool Documentation

**Each tool should have**:
- Clear description (what it does, when to use it)
- Parameter descriptions with types and constraints
- Example usage
- Error conditions and how to handle them

**Example**:
```markdown
### create_tunnel

Create a network tunnel to a target host using Chisel or Ligolo-ng.

**Parameters**:
- `target_host` (string, required): Target host IP address or hostname
- `target_port` (integer, required): Target port number (1-65535)
- `tunnel_type` (string, optional): Tunnel technology ("chisel" or "ligolo"), default: "chisel"
- `local_port` (integer, optional): Local port for tunnel (auto-assigned if not specified)

**Returns**:
```json
{
  "success": true,
  "tunnel_id": "tunnel_abc123",
  "local_port": 8080,
  "target": "192.168.1.10:22",
  "status": "connected"
}
```

**Example Usage**:
```python
# Create a tunnel to SSH port
result = await create_tunnel(
    target_host="192.168.1.10",
    target_port=22
)
tunnel_id = result["tunnel_id"]
```

**Error Conditions**:
- `VALIDATION_ERROR`: Invalid parameters (check host format and port range)
- `CONNECTION_FAILED`: Cannot reach target (check network connectivity)
- `RESOURCE_LIMIT`: Maximum tunnel limit reached (close unused tunnels)
```

### 2. README Structure

**Essential sections**:
1. Overview (what the server does)
2. Installation (dependencies, setup)
3. Configuration (environment variables, config files)
4. Available Tools (list with brief descriptions)
5. Usage Examples (common workflows)
6. Troubleshooting (common issues and solutions)
7. Security Considerations
8. Contributing Guidelines


## Key Takeaways for AMP Implementation

### Architecture Decisions

1. **Connection Mode**: Use stdio (simpler, more secure for single-user local deployment)
2. **State Management**: Stateful server with SQLite persistence and session recovery
3. **Long Operations**: Use async pattern with operation IDs for network scans
4. **Error Handling**: Structured errors with codes, messages, and retry guidance
5. **Resource Limits**: Enforce max 20 tunnels, 50 shells, with automatic cleanup

### Tool Design Principles

1. **Naming**: Use verb_noun pattern (create_tunnel, execute_command)
2. **Parameters**: Validate all inputs, provide sensible defaults
3. **Responses**: Return structured JSON with success status and metadata
4. **Idempotency**: Make tools idempotent where possible (create_tunnel, upload_file)
5. **Timeouts**: Set appropriate timeouts (5s for quick ops, 30s for commands, 5min for scans)

### Security Requirements

1. **Input Validation**: Prevent command injection, validate IPs/hostnames
2. **Secrets Management**: Never log secrets, use environment variables
3. **Resource Limits**: Prevent exhaustion with max concurrent operations
4. **Isolation**: Run in Docker with minimal capabilities
5. **Logging**: Structured logs with sensitive data redacted

### Implementation Priorities

1. **Phase 1**: Basic MCP server setup with stdio transport
2. **Phase 2**: Implement core tools (create_tunnel, execute_command, get_context)
3. **Phase 3**: Add state persistence and health monitoring
4. **Phase 4**: Implement async operations for long-running tasks
5. **Phase 5**: Add comprehensive error handling and recovery

## External References

### Official Documentation

- **MCP Specification**: https://spec.modelcontextprotocol.io/
  - Protocol overview, message formats, transport layers
  
- **MCP Python SDK**: https://github.com/modelcontextprotocol/python-sdk
  - Official Python implementation, examples, API reference
  
- **MCP TypeScript SDK**: https://github.com/modelcontextprotocol/typescript-sdk
  - Official TypeScript implementation (for reference)

### Reference Implementations

- **MCP Servers Repository**: https://github.com/modelcontextprotocol/servers
  - Collection of official MCP servers (filesystem, postgres, brave-search, etc.)
  - Best practices examples for tool design and error handling
  
- **Claude Code Documentation**: https://docs.anthropic.com/claude/docs/claude-code
  - Integration guide for MCP servers with Claude Code CLI
  - Configuration examples and troubleshooting

### Related Technologies

- **Chisel**: https://github.com/jpillora/chisel
  - Fast TCP/UDP tunnel over HTTP, secured via SSH
  
- **Ligolo-ng**: https://github.com/nicocha30/ligolo-ng
  - Advanced tunneling tool for penetration testing
  
- **tmux**: https://github.com/tmux/tmux
  - Terminal multiplexer for persistent shell sessions

## Caveats / Not Found

### Limitations of Current Research

1. **MCP Streaming**: Limited documentation on streaming responses in stdio mode (primarily documented for HTTP/SSE)
2. **Performance Benchmarks**: No official benchmarks for MCP server performance under load
3. **Multi-tenancy**: Limited guidance on multi-user MCP server patterns (most examples are single-user)
4. **Advanced Auth**: OAuth2/OIDC integration patterns not well documented for MCP servers

### Areas Requiring Further Investigation

1. **Context Window Management**: How Claude Code handles large tool responses (truncation behavior)
2. **Tool Call Limits**: Rate limits or concurrency limits for tool calls from Claude Code
3. **Error Recovery**: How Claude Code retries failed tool calls (automatic vs manual)
4. **State Synchronization**: Best practices for keeping MCP server state in sync with Claude Code's understanding

### Recommendations for Next Steps

1. Review official MCP Python SDK examples in detail
2. Study existing MCP servers (filesystem, postgres) for implementation patterns
3. Prototype basic MCP server with 2-3 tools to validate architecture
4. Test integration with Claude Code CLI to understand behavior
5. Document any gaps or issues discovered during implementation

---

**Research completed**: 2026-05-06
**Total sections**: 11 (Overview, Architecture, Tool Design, Long Operations, Security, Reference Implementations, AMP Recommendations, Testing, Performance, Documentation, Key Takeaways)
**External references**: 8 links to official docs and reference implementations
