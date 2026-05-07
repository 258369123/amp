"""MCP server startup script.

Run this script to start the MCP server with stdio transport.
This is the entry point for Claude Code integration.
"""

import asyncio
import logging
import sys
from pathlib import Path

from mcp.server.stdio import stdio_server

from amp.config import settings
from amp.mcp.mcp_server import create_mcp_server
from amp.storage.database import Database

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),  # Log to stderr, not stdout (stdout is for MCP protocol)
    ]
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for MCP server."""
    try:
        logger.info("Starting AMP MCP Server")
        logger.info(f"Database: {settings.database.url}")

        # Ensure data directory exists
        data_dir = Path(settings.database.url.replace("sqlite:///", "")).parent
        data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        database = Database(settings.database.url)
        database.create_tables()
        logger.info("Database initialized")

        # Create MCP server (fast startup - no model preloading)
        server = create_mcp_server(database)
        logger.info("MCP server created")

        # Run server with stdio transport
        logger.info("Starting stdio server (MCP protocol)")
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


def cli_main():
    """Entry point for console script."""
    asyncio.run(main())
