"""Tool registry for MCP server - registers all AMP tools."""

import logging
from typing import Any

from amp.core.context.compression import ContextCompressor
from amp.core.context.prompt_builder import PromptBuilder
from amp.core.context.search import SimilaritySearch
from amp.core.context.vector_store import VectorStore
from amp.core.network.graph import NetworkGraph
from amp.core.network.router import RouteCalculator
from amp.core.network.visualizer import TopologyVisualizer
from amp.core.shell.manager import ShellManager
from amp.core.tunnel.manager import TunnelManager
from amp.mcp.protocol import ParameterType, ToolParameter
from amp.mcp.tool_registry import tool_registry
from amp.mcp.tools import context_tools, network_tools, shell_tools, tunnel_tools
from amp.storage.database import Database
from amp.web.api import set_web_components

logger = logging.getLogger(__name__)


def initialize_managers(database: Database) -> dict[str, Any]:
    """Initialize all manager instances.

    Args:
        database: Database instance

    Returns:
        Dictionary of initialized managers
    """
    # Initialize managers
    tunnel_manager = TunnelManager(database)
    shell_manager = ShellManager(database)

    # Initialize context components
    vector_store = VectorStore()
    similarity_search = SimilaritySearch(vector_store)
    prompt_builder = PromptBuilder(
        vector_store=vector_store,
        tunnel_manager=tunnel_manager,
        shell_manager=shell_manager,
    )
    context_compressor = ContextCompressor()

    # Initialize network components
    network_graph = NetworkGraph()
    topology_visualizer = TopologyVisualizer(network_graph)
    route_calculator = RouteCalculator(network_graph)

    return {
        "tunnel_manager": tunnel_manager,
        "shell_manager": shell_manager,
        "vector_store": vector_store,
        "similarity_search": similarity_search,
        "prompt_builder": prompt_builder,
        "context_compressor": context_compressor,
        "network_graph": network_graph,
        "topology_visualizer": topology_visualizer,
        "route_calculator": route_calculator,
    }


def register_all_tools(managers: dict[str, Any]) -> None:
    """Register all MCP tools.

    Args:
        managers: Dictionary of manager instances
    """
    # Set manager instances in tool modules
    tunnel_tools.set_tunnel_manager(managers["tunnel_manager"])
    shell_tools.set_shell_manager(managers["shell_manager"])
    context_tools.set_context_components(
        managers["similarity_search"],
        managers["prompt_builder"],
        managers["context_compressor"],
    )
    network_tools.set_network_components(
        managers["network_graph"],
        managers["topology_visualizer"],
        managers["route_calculator"],
    )

    # Set web components (for web UI API endpoints)
    set_web_components(
        database,
        managers["network_graph"],
        managers["topology_visualizer"],
        managers["route_calculator"],
    )

    # Register tunnel tools
    register_tunnel_tools()

    # Register shell tools
    register_shell_tools()

    # Register context tools
    register_context_tools()

    # Register network tools
    register_network_tools()

    logger.info(f"Registered {len(tool_registry.list_tools())} MCP tools")


def register_tunnel_tools() -> None:
    """Register tunnel management tools."""
    tool_registry.register_tool(
        name="create_tunnel",
        func=tunnel_tools.create_tunnel,
        description="Create a new network tunnel (chisel, ligolo, or ssh)",
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
                description="Tunnel type (chisel, ligolo, ssh)",
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
            ToolParameter(
                name="local_host",
                type=ParameterType.STRING,
                description="Local host to bind (default: 127.0.0.1)",
                required=False,
                default="127.0.0.1",
            ),
            ToolParameter(
                name="parent_id",
                type=ParameterType.STRING,
                description="Parent tunnel ID for nested tunnels",
                required=False,
            ),
            ToolParameter(
                name="config",
                type=ParameterType.OBJECT,
                description="Additional tunnel configuration",
                required=False,
            ),
        ],
    )

    tool_registry.register_tool(
        name="start_tunnel",
        func=tunnel_tools.start_tunnel,
        description="Start an existing tunnel",
        parameters=[
            ToolParameter(
                name="tunnel_id",
                type=ParameterType.STRING,
                description="Tunnel ID to start",
                required=True,
            ),
        ],
    )

    tool_registry.register_tool(
        name="stop_tunnel",
        func=tunnel_tools.stop_tunnel,
        description="Stop a running tunnel",
        parameters=[
            ToolParameter(
                name="tunnel_id",
                type=ParameterType.STRING,
                description="Tunnel ID to stop",
                required=True,
            ),
        ],
    )

    tool_registry.register_tool(
        name="delete_tunnel",
        func=tunnel_tools.delete_tunnel,
        description="Delete a tunnel (stops if running)",
        parameters=[
            ToolParameter(
                name="tunnel_id",
                type=ParameterType.STRING,
                description="Tunnel ID to delete",
                required=True,
            ),
        ],
    )

    tool_registry.register_tool(
        name="list_tunnels",
        func=tunnel_tools.list_tunnels,
        description="List all tunnels, optionally filtered by status",
        parameters=[
            ToolParameter(
                name="status",
                type=ParameterType.STRING,
                description="Optional status filter (active, disconnected, stopped)",
                required=False,
            ),
        ],
    )

    tool_registry.register_tool(
        name="get_tunnel_status",
        func=tunnel_tools.get_tunnel_status,
        description="Get tunnel health status and statistics",
        parameters=[
            ToolParameter(
                name="tunnel_id",
                type=ParameterType.STRING,
                description="Tunnel ID to check",
                required=True,
            ),
        ],
    )


def register_shell_tools() -> None:
    """Register shell management tools."""
    tool_registry.register_tool(
        name="create_shell",
        func=shell_tools.create_shell,
        description="Create a new shell session (reverse, bind, or ssh)",
        parameters=[
            ToolParameter(
                name="name",
                type=ParameterType.STRING,
                description="Shell name",
                required=True,
            ),
            ToolParameter(
                name="shell_type",
                type=ParameterType.STRING,
                description="Shell type (reverse, bind, ssh)",
                required=True,
            ),
            ToolParameter(
                name="target_host",
                type=ParameterType.STRING,
                description="Target host",
                required=True,
            ),
            ToolParameter(
                name="os_type",
                type=ParameterType.STRING,
                description="Operating system type (linux, windows)",
                required=False,
                default="linux",
            ),
            ToolParameter(
                name="tunnel_id",
                type=ParameterType.STRING,
                description="Tunnel ID if using tunnel",
                required=False,
            ),
            ToolParameter(
                name="local_port",
                type=ParameterType.INTEGER,
                description="Local port for reverse shells",
                required=False,
            ),
            ToolParameter(
                name="target_port",
                type=ParameterType.INTEGER,
                description="Target port for bind/ssh shells",
                required=False,
            ),
            ToolParameter(
                name="shell_program",
                type=ParameterType.STRING,
                description="Shell program (bash, sh, powershell, cmd)",
                required=False,
                default="bash",
            ),
            ToolParameter(
                name="username",
                type=ParameterType.STRING,
                description="Username for SSH shells",
                required=False,
            ),
            ToolParameter(
                name="password",
                type=ParameterType.STRING,
                description="Password for SSH shells",
                required=False,
            ),
            ToolParameter(
                name="key_path",
                type=ParameterType.STRING,
                description="SSH key path for SSH shells",
                required=False,
            ),
            ToolParameter(
                name="payload_type",
                type=ParameterType.STRING,
                description="Payload type for reverse shells",
                required=False,
            ),
            ToolParameter(
                name="use_tmux",
                type=ParameterType.BOOLEAN,
                description="Whether to use tmux for persistence",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="timeout",
                type=ParameterType.INTEGER,
                description="Connection timeout in seconds",
                required=False,
                default=30,
            ),
        ],
    )

    tool_registry.register_tool(
        name="execute_command",
        func=shell_tools.execute_command,
        description="Execute command in shell session",
        parameters=[
            ToolParameter(
                name="shell_id",
                type=ParameterType.STRING,
                description="Shell ID",
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
                description="Timeout in seconds",
                required=False,
                default=30,
            ),
        ],
    )

    tool_registry.register_tool(
        name="close_shell",
        func=shell_tools.close_shell,
        description="Close shell session",
        parameters=[
            ToolParameter(
                name="shell_id",
                type=ParameterType.STRING,
                description="Shell ID to close",
                required=True,
            ),
        ],
    )

    tool_registry.register_tool(
        name="list_shells",
        func=shell_tools.list_shells,
        description="List all shells, optionally filtered by status",
        parameters=[
            ToolParameter(
                name="status",
                type=ParameterType.STRING,
                description="Optional status filter (active, dead, zombie)",
                required=False,
            ),
        ],
    )

    tool_registry.register_tool(
        name="get_shell_status",
        func=shell_tools.get_shell_status,
        description="Get shell status and information",
        parameters=[
            ToolParameter(
                name="shell_id",
                type=ParameterType.STRING,
                description="Shell ID to check",
                required=True,
            ),
        ],
    )


def register_context_tools() -> None:
    """Register context query tools."""
    tool_registry.register_tool(
        name="get_relevant_operations",
        func=context_tools.get_relevant_operations,
        description="Get relevant operation history based on query",
        parameters=[
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="Query text to search for",
                required=True,
            ),
            ToolParameter(
                name="shell_id",
                type=ParameterType.STRING,
                description="Optional shell ID filter",
                required=False,
            ),
            ToolParameter(
                name="tunnel_id",
                type=ParameterType.STRING,
                description="Optional tunnel ID filter",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type=ParameterType.INTEGER,
                description="Maximum number of operations to return",
                required=False,
                default=10,
            ),
            ToolParameter(
                name="threshold",
                type=ParameterType.INTEGER,
                description="Minimum similarity threshold (0-1)",
                required=False,
                default=0.5,
            ),
        ],
    )

    tool_registry.register_tool(
        name="build_prompt",
        func=context_tools.build_prompt,
        description="Build dynamic prompt with context for Claude Code",
        parameters=[
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="Current task/query",
                required=True,
            ),
            ToolParameter(
                name="shell_id",
                type=ParameterType.STRING,
                description="Optional shell ID for context",
                required=False,
            ),
            ToolParameter(
                name="tunnel_id",
                type=ParameterType.STRING,
                description="Optional tunnel ID for context",
                required=False,
            ),
            ToolParameter(
                name="include_topology",
                type=ParameterType.BOOLEAN,
                description="Include network topology diagram",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="include_tunnels",
                type=ParameterType.BOOLEAN,
                description="Include active tunnels list",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="include_shells",
                type=ParameterType.BOOLEAN,
                description="Include active shells list",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="include_operations",
                type=ParameterType.BOOLEAN,
                description="Include relevant operation history",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="max_operations",
                type=ParameterType.INTEGER,
                description="Maximum number of operations to include",
                required=False,
                default=20,
            ),
        ],
    )

    tool_registry.register_tool(
        name="compress_context",
        func=context_tools.compress_context,
        description="Compress context to fit token budget",
        parameters=[
            ToolParameter(
                name="operations",
                type=ParameterType.ARRAY,
                description="List of operations to compress",
                required=True,
            ),
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="Current query for relevance scoring",
                required=True,
            ),
            ToolParameter(
                name="max_tokens",
                type=ParameterType.INTEGER,
                description="Maximum token budget",
                required=False,
                default=4000,
            ),
            ToolParameter(
                name="threshold",
                type=ParameterType.INTEGER,
                description="Minimum relevance threshold",
                required=False,
                default=0.3,
            ),
        ],
    )


def register_network_tools() -> None:
    """Register network topology tools."""
    tool_registry.register_tool(
        name="visualize_topology",
        func=network_tools.visualize_topology,
        description="Generate network topology visualization",
        parameters=[
            ToolParameter(
                name="format",
                type=ParameterType.STRING,
                description="Output format (mermaid, ascii, summary)",
                required=False,
                default="mermaid",
            ),
            ToolParameter(
                name="highlight_route_source",
                type=ParameterType.STRING,
                description="Optional source segment to highlight route",
                required=False,
            ),
            ToolParameter(
                name="highlight_route_target",
                type=ParameterType.STRING,
                description="Optional target segment to highlight route",
                required=False,
            ),
        ],
    )

    tool_registry.register_tool(
        name="find_route",
        func=network_tools.find_route,
        description="Find route between network segments",
        parameters=[
            ToolParameter(
                name="source",
                type=ParameterType.STRING,
                description="Source segment ID",
                required=True,
            ),
            ToolParameter(
                name="target",
                type=ParameterType.STRING,
                description="Target segment ID",
                required=True,
            ),
            ToolParameter(
                name="active_only",
                type=ParameterType.BOOLEAN,
                description="Only consider active tunnels",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="find_all",
                type=ParameterType.BOOLEAN,
                description="Find all possible routes (not just optimal)",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="max_hops",
                type=ParameterType.INTEGER,
                description="Maximum number of hops to consider",
                required=False,
                default=10,
            ),
        ],
    )

    tool_registry.register_tool(
        name="get_affected_segments",
        func=network_tools.get_affected_segments,
        description="Get segments affected by tunnel failure",
        parameters=[
            ToolParameter(
                name="tunnel_id",
                type=ParameterType.STRING,
                description="Tunnel ID to analyze",
                required=True,
            ),
        ],
    )
