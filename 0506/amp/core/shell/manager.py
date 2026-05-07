"""Shell manager for creating and managing shell sessions."""

import logging
import socket
import threading
import time

from amp.config import settings
from amp.exceptions import (
    ShellCreationFailed,
    ShellDied,
    ShellLimitExceeded,
)
from amp.storage.database import Database
from amp.storage.models import (
    ExecuteCommandResponse,
    OperationType,
    OSType,
    PrivilegeLevel,
    ShellModel,
    ShellProgram,
    ShellStatus,
    ShellType,
)
from amp.storage.repository import OperationRepository, ShellRepository

from .executor import CommandExecutor
from .payloads import ShellPayloads
from .state import ShellState
from .tmux_backend import TmuxBackend

logger = logging.getLogger(__name__)


class ShellManager:
    """Manager for shell session lifecycle and command execution."""

    def __init__(self, database: Database):
        """Initialize shell manager.

        Args:
            database: Database instance for persistence
        """
        self.database = database
        self.tmux = TmuxBackend()
        self.executor = CommandExecutor()
        self.state = ShellState()
        self._listeners: dict[str, socket.socket] = {}
        self._listener_threads: dict[str, threading.Thread] = {}

    def create_reverse_shell(
        self,
        name: str,
        local_port: int,
        target_host: str,
        tunnel_id: str | None = None,
        payload_type: str = "bash",
        use_tmux: bool = True,
        timeout: int = 30,
    ) -> tuple[ShellModel, str]:
        """Create a reverse shell (listener on attacker).

        Args:
            name: Shell name
            local_port: Local port to listen on
            target_host: Target host (for documentation)
            tunnel_id: Tunnel ID if using tunnel
            payload_type: Payload type (bash, python, nc, etc.)
            use_tmux: Whether to use tmux for persistence
            timeout: Timeout in seconds to wait for connection

        Returns:
            Tuple of (shell model, payload command)

        Raises:
            ShellLimitExceeded: If max shells limit reached
            ShellCreationFailed: If shell creation fails
        """
        with self.database.session() as session:
            repo = ShellRepository(session)

            # Check shell limit
            active_count = len(repo.list_active())
            if active_count >= settings.shell.max_shells:
                raise ShellLimitExceeded(active_count, settings.shell.max_shells)

            # Generate payload
            local_ip = "0.0.0.0"  # Listen on all interfaces
            payload = ShellPayloads.get_payload(payload_type, local_ip, local_port)

            # Create shell record
            shell_data = {
                "name": name,
                "shell_type": ShellType.REVERSE.value,
                "os_type": OSType.LINUX.value,
                "shell_program": ShellProgram.BASH.value,
                "status": ShellStatus.ACTIVE.value,
                "tunnel_id": tunnel_id,
                "target_host": target_host,
                "target_port": local_port,
                "tmux_session": f"amp-shell-{name}" if use_tmux else None,
                "privilege_level": PrivilegeLevel.USER.value,
                "config": {
                    "payload_type": payload_type,
                    "local_port": local_port,
                },
            }

            shell_model = repo.create(shell_data)
            session.commit()

            # Start listener
            try:
                self._start_reverse_listener(
                    shell_model.id,
                    local_port,
                    use_tmux,
                    timeout,
                )
            except Exception as e:
                # Clean up on failure
                repo.update_status(shell_model.id, ShellStatus.DEAD)
                session.commit()
                raise ShellCreationFailed(
                    reason=f"Failed to start listener: {e}",
                    target=target_host,
                ) from e

            logger.info(
                f"Created reverse shell {shell_model.id} ({name}) "
                f"listening on port {local_port}"
            )

            return shell_model, payload

    def _start_reverse_listener(
        self,
        shell_id: str,
        port: int,
        use_tmux: bool,
        timeout: int,
    ) -> None:
        """Start reverse shell listener.

        Args:
            shell_id: Shell ID
            port: Port to listen on
            use_tmux: Whether to use tmux
            timeout: Connection timeout
        """
        # Create listener socket
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("0.0.0.0", port))
        listener.listen(1)
        listener.settimeout(timeout)

        self._listeners[shell_id] = listener

        # Start listener thread
        thread = threading.Thread(
            target=self._accept_reverse_connection,
            args=(shell_id, listener, use_tmux),
            daemon=True,
        )
        thread.start()
        self._listener_threads[shell_id] = thread

        logger.info(f"Started reverse listener for shell {shell_id} on port {port}")

    def _accept_reverse_connection(
        self,
        shell_id: str,
        listener: socket.socket,
        use_tmux: bool,
    ) -> None:
        """Accept reverse shell connection.

        Args:
            shell_id: Shell ID
            listener: Listener socket
            use_tmux: Whether to use tmux
        """
        try:
            conn, addr = listener.accept()
            logger.info(f"Accepted reverse connection for shell {shell_id} from {addr}")

            # If using tmux, create session and attach
            if use_tmux:
                with self.database.session() as session:
                    repo = ShellRepository(session)
                    shell = repo.get(shell_id)
                    if shell and shell.tmux_session:
                        self.tmux.create_session(shell.tmux_session, "bash")

            # Spawn shell with executor
            self.executor.spawn_shell(shell_id, "bash")

            # Update shell state
            self._update_shell_state_internal(shell_id)

        except TimeoutError:
            logger.warning(f"Reverse listener timeout for shell {shell_id}")
            with self.database.session() as session:
                repo = ShellRepository(session)
                repo.update_status(shell_id, ShellStatus.DEAD)
                session.commit()
        except Exception as e:
            logger.error(f"Error accepting reverse connection for shell {shell_id}: {e}")
            with self.database.session() as session:
                repo = ShellRepository(session)
                repo.update_status(shell_id, ShellStatus.DEAD)
                session.commit()
        finally:
            listener.close()
            if shell_id in self._listeners:
                del self._listeners[shell_id]

    def create_bind_shell(
        self,
        name: str,
        target_host: str,
        target_port: int,
        tunnel_id: str | None = None,
        use_tmux: bool = True,
    ) -> ShellModel:
        """Create a bind shell (listener on target).

        Args:
            name: Shell name
            target_host: Target host
            target_port: Target port
            tunnel_id: Tunnel ID if using tunnel
            use_tmux: Whether to use tmux for persistence

        Returns:
            Shell model

        Raises:
            ShellLimitExceeded: If max shells limit reached
            ShellCreationFailed: If shell creation fails
        """
        with self.database.session() as session:
            repo = ShellRepository(session)

            # Check shell limit
            active_count = len(repo.list_active())
            if active_count >= settings.shell.max_shells:
                raise ShellLimitExceeded(active_count, settings.shell.max_shells)

            # Create shell record
            shell_data = {
                "name": name,
                "shell_type": ShellType.BIND.value,
                "os_type": OSType.LINUX.value,
                "shell_program": ShellProgram.BASH.value,
                "status": ShellStatus.ACTIVE.value,
                "tunnel_id": tunnel_id,
                "target_host": target_host,
                "target_port": target_port,
                "tmux_session": f"amp-shell-{name}" if use_tmux else None,
                "privilege_level": PrivilegeLevel.USER.value,
                "config": {},
            }

            shell_model = repo.create(shell_data)
            session.commit()

            # Connect to bind shell
            try:
                # Create tmux session if needed
                if use_tmux and shell_model.tmux_session:
                    self.tmux.create_session(shell_model.tmux_session, "bash")

                # Connect using netcat or similar
                connect_cmd = f"nc {target_host} {target_port}"
                self.executor.spawn_shell(shell_model.id, connect_cmd)

                # Update shell state
                self._update_shell_state_internal(shell_model.id)

            except Exception as e:
                repo.update_status(shell_model.id, ShellStatus.DEAD)
                session.commit()
                raise ShellCreationFailed(
                    reason=f"Failed to connect to bind shell: {e}",
                    target=f"{target_host}:{target_port}",
                ) from e

            logger.info(
                f"Created bind shell {shell_model.id} ({name}) "
                f"connected to {target_host}:{target_port}"
            )

            return shell_model

    def create_ssh_shell(
        self,
        name: str,
        target_host: str,
        username: str,
        password: str | None = None,
        key_path: str | None = None,
        tunnel_id: str | None = None,
        port: int = 22,
        use_tmux: bool = True,
    ) -> ShellModel:
        """Create an SSH shell.

        Args:
            name: Shell name
            target_host: Target host
            username: SSH username
            password: SSH password (optional)
            key_path: SSH key path (optional)
            tunnel_id: Tunnel ID if using tunnel
            port: SSH port (default: 22)
            use_tmux: Whether to use tmux for persistence

        Returns:
            Shell model

        Raises:
            ShellLimitExceeded: If max shells limit reached
            ShellCreationFailed: If shell creation fails
        """
        with self.database.session() as session:
            repo = ShellRepository(session)

            # Check shell limit
            active_count = len(repo.list_active())
            if active_count >= settings.shell.max_shells:
                raise ShellLimitExceeded(active_count, settings.shell.max_shells)

            # Create shell record
            shell_data = {
                "name": name,
                "shell_type": ShellType.SSH.value,
                "os_type": OSType.LINUX.value,
                "shell_program": ShellProgram.BASH.value,
                "status": ShellStatus.ACTIVE.value,
                "tunnel_id": tunnel_id,
                "target_host": target_host,
                "target_port": port,
                "tmux_session": f"amp-shell-{name}" if use_tmux else None,
                "privilege_level": PrivilegeLevel.USER.value,
                "config": {
                    "username": username,
                    "key_path": key_path,
                },
            }

            shell_model = repo.create(shell_data)
            session.commit()

            # Connect via SSH
            try:
                # Create tmux session if needed
                if use_tmux and shell_model.tmux_session:
                    self.tmux.create_session(shell_model.tmux_session, "bash")

                # Build SSH command
                ssh_cmd = f"ssh {username}@{target_host} -p {port}"
                if key_path:
                    ssh_cmd += f" -i {key_path}"

                self.executor.spawn_shell(shell_model.id, ssh_cmd)

                # If password provided, send it
                if password:
                    time.sleep(1)  # Wait for password prompt
                    self.executor.execute(shell_model.id, password, timeout=10)

                # Update shell state
                self._update_shell_state_internal(shell_model.id)

            except Exception as e:
                repo.update_status(shell_model.id, ShellStatus.DEAD)
                session.commit()
                raise ShellCreationFailed(
                    reason=f"Failed to connect via SSH: {e}",
                    target=f"{username}@{target_host}:{port}",
                ) from e

            logger.info(
                f"Created SSH shell {shell_model.id} ({name}) "
                f"connected to {username}@{target_host}:{port}"
            )

            return shell_model

    def execute_command(
        self,
        shell_id: str,
        command: str,
        timeout: int = 30,
    ) -> ExecuteCommandResponse:
        """Execute command in shell session.

        Args:
            shell_id: Shell ID
            command: Command to execute
            timeout: Timeout in seconds (default: 30)

        Returns:
            Command execution response

        Raises:
            ShellNotFound: If shell not found
            ShellTimeout: If command times out
        """
        with self.database.session() as session:
            shell_repo = ShellRepository(session)
            op_repo = OperationRepository(session)

            # Verify shell exists
            shell_repo.get_or_raise(shell_id)

            # Check if shell is alive
            if not self.executor.is_alive(shell_id):
                shell_repo.update_status(shell_id, ShellStatus.DEAD)
                session.commit()
                raise ShellDied(shell_id, "Shell process is not alive")

            # Execute command
            start_time = time.time()
            try:
                result = self.executor.execute(shell_id, command, timeout)
            except Exception as e:
                # Record failed operation
                duration_ms = int((time.time() - start_time) * 1000)
                op_data = {
                    "operation_type": OperationType.COMMAND.value,
                    "shell_id": shell_id,
                    "command": command,
                    "stdout": "",
                    "stderr": str(e),
                    "exit_code": -1,
                    "duration_ms": duration_ms,
                    "success": False,
                }
                operation = op_repo.create(op_data)
                session.commit()
                raise

            # Record operation
            op_data = {
                "operation_type": OperationType.COMMAND.value,
                "shell_id": shell_id,
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "success": result.success,
            }
            operation = op_repo.create(op_data)

            # Update shell activity
            shell_repo.update_activity(shell_id)
            session.commit()

            logger.info(
                f"Executed command in shell {shell_id}: {command} "
                f"(exit_code={result.exit_code})"
            )

            return ExecuteCommandResponse(
                operation_id=operation.id,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                duration_ms=result.duration_ms,
                success=result.success,
            )

    def get_shell(self, shell_id: str) -> ShellModel:
        """Get shell by ID.

        Args:
            shell_id: Shell ID

        Returns:
            Shell model

        Raises:
            ShellNotFound: If shell not found
        """
        with self.database.session() as session:
            repo = ShellRepository(session)
            return repo.get_or_raise(shell_id)

    def list_active_shells(self) -> list[ShellModel]:
        """List all active shells.

        Returns:
            List of active shell models
        """
        with self.database.session() as session:
            repo = ShellRepository(session)
            return repo.list_active()

    def close_shell(self, shell_id: str) -> None:
        """Close shell session.

        Args:
            shell_id: Shell ID

        Raises:
            ShellNotFound: If shell not found
        """
        with self.database.session() as session:
            repo = ShellRepository(session)
            shell = repo.get_or_raise(shell_id)

            # Close executor session
            self.executor.close_shell(shell_id)

            # Kill tmux session if exists
            if shell.tmux_session:
                self.tmux.kill_session(shell.tmux_session)

            # Close listener if exists
            if shell_id in self._listeners:
                self._listeners[shell_id].close()
                del self._listeners[shell_id]

            # Clear state
            self.state.clear_state(shell_id)

            # Update status
            repo.update_status(shell_id, ShellStatus.DEAD)
            session.commit()

            logger.info(f"Closed shell {shell_id}")

    def update_shell_state(self, shell_id: str) -> None:
        """Update shell state (cwd, env, privilege, shell type).

        Args:
            shell_id: Shell ID

        Raises:
            ShellNotFound: If shell not found
        """
        self._update_shell_state_internal(shell_id)

    def _update_shell_state_internal(self, shell_id: str) -> None:
        """Internal method to update shell state.

        Args:
            shell_id: Shell ID
        """
        try:
            # Detect working directory
            result = self.executor.execute(shell_id, "pwd", timeout=5)
            if result.success:
                cwd = result.stdout.strip()
                self.state.update_cwd(shell_id, cwd)

                # Update in database
                with self.database.session() as session:
                    repo = ShellRepository(session)
                    repo.update_working_directory(shell_id, cwd)
                    session.commit()

            # Detect privilege level
            result = self.executor.execute(shell_id, "id -u", timeout=5)
            if result.success:
                privilege = self.state.detect_privilege(result.stdout)
                self.state.update_privilege(shell_id, privilege)

            # Detect shell type
            result = self.executor.execute(shell_id, "echo $SHELL", timeout=5)
            if result.success:
                shell_type = self.state.detect_shell_type(result.stdout)
                self.state.update_shell_type(shell_id, shell_type)

            # Get environment variables (optional, can be slow)
            # result = self.executor.execute(shell_id, "env", timeout=10)
            # if result.success:
            #     env = self.state.parse_env_output(result.stdout)
            #     self.state.update_env(shell_id, env)

        except Exception as e:
            logger.debug(f"Failed to update shell state for {shell_id}: {e}")
