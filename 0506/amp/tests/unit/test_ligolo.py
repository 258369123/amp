"""Unit tests for Ligolo-ng process wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from amp.core.tunnel.ligolo import LigoloProcess
from amp.exceptions import TunnelCreationFailed


class TestLigoloProcess:
    """Test LigoloProcess wrapper."""

    def test_build_agent_command(self):
        """Test building agent command."""
        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
            ignore_cert=True,
        )

        cmd = process._build_command()

        assert "/usr/bin/ligolo-ng" in cmd
        assert "agent" in cmd
        assert "-connect" in cmd
        assert "192.168.1.100:11601" in cmd
        assert "-ignore-cert" in cmd

    def test_build_proxy_command(self):
        """Test building proxy command."""
        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="proxy",
            listen_addr="0.0.0.0",
            listen_port=11601,
            selfcert=True,
        )

        cmd = process._build_command()

        assert "/usr/bin/ligolo-ng" in cmd
        assert "proxy" in cmd
        assert "-selfcert" in cmd
        assert "-laddr" in cmd
        assert "0.0.0.0:11601" in cmd

    def test_build_agent_command_missing_proxy(self):
        """Test building agent command without proxy host/port."""
        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
        )

        with pytest.raises(TunnelCreationFailed) as exc_info:
            process._build_command()

        assert "proxy_host and proxy_port required" in str(exc_info.value)
        assert exc_info.value.retry_possible is False

    @patch("amp.core.tunnel.ligolo.Path")
    @patch("amp.core.tunnel.ligolo.subprocess.Popen")
    @patch("amp.core.tunnel.ligolo.time.sleep")
    @patch("amp.core.tunnel.ligolo.psutil.Process")
    def test_start_process(self, mock_psutil, mock_sleep, mock_popen, mock_path):
        """Test starting Ligolo-ng process."""
        # Mock binary exists
        mock_path.return_value.exists.return_value = True

        # Mock process
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        # Mock psutil
        mock_psutil_proc = MagicMock()
        mock_psutil_proc.is_running.return_value = True
        mock_psutil_proc.status.return_value = "running"
        mock_psutil.return_value = mock_psutil_proc

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )

        pid = process.start()

        assert pid == 12345
        assert process.pid == 12345
        mock_popen.assert_called_once()

    @patch("amp.core.tunnel.ligolo.Path")
    def test_start_process_binary_not_found(self, mock_path):
        """Test starting process when binary doesn't exist."""
        mock_path.return_value.exists.return_value = False

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )

        with pytest.raises(TunnelCreationFailed) as exc_info:
            process.start()

        assert "binary not found" in str(exc_info.value)
        assert exc_info.value.retry_possible is False

    @patch("amp.core.tunnel.ligolo.Path")
    @patch("amp.core.tunnel.ligolo.subprocess.Popen")
    @patch("amp.core.tunnel.ligolo.time.sleep")
    @patch("amp.core.tunnel.ligolo.psutil.Process")
    def test_start_process_dies_immediately(
        self, mock_psutil, mock_sleep, mock_popen, mock_path
    ):
        """Test starting process that dies immediately."""
        mock_path.return_value.exists.return_value = True

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.stderr = MagicMock()
        mock_popen.return_value = mock_proc

        # Mock process as dead
        mock_psutil_proc = MagicMock()
        mock_psutil_proc.is_running.return_value = False
        mock_psutil.return_value = mock_psutil_proc

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )

        with pytest.raises(TunnelCreationFailed) as exc_info:
            process.start()

        assert "died immediately" in str(exc_info.value)
        assert exc_info.value.retry_possible is True

    def test_start_already_started(self):
        """Test starting process that's already started."""
        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )
        process.process = MagicMock()  # Simulate already started

        with pytest.raises(TunnelCreationFailed) as exc_info:
            process.start()

        assert "already started" in str(exc_info.value)
        assert exc_info.value.retry_possible is False

    @patch("amp.core.tunnel.ligolo.psutil.Process")
    def test_is_alive(self, mock_psutil):
        """Test checking if process is alive."""
        mock_proc = MagicMock()
        mock_proc.is_running.return_value = True
        mock_proc.status.return_value = "running"
        mock_psutil.return_value = mock_proc

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )
        process.pid = 12345
        process.process = MagicMock()

        assert process.is_alive() is True

    @patch("amp.core.tunnel.ligolo.psutil.Process")
    def test_is_alive_zombie(self, mock_psutil):
        """Test checking if process is zombie."""
        mock_proc = MagicMock()
        mock_proc.is_running.return_value = True
        mock_proc.status.return_value = "zombie"
        mock_psutil.return_value = mock_proc

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )
        process.pid = 12345
        process.process = MagicMock()

        assert process.is_alive() is False

    @patch("amp.core.tunnel.ligolo.psutil.Process")
    def test_stop_process(self, mock_psutil):
        """Test stopping process."""
        mock_proc = MagicMock()
        mock_psutil.return_value = mock_proc

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )
        process.pid = 12345
        process.process = MagicMock()

        process.stop()

        mock_proc.terminate.assert_called_once()
        assert process.pid is None
        assert process.process is None

    @patch("amp.core.tunnel.ligolo.psutil.Process")
    def test_stop_process_force_kill(self, mock_psutil):
        """Test stopping process with force kill."""
        import psutil

        mock_proc = MagicMock()
        # First wait times out, second succeeds
        mock_proc.wait.side_effect = [psutil.TimeoutExpired(5), None]
        mock_psutil.return_value = mock_proc
        mock_psutil.TimeoutExpired = psutil.TimeoutExpired

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )
        process.pid = 12345
        process.process = MagicMock()

        process.stop()

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    @patch("amp.core.tunnel.ligolo.psutil.Process")
    def test_get_stats(self, mock_psutil):
        """Test getting process statistics."""
        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 1.5
        mock_proc.memory_info.return_value.rss = 10485760  # 10 MB
        mock_proc.num_threads.return_value = 2
        mock_proc.status.return_value = "running"
        mock_proc.create_time.return_value = 1234567890.0
        mock_psutil.return_value = mock_proc

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )
        process.pid = 12345
        process.process = MagicMock()

        stats = process.get_stats()

        assert stats["pid"] == 12345
        assert stats["cpu_percent"] == 1.5
        assert stats["memory_mb"] == 10.0
        assert stats["num_threads"] == 2
        assert stats["status"] == "running"

    def test_get_stats_no_process(self):
        """Test getting stats when process is not running."""
        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )

        stats = process.get_stats()
        assert stats == {}

    def test_get_logs(self):
        """Test getting process logs."""
        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )

        # Simulate some logs
        process._stdout_log = ["line1\n", "line2\n"]
        process._stderr_log = ["error1\n"]

        logs = process.get_logs()

        assert logs["stdout"] == "line1\nline2\n"
        assert logs["stderr"] == "error1\n"

    @patch("amp.core.tunnel.ligolo.subprocess.run")
    def test_add_route(self, mock_run):
        """Test adding a route."""
        mock_run.return_value = MagicMock(returncode=0)

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="proxy",
            interface="ligolo",
            listen_port=11601,
        )

        result = process.add_route("10.0.0.0/24")

        assert result is True
        assert "10.0.0.0/24" in process.routes
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ip" in args
        assert "route" in args
        assert "add" in args
        assert "10.0.0.0/24" in args
        assert "ligolo" in args

    @patch("amp.core.tunnel.ligolo.subprocess.run")
    def test_add_route_fails(self, mock_run):
        """Test adding a route that fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Route exists")

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="proxy",
            interface="ligolo",
            listen_port=11601,
        )

        result = process.add_route("10.0.0.0/24")

        assert result is False
        assert "10.0.0.0/24" not in process.routes

    def test_add_route_agent_mode(self):
        """Test adding route in agent mode (should fail)."""
        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="agent",
            proxy_host="192.168.1.100",
            proxy_port=11601,
        )

        result = process.add_route("10.0.0.0/24")
        assert result is False

    @patch("amp.core.tunnel.ligolo.subprocess.run")
    def test_remove_route(self, mock_run):
        """Test removing a route."""
        mock_run.return_value = MagicMock(returncode=0)

        process = LigoloProcess(
            ligolo_binary="/usr/bin/ligolo-ng",
            mode="proxy",
            interface="ligolo",
            listen_port=11601,
        )
        process.routes = ["10.0.0.0/24"]

        result = process.remove_route("10.0.0.0/24")

        assert result is True
        assert "10.0.0.0/24" not in process.routes
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ip" in args
        assert "route" in args
        assert "del" in args
        assert "10.0.0.0/24" in args
