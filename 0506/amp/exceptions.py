"""AMP exception hierarchy."""

from datetime import datetime


class AMPException(Exception):
    """Base exception for all AMP errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# Tunnel exceptions
class TunnelException(AMPException):
    """Base exception for tunnel-related errors."""


class TunnelCreationFailed(TunnelException):
    """Raised when tunnel creation fails."""

    def __init__(self, reason: str, retry_possible: bool = True):
        super().__init__(
            f"Tunnel creation failed: {reason}",
            {"reason": reason, "retry_possible": retry_possible},
        )
        self.reason = reason
        self.retry_possible = retry_possible


class TunnelDisconnected(TunnelException):
    """Raised when tunnel disconnects unexpectedly."""

    def __init__(self, tunnel_id: str, last_heartbeat: datetime):
        super().__init__(
            f"Tunnel {tunnel_id} disconnected",
            {"tunnel_id": tunnel_id, "last_heartbeat": last_heartbeat.isoformat()},
        )
        self.tunnel_id = tunnel_id
        self.last_heartbeat = last_heartbeat


class TunnelNotFound(TunnelException):
    """Raised when tunnel is not found."""

    def __init__(self, tunnel_id: str):
        super().__init__(f"Tunnel {tunnel_id} not found", {"tunnel_id": tunnel_id})
        self.tunnel_id = tunnel_id


# Shell exceptions
class ShellException(AMPException):
    """Base exception for shell-related errors."""


class ShellCreationFailed(ShellException):
    """Raised when shell creation fails."""

    def __init__(self, reason: str, target: str):
        super().__init__(
            f"Shell creation failed for {target}: {reason}",
            {"reason": reason, "target": target},
        )
        self.reason = reason
        self.target = target


class CommandExecutionFailed(ShellException):
    """Raised when command execution fails."""

    def __init__(self, command: str, exit_code: int, stderr: str):
        super().__init__(
            f"Command failed with exit code {exit_code}: {command}",
            {"command": command, "exit_code": exit_code, "stderr": stderr},
        )
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr


class ShellDied(ShellException):
    """Raised when shell session dies unexpectedly."""

    def __init__(self, shell_id: str, reason: str | None = None):
        msg = f"Shell {shell_id} died"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, {"shell_id": shell_id, "reason": reason})
        self.shell_id = shell_id
        self.reason = reason


class ShellNotFound(ShellException):
    """Raised when shell is not found."""

    def __init__(self, shell_id: str):
        super().__init__(f"Shell {shell_id} not found", {"shell_id": shell_id})
        self.shell_id = shell_id


class ShellTimeout(ShellException):
    """Raised when shell command times out."""

    def __init__(self, command: str, timeout: int):
        super().__init__(
            f"Command timed out after {timeout}s: {command}",
            {"command": command, "timeout": timeout},
        )
        self.command = command
        self.timeout = timeout


# Context exceptions
class ContextException(AMPException):
    """Base exception for context engine errors."""


class ContextCompressionFailed(ContextException):
    """Raised when context compression fails."""


class VectorStoreFailed(ContextException):
    """Raised when vector store operation fails."""


# Network exceptions
class NetworkException(AMPException):
    """Base exception for network-related errors."""


class NetworkScanFailed(NetworkException):
    """Raised when network scan fails."""

    def __init__(self, target: str, reason: str):
        super().__init__(
            f"Network scan failed for {target}: {reason}",
            {"target": target, "reason": reason},
        )
        self.target = target
        self.reason = reason


class RouteNotFound(NetworkException):
    """Raised when no route to target is found."""

    def __init__(self, target: str):
        super().__init__(f"No route to {target}", {"target": target})
        self.target = target


# Resource exceptions
class ResourceException(AMPException):
    """Base exception for resource limit errors."""


class TunnelLimitExceeded(ResourceException):
    """Raised when tunnel limit is exceeded."""

    def __init__(self, current: int, limit: int):
        super().__init__(
            f"Tunnel limit exceeded: {current}/{limit}",
            {"current": current, "limit": limit},
        )
        self.current = current
        self.limit = limit


class ShellLimitExceeded(ResourceException):
    """Raised when shell limit is exceeded."""

    def __init__(self, current: int, limit: int):
        super().__init__(
            f"Shell limit exceeded: {current}/{limit}",
            {"current": current, "limit": limit},
        )
        self.current = current
        self.limit = limit


# MCP exceptions
class MCPException(AMPException):
    """Base exception for MCP-related errors."""


class MCPAuthenticationFailed(MCPException):
    """Raised when MCP authentication fails."""


class MCPToolExecutionFailed(MCPException):
    """Raised when MCP tool execution fails."""

    def __init__(self, tool_name: str, reason: str):
        super().__init__(
            f"Tool {tool_name} execution failed: {reason}",
            {"tool_name": tool_name, "reason": reason},
        )
        self.tool_name = tool_name
        self.reason = reason
