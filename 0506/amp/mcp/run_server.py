"""Startup script for AMP MCP server."""

import logging

import uvicorn

from amp.config import settings
from amp.mcp.server import create_app
from amp.mcp.tools.registry import initialize_managers, register_all_tools

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the server."""
    logger.info("Starting AMP MCP Server...")

    # Ensure directories exist
    settings.ensure_directories()
    logger.info("Directories ensured")

    # Initialize database
    from amp.storage.database import Database

    database = Database(settings.database.url)
    logger.info("Database initialized")

    # Initialize managers
    logger.info("Initializing managers...")
    managers = initialize_managers(database)
    logger.info(f"Initialized {len(managers)} managers")

    # Register all tools
    logger.info("Registering tools...")
    register_all_tools(managers)
    logger.info("Tools registered")

    # Create app
    app = create_app()

    # Start server
    logger.info(f"Starting server on {settings.mcp.host}:{settings.mcp.port}")
    uvicorn.run(
        app,
        host=settings.mcp.host,
        port=settings.mcp.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
