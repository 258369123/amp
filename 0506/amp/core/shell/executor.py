"""Command execution with pexpect."""

import logging
import re
import time

import pexpect

from amp.exceptions import CommandExecutionFailed, ShellTimeout

logger = logging.getLogger(__name__)


class CommandResult:
    """Result of command execution."""

    def __init__(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_ms: int,
        success: bool,
    ):
        """Initialize command result.

        Args:
            stdout: Standard output
            stderr: Standard error
            exit_code: Exit code
            duration_ms: Execution duration in milliseconds
            success: Whether command succeeded
        """
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration_ms = duration_ms
        self.success = success


class CommandExecutor:
    """Execute commands in shell sessions using pexpect."""

    # Common shell prompts
    PROMPT_PATTERNS = [
        r"[\$#>]\s*$",  # Generic shell prompt
        r".*@.*:.*[\$#]\s*$",  # user@host:path$
        r".*>\s*$",  # Windows-style prompt
        pexpect.TIMEOUT,
        pexpect.EOF,
    ]

    def __init__(self) -> None:
        """Initialize command executor."""
        self._sessions: dict[str, pexpect.spawn] = {}

    def spawn_shell(self, shell_id: str, command: str = "bash") -> None:
        """Spawn a new shell process.

        Args:
            shell_id: Shell ID
            command: Shell command to spawn (default: bash)

        Raises:
            CommandExecutionFailed: If spawn fails
        """
        try:
            child = pexpect.spawn(
                command,
                encoding="utf-8",
                echo=False,
                timeout=30,
            )
            # Wait for initial prompt
            child.expect(self.PROMPT_PATTERNS, timeout=5)
            self._sessions[shell_id] = child
            logger.info(f"Spawned shell {shell_id} with command: {command}")
        except pexpect.ExceptionPexpect as e:
            raise CommandExecutionFailed(
                command=command,
                exit_code=-1,
                stderr=str(e),
            ) from e

    def execute(
        self,
        shell_id: str,
        command: str,
        timeout: int = 30,
    ) -> CommandResult:
        """Execute command in shell session.

        Args:
            shell_id: Shell ID
            command: Command to execute
            timeout: Timeout in seconds (default: 30)

        Returns:
            Command result

        Raises:
            ShellTimeout: If command times out
            CommandExecutionFailed: If execution fails
        """
        if shell_id not in self._sessions:
            raise CommandExecutionFailed(
                command=command,
                exit_code=-1,
                stderr=f"Shell {shell_id} not found",
            )

        child = self._sessions[shell_id]
        start_time = time.time()

        try:
            # Send command
            child.sendline(command)

            # Wait for command to complete
            index = child.expect(self.PROMPT_PATTERNS, timeout=timeout)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Get output
            output = child.before if child.before else ""

            # Check for timeout or EOF
            if index == len(self.PROMPT_PATTERNS) - 2:  # TIMEOUT
                raise ShellTimeout(command=command, timeout=timeout)
            if index == len(self.PROMPT_PATTERNS) - 1:  # EOF
                raise CommandExecutionFailed(
                    command=command,
                    exit_code=-1,
                    stderr="Shell process terminated unexpectedly",
                )

            # Get exit code
            exit_code = self._get_exit_code(child, timeout=5)

            # Parse output (remove command echo)
            stdout = self._clean_output(output, command)

            logger.debug(
                f"Executed command in shell {shell_id}: {command} "
                f"(exit_code={exit_code}, duration={duration_ms}ms)"
            )

            return CommandResult(
                stdout=stdout,
                stderr="",
                exit_code=exit_code,
                duration_ms=duration_ms,
                success=(exit_code == 0),
            )

        except pexpect.TIMEOUT as e:
            duration_ms = int((time.time() - start_time) * 1000)
            raise ShellTimeout(command=command, timeout=timeout) from e
        except pexpect.EOF as e:
            raise CommandExecutionFailed(
                command=command,
                exit_code=-1,
                stderr="Shell process terminated unexpectedly",
            ) from e
        except Exception as e:
            raise CommandExecutionFailed(
                command=command,
                exit_code=-1,
                stderr=str(e),
            ) from e

    def _get_exit_code(self, child: pexpect.spawn, timeout: int = 5) -> int:
        """Get exit code of last command.

        Args:
            child: pexpect spawn object
            timeout: Timeout in seconds

        Returns:
            Exit code (0 if unable to determine)
        """
        try:
            # Send command to get exit code
            child.sendline("echo $?")
            child.expect(self.PROMPT_PATTERNS, timeout=timeout)
            output = child.before if child.before else ""

            # Parse exit code from output
            match = re.search(r"(\d+)", output)
            if match:
                return int(match.group(1))
        except Exception as e:
            logger.debug(f"Failed to get exit code: {e}")

        return 0

    def _clean_output(self, output: str, command: str) -> str:
        """Clean command output by removing echo and prompts.

        Args:
            output: Raw output
            command: Command that was executed

        Returns:
            Cleaned output
        """
        lines = output.split("\n")

        # Remove first line if it's the command echo
        if lines and command in lines[0]:
            lines = lines[1:]

        # Remove empty lines at start and end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        return "\n".join(lines)

    def close_shell(self, shell_id: str) -> None:
        """Close shell session.

        Args:
            shell_id: Shell ID
        """
        if shell_id in self._sessions:
            try:
                child = self._sessions[shell_id]
                child.sendline("exit")
                child.close(force=True)
            except Exception as e:
                logger.debug(f"Error closing shell {shell_id}: {e}")
            finally:
                del self._sessions[shell_id]
                logger.info(f"Closed shell {shell_id}")

    def is_alive(self, shell_id: str) -> bool:
        """Check if shell session is alive.

        Args:
            shell_id: Shell ID

        Returns:
            True if shell is alive
        """
        if shell_id not in self._sessions:
            return False
        return self._sessions[shell_id].isalive()
