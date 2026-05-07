"""Test script for MCP server functionality."""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from amp.config import settings
from amp.mcp.mcp_server import create_mcp_server
from amp.storage.database import Database


async def test_mcp_server() -> None:
    """Test MCP server initialization and tool listing."""
    print("=" * 60)
    print("AMP MCP Server Test")
    print("=" * 60)

    try:
        # Initialize database
        print("\n1. Initializing database...")
        database = Database("sqlite:///:memory:")
        print("   ✓ Database initialized")

        # Create MCP server
        print("\n2. Creating MCP server...")
        server = create_mcp_server(database)
        print("   ✓ MCP server created")

        # Get tool adapter to test tool listing
        print("\n3. Testing tool listing...")
        from amp.mcp.mcp_tools import MCPToolAdapter
        adapter = MCPToolAdapter(database)
        tools = adapter.get_all_tools()

        print(f"   ✓ Found {len(tools)} tools")

        # Display tools
        print("\n4. Available Tools:")
        print("-" * 60)

        # Group tools by category
        tunnel_tools = []
        shell_tools = []
        context_tools = []
        network_tools = []

        for tool in tools:
            if "tunnel" in tool.name:
                tunnel_tools.append(tool)
            elif "shell" in tool.name or "command" in tool.name:
                shell_tools.append(tool)
            elif "context" in tool.name or "prompt" in tool.name or "operations" in tool.name or "compress" in tool.name:
                context_tools.append(tool)
            else:
                network_tools.append(tool)

        print(f"\n   Tunnel Management ({len(tunnel_tools)} tools):")
        for tool in tunnel_tools:
            print(f"   - {tool.name}: {tool.description}")

        print(f"\n   Shell Management ({len(shell_tools)} tools):")
        for tool in shell_tools:
            print(f"   - {tool.name}: {tool.description}")

        print(f"\n   Context Management ({len(context_tools)} tools):")
        for tool in context_tools:
            print(f"   - {tool.name}: {tool.description}")

        print(f"\n   Network Topology ({len(network_tools)} tools):")
        for tool in network_tools:
            print(f"   - {tool.name}: {tool.description}")

        # Test tool schema
        print("\n5. Testing tool schema (sample):")
        print("-" * 60)
        sample_tool = tools[0]
        print(f"\n   Tool: {sample_tool.name}")
        print(f"   Description: {sample_tool.description}")
        print(f"   Input Schema:")
        print(f"   {json.dumps(sample_tool.inputSchema, indent=6)}")

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

        print("\n6. Next Steps:")
        print("   - Start MCP server: python amp/mcp/run_mcp_server.py")
        print("   - Or use entry point: amp-mcp (after pip install)")
        print("   - Configure Claude Code to use this MCP server")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
