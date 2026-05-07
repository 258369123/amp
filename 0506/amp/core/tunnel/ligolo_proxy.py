"""Ligolo-ng proxy implementation for managing agent connections."""

import logging
import queue
import re
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from amp.exceptions import TunnelCreationFailed

from .models import Forward, Route, SessionInfo, SessionStatus

logger = logging.getLogger(__name__)


class LigoloProxy:
    """Ligolo-ng proxy that manages agent connections and routing."""

    def __init__(
        self,
        ligolo_binary: str,
        port: int,
        host: str = "0.0.0.0",
        selfcert: bool = True,
        extra_args: list[str] | None = None,
    ):
        """Initialize Ligolo-ng proxy.

        Args:
            ligolo_binary: Path to ligolo-ng binary
            port: Port to listen on
            host: Host to bind to (default: 0.0.0.0)
            selfcert: Use self-signed certificate
            extra_args: Additional command-line arguments
        """
        self.ligolo_binary = ligolo_binary
        self.port = port
        self.host = host
        self.selfcert = selfcert
        self.extra_args = extra_args or []

        self.process: subprocess.Popen[bytes] | None = None
        self.pid: int | None = None
        self._sessions: dict[str, SessionInfo] = {}
        self._command_queue: queue.Queue[str] = queue.Queue()
        self._monitor_thread: threading.Thread | None = None
        self._command_thread: threading.Thread | None = None
        self._stop_monitoring = threading.Event()

    def _build_command(self) -> list[str]:
        """Build ligolo-ng proxy command line."""
        cmd = [self.ligolo_binary, "proxy"]

        if self.selfcert:
            cmd.append("-selfcert")

        cmd.extend(["-laddr", f"{self.host}:{self.port}"])

        # Add extra arguments
        cmd.extend(self.extra_args)

        return cmd

    def start(self) -> int:
        """Start the Ligolo-ng proxy process.

        Returns:
            Process PID

        Raises:
            TunnelCreationFailed: If process fails to start
        """
        if self.process is not None:
            raise TunnelCreationFailed("Proxy already started", retry_possible=False)

        # Check if binary exists
        if not Path(self.ligolo_binary).exists():
            raise TunnelCreationFailed(
                f"Ligolo-ng binary not found: {self.ligolo_binary}",
                retry_possible=False,
            )

        cmd = self._build_command()
        logger.info(f"Starting Ligolo-ng proxy: {' '.join(cmd)}")

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                start_new_session=True,
            )
            self.pid = self.process.pid

            # Start monitoring threads
            self._stop_monitoring.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_output,
                daemon=True,
            )
            self._monitor_thread.start()

            self._command_thread = threading.Thread(
                target=self._command_sender,
                daemon=True,
            )
            self._command_thread.start()

            logger.info(f"Ligolo-ng proxy started with PID {self.pid}")
            return self.pid

        except FileNotFoundError as e:
            raise TunnelCreationFailed(
                f"Failed to execute ligolo-ng binary: {e}",
                retry_possible=False,
            ) from e
        except Exception as e:
            raise TunnelCreationFailed(
                f"Failed to start proxy: {e}",
                retry_possible=True,
            ) from e

    def _command_sender(self) -> None:
        """Send commands to proxy via stdin."""
        if not self.process or not self.process.stdin:
            return

        try:
            while not self._stop_monitoring.is_set():
                try:
                    # Get command from queue with timeout
                    command = self._command_queue.get(timeout=1)

                    # Send command to stdin
                    self.process.stdin.write(f"{command}\n".encode("utf-8"))
                    self.process.stdin.flush()
                    logger.debug(f"Sent command to ligolo proxy: {command}")

                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error sending command to proxy: {e}")
                    break

        except Exception as e:
            logger.error(f"Command sender thread error: {e}")

    def _monitor_output(self) -> None:
        """Monitor stdout for agent connections and events.

        Ligolo-ng logs agent info to stdout in format:
        Agent joined. name=agent-1 remote=192.168.1.100:12345
        """
        if not self.process or not self.process.stdout:
            return

        # Pattern to match agent connections
        # Example: "Agent joined. name=agent-1 remote=192.168.1.100:12345"
        agent_pattern = re.compile(
            r"Agent joined\.\s+name=([^\s]+)\s+remote=([^\s]+)"
        )

        try:
            for line in iter(self.process.stdout.readline, b""):
                if self._stop_monitoring.is_set():
                    break

                try:
                    text = line.decode("utf-8", errors="replace").strip()
                    logger.debug(f"Ligolo proxy log: {text}")

                    # Check for agent connection
                    match = agent_pattern.search(text)
                    if match:
                        agent_name = match.group(1)
                        remote_addr = match.group(2)

                        session_id = agent_name

                        # Create or update session
                        if session_id not in self._sessions:
                            self._sessions[session_id] = SessionInfo(
                                session_id=session_id,
                                status=SessionStatus.ACTIVE,
                                remote_addr=remote_addr,
                                connected_at=datetime.utcnow(),
                                metadata={"agent_name": agent_name},
                            )
                            logger.info(
                                f"New ligolo agent: {agent_name} from {remote_addr}"
                            )
                        else:
                            # Update existing session
                            self._sessions[session_id].status = SessionStatus.ACTIVE
                            self._sessions[session_id].remote_addr = remote_addr

                    # Check for agent disconnection
                    if "Agent disconnected" in text or "Agent left" in text:
                        # Try to extract agent name
                        name_match = re.search(r"name=([^\s]+)", text)
                        if name_match:
                            session_id = name_match.group(1)
                            if session_id in self._sessions:
                                self._sessions[session_id].status = SessionStatus.DISCONNECTED
                                logger.info(f"Agent {session_id} disconnected")

                except Exception as e:
                    logger.debug(f"Error parsing ligolo log line: {e}")

        except Exception as e:
            logger.error(f"Error monitoring ligolo output: {e}")

    def add_listener(
        self,
        session_id: str,
        listen_addr: str,
        target_addr: str,
    ) -> bool:
        """Add a port forward listener for a session.

        Args:
            session_id: Agent session ID
            listen_addr: Listen address (e.g., "0.0.0.0:8080")
            target_addr: Target address (e.g., "localhost:80")

        Returns:
            True if listener added successfully
        """
        if session_id not in self._sessions:
            logger.warning(f"Session {session_id} not found")
            return False

        # Send listener command to proxy
        # Format: "listener_add --addr 0.0.0.0:8080 --to localhost:80 --agent agent-1"
        command = f"listener_add --addr {listen_addr} --to {target_addr} --agent {session_id}"
        self._command_queue.put(command)

        # Add forward to session
        forward = Forward(
            listen_addr=listen_addr,
            target_addr=target_addr,
            protocol="tcp",
        )
        self._sessions[session_id].forwards.append(forward)
        logger.info(
            f"Added listener for session {session_id}: {listen_addr} => {target_addr}"
        )

        return True

    def add_route(self, session_id: str, network: str, interface: str = "ligolo") -> bool:
        """Add a network route for a session.

        Args:
            session_id: Agent session ID
            network: Network in CIDR notation (e.g., "10.0.0.0/24")
            interface: TUN interface name (default: "ligolo")

        Returns:
            True if route added successfully
        """
        if session_id not in self._sessions:
            logger.warning(f"Session {session_id} not found")
            return False

        # Send route command to proxy
        # Format: "route_add --network 10.0.0.0/24 --agent agent-1"
        command = f"route_add --network {network} --agent {session_id}"
        self._command_queue.put(command)

        # Add route to session
        route = Route(network=network, interface=interface)
        self._sessions[session_id].routes.append(route)
        logger.info(f"Added route for session {session_id}: {network} via {interface}")

        return True

    def list_sessions(self) -> list[SessionInfo]:
        """List all agent sessions.

        Returns:
            List of session information
        """
        return list(self._sessions.values())

    def is_alive(self) -> bool:
        """Check if proxy process is alive.

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
        """Stop the Ligolo-ng proxy gracefully.

        Args:
            timeout: Timeout in seconds for graceful shutdown
        """
        if self.process is None or self.pid is None:
            logger.warning("No proxy process to stop")
            return

        logger.info(f"Stopping Ligolo-ng proxy {self.pid}")

        # Stop monitoring threads
        self._stop_monitoring.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)
        if self._command_thread and self._command_thread.is_alive():
            self._command_thread.join(timeout=2)

        try:
            proc = psutil.Process(self.pid)

            # Try graceful termination first
            proc.terminate()

            try:
                proc.wait(timeout=timeout)
                logger.info(f"Proxy {self.pid} terminated gracefully")
            except psutil.TimeoutExpired:
                # Force kill if graceful termination fails
                logger.warning(f"Proxy {self.pid} did not terminate, killing")
                proc.kill()
                proc.wait(timeout=2)
                logger.info(f"Proxy {self.pid} killed")

        except psutil.NoSuchProcess:
            logger.info(f"Proxy {self.pid} already dead")
        except Exception as e:
            logger.error(f"Error stopping proxy {self.pid}: {e}")

        finally:
            self.process = None
            self.pid = None
            self._sessions.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get proxy process statistics.

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
                    "num_agents": len(self._sessions),
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
