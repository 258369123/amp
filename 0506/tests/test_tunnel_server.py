"""Basic tests for tunnel server implementation."""

import pytest

from amp.core.tunnel.chisel_server import ChiselServer
from amp.core.tunnel.ligolo_proxy import LigoloProxy
from amp.core.tunnel.models import (
    Forward,
    ForwardStats,
    Route,
    SessionInfo,
    SessionStatus,
    TunnelServerType,
)


def test_tunnel_server_type_enum():
    """Test TunnelServerType enum."""
    assert TunnelServerType.CHISEL == "chisel"
    assert TunnelServerType.LIGOLO == "ligolo"


def test_session_status_enum():
    """Test SessionStatus enum."""
    assert SessionStatus.ACTIVE == "active"
    assert SessionStatus.DISCONNECTED == "disconnected"


def test_forward_stats_creation():
    """Test ForwardStats dataclass creation."""
    stats = ForwardStats()
    assert stats.bytes_sent == 0
    assert stats.bytes_received == 0
    assert stats.connections == 0

    stats = ForwardStats(bytes_sent=100, bytes_received=200, connections=5)
    assert stats.bytes_sent == 100
    assert stats.bytes_received == 200
    assert stats.connections == 5


def test_forward_creation():
    """Test Forward dataclass creation."""
    forward = Forward(
        listen_addr="0.0.0.0:8080",
        target_addr="localhost:80",
        protocol="tcp",
    )
    assert forward.listen_addr == "0.0.0.0:8080"
    assert forward.target_addr == "localhost:80"
    assert forward.protocol == "tcp"
    assert isinstance(forward.stats, ForwardStats)


def test_route_creation():
    """Test Route dataclass creation."""
    route = Route(network="10.0.0.0/24", interface="ligolo")
    assert route.network == "10.0.0.0/24"
    assert route.interface == "ligolo"


def test_session_info_creation():
    """Test SessionInfo dataclass creation."""
    from datetime import datetime

    now = datetime.utcnow()
    session = SessionInfo(
        session_id="session#1",
        status=SessionStatus.ACTIVE,
        remote_addr="192.168.1.100:12345",
        connected_at=now,
    )
    assert session.session_id == "session#1"
    assert session.status == SessionStatus.ACTIVE
    assert session.remote_addr == "192.168.1.100:12345"
    assert session.connected_at == now
    assert session.forwards == []
    assert session.routes == []
    assert session.metadata == {}


def test_chisel_server_creation():
    """Test ChiselServer can be instantiated."""
    server = ChiselServer(
        chisel_binary="/usr/bin/chisel",
        port=8080,
        host="0.0.0.0",
        auth="user:pass",
    )
    assert server.chisel_binary == "/usr/bin/chisel"
    assert server.port == 8080
    assert server.host == "0.0.0.0"
    assert server.auth == "user:pass"
    assert server.process is None
    assert server.pid is None


def test_ligolo_proxy_creation():
    """Test LigoloProxy can be instantiated."""
    proxy = LigoloProxy(
        ligolo_binary="/usr/bin/ligolo-ng",
        port=11601,
        host="0.0.0.0",
        selfcert=True,
    )
    assert proxy.ligolo_binary == "/usr/bin/ligolo-ng"
    assert proxy.port == 11601
    assert proxy.host == "0.0.0.0"
    assert proxy.selfcert is True
    assert proxy.process is None
    assert proxy.pid is None


def test_chisel_server_build_command():
    """Test ChiselServer command building."""
    server = ChiselServer(
        chisel_binary="/usr/bin/chisel",
        port=8080,
        host="0.0.0.0",
        auth="user:pass",
        keepalive=30,
    )
    cmd = server._build_command()
    assert cmd[0] == "/usr/bin/chisel"
    assert cmd[1] == "server"
    assert "--host" in cmd
    assert "0.0.0.0" in cmd
    assert "--port" in cmd
    assert "8080" in cmd
    assert "--auth" in cmd
    assert "user:pass" in cmd
    assert "--reverse" in cmd


def test_ligolo_proxy_build_command():
    """Test LigoloProxy command building."""
    proxy = LigoloProxy(
        ligolo_binary="/usr/bin/ligolo-ng",
        port=11601,
        host="0.0.0.0",
        selfcert=True,
    )
    cmd = proxy._build_command()
    assert cmd[0] == "/usr/bin/ligolo-ng"
    assert cmd[1] == "proxy"
    assert "-selfcert" in cmd
    assert "-laddr" in cmd
    assert "0.0.0.0:11601" in cmd


def test_chisel_server_list_sessions():
    """Test ChiselServer list_sessions method."""
    server = ChiselServer(
        chisel_binary="/usr/bin/chisel",
        port=8080,
    )
    sessions = server.list_sessions()
    assert isinstance(sessions, list)
    assert len(sessions) == 0


def test_ligolo_proxy_list_sessions():
    """Test LigoloProxy list_sessions method."""
    proxy = LigoloProxy(
        ligolo_binary="/usr/bin/ligolo-ng",
        port=11601,
    )
    sessions = proxy.list_sessions()
    assert isinstance(sessions, list)
    assert len(sessions) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
