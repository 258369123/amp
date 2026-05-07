"""MCP tools for AMP platform."""

from amp.mcp.tools.context_tools import (
    build_prompt,
    compress_context,
    get_relevant_operations,
)
from amp.mcp.tools.network_tools import (
    find_route,
    get_affected_segments,
    visualize_topology,
)
from amp.mcp.tools.registry import initialize_managers, register_all_tools
from amp.mcp.tools.shell_tools import (
    close_shell,
    create_shell,
    execute_command,
    get_shell_status,
    list_shells,
)
from amp.mcp.tools.tunnel_tools import (
    create_tunnel,
    delete_tunnel,
    get_tunnel_status,
    list_tunnels,
    start_tunnel,
    stop_tunnel,
)

__all__ = [
    # Registry
    "initialize_managers",
    "register_all_tools",
    # Tunnel tools
    "create_tunnel",
    "start_tunnel",
    "stop_tunnel",
    "delete_tunnel",
    "list_tunnels",
    "get_tunnel_status",
    # Shell tools
    "create_shell",
    "execute_command",
    "close_shell",
    "list_shells",
    "get_shell_status",
    # Context tools
    "get_relevant_operations",
    "build_prompt",
    "compress_context",
    # Network tools
    "visualize_topology",
    "find_route",
    "get_affected_segments",
]
