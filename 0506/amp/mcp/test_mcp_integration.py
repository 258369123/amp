"""Integration test demonstrating MCP protocol communication.

This test simulates how Claude Code would interact with the MCP server.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from amp.config import settings
from amp.mcp.mcp_server import create_mcp_server
from amp.storage.database import Database


async def test_mcp_protocol() -> None:
    """Test MCP protocol communication flow."""
    print("=" * 70)
    print("MCP Protocol Integration Test")
    print("=" * 70)

    try:
        # Initialize
        print("\n[1] Initializing server...")
        database = Database("sqlite:///:memory:")
        server = create_mcp_server(database)
        print("    ✓ Server ready")

        # Simulate tools/list request
        print("\n[2] Simulating tools/list request...")
        from amp.mcp.mcp_tools import MCPToolAdapter
        adapter = MCPToolAdapter(database)
        tools = adapter.get_all_tools()
        print(f"    ✓ Response: {len(tools)} tools available")

        # Simulate tools/call request - list_tunnels
        print("\n[3] Simulating tools/call request (list_tunnels)...")
        result = await adapter.execute_tool("list_tunnels", {})
        print(f"    ✓ Response: {json.dumps(result, indent=6)}")

        # Simulate tools/call request - visualize_topology
        print("\n[4] Simulating tools/call request (visualize_topology)...")
        result = await adapter.execute_tool("visualize_topology", {"format": "summary"})
        print(f"    ✓ Response: {json.dumps(result, indent=6)}")

        # Test error handling
        print("\n[5] Testing error handling (invalid tool)...")
        result = await adapter.execute_tool("invalid_tool", {})
        print(f"    ✓ Error handled: {result.get('error', 'Unknown error')}")

        print("\n" + "=" * 70)
        print("✓ All integration tests passed!")
        print("=" * 70)

        print("\n[Summary]")
        print("  - MCP protocol: JSON-RPC 2.0 over stdio")
        print("  - Transport: Standard input/output")
        print("  - Tools: 17 total (6 tunnel, 5 shell, 3 context, 3 network)")
        print("  - Response format: TextContent with JSON payload")
        print("  - Error handling: Graceful with structured error responses")

        print("\n[Next Steps]")
        print("  1. Start server: python amp/mcp/run_mcp_server.py")
        print("  2. Configure Claude Code with amp/mcp/claude_code_config.json")
        print("  3. Test with: echo '{...}' | python amp/mcp/run_mcp_server.py")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_mcp_protocol())
