"""Windows command execution with PowerShell and CMD support."""

import base64
import logging
import re
import time

import pexpect

from amp.exceptions import CommandExecutionFailed, ShellTimeout

logger = logging.getLogger(__name__)


class WindowsCommandResult:
    """Result of Windows command execution."""

    def __init__(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_ms: int,
        success: bool,
    ):
        """Initialize Windows command result.

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


class WindowsExecutor:
    """Execute commands in Windows shell sessions (PowerShell/CMD)."""

    # PowerShell prompts
    POWERSHELL_PROMPTS = [
        r"PS\s+[A-Z]:\\.*>\s*$",  # PS C:\Users\user>
        r"PS\s+.*>\s*$",  # PS >
        pexpect.TIMEOUT,
        pexpect.EOF,
    ]

    # CMD prompts
    CMD_PROMPTS = [
        r"[A-Z]:\\.*>\s*$",  # C:\Users\user>
        r">\s*$",  # >
        pexpect.TIMEOUT,
        pexpect.EOF,
    ]

    def __init__(self) -> None:
        """Initialize Windows command executor."""
        self._sessions: dict[str, pexpect.spawn] = {}
        self._shell_types: dict[str, str] = {}  # Track shell type (powershell/cmd)

    def spawn_powershell(self, shell_id: str) -> None:
        """Spawn a PowerShell process.

        Args:
            shell_id: Shell ID

        Raises:
            CommandExecutionFailed: If spawn fails
        """
        try:
            # Use PowerShell with no profile for faster startup
            child = pexpect.spawn(
                "powershell.exe -NoProfile -NoLogo",
                encoding="utf-8",
                echo=False,
                timeout=30,
            )
            # Wait for initial prompt
            child.expect(self.POWERSHELL_PROMPTS, timeout=10)
            self._sessions[shell_id] = child
            self._shell_types[shell_id] = "powershell"
            logger.info(f"Spawned PowerShell session {shell_id}")
        except pexpect.ExceptionPexpect as e:
            raise CommandExecutionFailed(
                command="powershell.exe",
                exit_code=-1,
                stderr=str(e),
            ) from e

    def spawn_cmd(self, shell_id: str) -> None:
        """Spawn a CMD process.

        Args:
            shell_id: Shell ID

        Raises:
            CommandExecutionFailed: If spawn fails
        """
        try:
            child = pexpect.spawn(
                "cmd.exe",
                encoding="utf-8",
                echo=False,
                timeout=30,
            )
            # Wait for initial prompt
            child.expect(self.CMD_PROMPTS, timeout=10)
            self._sessions[shell_id] = child
            self._shell_types[shell_id] = "cmd"
            logger.info(f"Spawned CMD session {shell_id}")
        except pexpect.ExceptionPexpect as e:
            raise CommandExecutionFailed(
                command="cmd.exe",
                exit_code=-1,
                stderr=str(e),
            ) from e

    def execute_powershell(
        self,
        shell_id: str,
        command: str,
        timeout: int = 30,
    ) -> WindowsCommandResult:
        """Execute PowerShell command.

        Args:
            shell_id: Shell ID
            command: PowerShell command to execute
            timeout: Timeout in seconds (default: 30)

        Returns:
            Windows command result

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
            index = child.expect(self.POWERSHELL_PROMPTS, timeout=timeout)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Get output
            output = child.before if child.before else ""

            # Check for timeout or EOF
            if index == len(self.POWERSHELL_PROMPTS) - 2:  # TIMEOUT
                raise ShellTimeout(command=command, timeout=timeout)
            if index == len(self.POWERSHELL_PROMPTS) - 1:  # EOF
                raise CommandExecutionFailed(
                    command=command,
                    exit_code=-1,
                    stderr="Shell process terminated unexpectedly",
                )

            # Get exit code
            exit_code = self._get_powershell_exit_code(child, timeout=5)

            # Parse output (remove command echo)
            stdout = self._clean_output(output, command)

            logger.debug(
                f"Executed PowerShell command in shell {shell_id}: {command} "
                f"(exit_code={exit_code}, duration={duration_ms}ms)"
            )

            return WindowsCommandResult(
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

    def execute_cmd(
        self,
        shell_id: str,
        command: str,
        timeout: int = 30,
    ) -> WindowsCommandResult:
        """Execute CMD command.

        Args:
            shell_id: Shell ID
            command: CMD command to execute
            timeout: Timeout in seconds (default: 30)

        Returns:
            Windows command result

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
            index = child.expect(self.CMD_PROMPTS, timeout=timeout)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Get output
            output = child.before if child.before else ""

            # Check for timeout or EOF
            if index == len(self.CMD_PROMPTS) - 2:  # TIMEOUT
                raise ShellTimeout(command=command, timeout=timeout)
            if index == len(self.CMD_PROMPTS) - 1:  # EOF
                raise CommandExecutionFailed(
                    command=command,
                    exit_code=-1,
                    stderr="Shell process terminated unexpectedly",
                )

            # Get exit code
            exit_code = self._get_cmd_exit_code(child, timeout=5)

            # Parse output (remove command echo)
            stdout = self._clean_output(output, command)

            logger.debug(
                f"Executed CMD command in shell {shell_id}: {command} "
                f"(exit_code={exit_code}, duration={duration_ms}ms)"
            )

            return WindowsCommandResult(
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

    def _get_powershell_exit_code(self, child: pexpect.spawn, timeout: int = 5) -> int:
        """Get exit code of last PowerShell command.

        Args:
            child: pexpect spawn object
            timeout: Timeout in seconds

        Returns:
            Exit code (0 if unable to determine)
        """
        try:
            # Send command to get exit code
            child.sendline("$LASTEXITCODE")
            child.expect(self.POWERSHELL_PROMPTS, timeout=timeout)
            output = child.before if child.before else ""

            # Parse exit code from output
            match = re.search(r"(\d+)", output)
            if match:
                return int(match.group(1))
        except Exception as e:
            logger.debug(f"Failed to get PowerShell exit code: {e}")

        return 0

    def _get_cmd_exit_code(self, child: pexpect.spawn, timeout: int = 5) -> int:
        """Get exit code of last CMD command.

        Args:
            child: pexpect spawn object
            timeout: Timeout in seconds

        Returns:
            Exit code (0 if unable to determine)
        """
        try:
            # Send command to get exit code
            child.sendline("echo %ERRORLEVEL%")
            child.expect(self.CMD_PROMPTS, timeout=timeout)
            output = child.before if child.before else ""

            # Parse exit code from output
            match = re.search(r"(\d+)", output)
            if match:
                return int(match.group(1))
        except Exception as e:
            logger.debug(f"Failed to get CMD exit code: {e}")

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

    def parse_powershell_output(self, output: str) -> str:
        """Parse PowerShell object output to text.

        PowerShell often returns objects that need formatting.

        Args:
            output: Raw PowerShell output

        Returns:
            Formatted text output
        """
        # PowerShell output is usually already formatted
        # This method can be extended for complex object parsing
        return output.strip()

    def close_shell(self, shell_id: str) -> None:
        """Close Windows shell session.

        Args:
            shell_id: Shell ID
        """
        if shell_id in self._sessions:
            try:
                child = self._sessions[shell_id]
                child.sendline("exit")
                child.close(force=True)
            except Exception as e:
                logger.debug(f"Error closing Windows shell {shell_id}: {e}")
            finally:
                del self._sessions[shell_id]
                if shell_id in self._shell_types:
                    del self._shell_types[shell_id]
                logger.info(f"Closed Windows shell {shell_id}")

    def is_alive(self, shell_id: str) -> bool:
        """Check if Windows shell session is alive.

        Args:
            shell_id: Shell ID

        Returns:
            True if shell is alive
        """
        if shell_id not in self._sessions:
            return False
        return bool(self._sessions[shell_id].isalive())

    def get_shell_type(self, shell_id: str) -> str | None:
        """Get shell type (powershell/cmd).

        Args:
            shell_id: Shell ID

        Returns:
            Shell type or None if not found
        """
        return self._shell_types.get(shell_id)

    @staticmethod
    def encode_powershell_command(command: str) -> str:
        """Encode PowerShell command to Base64 (UTF-16LE).

        Useful for bypassing execution policy and special characters.

        Args:
            command: PowerShell command

        Returns:
            Base64 encoded command
        """
        # PowerShell expects UTF-16LE encoding
        encoded = base64.b64encode(command.encode("utf-16le")).decode()
        return encoded

    @staticmethod
    def build_encoded_powershell_command(command: str) -> str:
        """Build PowerShell command with encoded payload.

        Args:
            command: PowerShell command to encode

        Returns:
            Full PowerShell command with -EncodedCommand
        """
        encoded = WindowsExecutor.encode_powershell_command(command)
        return f"powershell.exe -EncodedCommand {encoded}"
