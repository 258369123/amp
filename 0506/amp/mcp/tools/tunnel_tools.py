"""Tunnel management tools for MCP."""

import logging
from typing import Any

from amp.exceptions import (
    TunnelCreationFailed,
    TunnelLimitExceeded,
    TunnelNotFound,
)
from amp.storage.models import TunnelStatus, TunnelType

logger = logging.getLogger(__name__)

# Global manager instances (initialized by registry)
_tunnel_manager = None


def set_tunnel_manager(manager: Any) -> None:
    """Set tunnel manager instance.

    Args:
        manager: TunnelManager instance
    """
    global _tunnel_manager
    _tunnel_manager = manager


async def create_tunnel(
    name: str,
    tunnel_type: str,
    local_port: int,
    remote_host: str,
    remote_port: int,
    local_host: str = "127.0.0.1",
    parent_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new network tunnel.

    Args:
        name: Tunnel name
        tunnel_type: Tunnel type (chisel, ligolo, ssh)
        local_port: Local port to bind
        remote_host: Remote host to connect to
        remote_port: Remote port to connect to
        local_host: Local host to bind (default: 127.0.0.1)
        parent_id: Parent tunnel ID for nested tunnels
        config: Additional configuration

    Returns:
        Response dict with tunnel info
    """
    try:
        if not _tunnel_manager:
            return {
                "success": False,
                "error": "Tunnel manager not initialized",
                "error_type": "initialization_error",
            }

        # Validate tunnel type
        try:
            tunnel_type_enum = TunnelType(tunnel_type)
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid tunnel type: {tunnel_type}",
                "error_type": "validation_error",
            }

        # Create tunnel
        tunnel = _tunnel_manager.create_tunnel(
            name=name,
            tunnel_type=tunnel_type_enum,
            local_port=local_port,
            remote_host=remote_host,
            remote_port=remote_port,
            local_host=local_host,
            parent_id=parent_id,
            config=config or {},
        )

        logger.info(f"Created tunnel {tunnel.id} ({name})")

        return {
            "success": True,
            "data": {
                "tunnel_id": tunnel.id,
                "name": tunnel.name,
                "tunnel_type": tunnel.tunnel_type.value,
                "status": tunnel.status.value,
                "local_host": tunnel.local_host,
                "local_port": tunnel.local_port,
                "remote_host": tunnel.remote_host,
                "remote_port": tunnel.remote_port,
                "parent_tunnel_id": tunnel.parent_tunnel_id,
            },
        }

    except TunnelLimitExceeded as e:
        logger.warning(f"Tunnel limit exceeded: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "limit_exceeded",
        }
    except TunnelCreationFailed as e:
        logger.error(f"Tunnel creation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "creation_failed",
            "retry_possible": e.retry_possible,
        }
    except Exception as e:
        logger.error(f"Unexpected error creating tunnel: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def start_tunnel(tunnel_id: str) -> dict[str, Any]:
    """Start an existing tunnel.

    Args:
        tunnel_id: Tunnel ID to start

    Returns:
        Response dict with tunnel status
    """
    try:
        if not _tunnel_manager:
            return {
                "success": False,
                "error": "Tunnel manager not initialized",
                "error_type": "initialization_error",
            }

        tunnel = _tunnel_manager.start_tunnel(tunnel_id)

        logger.info(f"Started tunnel {tunnel_id}")

        return {
            "success": True,
            "data": {
                "tunnel_id": tunnel.id,
                "name": tunnel.name,
                "status": tunnel.status.value,
                "process_pid": tunnel.process_pid,
            },
        }

    except TunnelNotFound as e:
        logger.warning(f"Tunnel not found: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "not_found",
        }
    except TunnelCreationFailed as e:
        logger.error(f"Failed to start tunnel: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "start_failed",
            "retry_possible": e.retry_possible,
        }
    except Exception as e:
        logger.error(f"Unexpected error starting tunnel: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def stop_tunnel(tunnel_id: str) -> dict[str, Any]:
    """Stop a running tunnel.

    Args:
        tunnel_id: Tunnel ID to stop

    Returns:
        Response dict with tunnel status
    """
    try:
        if not _tunnel_manager:
            return {
                "success": False,
                "error": "Tunnel manager not initialized",
                "error_type": "initialization_error",
            }

        tunnel = _tunnel_manager.stop_tunnel(tunnel_id)

        logger.info(f"Stopped tunnel {tunnel_id}")

        return {
            "success": True,
            "data": {
                "tunnel_id": tunnel.id,
                "name": tunnel.name,
                "status": tunnel.status.value,
            },
        }

    except TunnelNotFound as e:
        logger.warning(f"Tunnel not found: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "not_found",
        }
    except Exception as e:
        logger.error(f"Unexpected error stopping tunnel: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def delete_tunnel(tunnel_id: str) -> dict[str, Any]:
    """Delete a tunnel.

    Args:
        tunnel_id: Tunnel ID to delete

    Returns:
        Response dict with deletion status
    """
    try:
        if not _tunnel_manager:
            return {
                "success": False,
                "error": "Tunnel manager not initialized",
                "error_type": "initialization_error",
            }

        _tunnel_manager.delete_tunnel(tunnel_id)

        logger.info(f"Deleted tunnel {tunnel_id}")

        return {
            "success": True,
            "data": {
                "tunnel_id": tunnel_id,
                "message": "Tunnel deleted successfully",
            },
        }

    except TunnelNotFound as e:
        logger.warning(f"Tunnel not found: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "not_found",
        }
    except Exception as e:
        logger.error(f"Unexpected error deleting tunnel: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def list_tunnels(status: str | None = None) -> dict[str, Any]:
    """List all tunnels, optionally filtered by status.

    Args:
        status: Optional status filter (active, disconnected, stopped)

    Returns:
        Response dict with list of tunnels
    """
    try:
        if not _tunnel_manager:
            return {
                "success": False,
                "error": "Tunnel manager not initialized",
                "error_type": "initialization_error",
            }

        # Get tunnels based on filter
        if status:
            # Validate status
            try:
                status_enum = TunnelStatus(status)
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid status: {status}",
                    "error_type": "validation_error",
                }

            if status_enum == TunnelStatus.ACTIVE:
                tunnels = _tunnel_manager.list_active_tunnels()
            else:
                # Get all and filter
                all_tunnels = _tunnel_manager.list_all_tunnels()
                tunnels = [t for t in all_tunnels if t.status == status_enum]
        else:
            tunnels = _tunnel_manager.list_all_tunnels()

        # Convert to dict format
        tunnel_list = []
        for tunnel in tunnels:
            tunnel_list.append({
                "tunnel_id": tunnel.id,
                "name": tunnel.name,
                "tunnel_type": tunnel.tunnel_type.value,
                "status": tunnel.status.value,
                "local_host": tunnel.local_host,
                "local_port": tunnel.local_port,
                "remote_host": tunnel.remote_host,
                "remote_port": tunnel.remote_port,
                "parent_tunnel_id": tunnel.parent_tunnel_id,
                "process_pid": tunnel.process_pid,
                "created_at": tunnel.created_at.isoformat(),
            })

        logger.debug(f"Listed {len(tunnel_list)} tunnels (status={status})")

        return {
            "success": True,
            "data": {
                "tunnels": tunnel_list,
                "count": len(tunnel_list),
            },
        }

    except Exception as e:
        logger.error(f"Unexpected error listing tunnels: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def get_tunnel_status(tunnel_id: str) -> dict[str, Any]:
    """Get tunnel health status.

    Args:
        tunnel_id: Tunnel ID to check

    Returns:
        Response dict with tunnel health status
    """
    try:
        if not _tunnel_manager:
            return {
                "success": False,
                "error": "Tunnel manager not initialized",
                "error_type": "initialization_error",
            }

        # Get tunnel info
        tunnel = _tunnel_manager.get_tunnel(tunnel_id)

        # Run health check
        try:
            is_healthy = _tunnel_manager.health_check(tunnel_id)
        except Exception as e:
            is_healthy = False
            logger.debug(f"Health check failed for tunnel {tunnel_id}: {e}")

        # Get stats if available
        stats = _tunnel_manager.get_tunnel_stats(tunnel_id)

        logger.debug(f"Got status for tunnel {tunnel_id}: healthy={is_healthy}")

        return {
            "success": True,
            "data": {
                "tunnel_id": tunnel.id,
                "name": tunnel.name,
                "status": tunnel.status.value,
                "is_healthy": is_healthy,
                "process_pid": tunnel.process_pid,
                "last_heartbeat": tunnel.last_heartbeat.isoformat() if tunnel.last_heartbeat else None,
                "stats": stats,
            },
        }

    except TunnelNotFound as e:
        logger.warning(f"Tunnel not found: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "not_found",
        }
    except Exception as e:
        logger.error(f"Unexpected error getting tunnel status: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }
