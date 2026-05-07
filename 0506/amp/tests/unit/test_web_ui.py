"""Unit tests for web UI API endpoints."""

import pytest
from fastapi.testclient import TestClient

from amp.core.network.graph import NetworkGraph
from amp.core.network.router import RouteCalculator
from amp.core.network.visualizer import TopologyVisualizer
from amp.mcp.server import create_app
from amp.storage.database import Database
from amp.storage.models import SegmentType, TunnelStatus, TunnelType
from amp.storage.repository import ShellRepository, TunnelRepository
from amp.web.api import set_web_components


@pytest.fixture
def database():
    """Create test database."""
    db = Database("sqlite:///:memory:")
    db.create_tables()
    return db


@pytest.fixture
def network_graph():
    """Create test network graph."""
    graph = NetworkGraph()
    # Add test segments
    graph.add_segment("seg1", "10.0.0.0/24", SegmentType.EXTERNAL, "External")
    graph.add_segment("seg2", "192.168.1.0/24", SegmentType.DMZ, "DMZ")
    graph.add_segment("seg3", "172.16.0.0/16", SegmentType.INTERNAL, "Internal")
    return graph


@pytest.fixture
def topology_visualizer(network_graph):
    """Create topology visualizer."""
    return TopologyVisualizer(network_graph)


@pytest.fixture
def route_calculator(network_graph):
    """Create route calculator."""
    return RouteCalculator(network_graph)


@pytest.fixture
def app(database, network_graph, topology_visualizer, route_calculator):
    """Create test FastAPI app."""
    app = create_app()

    # Initialize web components
    set_web_components(
        database,
        network_graph,
        topology_visualizer,
        route_calculator,
    )

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestWebUIEndpoints:
    """Test web UI API endpoints."""

    def test_serve_ui(self, client):
        """Test serving the main UI page."""
        response = client.get("/")
        # Will return 404 if index.html doesn't exist in test environment
        # or 200 if it does
        assert response.status_code in [200, 404]

    def test_get_topology_empty(self, client):
        """Test getting topology with no data."""
        response = client.get("/api/topology")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "nodes" in data["data"]
        assert "links" in data["data"]
        assert len(data["data"]["nodes"]) == 3  # From fixture
        assert len(data["data"]["links"]) == 0

    def test_get_topology_with_tunnels(self, client, network_graph, database):
        """Test getting topology with tunnels."""
        # Add tunnel to graph
        network_graph.add_tunnel(
            "tunnel1",
            "seg1",
            "seg2",
            TunnelType.CHISEL,
            TunnelStatus.ACTIVE,
        )

        response = client.get("/api/topology")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["nodes"]) == 3
        assert len(data["data"]["links"]) == 1

        link = data["data"]["links"][0]
        assert link["source"] == "seg1"
        assert link["target"] == "seg2"
        assert link["status"] == "active"

    def test_get_status(self, client, database):
        """Test getting system status."""
        # Create test tunnel
        with database.session() as session:
            tunnel_repo = TunnelRepository(session)
            tunnel = tunnel_repo.create({
                "name": "test_tunnel",
                "tunnel_type": TunnelType.CHISEL,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "10.0.0.1",
                "remote_port": 9090,
                "status": TunnelStatus.ACTIVE,
                "config": {},
            })

            # Create test shell
            shell_repo = ShellRepository(session)
            shell = shell_repo.create({
                "name": "test_shell",
                "shell_type": "reverse",
                "target_host": "10.0.0.1",
                "os_type": "linux",
                "status": "active",
                "shell_program": "bash",
                "privilege_level": "user",
                "working_directory": "/tmp",
                "environment": {},
                "config": {},
            })

        response = client.get("/api/status")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data

        status = data["data"]
        assert "tunnels" in status
        assert status["tunnels"]["total"] == 1
        assert "shells" in status
        assert status["shells"]["total"] == 1
        assert "segments" in status
        assert status["segments"]["total"] == 3
        assert "recent_operations" in status

    def test_get_segment_details(self, client, network_graph):
        """Test getting segment details."""
        response = client.get("/api/segment/seg1")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data

        segment_data = data["data"]
        assert "segment" in segment_data
        assert segment_data["segment"]["id"] == "seg1"
        assert segment_data["segment"]["cidr"] == "10.0.0.0/24"
        assert segment_data["segment"]["type"] == "external"
        assert "connected_tunnels" in segment_data
        assert "shells" in segment_data

    def test_get_segment_not_found(self, client):
        """Test getting non-existent segment."""
        response = client.get("/api/segment/nonexistent")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_get_tunnel_details(self, client, database):
        """Test getting tunnel details."""
        # Create test tunnel
        with database.session() as session:
            tunnel_repo = TunnelRepository(session)
            tunnel = tunnel_repo.create({
                "name": "test_tunnel",
                "tunnel_type": TunnelType.CHISEL,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "10.0.0.1",
                "remote_port": 9090,
                "status": TunnelStatus.ACTIVE,
                "config": {},
            })
            tunnel_id = tunnel.id

        response = client.get(f"/api/tunnel/{tunnel_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data

        tunnel_data = data["data"]["tunnel"]
        assert tunnel_data["id"] == tunnel_id
        assert tunnel_data["tunnel_type"] == "chisel"
        assert tunnel_data["local_port"] == 8080
        assert tunnel_data["remote_host"] == "10.0.0.1"

    def test_get_tunnel_not_found(self, client):
        """Test getting non-existent tunnel."""
        response = client.get("/api/tunnel/nonexistent")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False
        assert "error" in data


class TestWebUIIntegration:
    """Integration tests for web UI."""

    def test_topology_update_flow(self, client, network_graph, database):
        """Test complete topology update flow."""
        # Initial state - empty topology
        response = client.get("/api/topology")
        data = response.json()
        assert len(data["data"]["links"]) == 0

        # Add tunnel to graph
        network_graph.add_tunnel(
            "tunnel1",
            "seg1",
            "seg2",
            TunnelType.CHISEL,
            TunnelStatus.ACTIVE,
        )

        # Check updated topology
        response = client.get("/api/topology")
        data = response.json()
        assert len(data["data"]["links"]) == 1

        # Add tunnel to database for status check
        with database.session() as session:
            tunnel_repo = TunnelRepository(session)
            tunnel = tunnel_repo.create({
                "name": "tunnel1",
                "tunnel_type": TunnelType.CHISEL,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "10.0.0.1",
                "remote_port": 9090,
                "status": TunnelStatus.ACTIVE,
                "config": {},
            })

        # Check status reflects the change
        response = client.get("/api/status")
        status = response.json()["data"]
        assert status["tunnels"]["total"] == 1
        assert status["tunnels"]["active"] == 1

    def test_segment_with_tunnels_and_shells(self, client, network_graph, database):
        """Test segment details with connected tunnels and shells."""
        # Add tunnel to graph
        network_graph.add_tunnel(
            "tunnel1",
            "seg1",
            "seg2",
            TunnelType.CHISEL,
            TunnelStatus.ACTIVE,
        )

        with database.session() as session:
            # Add shell with segment metadata
            shell_repo = ShellRepository(session)
            shell = shell_repo.create({
                "name": "test_shell",
                "shell_type": "reverse",
                "target_host": "10.0.0.1",
                "os_type": "linux",
                "status": "active",
                "shell_program": "bash",
                "privilege_level": "user",
                "working_directory": "/tmp",
                "environment": {},
                "config": {"segment_id": "seg1"},
            })

        # Get segment details
        response = client.get("/api/segment/seg1")
        data = response.json()["data"]

        assert len(data["connected_tunnels"]) == 1
        assert data["connected_tunnels"][0]["source"] == "seg1"
        assert len(data["shells"]) == 1
        assert data["shells"][0]["target_host"] == "10.0.0.1"
