"""Unit tests for shell manager."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from amp.core.shell.executor import CommandExecutor, CommandResult
from amp.core.shell.manager import ShellManager
from amp.core.shell.payloads import ShellPayloads
from amp.core.shell.state import ShellState
from amp.core.shell.tmux_backend import TmuxBackend
from amp.exceptions import (
    CommandExecutionFailed,
    ShellLimitExceeded,
    ShellNotFound,
)
from amp.storage.database import Database
from amp.storage.models import (
    OSType,
    PrivilegeLevel,
    ShellModel,
    ShellProgram,
    ShellStatus,
    ShellType,
)


@pytest.fixture
def mock_database():
    """Create mock database."""
    db = Mock(spec=Database)
    session_mock = MagicMock()
    db.session.return_value.__enter__ = Mock(return_value=session_mock)
    db.session.return_value.__exit__ = Mock(return_value=False)
    return db


@pytest.fixture
def shell_manager(mock_database):
    """Create shell manager with mocked dependencies."""
    with patch("amp.core.shell.manager.TmuxBackend"), \
         patch("amp.core.shell.manager.CommandExecutor"), \
         patch("amp.core.shell.manager.ShellState"):
        manager = ShellManager(mock_database)
        return manager


class TestTmuxBackend:
    """Tests for tmux backend."""

    @patch("subprocess.run")
    def test_verify_tmux_installed(self, mock_run):
        """Test tmux installation verification."""
        mock_run.return_value = Mock(returncode=0)
        backend = TmuxBackend()
        assert backend is not None

    @patch("subprocess.run")
    def test_create_session(self, mock_run):
        """Test creating tmux session."""
        mock_run.return_value = Mock(returncode=0)
        backend = TmuxBackend()
        backend.create_session("test-session", "bash")
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_session_exists(self, mock_run):
        """Test checking if session exists."""
        mock_run.return_value = Mock(returncode=0)
        backend = TmuxBackend()
        assert backend.session_exists("test-session") is True

    @patch("subprocess.run")
    def test_send_command(self, mock_run):
        """Test sending command to session."""
        mock_run.return_value = Mock(returncode=0)
        backend = TmuxBackend()
        backend.send_command("test-session", "ls -la", wait_ms=0)
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_capture_output(self, mock_run):
        """Test capturing output from session."""
        mock_run.return_value = Mock(returncode=0, stdout="test output")
        backend = TmuxBackend()
        output = backend.capture_output("test-session")
        assert output == "test output"

    @patch("subprocess.run")
    def test_list_sessions(self, mock_run):
        """Test listing sessions."""
        mock_run.return_value = Mock(returncode=0, stdout="session1\nsession2\n")
        backend = TmuxBackend()
        sessions = backend.list_sessions()
        assert sessions == ["session1", "session2"]

    @patch("subprocess.run")
    def test_kill_session(self, mock_run):
        """Test killing session."""
        mock_run.return_value = Mock(returncode=0)
        backend = TmuxBackend()
        backend.kill_session("test-session")
        mock_run.assert_called()


class TestCommandExecutor:
    """Tests for command executor."""

    @patch("pexpect.spawn")
    def test_spawn_shell(self, mock_spawn):
        """Test spawning shell."""
        mock_child = Mock()
        mock_child.expect = Mock(return_value=0)
        mock_spawn.return_value = mock_child

        executor = CommandExecutor()
        executor.spawn_shell("shell-1", "bash")
        assert "shell-1" in executor._sessions

    @patch("pexpect.spawn")
    def test_execute_command(self, mock_spawn):
        """Test executing command."""
        mock_child = Mock()
        mock_child.expect = Mock(return_value=0)
        mock_child.before = "output"
        mock_child.sendline = Mock()
        mock_spawn.return_value = mock_child

        executor = CommandExecutor()
        executor.spawn_shell("shell-1", "bash")

        result = executor.execute("shell-1", "ls", timeout=30)
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0

    @patch("pexpect.spawn")
    def test_execute_command_timeout(self, mock_spawn):
        """Test command timeout."""
        mock_child = Mock()
        # First expect for spawn_shell succeeds
        mock_child.expect = Mock(side_effect=[
            0,  # spawn_shell succeeds
            CommandExecutionFailed("timeout", -1, "timeout")  # execute fails
        ])
        mock_child.sendline = Mock()
        mock_spawn.return_value = mock_child

        executor = CommandExecutor()
        executor.spawn_shell("shell-1", "bash")

        with pytest.raises(CommandExecutionFailed):
            executor.execute("shell-1", "sleep 100", timeout=1)

    @patch("pexpect.spawn")
    def test_close_shell(self, mock_spawn):
        """Test closing shell."""
        mock_child = Mock()
        mock_child.expect = Mock(return_value=0)
        mock_child.sendline = Mock()
        mock_child.close = Mock()
        mock_child.isalive = Mock(return_value=False)
        mock_spawn.return_value = mock_child

        executor = CommandExecutor()
        executor.spawn_shell("shell-1", "bash")
        executor.close_shell("shell-1")
        assert "shell-1" not in executor._sessions

    @patch("pexpect.spawn")
    def test_is_alive(self, mock_spawn):
        """Test checking if shell is alive."""
        mock_child = Mock()
        mock_child.expect = Mock(return_value=0)
        mock_child.isalive = Mock(return_value=True)
        mock_spawn.return_value = mock_child

        executor = CommandExecutor()
        executor.spawn_shell("shell-1", "bash")
        assert executor.is_alive("shell-1") is True


class TestShellState:
    """Tests for shell state tracking."""

    def test_update_cwd(self):
        """Test updating working directory."""
        state = ShellState()
        state.update_cwd("shell-1", "/home/user")
        assert state.get_state("shell-1")["cwd"] == "/home/user"

    def test_update_env(self):
        """Test updating environment variables."""
        state = ShellState()
        env = {"PATH": "/usr/bin", "HOME": "/home/user"}
        state.update_env("shell-1", env)
        assert state.get_state("shell-1")["env"] == env

    def test_update_privilege(self):
        """Test updating privilege level."""
        state = ShellState()
        state.update_privilege("shell-1", PrivilegeLevel.ROOT)
        assert state.get_state("shell-1")["privilege"] == PrivilegeLevel.ROOT

    def test_detect_privilege_root(self):
        """Test detecting root privilege."""
        state = ShellState()
        assert state.detect_privilege("0") == PrivilegeLevel.ROOT
        assert state.detect_privilege("root") == PrivilegeLevel.ROOT

    def test_detect_privilege_user(self):
        """Test detecting user privilege."""
        state = ShellState()
        assert state.detect_privilege("1000") == PrivilegeLevel.USER
        assert state.detect_privilege("user") == PrivilegeLevel.USER

    def test_detect_shell_type_bash(self):
        """Test detecting bash shell."""
        state = ShellState()
        assert state.detect_shell_type("/bin/bash") == ShellProgram.BASH

    def test_detect_shell_type_sh(self):
        """Test detecting sh shell."""
        state = ShellState()
        assert state.detect_shell_type("/bin/sh") == ShellProgram.SH

    def test_parse_env_output(self):
        """Test parsing environment output."""
        state = ShellState()
        output = "PATH=/usr/bin\nHOME=/home/user\nUSER=test"
        env = state.parse_env_output(output)
        assert env["PATH"] == "/usr/bin"
        assert env["HOME"] == "/home/user"
        assert env["USER"] == "test"

    def test_clear_state(self):
        """Test clearing state."""
        state = ShellState()
        state.update_cwd("shell-1", "/home/user")
        state.clear_state("shell-1")
        assert state.get_state("shell-1") == {}


class TestShellPayloads:
    """Tests for shell payload generation."""

    def test_bash_reverse_shell(self):
        """Test bash reverse shell payload."""
        payload = ShellPayloads.bash_reverse_shell("10.0.0.1", 4444)
        assert "10.0.0.1" in payload
        assert "4444" in payload
        assert "bash" in payload

    def test_python_reverse_shell(self):
        """Test python reverse shell payload."""
        payload = ShellPayloads.python_reverse_shell("10.0.0.1", 4444)
        assert "10.0.0.1" in payload
        assert "4444" in payload
        assert "python" in payload

    def test_nc_reverse_shell(self):
        """Test netcat reverse shell payload."""
        payload = ShellPayloads.nc_reverse_shell("10.0.0.1", 4444)
        assert "10.0.0.1" in payload
        assert "4444" in payload
        assert "nc" in payload

    def test_powershell_reverse_shell(self):
        """Test PowerShell reverse shell payload."""
        payload = ShellPayloads.powershell_reverse_shell("10.0.0.1", 4444)
        assert "10.0.0.1" in payload
        assert "4444" in payload
        assert "powershell" in payload

    def test_get_payload(self):
        """Test getting payload by type."""
        payload = ShellPayloads.get_payload("bash", "10.0.0.1", 4444)
        assert "10.0.0.1" in payload
        assert "4444" in payload

    def test_get_payload_invalid_type(self):
        """Test getting payload with invalid type."""
        with pytest.raises(ValueError):
            ShellPayloads.get_payload("invalid", "10.0.0.1", 4444)


class TestShellManager:
    """Tests for shell manager."""

    @patch("amp.core.shell.manager.ShellRepository")
    @patch("amp.core.shell.manager.socket.socket")
    def test_create_reverse_shell(self, mock_socket, mock_repo_class, shell_manager):
        """Test creating reverse shell."""
        # Mock repository
        mock_repo = Mock()
        mock_repo.list_active.return_value = []
        mock_repo.create.return_value = ShellModel(
            id="shell-1",
            name="test-shell",
            shell_type=ShellType.REVERSE,
            os_type=OSType.LINUX,
            shell_program=ShellProgram.BASH,
            status=ShellStatus.ACTIVE,
            target_host="10.0.0.1",
            target_port=4444,
            privilege_level=PrivilegeLevel.USER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_repo_class.return_value = mock_repo

        # Mock socket
        mock_listener = Mock()
        mock_socket.return_value = mock_listener

        # Create reverse shell
        with patch.object(shell_manager, "_start_reverse_listener"):
            shell, payload = shell_manager.create_reverse_shell(
                name="test-shell",
                local_port=4444,
                target_host="10.0.0.1",
            )

        assert shell.id == "shell-1"
        assert "4444" in payload

    @patch("amp.core.shell.manager.ShellRepository")
    def test_create_reverse_shell_limit_exceeded(self, mock_repo_class, shell_manager):
        """Test reverse shell creation with limit exceeded."""
        # Mock repository with max shells
        mock_repo = Mock()
        mock_repo.list_active.return_value = [Mock()] * 50  # Max shells
        mock_repo_class.return_value = mock_repo

        with pytest.raises(ShellLimitExceeded):
            shell_manager.create_reverse_shell(
                name="test-shell",
                local_port=4444,
                target_host="10.0.0.1",
            )

    @patch("amp.core.shell.manager.ShellRepository")
    def test_execute_command(self, mock_repo_class, shell_manager):
        """Test executing command."""
        # Mock repository
        mock_repo = Mock()
        mock_repo.get_or_raise.return_value = ShellModel(
            id="shell-1",
            name="test-shell",
            shell_type=ShellType.SSH,
            os_type=OSType.LINUX,
            shell_program=ShellProgram.BASH,
            status=ShellStatus.ACTIVE,
            target_host="10.0.0.1",
            privilege_level=PrivilegeLevel.USER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_repo_class.return_value = mock_repo

        # Mock executor
        shell_manager.executor.is_alive = Mock(return_value=True)
        shell_manager.executor.execute = Mock(
            return_value=CommandResult(
                stdout="output",
                stderr="",
                exit_code=0,
                duration_ms=100,
                success=True,
            )
        )

        # Mock operation repository
        with patch("amp.core.shell.manager.OperationRepository") as mock_op_repo_class:
            mock_op_repo = Mock()
            mock_op_repo.create.return_value = Mock(id="op-1")
            mock_op_repo_class.return_value = mock_op_repo

            response = shell_manager.execute_command("shell-1", "ls")

        assert response.exit_code == 0
        assert response.stdout == "output"
        assert response.success is True

    @patch("amp.core.shell.manager.ShellRepository")
    def test_execute_command_shell_not_found(self, mock_repo_class, shell_manager):
        """Test executing command with shell not found."""
        mock_repo = Mock()
        mock_repo.get_or_raise.side_effect = ShellNotFound("shell-1")
        mock_repo_class.return_value = mock_repo

        with pytest.raises(ShellNotFound):
            shell_manager.execute_command("shell-1", "ls")

    @patch("amp.core.shell.manager.ShellRepository")
    def test_get_shell(self, mock_repo_class, shell_manager):
        """Test getting shell."""
        mock_repo = Mock()
        mock_repo.get_or_raise.return_value = ShellModel(
            id="shell-1",
            name="test-shell",
            shell_type=ShellType.SSH,
            os_type=OSType.LINUX,
            shell_program=ShellProgram.BASH,
            status=ShellStatus.ACTIVE,
            target_host="10.0.0.1",
            privilege_level=PrivilegeLevel.USER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_repo_class.return_value = mock_repo

        shell = shell_manager.get_shell("shell-1")
        assert shell.id == "shell-1"

    @patch("amp.core.shell.manager.ShellRepository")
    def test_list_active_shells(self, mock_repo_class, shell_manager):
        """Test listing active shells."""
        mock_repo = Mock()
        mock_repo.list_active.return_value = [
            ShellModel(
                id="shell-1",
                name="test-shell-1",
                shell_type=ShellType.SSH,
                os_type=OSType.LINUX,
                shell_program=ShellProgram.BASH,
                status=ShellStatus.ACTIVE,
                target_host="10.0.0.1",
                privilege_level=PrivilegeLevel.USER,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
            ShellModel(
                id="shell-2",
                name="test-shell-2",
                shell_type=ShellType.SSH,
                os_type=OSType.LINUX,
                shell_program=ShellProgram.BASH,
                status=ShellStatus.ACTIVE,
                target_host="10.0.0.2",
                privilege_level=PrivilegeLevel.USER,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
        ]
        mock_repo_class.return_value = mock_repo

        shells = shell_manager.list_active_shells()
        assert len(shells) == 2

    @patch("amp.core.shell.manager.ShellRepository")
    def test_close_shell(self, mock_repo_class, shell_manager):
        """Test closing shell."""
        mock_repo = Mock()
        mock_repo.get_or_raise.return_value = ShellModel(
            id="shell-1",
            name="test-shell",
            shell_type=ShellType.SSH,
            os_type=OSType.LINUX,
            shell_program=ShellProgram.BASH,
            status=ShellStatus.ACTIVE,
            target_host="10.0.0.1",
            tmux_session="amp-shell-test",
            privilege_level=PrivilegeLevel.USER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_repo_class.return_value = mock_repo

        shell_manager.executor.close_shell = Mock()
        shell_manager.tmux.kill_session = Mock()
        shell_manager.state.clear_state = Mock()

        shell_manager.close_shell("shell-1")

        shell_manager.executor.close_shell.assert_called_once_with("shell-1")
        shell_manager.tmux.kill_session.assert_called_once_with("amp-shell-test")
        shell_manager.state.clear_state.assert_called_once_with("shell-1")
