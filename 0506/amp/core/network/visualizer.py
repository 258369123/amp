"""Topology visualization for network graphs."""

import logging
from typing import Any

from .graph import NetworkGraph, NetworkSegment, TunnelEdge
from .router import Route

logger = logging.getLogger(__name__)


class TopologyVisualizer:
    """Generate visual representations of network topology."""

    def __init__(self, graph: NetworkGraph):
        """Initialize topology visualizer.

        Args:
            graph: Network graph to visualize
        """
        self.graph = graph

    def generate_mermaid(self, highlight_route: Route | None = None) -> str:
        """Generate Mermaid diagram of the network topology.

        Args:
            highlight_route: Optional route to highlight in the diagram

        Returns:
            Mermaid diagram as string
        """
        lines = ["graph LR"]

        # Track which segments and tunnels are in the highlighted route
        highlighted_segments = set(highlight_route.segments) if highlight_route else set()
        highlighted_tunnels = set(highlight_route.tunnels) if highlight_route else set()

        # Add segments as nodes
        for segment in self.graph.get_all_segments():
            label = self.format_segment(segment)
            node_id = self._sanitize_id(segment.id)

            # Choose node shape based on segment type
            if segment.segment_type.value == "external":
                node_shape = f"{node_id}[({label})]"  # Stadium shape
            elif segment.segment_type.value == "domain":
                node_shape = f"{node_id}[{{{label}}}]"  # Hexagon
            else:
                node_shape = f"{node_id}[{label}]"  # Rectangle

            lines.append(f"    {node_shape}")

            # Highlight if in route
            if segment.id in highlighted_segments:
                lines.append(f"    style {node_id} fill:#90EE90,stroke:#006400,stroke-width:3px")

        # Add tunnels as edges
        for tunnel in self.graph.get_all_tunnels():
            source_id = self._sanitize_id(tunnel.source)
            target_id = self._sanitize_id(tunnel.target)
            label = self.format_tunnel(tunnel)

            # Choose arrow style based on status
            if tunnel.is_active():
                arrow = "==>"  # Thick arrow for active
            else:
                arrow = "-->"  # Thin arrow for inactive

            edge_line = f"    {source_id} {arrow}|{label}| {target_id}"
            lines.append(edge_line)

            # Highlight if in route
            if tunnel.id in highlighted_tunnels:
                edge_count = len([line for line in lines if '==>' in line or '-->' in line]) - 1
                lines.append(f"    linkStyle {edge_count} stroke:#006400,stroke-width:3px")

        diagram = "\n".join(lines)
        logger.debug(f"Generated Mermaid diagram with {len(self.graph.segments)} segments")
        return diagram

    def generate_ascii(self, max_width: int = 80) -> str:
        """Generate ASCII art diagram of the network topology.

        Args:
            max_width: Maximum width of the diagram

        Returns:
            ASCII diagram as string
        """
        lines = []
        lines.append("=" * max_width)
        lines.append("Network Topology".center(max_width))
        lines.append("=" * max_width)
        lines.append("")

        # Group segments by type
        segments_by_type: dict[str, list[NetworkSegment]] = {}
        for segment in self.graph.get_all_segments():
            seg_type = segment.segment_type.value
            if seg_type not in segments_by_type:
                segments_by_type[seg_type] = []
            segments_by_type[seg_type].append(segment)

        # Display segments by type
        for seg_type in ["external", "dmz", "internal", "domain"]:
            if seg_type not in segments_by_type:
                continue

            lines.append(f"[{seg_type.upper()}]")
            for segment in segments_by_type[seg_type]:
                lines.append(f"  • {segment.name} ({segment.cidr})")

                # Show outgoing tunnels
                for neighbor_id, tunnel_id in self.graph.adjacency.get(segment.id, []):
                    tunnel = self.graph.tunnels.get(tunnel_id)
                    neighbor = self.graph.segments.get(neighbor_id)
                    if tunnel and neighbor:
                        status_icon = "✓" if tunnel.is_active() else "✗"
                        lines.append(
                            f"    └─> {neighbor.name} "
                            f"[{tunnel.tunnel_type.value}] {status_icon}"
                        )
            lines.append("")

        # Summary statistics
        lines.append("-" * max_width)
        lines.append("Statistics:")
        lines.append(f"  Total Segments: {len(self.graph.segments)}")
        lines.append(f"  Total Tunnels: {len(self.graph.tunnels)}")
        lines.append(f"  Active Tunnels: {len(self.graph.get_active_tunnels())}")
        lines.append("=" * max_width)

        return "\n".join(lines)

    def format_segment(self, segment: NetworkSegment) -> str:
        """Format segment for display.

        Args:
            segment: Network segment to format

        Returns:
            Formatted string
        """
        # Use name if available, otherwise use ID
        name = segment.name if segment.name != segment.id else segment.id[:8]
        return f"{name}\\n{segment.cidr}"

    def format_tunnel(self, tunnel: TunnelEdge) -> str:
        """Format tunnel for display.

        Args:
            tunnel: Tunnel edge to format

        Returns:
            Formatted string
        """
        type_abbrev = {
            "chisel": "CH",
            "ligolo": "LG",
            "ssh": "SSH",
        }
        abbrev = type_abbrev.get(tunnel.tunnel_type.value, tunnel.tunnel_type.value[:3].upper())

        status_icon = "✓" if tunnel.is_active() else "✗"
        return f"{abbrev} {status_icon}"

    def generate_route_diagram(self, route: Route) -> str:
        """Generate a simple text diagram of a specific route.

        Args:
            route: Route to visualize

        Returns:
            Text diagram of the route
        """
        lines = []
        lines.append("Route Path:")
        lines.append("")

        for i, segment_id in enumerate(route.segments):
            segment = self.graph.segments.get(segment_id)
            if segment:
                lines.append(f"  [{i}] {segment.name} ({segment.cidr})")

                # Add tunnel info if not last segment
                if i < len(route.tunnels):
                    tunnel_id = route.tunnels[i]
                    tunnel = self.graph.tunnels.get(tunnel_id)
                    if tunnel:
                        status = "ACTIVE" if tunnel.is_active() else "INACTIVE"
                        lines.append(
                            f"       |  via {tunnel.tunnel_type.value} "
                            f"[{status}]"
                        )
                        lines.append("       v")

        lines.append("")
        lines.append(f"Total Hops: {route.hop_count}")

        return "\n".join(lines)

    def generate_summary(self) -> dict[str, Any]:
        """Generate summary statistics of the topology.

        Returns:
            Dictionary with topology statistics
        """
        segments_by_type: dict[str, int] = {}
        for segment in self.graph.get_all_segments():
            seg_type = segment.segment_type.value
            segments_by_type[seg_type] = segments_by_type.get(seg_type, 0) + 1

        tunnels_by_type: dict[str, int] = {}
        tunnels_by_status: dict[str, int] = {}
        for tunnel in self.graph.get_all_tunnels():
            t_type = tunnel.tunnel_type.value
            t_status = tunnel.status.value
            tunnels_by_type[t_type] = tunnels_by_type.get(t_type, 0) + 1
            tunnels_by_status[t_status] = tunnels_by_status.get(t_status, 0) + 1

        return {
            "total_segments": len(self.graph.segments),
            "total_tunnels": len(self.graph.tunnels),
            "active_tunnels": len(self.graph.get_active_tunnels()),
            "segments_by_type": segments_by_type,
            "tunnels_by_type": tunnels_by_type,
            "tunnels_by_status": tunnels_by_status,
            "has_cycles": not self.graph.validate_no_cycles(),
        }

    @staticmethod
    def _sanitize_id(node_id: str) -> str:
        """Sanitize node ID for Mermaid compatibility.

        Args:
            node_id: Original node ID

        Returns:
            Sanitized ID safe for Mermaid
        """
        # Replace characters that might cause issues in Mermaid
        sanitized = node_id.replace("-", "_").replace(".", "_").replace("/", "_")
        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "n" + sanitized
        return sanitized
