"""Shell state tracking."""

import logging
from typing import Any

from amp.storage.models import PrivilegeLevel, ShellProgram

logger = logging.getLogger(__name__)


class ShellState:
    """Track and update shell session state."""

    def __init__(self) -> None:
        """Initialize shell state tracker."""
        self._state_cache: dict[str, dict[str, Any]] = {}

    def get_state(self, shell_id: str) -> dict[str, Any]:
        """Get cached state for a shell.

        Args:
            shell_id: Shell ID

        Returns:
            State dictionary
        """
        return self._state_cache.get(shell_id, {})

    def update_cwd(self, shell_id: str, cwd: str) -> None:
        """Update working directory for a shell.

        Args:
            shell_id: Shell ID
            cwd: Current working directory
        """
        if shell_id not in self._state_cache:
            self._state_cache[shell_id] = {}
        self._state_cache[shell_id]["cwd"] = cwd
        logger.debug(f"Updated cwd for shell {shell_id}: {cwd}")

    def update_env(self, shell_id: str, env: dict[str, str]) -> None:
        """Update environment variables for a shell.

        Args:
            shell_id: Shell ID
            env: Environment variables
        """
        if shell_id not in self._state_cache:
            self._state_cache[shell_id] = {}
        self._state_cache[shell_id]["env"] = env
        logger.debug(f"Updated env for shell {shell_id}: {len(env)} variables")

    def update_privilege(self, shell_id: str, privilege: PrivilegeLevel) -> None:
        """Update privilege level for a shell.

        Args:
            shell_id: Shell ID
            privilege: Privilege level
        """
        if shell_id not in self._state_cache:
            self._state_cache[shell_id] = {}
        self._state_cache[shell_id]["privilege"] = privilege
        logger.debug(f"Updated privilege for shell {shell_id}: {privilege.value}")

    def update_shell_type(self, shell_id: str, shell_type: ShellProgram) -> None:
        """Update shell type for a shell.

        Args:
            shell_id: Shell ID
            shell_type: Shell program type
        """
        if shell_id not in self._state_cache:
            self._state_cache[shell_id] = {}
        self._state_cache[shell_id]["shell_type"] = shell_type
        logger.debug(f"Updated shell type for shell {shell_id}: {shell_type.value}")

    def detect_privilege(self, output: str) -> PrivilegeLevel:
        """Detect privilege level from command output.

        Args:
            output: Command output (e.g., from 'id -u' or 'whoami')

        Returns:
            Detected privilege level
        """
        output = output.strip().lower()

        # Check for root/system indicators
        if output == "0":  # uid=0 means root
            return PrivilegeLevel.ROOT
        if "root" in output or "administrator" in output:
            return PrivilegeLevel.ROOT
        if "system" in output or "nt authority\\system" in output:
            return PrivilegeLevel.SYSTEM

        return PrivilegeLevel.USER

    def detect_windows_privilege(self, output: str) -> PrivilegeLevel:
        """Detect Windows privilege level from command output.

        Args:
            output: Command output (e.g., from 'whoami' or 'net session')

        Returns:
            Detected privilege level
        """
        output = output.strip().lower()

        # Check for SYSTEM account
        if "nt authority\\system" in output or "system" in output:
            return PrivilegeLevel.SYSTEM

        # Check for Administrator
        if "administrator" in output or "admin" in output:
            return PrivilegeLevel.ROOT

        # Check for "Access is denied" which indicates non-admin
        if "access is denied" in output:
            return PrivilegeLevel.USER

        return PrivilegeLevel.USER

    def detect_uac_status(self, output: str) -> bool:
        """Detect if UAC is enabled from registry query output.

        Args:
            output: Output from UAC registry query

        Returns:
            True if UAC is enabled, False otherwise
        """
        output = output.strip().lower()

        # Check registry value
        if "enablelua" in output:
            # Look for the value (0x1 = enabled, 0x0 = disabled)
            if "0x1" in output or "1" in output:
                return True
            if "0x0" in output or "0" in output:
                return False

        # Default to enabled (safer assumption)
        return True

    def parse_windows_env(self, output: str) -> dict[str, str]:
        """Parse Windows environment variables from command output.

        Args:
            output: Output from 'set' command (CMD) or '$env:' (PowerShell)

        Returns:
            Dictionary of environment variables
        """
        env = {}
        for line in output.split("\n"):
            line = line.strip()
            if "=" in line:
                key, _, value = line.partition("=")
                env[key] = value
        return env

    def detect_shell_type(self, output: str) -> ShellProgram:
        """Detect shell type from command output.

        Args:
            output: Command output (e.g., from 'echo $SHELL' or '$PSVersionTable')

        Returns:
            Detected shell program
        """
        output = output.strip().lower()

        # Check for shell indicators
        if "powershell" in output or "psversion" in output:
            return ShellProgram.POWERSHELL
        if "cmd" in output or "command.com" in output:
            return ShellProgram.CMD
        if "bash" in output or "/bash" in output:
            return ShellProgram.BASH
        if "sh" in output or "/sh" in output:
            return ShellProgram.SH

        # Default to bash for Linux
        return ShellProgram.BASH

    def parse_env_output(self, output: str) -> dict[str, str]:
        """Parse environment variables from command output.

        Args:
            output: Output from 'env' or 'set' command

        Returns:
            Dictionary of environment variables
        """
        env = {}
        for line in output.split("\n"):
            line = line.strip()
            if "=" in line:
                key, _, value = line.partition("=")
                env[key] = value
        return env

    def clear_state(self, shell_id: str) -> None:
        """Clear cached state for a shell.

        Args:
            shell_id: Shell ID
        """
        if shell_id in self._state_cache:
            del self._state_cache[shell_id]
            logger.debug(f"Cleared state for shell {shell_id}")
