"""Ligolo-ng process wrapper for tunnel management."""

import logging
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from amp.exceptions import TunnelCreationFailed

logger = logging.getLogger(__name__)


class LigoloProcess:
    """Wrapper for Ligolo-ng agent/proxy processes."""

    def __init__(
        self,
        ligolo_binary: str,
        mode: str,
        interface: str | None = None,
        routes: list[str] | None = None,
        proxy_host: str | None = None,
        proxy_port: int | None = None,
        listen_addr: str | None = None,
        listen_port: int | None = None,
        ignore_cert: bool = True,
        selfcert: bool = True,
        extra_args: list[str] | None = None,
    ):
        """Initialize Ligolo-ng process wrapper.

        Args:
            ligolo_binary: Path to ligolo-ng binary
            mode: "agent" or "proxy"
            interface: TUN interface name (for proxy mode)
            routes: List of routes to add (CIDR format)
            proxy_host: Proxy host to connect to (for agent mode)
            proxy_port: Proxy port to connect to (for agent mode)
            listen_addr: Listen address (for proxy mode)
            listen_port: Listen port (for proxy mode)
            ignore_cert: Ignore certificate errors (agent mode)
            selfcert: Use self-signed certificate (proxy mode)
            extra_args: Additional command-line arguments
        """
        self.ligolo_binary = ligolo_binary
        self.mode = mode
        self.interface = interface
        self.routes = routes or []
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.listen_addr = listen_addr
        self.listen_port = listen_port
        self.ignore_cert = ignore_cert
        self.selfcert = selfcert
        self.extra_args = extra_args or []

        self.process: subprocess.Popen[bytes] | None = None
        self.pid: int | None = None
        self._stdout_log: list[str] = []
        self._stderr_log: list[str] = []

    def _build_command(self) -> list[str]:
        """Build ligolo-ng command line."""
        cmd = [self.ligolo_binary, self.mode]

        if self.mode == "proxy":
            if self.selfcert:
                cmd.append("-selfcert")

            if self.listen_addr and self.listen_port:
                cmd.extend(["-laddr", f"{self.listen_addr}:{self.listen_port}"])
            elif self.listen_port:
                cmd.extend(["-laddr", f"0.0.0.0:{self.listen_port}"])

        elif self.mode == "agent":
            if not self.proxy_host or not self.proxy_port:
                raise TunnelCreationFailed(
                    "proxy_host and proxy_port required for agent mode",
                    retry_possible=False,
                )

            # Connect to proxy
            cmd.extend(["-connect", f"{self.proxy_host}:{self.proxy_port}"])

            if self.ignore_cert:
                cmd.append("-ignore-cert")

        # Add extra arguments
        cmd.extend(self.extra_args)

        return cmd

    def start(self) -> int:
        """Start the Ligolo-ng process.

        Returns:
            Process PID

        Raises:
            TunnelCreationFailed: If process fails to start
        """
        if self.process is not None:
            raise TunnelCreationFailed("Process already started", retry_possible=False)

        # Check if binary exists
        if not Path(self.ligolo_binary).exists():
            raise TunnelCreationFailed(
                f"Ligolo-ng binary not found: {self.ligolo_binary}",
                retry_possible=False,
            )

        cmd = self._build_command()
        logger.info(f"Starting Ligolo-ng process: {' '.join(cmd)}")

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

            logger.info(f"Ligolo-ng process started with PID {self.pid}")
            return self.pid

        except FileNotFoundError as e:
            raise TunnelCreationFailed(
                f"Failed to execute ligolo-ng binary: {e}",
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
        """Stop the Ligolo-ng process gracefully.

        Args:
            timeout: Timeout in seconds for graceful shutdown
        """
        if self.process is None or self.pid is None:
            logger.warning("No process to stop")
            return

        logger.info(f"Stopping Ligolo-ng process {self.pid}")

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

    def add_route(self, cidr: str) -> bool:
        """Add a route through the TUN interface.

        Args:
            cidr: CIDR notation (e.g., "10.0.0.0/24")

        Returns:
            True if route added successfully
        """
        if self.mode != "proxy" or not self.interface:
            logger.warning("Routes can only be added in proxy mode with interface")
            return False

        try:
            # Use ip route add command
            cmd = ["ip", "route", "add", cidr, "dev", self.interface]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                logger.info(f"Added route {cidr} via {self.interface}")
                self.routes.append(cidr)
                return True
            else:
                logger.error(f"Failed to add route: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error adding route {cidr}: {e}")
            return False

    def remove_route(self, cidr: str) -> bool:
        """Remove a route from the TUN interface.

        Args:
            cidr: CIDR notation (e.g., "10.0.0.0/24")

        Returns:
            True if route removed successfully
        """
        if self.mode != "proxy" or not self.interface:
            logger.warning("Routes can only be removed in proxy mode with interface")
            return False

        try:
            # Use ip route del command
            cmd = ["ip", "route", "del", cidr, "dev", self.interface]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                logger.info(f"Removed route {cidr} from {self.interface}")
                if cidr in self.routes:
                    self.routes.remove(cidr)
                return True
            else:
                logger.error(f"Failed to remove route: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error removing route {cidr}: {e}")
            return False

    def __del__(self) -> None:
        """Cleanup on deletion."""
        if self.process is not None:
            try:
                self.stop(timeout=2)
            except Exception:
                pass
