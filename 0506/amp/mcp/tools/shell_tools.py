"""Shell management tools for MCP."""

import logging
from typing import Any

from amp.exceptions import (
    ShellCreationFailed,
    ShellDied,
    ShellLimitExceeded,
    ShellNotFound,
)
from amp.storage.models import OSType, ShellProgram, ShellStatus, ShellType

logger = logging.getLogger(__name__)

# Global manager instances (initialized by registry)
_shell_manager = None


def set_shell_manager(manager: Any) -> None:
    """Set shell manager instance.

    Args:
        manager: ShellManager instance
    """
    global _shell_manager
    _shell_manager = manager


async def create_shell(
    name: str,
    shell_type: str,
    target_host: str,
    os_type: str = "linux",
    tunnel_id: str | None = None,
    local_port: int | None = None,
    target_port: int | None = None,
    shell_program: str = "bash",
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    payload_type: str | None = None,
    use_tmux: bool = True,
    timeout: int = 30,
) -> dict[str, Any]:
    """Create a new shell session.

    Args:
        name: Shell name
        shell_type: Shell type (reverse, bind, ssh)
        target_host: Target host
        os_type: Operating system type (linux, windows)
        tunnel_id: Tunnel ID if using tunnel
        local_port: Local port for reverse shells
        target_port: Target port for bind/ssh shells
        shell_program: Shell program (bash, sh, powershell, cmd)
        username: Username for SSH shells
        password: Password for SSH shells
        key_path: SSH key path for SSH shells
        payload_type: Payload type for reverse shells
        use_tmux: Whether to use tmux for persistence
        timeout: Connection timeout in seconds

    Returns:
        Response dict with shell info
    """
    try:
        if not _shell_manager:
            return {
                "success": False,
                "error": "Shell manager not initialized",
                "error_type": "initialization_error",
            }

        # Validate enums
        try:
            shell_type_enum = ShellType(shell_type)
            os_type_enum = OSType(os_type)
            shell_program_enum = ShellProgram(shell_program)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid parameter: {e}",
                "error_type": "validation_error",
            }

        # Create shell based on type and OS
        if shell_type_enum == ShellType.REVERSE:
            if os_type_enum == OSType.WINDOWS:
                # Windows reverse shell
                shell, payload = _shell_manager.create_windows_shell(
                    name=name,
                    target_host=target_host,
                    shell_program=shell_program_enum,
                    tunnel_id=tunnel_id,
                    local_port=local_port,
                    payload_type=payload_type or "powershell",
                    use_tmux=use_tmux,
                    timeout=timeout,
                )
            else:
                # Linux reverse shell
                if not local_port:
                    return {
                        "success": False,
                        "error": "local_port is required for reverse shells",
                        "error_type": "validation_error",
                    }
                shell, payload = _shell_manager.create_reverse_shell(
                    name=name,
                    local_port=local_port,
                    target_host=target_host,
                    tunnel_id=tunnel_id,
                    payload_type=payload_type or "bash",
                    use_tmux=use_tmux,
                    timeout=timeout,
                )

            logger.info(f"Created reverse shell {shell.id} ({name})")

            return {
                "success": True,
                "data": {
                    "shell_id": shell.id,
                    "name": shell.name,
                    "shell_type": shell.shell_type.value,
                    "os_type": shell.os_type.value,
                    "status": shell.status.value,
                    "target_host": shell.target_host,
                    "payload": payload,
                    "message": "Execute the payload on the target to establish connection",
                },
            }

        elif shell_type_enum == ShellType.BIND:
            if not target_port:
                return {
                    "success": False,
                    "error": "target_port is required for bind shells",
                    "error_type": "validation_error",
                }

            shell = _shell_manager.create_bind_shell(
                name=name,
                target_host=target_host,
                target_port=target_port,
                tunnel_id=tunnel_id,
                use_tmux=use_tmux,
            )

            logger.info(f"Created bind shell {shell.id} ({name})")

            return {
                "success": True,
                "data": {
                    "shell_id": shell.id,
                    "name": shell.name,
                    "shell_type": shell.shell_type.value,
                    "os_type": shell.os_type.value,
                    "status": shell.status.value,
                    "target_host": shell.target_host,
                    "target_port": shell.target_port,
                },
            }

        elif shell_type_enum == ShellType.SSH:
            if not username:
                return {
                    "success": False,
                    "error": "username is required for SSH shells",
                    "error_type": "validation_error",
                }

            shell = _shell_manager.create_ssh_shell(
                name=name,
                target_host=target_host,
                username=username,
                password=password,
                key_path=key_path,
                tunnel_id=tunnel_id,
                port=target_port or 22,
                use_tmux=use_tmux,
            )

            logger.info(f"Created SSH shell {shell.id} ({name})")

            return {
                "success": True,
                "data": {
                    "shell_id": shell.id,
                    "name": shell.name,
                    "shell_type": shell.shell_type.value,
                    "os_type": shell.os_type.value,
                    "status": shell.status.value,
                    "target_host": shell.target_host,
                    "target_port": shell.target_port,
                },
            }

        else:
            return {
                "success": False,
                "error": f"Unsupported shell type: {shell_type}",
                "error_type": "validation_error",
            }

    except ShellLimitExceeded as e:
        logger.warning(f"Shell limit exceeded: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "limit_exceeded",
        }
    except ShellCreationFailed as e:
        logger.error(f"Shell creation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "creation_failed",
        }
    except Exception as e:
        logger.error(f"Unexpected error creating shell: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def execute_command(
    shell_id: str,
    command: str,
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute command in shell session and auto-record to database.

    Args:
        shell_id: Shell ID
        command: Command to execute
        timeout: Timeout in seconds

    Returns:
        Response dict with command output
    """
    try:
        if not _shell_manager:
            return {
                "success": False,
                "error": "Shell manager not initialized",
                "error_type": "initialization_error",
            }

        # Get shell to determine OS type
        shell = _shell_manager.get_shell(shell_id)

        # Execute command based on OS type
        if shell.os_type == OSType.WINDOWS:
            result = _shell_manager.execute_windows_command(
                shell_id=shell_id,
                command=command,
                timeout=timeout,
            )
        else:
            result = _shell_manager.execute_command(
                shell_id=shell_id,
                command=command,
                timeout=timeout,
            )

        logger.info(
            f"Executed command in shell {shell_id}: {command[:50]}... "
            f"(exit_code={result.exit_code})"
        )

        # Auto-record to database (operation is already recorded by manager)
        # The shell manager already creates Operation records, so we just
        # need to ensure the operation_id is returned

        return {
            "success": True,
            "data": {
                "operation_id": result.operation_id,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "command_success": result.success,
            },
        }

    except ShellNotFound as e:
        logger.warning(f"Shell not found: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "not_found",
        }
    except ShellDied as e:
        logger.error(f"Shell died: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "shell_died",
        }
    except Exception as e:
        logger.error(f"Unexpected error executing command: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def close_shell(shell_id: str) -> dict[str, Any]:
    """Close shell session.

    Args:
        shell_id: Shell ID to close

    Returns:
        Response dict with closure status
    """
    try:
        if not _shell_manager:
            return {
                "success": False,
                "error": "Shell manager not initialized",
                "error_type": "initialization_error",
            }

        _shell_manager.close_shell(shell_id)

        logger.info(f"Closed shell {shell_id}")

        return {
            "success": True,
            "data": {
                "shell_id": shell_id,
                "message": "Shell closed successfully",
            },
        }

    except ShellNotFound as e:
        logger.warning(f"Shell not found: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "not_found",
        }
    except Exception as e:
        logger.error(f"Unexpected error closing shell: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def list_shells(status: str | None = None) -> dict[str, Any]:
    """List all shells, optionally filtered by status.

    Args:
        status: Optional status filter ('active', 'dead', 'zombie', 'all', or None defaults to 'all')

    Returns:
        Response dict with list of shells
    """
    try:
        if not _shell_manager:
            return {
                "success": False,
                "error": "Shell manager not initialized",
                "error_type": "initialization_error",
            }

        # Default to 'all' if status is None
        if status is None:
            status = 'all'

        # Get shells based on filter
        if status == 'all':
            shells = _shell_manager.list_all_shells()
        elif status == 'active':
            shells = _shell_manager.list_active_shells()
        elif status == 'dead':
            shells = _shell_manager.list_dead_shells()
        elif status == 'zombie':
            shells = _shell_manager.list_shells_by_status(ShellStatus.ZOMBIE)
        else:
            return {
                "success": False,
                "error": f"Invalid status filter: {status}. Use 'all', 'active', 'dead', or 'zombie'",
                "error_type": "validation_error",
            }

        # Convert to dict format
        shell_list = []
        for shell in shells:
            shell_list.append({
                "shell_id": shell.id,
                "name": shell.name,
                "shell_type": shell.shell_type.value,
                "os_type": shell.os_type.value,
                "shell_program": shell.shell_program.value,
                "status": shell.status.value,
                "target_host": shell.target_host,
                "target_port": shell.target_port,
                "tunnel_id": shell.tunnel_id,
                "working_directory": shell.working_directory,
                "privilege_level": shell.privilege_level.value,
                "created_at": shell.created_at.isoformat(),
            })

        logger.debug(f"Listed {len(shell_list)} shells (status={status})")

        return {
            "success": True,
            "data": {
                "shells": shell_list,
                "count": len(shell_list),
                "filter": status,
            },
        }

    except Exception as e:
        logger.error(f"Unexpected error listing shells: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def get_shell_status(shell_id: str) -> dict[str, Any]:
    """Get shell status and information.

    Args:
        shell_id: Shell ID to check

    Returns:
        Response dict with shell status
    """
    try:
        if not _shell_manager:
            return {
                "success": False,
                "error": "Shell manager not initialized",
                "error_type": "initialization_error",
            }

        # Get shell info
        shell = _shell_manager.get_shell(shell_id)

        # Update shell state
        try:
            if shell.os_type == OSType.WINDOWS:
                _shell_manager.update_windows_shell_state(shell_id)
            else:
                _shell_manager.update_shell_state(shell_id)
        except Exception as e:
            logger.debug(f"Failed to update shell state: {e}")

        # Get updated shell info
        shell = _shell_manager.get_shell(shell_id)

        logger.debug(f"Got status for shell {shell_id}")

        return {
            "success": True,
            "data": {
                "shell_id": shell.id,
                "name": shell.name,
                "shell_type": shell.shell_type.value,
                "os_type": shell.os_type.value,
                "shell_program": shell.shell_program.value,
                "status": shell.status.value,
                "target_host": shell.target_host,
                "target_port": shell.target_port,
                "tunnel_id": shell.tunnel_id,
                "working_directory": shell.working_directory,
                "privilege_level": shell.privilege_level.value,
                "tmux_session": shell.tmux_session,
                "last_activity": shell.last_activity.isoformat() if shell.last_activity else None,
            },
        }

    except ShellNotFound as e:
        logger.warning(f"Shell not found: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "not_found",
        }
    except Exception as e:
        logger.error(f"Unexpected error getting shell status: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }
