"""Tmux-based shell manager - reliable and simple."""

import logging
import re
import subprocess
import time
from typing import Any

from amp.exceptions import ShellException

logger = logging.getLogger(__name__)


class TmuxShellManager:
    """Tmux-based shell manager - no prompt detection needed."""

    def __init__(self, session_name: str = "amp-shells"):
        """Initialize tmux shell manager.

        Args:
            session_name: Base tmux session name
        """
        self.session_name = session_name
        self._verify_tmux_installed()
        self._ensure_session()

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

    def _ensure_session(self) -> None:
        """Ensure tmux session exists."""
        if not self._session_exists():
            try:
                subprocess.run(
                    ["tmux", "new-session", "-d", "-s", self.session_name],
                    capture_output=True,
                    check=True,
                    timeout=10,
                )
                logger.info(f"Created tmux session: {self.session_name}")
            except subprocess.CalledProcessError as e:
                raise ShellException(
                    f"Failed to create tmux session: {e.stderr.decode()}"
                ) from e

    def _session_exists(self) -> bool:
        """Check if tmux session exists."""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", self.session_name],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def create_shell(
        self,
        shell_id: str,
        shell_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create shell as tmux window.

        Args:
            shell_id: Unique shell ID
            shell_type: 'bind', 'reverse', 'ssh'
            **kwargs: Connection parameters

        Returns:
            Shell info dict with success status
        """
        window_name = f"shell-{shell_id}"

        try:
            # Create new tmux window
            subprocess.run(
                ["tmux", "new-window", "-t", self.session_name, "-n", window_name],
                capture_output=True,
                check=True,
                timeout=10,
            )

            # Start appropriate shell type
            if shell_type == "bind":
                return self._start_bind_shell(
                    shell_id,
                    kwargs["target_host"],
                    kwargs["target_port"],
                )
            elif shell_type == "ssh":
                return self._start_ssh_shell(
                    shell_id,
                    kwargs["target_host"],
                    kwargs["username"],
                    kwargs.get("password"),
                    kwargs.get("key_path"),
                    kwargs.get("port", 22),
                )
            else:
                raise ShellException(f"Unsupported shell type: {shell_type}")

        except subprocess.CalledProcessError as e:
            raise ShellException(
                f"Failed to create tmux window: {e.stderr.decode()}"
            ) from e

    def _start_bind_shell(
        self,
        shell_id: str,
        target_host: str,
        target_port: int,
    ) -> dict[str, Any]:
        """Start bind shell using nc.

        Args:
            shell_id: Shell ID
            target_host: Target host
            target_port: Target port

        Returns:
            Shell info dict
        """
        window_name = f"shell-{shell_id}"
        target = f"{self.session_name}:{window_name}"

        try:
            # Send nc command
            self._send_keys(target, f"nc {target_host} {target_port}")
            time.sleep(0.5)

            # Disable colored prompt for cleaner output
            self._send_keys(target, "export PS1='$ '")
            time.sleep(0.2)

            logger.info(f"Started bind shell {shell_id} to {target_host}:{target_port}")

            return {
                "success": True,
                "shell_id": shell_id,
                "window_name": window_name,
                "connection": f"{target_host}:{target_port}",
            }

        except Exception as e:
            logger.error(f"Failed to start bind shell: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _start_ssh_shell(
        self,
        shell_id: str,
        target_host: str,
        username: str,
        password: str | None = None,
        key_path: str | None = None,
        port: int = 22,
    ) -> dict[str, Any]:
        """Start SSH shell.

        Args:
            shell_id: Shell ID
            target_host: Target host
            username: SSH username
            password: SSH password (optional)
            key_path: SSH key path (optional)
            port: SSH port

        Returns:
            Shell info dict
        """
        window_name = f"shell-{shell_id}"
        target = f"{self.session_name}:{window_name}"

        try:
            # Build SSH command
            if password:
                # Use sshpass if password provided
                ssh_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no {username}@{target_host} -p {port}"
            elif key_path:
                ssh_cmd = f"ssh -i {key_path} -o StrictHostKeyChecking=no {username}@{target_host} -p {port}"
            else:
                ssh_cmd = f"ssh -o StrictHostKeyChecking=no {username}@{target_host} -p {port}"

            # Send SSH command
            self._send_keys(target, ssh_cmd)
            time.sleep(2.0)  # Wait for SSH connection

            # Verify connection by sending test command
            self._send_keys(target, "echo SSH_READY")
            time.sleep(1.0)

            # Check output to verify connection
            output = self._capture_pane(target)
            if "SSH_READY" not in output:
                logger.error(f"SSH connection not established for {shell_id}")
                raise Exception("SSH connection not established - check credentials and network")

            # Disable colored prompt for cleaner output
            self._send_keys(target, "export PS1='$ '")
            self._send_keys(target, "export PS2='> '")
            time.sleep(0.2)

            logger.info(f"Started SSH shell {shell_id} to {username}@{target_host}:{port}")

            return {
                "success": True,
                "shell_id": shell_id,
                "window_name": window_name,
                "connection": f"{username}@{target_host}:{port}",
            }

        except Exception as e:
            logger.error(f"Failed to start SSH shell: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def execute_command(
        self,
        shell_id: str,
        command: str,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute command in shell with comprehensive error handling.

        Strategy:
        1. Check if window exists
        2. Clear pane history
        3. Send command
        4. Wait for output to stabilize
        5. Verify command was executed (check echo)
        6. Clean output

        Args:
            shell_id: Shell ID
            command: Command to execute
            timeout: Timeout in seconds

        Returns:
            Result dict with success, stdout, stderr, exit_code
        """
        window_name = f"shell-{shell_id}"
        target = f"{self.session_name}:{window_name}"

        try:
            # Check if window exists
            if not self._window_exists(shell_id):
                logger.error(f"Shell {shell_id} not found")
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                    "error": f"Shell {shell_id} not found",
                }

            # 1. Clear pane
            self._clear_pane(target)

            # 2. Send command
            self._send_keys(target, command)

            # 3. Wait for stable output
            output = self._wait_for_stable_output(target, timeout)

            # 4. Verify command echo
            if command.strip() not in output:
                logger.warning(f"Command not echoed - may not have been sent: {command}")
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                    "error": "Command not echoed - not sent",
                }

            # 5. Clean output (remove command echo)
            cleaned = self._clean_output(output, command)

            # 6. Verify output for commands that should have output
            if self._should_have_output(command) and not cleaned:
                logger.warning(f"Expected output but got none for: {command}")
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                    "error": "Expected output but got none",
                }

            logger.debug(f"Executed command in shell {shell_id}: {command}")

            return {
                "success": True,
                "stdout": cleaned,
                "stderr": "",
                "exit_code": 0,
            }

        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "error": str(e),
            }

    def _wait_for_stable_output(self, target: str, timeout: int) -> str:
        """Wait for output to stabilize.

        Strategy:
        - Capture output repeatedly
        - If same content 2 times = stable
        - Timeout = return current

        Args:
            target: Tmux target (session:window)
            timeout: Timeout in seconds

        Returns:
            Stable output
        """
        start_time = time.time()
        previous_output = ""
        stable_count = 0

        while time.time() - start_time < timeout:
            current_output = self._capture_pane(target)

            if current_output == previous_output:
                stable_count += 1
                if stable_count >= 2:
                    # Output is stable
                    return current_output
            else:
                stable_count = 0

            previous_output = current_output
            time.sleep(0.3)

        # Timeout - return current output
        return previous_output

    def _should_have_output(self, command: str) -> bool:
        """Check if command should produce output.

        Args:
            command: Command string

        Returns:
            True if command should produce output
        """
        output_commands = [
            "echo", "cat", "ls", "pwd", "whoami", "id",
            "hostname", "uname", "ps", "netstat", "ifconfig",
            "ip", "find", "grep", "awk", "sed", "head", "tail",
        ]
        command_lower = command.lower()
        return any(cmd in command_lower for cmd in output_commands)

    def _window_exists(self, shell_id: str) -> bool:
        """Check if tmux window exists.

        Args:
            shell_id: Shell ID

        Returns:
            True if window exists, False otherwise
        """
        window_name = f"shell-{shell_id}"
        try:
            result = subprocess.run(
                ["tmux", "list-windows", "-t", self.session_name, "-F", "#{window_name}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return window_name in result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    def _send_keys(self, target: str, keys: str) -> None:
        """Send keys to tmux window.

        Args:
            target: Tmux target (session:window)
            keys: Keys to send
        """
        subprocess.run(
            ["tmux", "send-keys", "-t", target, keys, "Enter"],
            capture_output=True,
            check=True,
            timeout=5,
        )

    def _capture_pane(self, target: str) -> str:
        """Capture tmux pane content.

        Args:
            target: Tmux target (session:window)

        Returns:
            Pane content
        """
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", target, "-p"],
            capture_output=True,
            timeout=5,
            text=True,
        )
        return result.stdout

    def _clear_pane(self, target: str) -> None:
        """Clear pane history.

        Args:
            target: Tmux target (session:window)
        """
        # Send Ctrl-L to clear screen
        subprocess.run(
            ["tmux", "send-keys", "-t", target, "C-l"],
            capture_output=True,
            timeout=5,
        )
        time.sleep(0.1)

        # Clear history buffer
        subprocess.run(
            ["tmux", "clear-history", "-t", target],
            capture_output=True,
            timeout=5,
        )

    def _clean_output(self, output: str, command: str) -> str:
        """Clean command output by removing echo, prompts, and ANSI codes.

        Args:
            output: Raw output
            command: Command that was executed

        Returns:
            Cleaned output
        """
        if not output:
            return ""

        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[mGKHJABCDEFnsuhl]')
        output = ansi_escape.sub('', output)

        lines = output.split("\n")

        # Remove first line if it contains the command echo
        if lines and lines[0].strip() == command.strip():
            lines = lines[1:]

        # Remove prompt lines (lines ending with $ or #)
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.endswith('$') and not stripped.endswith('#'):
                cleaned_lines.append(line)
            elif stripped and not (stripped == '$' or stripped == '#'):
                # Line has content before prompt
                cleaned_lines.append(line)

        # Remove empty lines at start and end
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()

        return "\n".join(cleaned_lines).strip()

    def close_shell(self, shell_id: str) -> None:
        """Close shell (kill tmux window).

        Args:
            shell_id: Shell ID
        """
        window_name = f"shell-{shell_id}"
        target = f"{self.session_name}:{window_name}"

        try:
            subprocess.run(
                ["tmux", "kill-window", "-t", target],
                capture_output=True,
                timeout=5,
            )
            logger.info(f"Closed shell {shell_id}")
        except Exception as e:
            logger.debug(f"Failed to close shell {shell_id}: {e}")

    def list_shells(self) -> list[str]:
        """List all shells (tmux windows).

        Returns:
            List of shell IDs
        """
        try:
            result = subprocess.run(
                ["tmux", "list-windows", "-t", self.session_name, "-F", "#{window_name}"],
                capture_output=True,
                timeout=5,
                text=True,
            )

            if result.returncode != 0:
                return []

            # Extract shell IDs from window names (shell-{id})
            shell_ids = []
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("shell-"):
                    shell_id = line[6:]  # Remove "shell-" prefix
                    shell_ids.append(shell_id)

            return shell_ids

        except Exception as e:
            logger.debug(f"Failed to list shells: {e}")
            return []

    def is_alive(self, shell_id: str) -> bool:
        """Check if shell is alive.

        Args:
            shell_id: Shell ID

        Returns:
            True if shell window exists
        """
        return shell_id in self.list_shells()
