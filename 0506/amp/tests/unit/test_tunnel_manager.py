"""Unit tests for tunnel manager."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from amp.core.tunnel.chisel import ChiselProcess
from amp.core.tunnel.manager import TunnelManager
from amp.exceptions import (
    TunnelCreationFailed,
    TunnelDisconnected,
    TunnelLimitExceeded,
    TunnelNotFound,
)
from amp.storage.database import Database
from amp.storage.models import TunnelStatus, TunnelType


@pytest.fixture
def db():
    """Create in-memory database for testing."""
    database = Database("sqlite:///:memory:")
    database.create_tables()
    return database


@pytest.fixture
def tunnel_manager(db):
    """Create tunnel manager instance."""
    return TunnelManager(db)


@pytest.fixture
def mock_chisel_process():
    """Create mock ChiselProcess."""
    with patch("amp.core.tunnel.manager.ChiselProcess") as mock:
        process = Mock(spec=ChiselProcess)
        process.start.return_value = 12345
        process.is_alive.return_value = True
        process.stop.return_value = None
        process.get_stats.return_value = {
            "pid": 12345,
            "cpu_percent": 0.5,
            "memory_mb": 10.0,
        }
        process.get_logs.return_value = {"stdout": "", "stderr": ""}
        mock.return_value = process
        yield mock


class TestTunnelManager:
    """Test tunnel manager."""

    def test_create_tunnel(self, tunnel_manager):
        """Test creating a tunnel."""
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        assert tunnel.id is not None
        assert tunnel.name == "test-tunnel"
        assert tunnel.tunnel_type == TunnelType.CHISEL
        assert tunnel.status == TunnelStatus.STOPPED
        assert tunnel.local_port == 8080
        assert tunnel.remote_host == "192.168.1.100"
        assert tunnel.remote_port == 9090

    def test_create_tunnel_with_parent(self, tunnel_manager):
        """Test creating a nested tunnel."""
        # Create parent tunnel
        parent = tunnel_manager.create_tunnel(
            name="parent-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        # Start parent to make it active
        with patch("amp.core.tunnel.manager.ChiselProcess") as mock:
            process = Mock()
            process.start.return_value = 12345
            process.is_alive.return_value = True
            mock.return_value = process
            tunnel_manager.start_tunnel(parent.id)

        # Create child tunnel
        child = tunnel_manager.create_tunnel(
            name="child-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8081,
            remote_host="10.0.0.100",
            remote_port=9090,
            parent_id=parent.id,
        )

        assert child.parent_tunnel_id == parent.id

    def test_create_tunnel_with_invalid_parent(self, tunnel_manager):
        """Test creating tunnel with non-existent parent."""
        with pytest.raises(TunnelNotFound):
            tunnel_manager.create_tunnel(
                name="child-tunnel",
                tunnel_type=TunnelType.CHISEL,
                local_port=8081,
                remote_host="10.0.0.100",
                remote_port=9090,
                parent_id="nonexistent-id",
            )

    def test_create_tunnel_exceeds_limit(self, tunnel_manager):
        """Test tunnel limit enforcement."""
        # Create max tunnels
        with patch("amp.core.tunnel.manager.settings.tunnel.max_tunnels", 2):
            tunnel1 = tunnel_manager.create_tunnel(
                name="tunnel-1",
                tunnel_type=TunnelType.CHISEL,
                local_port=8080,
                remote_host="192.168.1.100",
                remote_port=9090,
            )

            tunnel2 = tunnel_manager.create_tunnel(
                name="tunnel-2",
                tunnel_type=TunnelType.CHISEL,
                local_port=8081,
                remote_host="192.168.1.101",
                remote_port=9090,
            )

            # Start both to make them active
            with patch("amp.core.tunnel.manager.ChiselProcess") as mock:
                process = Mock()
                process.start.return_value = 12345
                process.is_alive.return_value = True
                mock.return_value = process
                tunnel_manager.start_tunnel(tunnel1.id)
                tunnel_manager.start_tunnel(tunnel2.id)

            # Try to create one more (should fail)
            with pytest.raises(TunnelLimitExceeded):
                tunnel_manager.create_tunnel(
                    name="tunnel-3",
                    tunnel_type=TunnelType.CHISEL,
                    local_port=8082,
                    remote_host="192.168.1.101",
                    remote_port=9090,
                )

    def test_start_tunnel(self, tunnel_manager, mock_chisel_process):
        """Test starting a tunnel."""
        # Create tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        # Start tunnel
        started = tunnel_manager.start_tunnel(tunnel.id)

        assert started.status == TunnelStatus.ACTIVE
        assert started.process_pid == 12345
        assert started.last_heartbeat is not None
        mock_chisel_process.assert_called_once()

    def test_start_already_active_tunnel(self, tunnel_manager, mock_chisel_process):
        """Test starting an already active tunnel."""
        # Create and start tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel.id)

        # Try to start again
        started = tunnel_manager.start_tunnel(tunnel.id)
        assert started.status == TunnelStatus.ACTIVE

        # Should only be called once
        assert mock_chisel_process.call_count == 1

    def test_start_tunnel_process_fails(self, tunnel_manager):
        """Test starting tunnel when process fails."""
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        with patch("amp.core.tunnel.manager.ChiselProcess") as mock:
            process = Mock()
            process.start.side_effect = TunnelCreationFailed("Failed to start", True)
            mock.return_value = process

            with pytest.raises(TunnelCreationFailed):
                tunnel_manager.start_tunnel(tunnel.id)

    def test_stop_tunnel(self, tunnel_manager, mock_chisel_process):
        """Test stopping a tunnel."""
        # Create and start tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel.id)

        # Stop tunnel
        stopped = tunnel_manager.stop_tunnel(tunnel.id)

        assert stopped.status == TunnelStatus.STOPPED
        mock_chisel_process.return_value.stop.assert_called_once()

    def test_stop_nonexistent_tunnel(self, tunnel_manager):
        """Test stopping a non-existent tunnel."""
        with pytest.raises(TunnelNotFound):
            tunnel_manager.stop_tunnel("nonexistent-id")

    def test_delete_tunnel(self, tunnel_manager):
        """Test deleting a tunnel."""
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        tunnel_manager.delete_tunnel(tunnel.id)

        with pytest.raises(TunnelNotFound):
            tunnel_manager.get_tunnel(tunnel.id)

    def test_delete_active_tunnel(self, tunnel_manager, mock_chisel_process):
        """Test deleting an active tunnel."""
        # Create and start tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel.id)

        # Delete tunnel (should stop it first)
        tunnel_manager.delete_tunnel(tunnel.id)

        mock_chisel_process.return_value.stop.assert_called_once()

        with pytest.raises(TunnelNotFound):
            tunnel_manager.get_tunnel(tunnel.id)

    def test_delete_tunnel_with_children(self, tunnel_manager, mock_chisel_process):
        """Test deleting a tunnel with child tunnels."""
        # Create parent and child
        parent = tunnel_manager.create_tunnel(
            name="parent-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(parent.id)

        child = tunnel_manager.create_tunnel(
            name="child-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8081,
            remote_host="10.0.0.100",
            remote_port=9090,
            parent_id=parent.id,
        )

        # Delete parent (should delete child too)
        tunnel_manager.delete_tunnel(parent.id)

        with pytest.raises(TunnelNotFound):
            tunnel_manager.get_tunnel(parent.id)

        with pytest.raises(TunnelNotFound):
            tunnel_manager.get_tunnel(child.id)

    def test_get_tunnel(self, tunnel_manager):
        """Test getting a tunnel by ID."""
        created = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        retrieved = tunnel_manager.get_tunnel(created.id)
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_nonexistent_tunnel(self, tunnel_manager):
        """Test getting a non-existent tunnel."""
        with pytest.raises(TunnelNotFound):
            tunnel_manager.get_tunnel("nonexistent-id")

    def test_list_active_tunnels(self, tunnel_manager, mock_chisel_process):
        """Test listing active tunnels."""
        # Create tunnels
        tunnel1 = tunnel_manager.create_tunnel(
            name="tunnel-1",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        tunnel_manager.create_tunnel(
            name="tunnel-2",
            tunnel_type=TunnelType.CHISEL,
            local_port=8081,
            remote_host="192.168.1.101",
            remote_port=9090,
        )

        # Start only tunnel1
        tunnel_manager.start_tunnel(tunnel1.id)

        active = tunnel_manager.list_active_tunnels()
        assert len(active) == 1
        assert active[0].id == tunnel1.id

    def test_list_all_tunnels(self, tunnel_manager):
        """Test listing all tunnels."""
        tunnel_manager.create_tunnel(
            name="tunnel-1",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        tunnel_manager.create_tunnel(
            name="tunnel-2",
            tunnel_type=TunnelType.CHISEL,
            local_port=8081,
            remote_host="192.168.1.101",
            remote_port=9090,
        )

        all_tunnels = tunnel_manager.list_all_tunnels()
        assert len(all_tunnels) == 2

    def test_health_check_healthy(self, tunnel_manager, mock_chisel_process):
        """Test health check on healthy tunnel."""
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel.id)

        # Health check should pass
        is_healthy = tunnel_manager.health_check(tunnel.id)
        assert is_healthy is True

    def test_health_check_dead_process(self, tunnel_manager, mock_chisel_process):
        """Test health check on dead process."""
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel.id)

        # Simulate process death
        mock_chisel_process.return_value.is_alive.return_value = False

        # Health check should fail
        with pytest.raises(TunnelDisconnected):
            tunnel_manager.health_check(tunnel.id)

        # Tunnel should be marked as disconnected
        tunnel = tunnel_manager.get_tunnel(tunnel.id)
        assert tunnel.status == TunnelStatus.DISCONNECTED

    def test_health_check_stopped_tunnel(self, tunnel_manager):
        """Test health check on stopped tunnel."""
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        # Health check on stopped tunnel should return False
        is_healthy = tunnel_manager.health_check(tunnel.id)
        assert is_healthy is False

    def test_health_check_all(self, tunnel_manager, mock_chisel_process):
        """Test health check on all tunnels."""
        # Create and start multiple tunnels
        tunnel1 = tunnel_manager.create_tunnel(
            name="tunnel-1",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel1.id)

        tunnel2 = tunnel_manager.create_tunnel(
            name="tunnel-2",
            tunnel_type=TunnelType.CHISEL,
            local_port=8081,
            remote_host="192.168.1.101",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel2.id)

        # Run health check on all
        results = tunnel_manager.health_check_all()

        assert len(results) == 2
        assert results[tunnel1.id] is True
        assert results[tunnel2.id] is True

    def test_get_tunnel_stats(self, tunnel_manager, mock_chisel_process):
        """Test getting tunnel statistics."""
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel.id)

        stats = tunnel_manager.get_tunnel_stats(tunnel.id)

        assert stats["status"] == "running"
        assert "stats" in stats
        assert "logs" in stats

    def test_cleanup_stale_tunnels(self, tunnel_manager, mock_chisel_process):
        """Test cleaning up stale disconnected tunnels."""
        # Create and start tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel.id)

        # Simulate process death
        mock_chisel_process.return_value.is_alive.return_value = False

        try:
            tunnel_manager.health_check(tunnel.id)
        except TunnelDisconnected:
            pass

        # Manually set updated_at to old time
        with tunnel_manager.database.session() as session:
            from amp.storage.schema import Tunnel

            tunnel_orm = session.query(Tunnel).filter(Tunnel.id == tunnel.id).first()
            tunnel_orm.updated_at = datetime.utcnow() - timedelta(hours=25)
            session.commit()

        # Cleanup stale tunnels
        cleaned = tunnel_manager.cleanup_stale_tunnels(max_age_hours=24)

        assert cleaned == 1

        with pytest.raises(TunnelNotFound):
            tunnel_manager.get_tunnel(tunnel.id)

    def test_shutdown(self, tunnel_manager, mock_chisel_process):
        """Test shutting down tunnel manager."""
        # Create and start multiple tunnels
        tunnel1 = tunnel_manager.create_tunnel(
            name="tunnel-1",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel1.id)

        tunnel2 = tunnel_manager.create_tunnel(
            name="tunnel-2",
            tunnel_type=TunnelType.CHISEL,
            local_port=8081,
            remote_host="192.168.1.101",
            remote_port=9090,
        )
        tunnel_manager.start_tunnel(tunnel2.id)

        # Shutdown
        tunnel_manager.shutdown()

        # All processes should be stopped
        assert len(tunnel_manager._processes) == 0

        # Tunnels should be marked as stopped
        tunnel1 = tunnel_manager.get_tunnel(tunnel1.id)
        tunnel2 = tunnel_manager.get_tunnel(tunnel2.id)
        assert tunnel1.status == TunnelStatus.STOPPED
        assert tunnel2.status == TunnelStatus.STOPPED


class TestChiselProcess:
    """Test ChiselProcess wrapper."""

    def test_build_client_command(self):
        """Test building client command."""
        process = ChiselProcess(
            chisel_binary="/usr/bin/chisel",
            mode="client",
            local_host="127.0.0.1",
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
            auth="user:pass",
            keepalive=30,
        )

        cmd = process._build_command()

        assert "/usr/bin/chisel" in cmd
        assert "client" in cmd
        assert "http://192.168.1.100:9090" in cmd
        assert "8080:127.0.0.1:8080" in cmd
        assert "--auth" in cmd
        assert "user:pass" in cmd
        assert "--keepalive" in cmd
        assert "30s" in cmd

    def test_build_server_command(self):
        """Test building server command."""
        process = ChiselProcess(
            chisel_binary="/usr/bin/chisel",
            mode="server",
            local_host="0.0.0.0",
            local_port=9090,
            auth="user:pass",
            keepalive=30,
        )

        cmd = process._build_command()

        assert "/usr/bin/chisel" in cmd
        assert "server" in cmd
        assert "--host" in cmd
        assert "0.0.0.0" in cmd
        assert "--port" in cmd
        assert "9090" in cmd
        assert "--auth" in cmd
        assert "user:pass" in cmd

    @patch("amp.core.tunnel.chisel.Path")
    @patch("amp.core.tunnel.chisel.subprocess.Popen")
    @patch("amp.core.tunnel.chisel.time.sleep")
    @patch("amp.core.tunnel.chisel.psutil.Process")
    def test_start_process(self, mock_psutil, mock_sleep, mock_popen, mock_path):
        """Test starting Chisel process."""
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

        process = ChiselProcess(
            chisel_binary="/usr/bin/chisel",
            mode="client",
            local_host="127.0.0.1",
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        pid = process.start()

        assert pid == 12345
        assert process.pid == 12345
        mock_popen.assert_called_once()

    @patch("amp.core.tunnel.chisel.psutil.Process")
    def test_is_alive(self, mock_psutil):
        """Test checking if process is alive."""
        mock_proc = MagicMock()
        mock_proc.is_running.return_value = True
        mock_proc.status.return_value = "running"
        mock_psutil.return_value = mock_proc

        process = ChiselProcess(
            chisel_binary="/usr/bin/chisel",
            mode="client",
            local_host="127.0.0.1",
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        process.pid = 12345
        process.process = MagicMock()  # Need to set process object

        assert process.is_alive() is True

    @patch("amp.core.tunnel.chisel.psutil.Process")
    def test_stop_process(self, mock_psutil):
        """Test stopping process."""
        mock_proc = MagicMock()
        mock_psutil.return_value = mock_proc

        process = ChiselProcess(
            chisel_binary="/usr/bin/chisel",
            mode="client",
            local_host="127.0.0.1",
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )
        process.pid = 12345
        process.process = MagicMock()

        process.stop()

        mock_proc.terminate.assert_called_once()
        assert process.pid is None
        assert process.process is None
