"""Unit tests for network topology module."""

import pytest

from amp.core.network import (
    NetworkGraph,
    NetworkSegment,
    Route,
    RouteCalculator,
    TopologyVisualizer,
    TunnelEdge,
)
from amp.exceptions import NetworkException
from amp.storage.models import SegmentType, TunnelStatus, TunnelType


class TestNetworkSegment:
    """Tests for NetworkSegment class."""

    def test_create_segment(self) -> None:
        """Test creating a network segment."""
        segment = NetworkSegment(
            segment_id="seg1",
            cidr="192.168.1.0/24",
            segment_type=SegmentType.INTERNAL,
            name="Internal Network",
        )

        assert segment.id == "seg1"
        assert segment.cidr == "192.168.1.0/24"
        assert segment.segment_type == SegmentType.INTERNAL
        assert segment.name == "Internal Network"
        assert segment.metadata == {}

    def test_segment_with_metadata(self) -> None:
        """Test segment with metadata."""
        metadata = {"vlan": 100, "gateway": "192.168.1.1"}
        segment = NetworkSegment(
            segment_id="seg1",
            cidr="192.168.1.0/24",
            segment_type=SegmentType.DMZ,
            metadata=metadata,
        )

        assert segment.metadata == metadata

    def test_segment_default_name(self) -> None:
        """Test segment uses ID as default name."""
        segment = NetworkSegment(
            segment_id="seg1",
            cidr="192.168.1.0/24",
            segment_type=SegmentType.EXTERNAL,
        )

        assert segment.name == "seg1"


class TestTunnelEdge:
    """Tests for TunnelEdge class."""

    def test_create_tunnel(self) -> None:
        """Test creating a tunnel edge."""
        tunnel = TunnelEdge(
            tunnel_id="t1",
            source_segment="seg1",
            target_segment="seg2",
            tunnel_type=TunnelType.CHISEL,
            status=TunnelStatus.ACTIVE,
        )

        assert tunnel.id == "t1"
        assert tunnel.source == "seg1"
        assert tunnel.target == "seg2"
        assert tunnel.tunnel_type == TunnelType.CHISEL
        assert tunnel.status == TunnelStatus.ACTIVE

    def test_tunnel_is_active(self) -> None:
        """Test tunnel active status check."""
        active_tunnel = TunnelEdge(
            tunnel_id="t1",
            source_segment="seg1",
            target_segment="seg2",
            tunnel_type=TunnelType.CHISEL,
            status=TunnelStatus.ACTIVE,
        )
        inactive_tunnel = TunnelEdge(
            tunnel_id="t2",
            source_segment="seg1",
            target_segment="seg2",
            tunnel_type=TunnelType.CHISEL,
            status=TunnelStatus.STOPPED,
        )

        assert active_tunnel.is_active() is True
        assert inactive_tunnel.is_active() is False


class TestNetworkGraph:
    """Tests for NetworkGraph class."""

    def test_create_empty_graph(self) -> None:
        """Test creating an empty graph."""
        graph = NetworkGraph()

        assert len(graph.segments) == 0
        assert len(graph.tunnels) == 0
        assert len(graph.adjacency) == 0

    def test_add_segment(self) -> None:
        """Test adding a segment to the graph."""
        graph = NetworkGraph()
        segment = graph.add_segment(
            segment_id="seg1",
            cidr="192.168.1.0/24",
            segment_type=SegmentType.INTERNAL,
            name="Internal",
        )

        assert segment.id == "seg1"
        assert "seg1" in graph.segments
        assert "seg1" in graph.adjacency

    def test_add_tunnel(self) -> None:
        """Test adding a tunnel to the graph."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)

        tunnel = graph.add_tunnel(
            tunnel_id="t1",
            source_segment="seg1",
            target_segment="seg2",
            tunnel_type=TunnelType.CHISEL,
            status=TunnelStatus.ACTIVE,
        )

        assert tunnel.id == "t1"
        assert "t1" in graph.tunnels
        assert ("seg2", "t1") in graph.adjacency["seg1"]

    def test_add_tunnel_missing_source(self) -> None:
        """Test adding tunnel with missing source segment."""
        graph = NetworkGraph()
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)

        with pytest.raises(NetworkException, match="Source segment seg1 not found"):
            graph.add_tunnel(
                tunnel_id="t1",
                source_segment="seg1",
                target_segment="seg2",
                tunnel_type=TunnelType.CHISEL,
                status=TunnelStatus.ACTIVE,
            )

    def test_add_tunnel_missing_target(self) -> None:
        """Test adding tunnel with missing target segment."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)

        with pytest.raises(NetworkException, match="Target segment seg2 not found"):
            graph.add_tunnel(
                tunnel_id="t1",
                source_segment="seg1",
                target_segment="seg2",
                tunnel_type=TunnelType.CHISEL,
                status=TunnelStatus.ACTIVE,
            )

    def test_remove_tunnel(self) -> None:
        """Test removing a tunnel from the graph."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)

        graph.remove_tunnel("t1")

        assert "t1" not in graph.tunnels
        assert ("seg2", "t1") not in graph.adjacency["seg1"]

    def test_update_tunnel_status(self) -> None:
        """Test updating tunnel status."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)

        graph.update_tunnel_status("t1", TunnelStatus.DISCONNECTED)

        tunnel = graph.get_tunnel("t1")
        assert tunnel is not None
        assert tunnel.status == TunnelStatus.DISCONNECTED

    def test_update_tunnel_status_not_found(self) -> None:
        """Test updating status of non-existent tunnel."""
        graph = NetworkGraph()

        with pytest.raises(NetworkException, match="Tunnel t1 not found"):
            graph.update_tunnel_status("t1", TunnelStatus.ACTIVE)

    def test_get_neighbors(self) -> None:
        """Test getting neighbor segments."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)
        graph.add_segment("seg3", "192.168.3.0/24", SegmentType.INTERNAL)
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t2", "seg1", "seg3", TunnelType.CHISEL, TunnelStatus.STOPPED)

        # All neighbors
        neighbors = graph.get_neighbors("seg1", active_only=False)
        assert set(neighbors) == {"seg2", "seg3"}

        # Active only
        active_neighbors = graph.get_neighbors("seg1", active_only=True)
        assert active_neighbors == ["seg2"]

    def test_get_active_tunnels(self) -> None:
        """Test getting active tunnels."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)
        graph.add_segment("seg3", "192.168.3.0/24", SegmentType.INTERNAL)
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t2", "seg1", "seg3", TunnelType.CHISEL, TunnelStatus.STOPPED)
        graph.add_tunnel("t3", "seg2", "seg3", TunnelType.LIGOLO, TunnelStatus.ACTIVE)

        active_tunnels = graph.get_active_tunnels()
        assert len(active_tunnels) == 2
        assert all(t.is_active() for t in active_tunnels)

    def test_validate_no_cycles_simple(self) -> None:
        """Test cycle detection on simple graph."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)
        graph.add_segment("seg3", "192.168.3.0/24", SegmentType.INTERNAL)
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t2", "seg2", "seg3", TunnelType.CHISEL, TunnelStatus.ACTIVE)

        assert graph.validate_no_cycles() is True

    def test_validate_no_cycles_with_cycle(self) -> None:
        """Test cycle detection with actual cycle."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)
        graph.add_segment("seg3", "192.168.3.0/24", SegmentType.INTERNAL)
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t2", "seg2", "seg3", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t3", "seg3", "seg1", TunnelType.CHISEL, TunnelStatus.ACTIVE)

        assert graph.validate_no_cycles() is False

    def test_clear_graph(self) -> None:
        """Test clearing the graph."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)

        graph.clear()

        assert len(graph.segments) == 0
        assert len(graph.tunnels) == 0
        assert len(graph.adjacency) == 0


class TestRoute:
    """Tests for Route class."""

    def test_create_route(self) -> None:
        """Test creating a route."""
        route = Route(
            segments=["seg1", "seg2", "seg3"],
            tunnels=["t1", "t2"],
        )

        assert route.segments == ["seg1", "seg2", "seg3"]
        assert route.tunnels == ["t1", "t2"]
        assert route.hop_count == 2
        assert route.source == "seg1"
        assert route.target == "seg3"

    def test_empty_route(self) -> None:
        """Test empty route."""
        route = Route(segments=[], tunnels=[])

        assert route.hop_count == 0
        assert route.source == ""
        assert route.target == ""


class TestRouteCalculator:
    """Tests for RouteCalculator class."""

    @pytest.fixture
    def simple_graph(self) -> NetworkGraph:
        """Create a simple test graph."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL, "External")
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ, "DMZ")
        graph.add_segment("seg3", "192.168.3.0/24", SegmentType.INTERNAL, "Internal")
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t2", "seg2", "seg3", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        return graph

    @pytest.fixture
    def complex_graph(self) -> NetworkGraph:
        """Create a complex test graph with multiple paths."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL)
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ)
        graph.add_segment("seg3", "192.168.3.0/24", SegmentType.INTERNAL)
        graph.add_segment("seg4", "192.168.4.0/24", SegmentType.INTERNAL)

        # Create two paths: seg1 -> seg2 -> seg4 and seg1 -> seg3 -> seg4
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t2", "seg1", "seg3", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t3", "seg2", "seg4", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t4", "seg3", "seg4", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        return graph

    def test_find_route_simple(self, simple_graph: NetworkGraph) -> None:
        """Test finding a simple route."""
        calculator = RouteCalculator(simple_graph)
        route = calculator.find_route("seg1", "seg3")

        assert route is not None
        assert route.source == "seg1"
        assert route.target == "seg3"
        assert route.hop_count == 2
        assert route.segments == ["seg1", "seg2", "seg3"]
        assert route.tunnels == ["t1", "t2"]

    def test_find_route_same_segment(self, simple_graph: NetworkGraph) -> None:
        """Test finding route to same segment."""
        calculator = RouteCalculator(simple_graph)
        route = calculator.find_route("seg1", "seg1")

        assert route is not None
        assert route.segments == ["seg1"]
        assert route.tunnels == []
        assert route.hop_count == 0

    def test_find_route_not_found(self, simple_graph: NetworkGraph) -> None:
        """Test finding route when no path exists."""
        calculator = RouteCalculator(simple_graph)
        # Add isolated segment
        simple_graph.add_segment("seg4", "192.168.4.0/24", SegmentType.DOMAIN)

        route = calculator.find_route("seg1", "seg4")
        assert route is None

    def test_find_route_inactive_tunnel(self, simple_graph: NetworkGraph) -> None:
        """Test finding route with inactive tunnel."""
        calculator = RouteCalculator(simple_graph)
        simple_graph.update_tunnel_status("t2", TunnelStatus.STOPPED)

        # Should not find route when active_only=True
        route = calculator.find_route("seg1", "seg3", active_only=True)
        assert route is None

        # Should find route when active_only=False
        route = calculator.find_route("seg1", "seg3", active_only=False)
        assert route is not None

    def test_find_all_routes(self, complex_graph: NetworkGraph) -> None:
        """Test finding all possible routes."""
        calculator = RouteCalculator(complex_graph)
        routes = calculator.find_all_routes("seg1", "seg4")

        assert len(routes) == 2
        # Both routes should have 2 hops
        assert all(r.hop_count == 2 for r in routes)

    def test_is_route_active(self, simple_graph: NetworkGraph) -> None:
        """Test checking if route is active."""
        calculator = RouteCalculator(simple_graph)
        route = calculator.find_route("seg1", "seg3")
        assert route is not None

        # Initially active
        assert calculator.is_route_active(route) is True

        # Make one tunnel inactive
        simple_graph.update_tunnel_status("t2", TunnelStatus.STOPPED)
        assert calculator.is_route_active(route) is False

    def test_get_affected_segments(self, simple_graph: NetworkGraph) -> None:
        """Test getting affected segments on tunnel failure."""
        calculator = RouteCalculator(simple_graph)

        # If t2 fails, seg3 becomes unreachable from seg1
        affected = calculator.get_affected_segments("t2")
        assert "seg3" in affected

    def test_get_route_metadata(self, simple_graph: NetworkGraph) -> None:
        """Test getting route metadata."""
        calculator = RouteCalculator(simple_graph)
        route = calculator.find_route("seg1", "seg3")
        assert route is not None

        metadata = calculator.get_route_metadata(route)

        assert metadata["source"] == "seg1"
        assert metadata["target"] == "seg3"
        assert metadata["hop_count"] == 2
        assert metadata["is_active"] is True
        assert len(metadata["segments"]) == 3
        assert len(metadata["tunnels"]) == 2


class TestTopologyVisualizer:
    """Tests for TopologyVisualizer class."""

    @pytest.fixture
    def test_graph(self) -> NetworkGraph:
        """Create a test graph."""
        graph = NetworkGraph()
        graph.add_segment("seg1", "192.168.1.0/24", SegmentType.EXTERNAL, "External")
        graph.add_segment("seg2", "192.168.2.0/24", SegmentType.DMZ, "DMZ")
        graph.add_segment("seg3", "192.168.3.0/24", SegmentType.INTERNAL, "Internal")
        graph.add_tunnel("t1", "seg1", "seg2", TunnelType.CHISEL, TunnelStatus.ACTIVE)
        graph.add_tunnel("t2", "seg2", "seg3", TunnelType.CHISEL, TunnelStatus.STOPPED)
        return graph

    def test_generate_mermaid(self, test_graph: NetworkGraph) -> None:
        """Test generating Mermaid diagram."""
        visualizer = TopologyVisualizer(test_graph)
        diagram = visualizer.generate_mermaid()

        assert "graph LR" in diagram
        assert "seg1" in diagram
        assert "seg2" in diagram
        assert "seg3" in diagram
        assert "==>" in diagram  # Active tunnel
        assert "-->" in diagram  # Inactive tunnel

    def test_generate_mermaid_with_highlight(self, test_graph: NetworkGraph) -> None:
        """Test generating Mermaid diagram with highlighted route."""
        visualizer = TopologyVisualizer(test_graph)
        route = Route(segments=["seg1", "seg2"], tunnels=["t1"])
        diagram = visualizer.generate_mermaid(highlight_route=route)

        assert "graph LR" in diagram
        assert "style" in diagram  # Highlighting styles

    def test_generate_ascii(self, test_graph: NetworkGraph) -> None:
        """Test generating ASCII diagram."""
        visualizer = TopologyVisualizer(test_graph)
        diagram = visualizer.generate_ascii()

        assert "Network Topology" in diagram
        assert "EXTERNAL" in diagram
        assert "DMZ" in diagram
        assert "INTERNAL" in diagram
        assert "Statistics:" in diagram

    def test_format_segment(self, test_graph: NetworkGraph) -> None:
        """Test formatting segment."""
        visualizer = TopologyVisualizer(test_graph)
        segment = test_graph.get_segment("seg1")
        assert segment is not None

        formatted = visualizer.format_segment(segment)
        assert "External" in formatted
        assert "192.168.1.0/24" in formatted

    def test_format_tunnel(self, test_graph: NetworkGraph) -> None:
        """Test formatting tunnel."""
        visualizer = TopologyVisualizer(test_graph)
        tunnel = test_graph.get_tunnel("t1")
        assert tunnel is not None

        formatted = visualizer.format_tunnel(tunnel)
        assert "CH" in formatted  # Chisel abbreviation
        assert "✓" in formatted  # Active icon

    def test_generate_route_diagram(self, test_graph: NetworkGraph) -> None:
        """Test generating route diagram."""
        visualizer = TopologyVisualizer(test_graph)
        route = Route(segments=["seg1", "seg2", "seg3"], tunnels=["t1", "t2"])
        diagram = visualizer.generate_route_diagram(route)

        assert "Route Path:" in diagram
        assert "External" in diagram
        assert "DMZ" in diagram
        assert "Internal" in diagram
        assert "Total Hops: 2" in diagram

    def test_generate_summary(self, test_graph: NetworkGraph) -> None:
        """Test generating topology summary."""
        visualizer = TopologyVisualizer(test_graph)
        summary = visualizer.generate_summary()

        assert summary["total_segments"] == 3
        assert summary["total_tunnels"] == 2
        assert summary["active_tunnels"] == 1
        assert summary["segments_by_type"]["external"] == 1
        assert summary["segments_by_type"]["dmz"] == 1
        assert summary["segments_by_type"]["internal"] == 1
        assert summary["tunnels_by_type"]["chisel"] == 2
        assert summary["has_cycles"] is False
