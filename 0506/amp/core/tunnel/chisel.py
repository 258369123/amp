"""Chisel process wrapper for tunnel management."""

import logging
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from amp.exceptions import TunnelCreationFailed

logger = logging.getLogger(__name__)


class ChiselProcess:
    """Wrapper for Chisel client/server processes."""

    def __init__(
        self,
        chisel_binary: str,
        mode: str,
        local_host: str,
        local_port: int,
        remote_host: str | None = None,
        remote_port: int | None = None,
        auth: str | None = None,
        keepalive: int = 30,
        extra_args: list[str] | None = None,
    ):
        """Initialize Chisel process wrapper.

        Args:
            chisel_binary: Path to chisel binary
            mode: "client" or "server"
            local_host: Local bind host
            local_port: Local bind port
            remote_host: Remote host (for client mode)
            remote_port: Remote port (for client mode)
            auth: Authentication string (user:pass)
            keepalive: Keepalive interval in seconds
            extra_args: Additional command-line arguments
        """
        self.chisel_binary = chisel_binary
        self.mode = mode
        self.local_host = local_host
        self.local_port = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.auth = auth
        self.keepalive = keepalive
        self.extra_args = extra_args or []

        self.process: subprocess.Popen[bytes] | None = None
        self.pid: int | None = None
        self._stdout_log: list[str] = []
        self._stderr_log: list[str] = []

    def _build_command(self) -> list[str]:
        """Build chisel command line."""
        cmd = [self.chisel_binary, self.mode]

        if self.mode == "server":
            cmd.extend(["--host", self.local_host])
            cmd.extend(["--port", str(self.local_port)])
            if self.auth:
                cmd.extend(["--auth", self.auth])
            cmd.extend(["--keepalive", f"{self.keepalive}s"])

        elif self.mode == "client":
            if not self.remote_host or not self.remote_port:
                raise TunnelCreationFailed(
                    "remote_host and remote_port required for client mode",
                    retry_possible=False,
                )

            # Server URL
            server_url = f"http://{self.remote_host}:{self.remote_port}"
            cmd.append(server_url)

            # Port forwarding spec: local_port:remote_host:remote_port
            forward_spec = f"{self.local_port}:{self.local_host}:{self.local_port}"
            cmd.append(forward_spec)

            if self.auth:
                cmd.extend(["--auth", self.auth])
            cmd.extend(["--keepalive", f"{self.keepalive}s"])

        # Add extra arguments
        cmd.extend(self.extra_args)

        return cmd

    def start(self) -> int:
        """Start the Chisel process.

        Returns:
            Process PID

        Raises:
            TunnelCreationFailed: If process fails to start
        """
        if self.process is not None:
            raise TunnelCreationFailed("Process already started", retry_possible=False)

        # Check if binary exists
        if not Path(self.chisel_binary).exists():
            raise TunnelCreationFailed(
                f"Chisel binary not found: {self.chisel_binary}",
                retry_possible=False,
            )

        cmd = self._build_command()
        logger.info(f"Starting Chisel process: {' '.join(cmd)}")

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.pid = self.process.pid

            # Wait a bit to check if process starts successfully
            time.sleep(0.5)

            if not self.is_alive():
                stderr = self._read_stderr()
                raise TunnelCreationFailed(
                    f"Process died immediately: {stderr}",
                    retry_possible=True,
                )

            logger.info(f"Chisel process started with PID {self.pid}")
            return self.pid

        except FileNotFoundError as e:
            raise TunnelCreationFailed(
                f"Failed to execute chisel binary: {e}",
                retry_possible=False,
            ) from e
        except Exception as e:
            raise TunnelCreationFailed(
                f"Failed to start process: {e}",
                retry_possible=True,
            ) from e

    def is_alive(self) -> bool:
        """Check if process is alive.

        Returns:
            True if process is running
        """
        if self.process is None or self.pid is None:
            return False

        try:
            proc = psutil.Process(self.pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
        except Exception as e:
            logger.warning(f"Error checking process status: {e}")
            return False

    def stop(self, timeout: int = 5) -> None:
        """Stop the Chisel process gracefully.

        Args:
            timeout: Timeout in seconds for graceful shutdown
        """
        if self.process is None or self.pid is None:
            logger.warning("No process to stop")
            return

        logger.info(f"Stopping Chisel process {self.pid}")

        try:
            proc = psutil.Process(self.pid)

            # Try graceful termination first
            proc.terminate()

            try:
                proc.wait(timeout=timeout)
                logger.info(f"Process {self.pid} terminated gracefully")
            except psutil.TimeoutExpired:
                # Force kill if graceful termination fails
                logger.warning(f"Process {self.pid} did not terminate, killing")
                proc.kill()
                proc.wait(timeout=2)
                logger.info(f"Process {self.pid} killed")

        except psutil.NoSuchProcess:
            logger.info(f"Process {self.pid} already dead")
        except Exception as e:
            logger.error(f"Error stopping process {self.pid}: {e}")

        finally:
            self.process = None
            self.pid = None

    def get_stats(self) -> dict[str, Any]:
        """Get process statistics.

        Returns:
            Dictionary with process stats (cpu, memory, etc.)
        """
        if not self.is_alive() or self.pid is None:
            return {}

        try:
            proc = psutil.Process(self.pid)
            with proc.oneshot():
                return {
                    "pid": self.pid,
                    "cpu_percent": proc.cpu_percent(),
                    "memory_mb": proc.memory_info().rss / 1024 / 1024,
                    "num_threads": proc.num_threads(),
                    "status": proc.status(),
                    "create_time": proc.create_time(),
                }
        except psutil.NoSuchProcess:
            return {}
        except Exception as e:
            logger.warning(f"Error getting process stats: {e}")
            return {}

    def _read_stdout(self) -> str:
        """Read available stdout data."""
        if self.process is None or self.process.stdout is None:
            return ""

        try:
            # Non-blocking read
            import select

            if select.select([self.process.stdout], [], [], 0)[0]:
                data = self.process.stdout.read(4096)
                if data:
                    text = data.decode("utf-8", errors="replace")
                    self._stdout_log.append(text)
                    return text
        except Exception as e:
            logger.debug(f"Error reading stdout: {e}")

        return ""

    def _read_stderr(self) -> str:
        """Read available stderr data."""
        if self.process is None or self.process.stderr is None:
            return ""

        try:
            # Non-blocking read
            import select

            if select.select([self.process.stderr], [], [], 0)[0]:
                data = self.process.stderr.read(4096)
                if data:
                    text = data.decode("utf-8", errors="replace")
                    self._stderr_log.append(text)
                    return text
        except Exception as e:
            logger.debug(f"Error reading stderr: {e}")

        return ""

    def get_logs(self) -> dict[str, str]:
        """Get captured stdout and stderr logs.

        Returns:
            Dictionary with stdout and stderr
        """
        # Try to read any new data
        self._read_stdout()
        self._read_stderr()

        return {
            "stdout": "".join(self._stdout_log),
            "stderr": "".join(self._stderr_log),
        }

    def __del__(self) -> None:
        """Cleanup on deletion."""
        if self.process is not None:
            try:
                self.stop(timeout=2)
            except Exception:
                pass
