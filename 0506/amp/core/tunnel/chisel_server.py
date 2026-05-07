"""Chisel server implementation for managing client sessions."""

import logging
import re
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from amp.exceptions import TunnelCreationFailed

from .models import Forward, SessionInfo, SessionStatus

logger = logging.getLogger(__name__)


class ChiselServer:
    """Chisel server that manages client connections and forwards."""

    def __init__(
        self,
        chisel_binary: str,
        port: int,
        host: str = "0.0.0.0",
        auth: str | None = None,
        keepalive: int = 30,
        extra_args: list[str] | None = None,
    ):
        """Initialize Chisel server.

        Args:
            chisel_binary: Path to chisel binary
            port: Port to listen on
            host: Host to bind to (default: 0.0.0.0)
            auth: Authentication string (user:pass)
            keepalive: Keepalive interval in seconds
            extra_args: Additional command-line arguments
        """
        self.chisel_binary = chisel_binary
        self.port = port
        self.host = host
        self.auth = auth
        self.keepalive = keepalive
        self.extra_args = extra_args or []

        self.process: subprocess.Popen[bytes] | None = None
        self.pid: int | None = None
        self._sessions: dict[str, SessionInfo] = {}
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitoring = threading.Event()

    def _build_command(self) -> list[str]:
        """Build chisel server command line."""
        cmd = [self.chisel_binary, "server"]
        cmd.extend(["--host", self.host])
        cmd.extend(["--port", str(self.port)])

        if self.auth:
            cmd.extend(["--auth", self.auth])

        cmd.extend(["--keepalive", f"{self.keepalive}s"])

        # Enable reverse tunneling
        cmd.append("--reverse")

        # Add extra arguments
        cmd.extend(self.extra_args)

        return cmd

    def start(self) -> int:
        """Start the Chisel server process.

        Returns:
            Process PID

        Raises:
            TunnelCreationFailed: If process fails to start
        """
        if self.process is not None:
            raise TunnelCreationFailed("Server already started", retry_possible=False)

        # Check if binary exists
        if not Path(self.chisel_binary).exists():
            raise TunnelCreationFailed(
                f"Chisel binary not found: {self.chisel_binary}",
                retry_possible=False,
            )

        cmd = self._build_command()
        logger.info(f"Starting Chisel server: {' '.join(cmd)}")

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.pid = self.process.pid

            # Start log monitoring thread
            self._stop_monitoring.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_logs,
                daemon=True,
            )
            self._monitor_thread.start()

            logger.info(f"Chisel server started with PID {self.pid}")
            return self.pid

        except FileNotFoundError as e:
            raise TunnelCreationFailed(
                f"Failed to execute chisel binary: {e}",
                retry_possible=False,
            ) from e
        except Exception as e:
            raise TunnelCreationFailed(
                f"Failed to start server: {e}",
                retry_possible=True,
            ) from e

    def _monitor_logs(self) -> None:
        """Monitor stderr logs for session information.

        Chisel logs session info to stderr in format:
        session#1 tun: proxy#R:0.0.0.0:9000=>localhost:80
        """
        if not self.process or not self.process.stderr:
            return

        # Pattern to match session logs
        # Example: "session#1 tun: proxy#R:0.0.0.0:9000=>localhost:80"
        session_pattern = re.compile(
            r"session#(\d+)\s+tun:\s+proxy#R:([^=]+)=>(.+)"
        )

        try:
            for line in iter(self.process.stderr.readline, b""):
                if self._stop_monitoring.is_set():
                    break

                try:
                    text = line.decode("utf-8", errors="replace").strip()
                    logger.debug(f"Chisel server log: {text}")

                    # Check for session connection
                    match = session_pattern.search(text)
                    if match:
                        session_num = match.group(1)
                        listen_addr = match.group(2)
                        target_addr = match.group(3)

                        session_id = f"session#{session_num}"

                        # Create or update session
                        if session_id not in self._sessions:
                            self._sessions[session_id] = SessionInfo(
                                session_id=session_id,
                                status=SessionStatus.ACTIVE,
                                remote_addr="unknown",  # Chisel doesn't log client IP easily
                                connected_at=datetime.utcnow(),
                            )
                            logger.info(f"New chisel session: {session_id}")

                        # Add forward to session
                        forward = Forward(
                            listen_addr=listen_addr,
                            target_addr=target_addr,
                            protocol="tcp",
                        )
                        self._sessions[session_id].forwards.append(forward)
                        logger.info(
                            f"Session {session_id} added forward: "
                            f"{listen_addr} => {target_addr}"
                        )

                    # Check for session disconnection
                    if "session closed" in text.lower() or "disconnected" in text.lower():
                        # Try to extract session number
                        session_match = re.search(r"session#(\d+)", text)
                        if session_match:
                            session_id = f"session#{session_match.group(1)}"
                            if session_id in self._sessions:
                                self._sessions[session_id].status = SessionStatus.DISCONNECTED
                                logger.info(f"Session {session_id} disconnected")

                except Exception as e:
                    logger.debug(f"Error parsing chisel log line: {e}")

        except Exception as e:
            logger.error(f"Error monitoring chisel logs: {e}")

    def list_sessions(self) -> list[SessionInfo]:
        """List all sessions.

        Returns:
            List of session information
        """
        return list(self._sessions.values())

    def is_alive(self) -> bool:
        """Check if server process is alive.

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
        """Stop the Chisel server gracefully.

        Args:
            timeout: Timeout in seconds for graceful shutdown
        """
        if self.process is None or self.pid is None:
            logger.warning("No server process to stop")
            return

        logger.info(f"Stopping Chisel server {self.pid}")

        # Stop monitoring thread
        self._stop_monitoring.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)

        try:
            proc = psutil.Process(self.pid)

            # Try graceful termination first
            proc.terminate()

            try:
                proc.wait(timeout=timeout)
                logger.info(f"Server {self.pid} terminated gracefully")
            except psutil.TimeoutExpired:
                # Force kill if graceful termination fails
                logger.warning(f"Server {self.pid} did not terminate, killing")
                proc.kill()
                proc.wait(timeout=2)
                logger.info(f"Server {self.pid} killed")

        except psutil.NoSuchProcess:
            logger.info(f"Server {self.pid} already dead")
        except Exception as e:
            logger.error(f"Error stopping server {self.pid}: {e}")

        finally:
            self.process = None
            self.pid = None
            self._sessions.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get server process statistics.

        Returns:
            Dictionary with process stats
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
                    "num_sessions": len(self._sessions),
                }
        except psutil.NoSuchProcess:
            return {}
        except Exception as e:
            logger.warning(f"Error getting process stats: {e}")
            return {}

    def __del__(self) -> None:
        """Cleanup on deletion."""
        if self.process is not None:
            try:
                self.stop(timeout=2)
            except Exception:
                pass
