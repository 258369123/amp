"""Example script demonstrating MCP server usage."""

import asyncio

from amp.mcp.protocol import ParameterType, ToolParameter
from amp.mcp.server import create_app
from amp.mcp.tools import tool_registry


# Example tool functions
def create_tunnel(
    name: str,
    tunnel_type: str,
    local_port: int,
    remote_host: str,
    remote_port: int,
) -> dict:
    """Example tunnel creation tool."""
    return {
        "tunnel_id": "example-123",
        "name": name,
        "tunnel_type": tunnel_type,
        "local_port": local_port,
        "remote_host": remote_host,
        "remote_port": remote_port,
        "status": "active",
    }


async def execute_command(shell_id: str, command: str, timeout: int = 30) -> dict:
    """Example command execution tool."""
    return {
        "operation_id": "op-456",
        "shell_id": shell_id,
        "command": command,
        "stdout": "Command output",
        "stderr": "",
        "exit_code": 0,
        "success": True,
    }


def get_network_topology() -> dict:
    """Example network topology tool."""
    return {
        "segments": [
            {"id": "external", "cidr": "0.0.0.0/0", "type": "external"},
            {"id": "dmz", "cidr": "192.168.1.0/24", "type": "dmz"},
        ],
        "tunnels": [
            {
                "id": "tunnel-1",
                "source": "external",
                "target": "dmz",
                "status": "active",
            }
        ],
    }


def register_example_tools() -> None:
    """Register example tools with the MCP server."""
    # Register create_tunnel tool
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
            ToolParameter(
                name="remote_host",
                type=ParameterType.STRING,
                description="Remote host to connect to",
                required=True,
            ),
            ToolParameter(
                name="remote_port",
                type=ParameterType.INTEGER,
                description="Remote port to connect to",
                required=True,
            ),
        ],
    )

    # Register execute_command tool
    tool_registry.register_tool(
        name="execute_command",
        func=execute_command,
        description="Execute a command in a shell session",
        parameters=[
            ToolParameter(
                name="shell_id",
                type=ParameterType.STRING,
                description="Shell session ID",
                required=True,
            ),
            ToolParameter(
                name="command",
                type=ParameterType.STRING,
                description="Command to execute",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type=ParameterType.INTEGER,
                description="Command timeout in seconds",
                required=False,
                default=30,
            ),
        ],
    )

    # Register get_network_topology tool
    tool_registry.register_tool(
        name="get_network_topology",
        func=get_network_topology,
        description="Get current network topology",
        parameters=[],
    )


def main() -> None:
    """Main function to demonstrate MCP server."""
    print("AMP MCP Server Example")
    print("=" * 50)

    # Register example tools
    print("\nRegistering example tools...")
    register_example_tools()

    # Create FastAPI app
    print("Creating FastAPI application...")
    app = create_app()

    # List registered tools
    tools = tool_registry.list_tools()
    print(f"\nRegistered {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
        if tool.parameters:
            print(f"    Parameters: {len(tool.parameters)}")
            for param in tool.parameters:
                req = "required" if param.required else "optional"
                print(f"      - {param.name} ({param.type}, {req}): {param.description}")

    print("\n" + "=" * 50)
    print("MCP Server is ready!")
    print("\nTo start the server, run:")
    print("  uvicorn amp.mcp.server:create_app --factory --host 127.0.0.1 --port 8000")
    print("\nAPI Documentation will be available at:")
    print("  http://127.0.0.1:8000/docs")
    print("\nExample API calls:")
    print("  GET  http://127.0.0.1:8000/health")
    print("  GET  http://127.0.0.1:8000/tools")
    print("  POST http://127.0.0.1:8000/tools/create_tunnel")


if __name__ == "__main__":
    main()
