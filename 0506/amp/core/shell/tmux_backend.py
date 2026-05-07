"""tmux backend for shell session management."""

import logging
import subprocess
import time

from amp.exceptions import ShellException

logger = logging.getLogger(__name__)


class TmuxBackend:
    """Backend for managing tmux sessions."""

    def __init__(self) -> None:
        """Initialize tmux backend."""
        self._verify_tmux_installed()

    def _verify_tmux_installed(self) -> None:
        """Verify tmux is installed."""
        try:
            subprocess.run(
                ["tmux", "-V"],
                capture_output=True,
                check=True,
                timeout=5,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise ShellException("tmux is not installed or not in PATH") from e

    def create_session(self, name: str, command: str = "bash") -> None:
        """Create a new tmux session.

        Args:
            name: Session name
            command: Command to run in session (default: bash)

        Raises:
            ShellException: If session creation fails
        """
        try:
            # Create detached session
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", name, command],
                capture_output=True,
                check=True,
                timeout=10,
            )
            logger.info(f"Created tmux session: {name}")
        except subprocess.CalledProcessError as e:
            raise ShellException(
                f"Failed to create tmux session {name}: {e.stderr.decode()}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise ShellException(f"Timeout creating tmux session {name}") from e

    def session_exists(self, name: str) -> bool:
        """Check if a tmux session exists.

        Args:
            name: Session name

        Returns:
            True if session exists
        """
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", name],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def send_command(self, session: str, command: str, wait_ms: int = 100) -> None:
        """Send command to tmux session.

        Args:
            session: Session name
            command: Command to send
            wait_ms: Milliseconds to wait after sending (default: 100)

        Raises:
            ShellException: If command send fails
        """
        try:
            # Send command with Enter key
            subprocess.run(
                ["tmux", "send-keys", "-t", session, command, "Enter"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            # Small delay to let command execute
            if wait_ms > 0:
                time.sleep(wait_ms / 1000.0)
            logger.debug(f"Sent command to session {session}: {command}")
        except subprocess.CalledProcessError as e:
            raise ShellException(
                f"Failed to send command to session {session}: {e.stderr.decode()}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise ShellException(f"Timeout sending command to session {session}") from e

    def capture_output(self, session: str, lines: int = 100) -> str:
        """Capture output from tmux session.

        Args:
            session: Session name
            lines: Number of lines to capture (default: 100)

        Returns:
            Captured output

        Raises:
            ShellException: If capture fails
        """
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session, "-p", "-S", f"-{lines}"],
                capture_output=True,
                check=True,
                timeout=5,
                text=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise ShellException(
                f"Failed to capture output from session {session}: {e.stderr.decode()}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise ShellException(f"Timeout capturing output from session {session}") from e

    def list_sessions(self) -> list[str]:
        """List all tmux sessions.

        Returns:
            List of session names
        """
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                timeout=5,
                text=True,
            )
            if result.returncode != 0:
                return []
            return [line.strip() for line in result.stdout.split("\n") if line.strip()]
        except subprocess.TimeoutExpired:
            return []

    def kill_session(self, name: str) -> None:
        """Kill a tmux session.

        Args:
            name: Session name

        Raises:
            ShellException: If kill fails
        """
        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", name],
                capture_output=True,
                check=True,
                timeout=5,
            )
            logger.info(f"Killed tmux session: {name}")
        except subprocess.CalledProcessError as e:
            # Session might not exist, which is fine
            logger.debug(f"Failed to kill session {name}: {e.stderr.decode()}")
        except subprocess.TimeoutExpired as e:
            raise ShellException(f"Timeout killing session {name}") from e

    def clear_history(self, session: str) -> None:
        """Clear history buffer for a session.

        Args:
            session: Session name
        """
        try:
            subprocess.run(
                ["tmux", "clear-history", "-t", session],
                capture_output=True,
                timeout=5,
            )
            logger.debug(f"Cleared history for session {session}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Not critical if this fails
            pass
