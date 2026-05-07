"""Authentication middleware for MCP server."""

import logging
from collections.abc import Callable

from fastapi import Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from amp.config import settings

logger = logging.getLogger(__name__)


async def verify_auth_token(authorization: str = Header(None)) -> str:
    """Verify authentication token.

    Args:
        authorization: Authorization header value

    Returns:
        Verified token

    Raises:
        HTTPException: If authentication fails
    """
    if not settings.mcp.auth_token:
        # Authentication disabled
        return ""

    if not authorization:
        logger.warning("Missing authorization header")
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning("Invalid authorization header format")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    if token != settings.mcp.auth_token:
        logger.warning("Invalid authentication token")
        raise HTTPException(
            status_code=403,
            detail="Invalid authentication token",
        )

    return token


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for MCP server."""

    def __init__(self, app: Callable, exempt_paths: list[str] | None = None):
        """Initialize auth middleware.

        Args:
            app: ASGI application
            exempt_paths: Paths exempt from authentication
        """
        super().__init__(app)
        self.exempt_paths = exempt_paths or ["/health", "/docs", "/openapi.json"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with authentication.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Skip authentication for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Skip authentication if no token configured
        if not settings.mcp.auth_token:
            return await call_next(request)

        # Verify authorization header
        authorization = request.headers.get("authorization")
        if not authorization:
            logger.warning(f"Unauthorized request to {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"error": "Missing authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract and verify token
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning(f"Invalid auth format for {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authorization header format"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = parts[1]
        if token != settings.mcp.auth_token:
            logger.warning(f"Invalid token for {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"error": "Invalid authentication token"},
            )

        # Token valid, proceed
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request details.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )

        # Process request
        response = await call_next(request)

        # Log response
        logger.info(
            f"Response: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware (in-memory)."""

    def __init__(self, app: Callable, max_requests: int = 100, window_seconds: int = 60):
        """Initialize rate limit middleware.

        Args:
            app: ASGI application
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        import time

        # Get client identifier
        client_id = request.client.host if request.client else "unknown"

        # Get current time
        now = time.time()

        # Initialize client request list if needed
        if client_id not in self._requests:
            self._requests[client_id] = []

        # Remove old requests outside the window
        self._requests[client_id] = [
            req_time
            for req_time in self._requests[client_id]
            if now - req_time < self.window_seconds
        ]

        # Check rate limit
        if len(self._requests[client_id]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for client {client_id}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "details": {
                        "max_requests": self.max_requests,
                        "window_seconds": self.window_seconds,
                    },
                },
                headers={
                    "Retry-After": str(self.window_seconds),
                },
            )

        # Add current request
        self._requests[client_id].append(now)

        # Process request
        return await call_next(request)
