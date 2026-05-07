"""Unit tests for tunnel recovery."""

import asyncio
from unittest.mock import patch

import pytest

from amp.core.tunnel.manager import TunnelManager
from amp.core.tunnel.recovery import TunnelRecovery
from amp.exceptions import TunnelCreationFailed
from amp.storage.database import Database
from amp.storage.models import TunnelType


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
def recovery(tunnel_manager):
    """Create recovery instance."""
    return TunnelRecovery(tunnel_manager)


class TestTunnelRecovery:
    """Test tunnel recovery functionality."""

    def test_enable_auto_recovery(self, recovery):
        """Test enabling auto-recovery."""
        tunnel_id = "test-tunnel-1"
        recovery.enable_auto_recovery(tunnel_id)

        assert recovery.is_recovery_enabled(tunnel_id) is True

    def test_disable_auto_recovery(self, recovery):
        """Test disabling auto-recovery."""
        tunnel_id = "test-tunnel-1"
        recovery.enable_auto_recovery(tunnel_id)
        recovery.disable_auto_recovery(tunnel_id)

        assert recovery.is_recovery_enabled(tunnel_id) is False

    def test_is_recovery_enabled_default(self, recovery):
        """Test recovery is disabled by default."""
        tunnel_id = "test-tunnel-1"
        assert recovery.is_recovery_enabled(tunnel_id) is False

    @pytest.mark.asyncio
    async def test_attempt_recovery_success(self, recovery, tunnel_manager):
        """Test successful recovery attempt."""
        # Create a tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        # Mock the start_tunnel and health_check methods
        with patch.object(tunnel_manager, "stop_tunnel"):
            with patch.object(tunnel_manager, "start_tunnel", return_value=tunnel):
                with patch.object(tunnel_manager, "health_check", return_value=True):
                    result = await recovery.attempt_recovery(
                        tunnel.id, max_attempts=3, delay=0.1
                    )

                    assert result is True

    @pytest.mark.asyncio
    async def test_attempt_recovery_failure(self, recovery, tunnel_manager):
        """Test failed recovery attempt."""
        # Create a tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        # Mock the methods to always fail
        with patch.object(tunnel_manager, "stop_tunnel"):
            with patch.object(
                tunnel_manager,
                "start_tunnel",
                side_effect=TunnelCreationFailed("Failed", retry_possible=True),
            ):
                result = await recovery.attempt_recovery(
                    tunnel.id, max_attempts=2, delay=0.1
                )

                assert result is False

    @pytest.mark.asyncio
    async def test_attempt_recovery_tunnel_not_found(self, recovery, tunnel_manager):
        """Test recovery when tunnel doesn't exist."""
        result = await recovery.attempt_recovery(
            "nonexistent-id", max_attempts=3, delay=0.1
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_attempt_recovery_not_retryable(self, recovery, tunnel_manager):
        """Test recovery when error is not retryable."""
        # Create a tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        # Mock the methods to fail with non-retryable error
        with patch.object(tunnel_manager, "stop_tunnel"):
            with patch.object(
                tunnel_manager,
                "start_tunnel",
                side_effect=TunnelCreationFailed("Failed", retry_possible=False),
            ):
                result = await recovery.attempt_recovery(
                    tunnel.id, max_attempts=3, delay=0.1
                )

                assert result is False

    @pytest.mark.asyncio
    async def test_attempt_recovery_health_check_fails(self, recovery, tunnel_manager):
        """Test recovery when health check fails."""
        # Create a tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        # Mock start succeeds but health check fails
        with patch.object(tunnel_manager, "stop_tunnel"):
            with patch.object(tunnel_manager, "start_tunnel", return_value=tunnel):
                with patch.object(tunnel_manager, "health_check", return_value=False):
                    result = await recovery.attempt_recovery(
                        tunnel.id, max_attempts=2, delay=0.1
                    )

                    assert result is False

    @pytest.mark.asyncio
    async def test_schedule_recovery(self, recovery, tunnel_manager):
        """Test scheduling recovery task."""
        # Create a tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        # Mock recovery to succeed quickly
        async def mock_recovery():
            return True

        with patch.object(recovery, "attempt_recovery", return_value=mock_recovery()):
            recovery.schedule_recovery(tunnel.id)

            # Check task was created
            assert tunnel.id in recovery._recovery_tasks

            # Wait for task to complete
            await asyncio.sleep(0.2)

            # Task should be cleaned up after completion
            assert tunnel.id not in recovery._recovery_tasks

    @pytest.mark.asyncio
    async def test_cancel_recovery(self, recovery, tunnel_manager):
        """Test canceling recovery task."""
        # Create a tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        # Create a long-running recovery task
        async def slow_recovery():
            await asyncio.sleep(10)
            return True

        with patch.object(recovery, "attempt_recovery", return_value=slow_recovery()):
            recovery.schedule_recovery(tunnel.id)

            # Task should exist
            assert tunnel.id in recovery._recovery_tasks

            # Cancel it
            recovery.cancel_recovery(tunnel.id)

            # Task should be removed
            assert tunnel.id not in recovery._recovery_tasks

    def test_get_recovery_status(self, recovery):
        """Test getting recovery status."""
        tunnel_id = "test-tunnel-1"

        # Initially disabled and not in progress
        status = recovery.get_recovery_status(tunnel_id)
        assert status["enabled"] is False
        assert status["in_progress"] is False

        # Enable recovery
        recovery.enable_auto_recovery(tunnel_id)
        status = recovery.get_recovery_status(tunnel_id)
        assert status["enabled"] is True
        assert status["in_progress"] is False

    @pytest.mark.asyncio
    async def test_shutdown(self, recovery, tunnel_manager):
        """Test shutting down recovery handler."""
        # Create some tunnels and enable recovery
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

        recovery.enable_auto_recovery(tunnel1.id)
        recovery.enable_auto_recovery(tunnel2.id)

        # Schedule some recovery tasks
        async def slow_recovery():
            await asyncio.sleep(10)
            return True

        with patch.object(recovery, "attempt_recovery", return_value=slow_recovery()):
            recovery.schedule_recovery(tunnel1.id)
            recovery.schedule_recovery(tunnel2.id)

        # Shutdown should cancel all tasks
        await recovery.shutdown()

        assert len(recovery._recovery_tasks) == 0
        assert len(recovery._recovery_enabled) == 0

    @pytest.mark.asyncio
    async def test_disable_auto_recovery_cancels_task(self, recovery, tunnel_manager):
        """Test that disabling auto-recovery cancels pending task."""
        # Create a tunnel
        tunnel = tunnel_manager.create_tunnel(
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        recovery.enable_auto_recovery(tunnel.id)

        # Schedule a recovery task
        async def slow_recovery():
            await asyncio.sleep(10)
            return True

        with patch.object(recovery, "attempt_recovery", return_value=slow_recovery()):
            recovery.schedule_recovery(tunnel.id)

            # Task should exist
            assert tunnel.id in recovery._recovery_tasks

            # Disable recovery (should cancel task)
            recovery.disable_auto_recovery(tunnel.id)

            # Task should be removed
            assert tunnel.id not in recovery._recovery_tasks
            assert not recovery.is_recovery_enabled(tunnel.id)
