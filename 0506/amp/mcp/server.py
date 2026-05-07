"""FastAPI server for MCP (Model Context Protocol)."""

import logging
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from amp.config import settings
from amp.exceptions import AMPException, MCPToolExecutionFailed
from amp.mcp.auth import AuthMiddleware, RequestLoggingMiddleware
from amp.mcp.protocol import (
    ErrorResponse,
    HealthResponse,
    ToolListResponse,
    ToolRequest,
    ToolResponse,
)
from amp.mcp.tool_registry import tool_registry
from amp.web import setup_web_routes

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="AMP MCP Server",
        description="Model Context Protocol server for AI-driven Autonomous Penetration Testing Platform",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Setup middleware
    setup_middleware(app)

    # Setup routes
    setup_routes(app)

    # Setup web UI routes
    setup_web_routes(app)

    # Setup exception handlers
    setup_exception_handlers(app)

    logger.info("MCP server application created")
    return app


def setup_middleware(app: FastAPI) -> None:
    """Setup middleware for the application.

    Args:
        app: FastAPI application
    """
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.mcp.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Authentication middleware
    app.add_middleware(
        AuthMiddleware,
        exempt_paths=["/health", "/docs", "/redoc", "/openapi.json"],
    )

    logger.info("Middleware configured")


def setup_routes(app: FastAPI) -> None:
    """Setup routes for the application.

    Args:
        app: FastAPI application
    """

    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check() -> HealthResponse:
        """Health check endpoint.

        Returns:
            Health status response
        """
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            timestamp=datetime.now(UTC).isoformat(),
        )

    @app.get("/tools", response_model=ToolListResponse, tags=["Tools"])
    async def list_tools() -> ToolListResponse:
        """List all available tools.

        Returns:
            List of tool definitions
        """
        tools = tool_registry.list_tools()
        return ToolListResponse(tools=tools, count=len(tools))

    @app.post("/tools/{tool_name}", response_model=ToolResponse, tags=["Tools"])
    async def execute_tool(tool_name: str, request: ToolRequest) -> ToolResponse:
        """Execute a tool.

        Args:
            tool_name: Name of the tool to execute
            request: Tool execution request with parameters

        Returns:
            Tool execution response

        Raises:
            HTTPException: If tool execution fails
        """
        try:
            result = await tool_registry.execute_tool(tool_name, request.parameters)
            return ToolResponse(success=True, result=result, error=None)
        except MCPToolExecutionFailed as e:
            logger.error(f"Tool execution failed: {e}")
            raise HTTPException(
                status_code=400,
                detail={"error": e.message, "details": e.details},
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error executing tool {tool_name}: {e}")
            raise HTTPException(
                status_code=500,
                detail={"error": "Internal server error", "details": {"message": str(e)}},
            ) from e

    logger.info("Routes configured")


def setup_exception_handlers(app: FastAPI) -> None:
    """Setup exception handlers for the application.

    Args:
        app: FastAPI application
    """

    @app.exception_handler(AMPException)
    async def amp_exception_handler(request, exc: AMPException) -> JSONResponse:
        """Handle AMP exceptions.

        Args:
            request: HTTP request
            exc: AMP exception

        Returns:
            JSON error response
        """
        logger.error(f"AMP exception: {exc.message}", extra={"details": exc.details})
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(error=exc.message, details=exc.details).model_dump(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc: Exception) -> JSONResponse:
        """Handle general exceptions.

        Args:
            request: HTTP request
            exc: Exception

        Returns:
            JSON error response
        """
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal server error",
                details={"message": str(exc)},
            ).model_dump(),
        )

    logger.info("Exception handlers configured")
