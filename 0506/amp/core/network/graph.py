"""Network topology graph for tunnel and segment management."""

import logging
from typing import Any

from amp.exceptions import NetworkException
from amp.storage.models import SegmentType, TunnelStatus, TunnelType

logger = logging.getLogger(__name__)


class NetworkSegment:
    """Represents a network segment node in the topology graph."""

    def __init__(
        self,
        segment_id: str,
        cidr: str,
        segment_type: SegmentType,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Initialize network segment.

        Args:
            segment_id: Unique segment identifier
            cidr: CIDR notation (e.g., "192.168.1.0/24")
            segment_type: Type of segment (external, dmz, internal, domain)
            name: Human-readable name
            metadata: Additional metadata
        """
        self.id = segment_id
        self.cidr = cidr
        self.segment_type = segment_type
        self.name = name or segment_id
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"NetworkSegment(id={self.id}, cidr={self.cidr}, type={self.segment_type})"


class TunnelEdge:
    """Represents a tunnel connection between segments."""

    def __init__(
        self,
        tunnel_id: str,
        source_segment: str,
        target_segment: str,
        tunnel_type: TunnelType,
        status: TunnelStatus,
        metadata: dict[str, Any] | None = None,
    ):
        """Initialize tunnel edge.

        Args:
            tunnel_id: Unique tunnel identifier
            source_segment: Source segment ID
            target_segment: Target segment ID
            tunnel_type: Type of tunnel (chisel, ligolo, ssh)
            status: Tunnel status (active, disconnected, stopped)
            metadata: Additional metadata
        """
        self.id = tunnel_id
        self.source = source_segment
        self.target = target_segment
        self.tunnel_type = tunnel_type
        self.status = status
        self.metadata = metadata or {}

    def is_active(self) -> bool:
        """Check if tunnel is active."""
        return self.status == TunnelStatus.ACTIVE

    def __repr__(self) -> str:
        return (
            f"TunnelEdge(id={self.id}, {self.source}->{self.target}, "
            f"type={self.tunnel_type}, status={self.status})"
        )


class NetworkGraph:
    """In-memory graph structure for network topology."""

    def __init__(self, database=None) -> None:
        """Initialize empty network graph.

        Args:
            database: Optional database instance for syncing
        """
        self.database = database
        self.segments: dict[str, NetworkSegment] = {}
        self.tunnels: dict[str, TunnelEdge] = {}
        # Adjacency list: segment_id -> list of (neighbor_id, tunnel_id)
        self.adjacency: dict[str, list[tuple[str, str]]] = {}

    def add_segment(
        self,
        segment_id: str,
        cidr: str,
        segment_type: SegmentType,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NetworkSegment:
        """Add a network segment to the graph.

        Args:
            segment_id: Unique segment identifier
            cidr: CIDR notation
            segment_type: Type of segment
            name: Human-readable name
            metadata: Additional metadata

        Returns:
            Created network segment
        """
        segment = NetworkSegment(segment_id, cidr, segment_type, name, metadata)
        self.segments[segment_id] = segment
        if segment_id not in self.adjacency:
            self.adjacency[segment_id] = []
        logger.debug(f"Added segment: {segment}")
        return segment

    def add_tunnel(
        self,
        tunnel_id: str,
        source_segment: str,
        target_segment: str,
        tunnel_type: TunnelType,
        status: TunnelStatus,
        metadata: dict[str, Any] | None = None,
    ) -> TunnelEdge:
        """Add a tunnel connection between segments.

        Args:
            tunnel_id: Unique tunnel identifier
            source_segment: Source segment ID
            target_segment: Target segment ID
            tunnel_type: Type of tunnel
            status: Tunnel status
            metadata: Additional metadata

        Returns:
            Created tunnel edge

        Raises:
            NetworkException: If source or target segment doesn't exist
        """
        if source_segment not in self.segments:
            raise NetworkException(
                f"Source segment {source_segment} not found",
                {"source": source_segment},
            )
        if target_segment not in self.segments:
            raise NetworkException(
                f"Target segment {target_segment} not found",
                {"target": target_segment},
            )

        tunnel = TunnelEdge(
            tunnel_id, source_segment, target_segment, tunnel_type, status, metadata
        )
        self.tunnels[tunnel_id] = tunnel

        # Update adjacency list (directed graph)
        if source_segment not in self.adjacency:
            self.adjacency[source_segment] = []
        self.adjacency[source_segment].append((target_segment, tunnel_id))

        logger.debug(f"Added tunnel: {tunnel}")
        return tunnel

    def remove_tunnel(self, tunnel_id: str) -> None:
        """Remove a tunnel from the graph.

        Args:
            tunnel_id: Tunnel identifier to remove
        """
        if tunnel_id not in self.tunnels:
            logger.warning(f"Tunnel {tunnel_id} not found in graph")
            return

        tunnel = self.tunnels[tunnel_id]
        source = tunnel.source

        # Remove from adjacency list
        if source in self.adjacency:
            self.adjacency[source] = [
                (neighbor, tid) for neighbor, tid in self.adjacency[source] if tid != tunnel_id
            ]

        del self.tunnels[tunnel_id]
        logger.debug(f"Removed tunnel: {tunnel_id}")

    def update_tunnel_status(self, tunnel_id: str, status: TunnelStatus) -> None:
        """Update tunnel status.

        Args:
            tunnel_id: Tunnel identifier
            status: New status

        Raises:
            NetworkException: If tunnel not found
        """
        if tunnel_id not in self.tunnels:
            raise NetworkException(f"Tunnel {tunnel_id} not found", {"tunnel_id": tunnel_id})

        self.tunnels[tunnel_id].status = status
        logger.debug(f"Updated tunnel {tunnel_id} status to {status}")

    def get_segment(self, segment_id: str) -> NetworkSegment | None:
        """Get segment by ID.

        Args:
            segment_id: Segment identifier

        Returns:
            Network segment or None if not found
        """
        return self.segments.get(segment_id)

    def get_tunnel(self, tunnel_id: str) -> TunnelEdge | None:
        """Get tunnel by ID.

        Args:
            tunnel_id: Tunnel identifier

        Returns:
            Tunnel edge or None if not found
        """
        return self.tunnels.get(tunnel_id)

    def get_neighbors(self, segment_id: str, active_only: bool = False) -> list[str]:
        """Get connected segments.

        Args:
            segment_id: Segment identifier
            active_only: Only return neighbors connected via active tunnels

        Returns:
            List of neighbor segment IDs
        """
        if segment_id not in self.adjacency:
            return []

        neighbors = []
        for neighbor_id, tunnel_id in self.adjacency[segment_id]:
            if active_only:
                tunnel = self.tunnels.get(tunnel_id)
                if tunnel and tunnel.is_active():
                    neighbors.append(neighbor_id)
            else:
                neighbors.append(neighbor_id)

        return neighbors

    def get_all_segments(self) -> list[NetworkSegment]:
        """Get all segments in the graph.

        Returns:
            List of all network segments
        """
        return list(self.segments.values())

    def get_all_tunnels(self) -> list[TunnelEdge]:
        """Get all tunnels in the graph.

        Returns:
            List of all tunnel edges
        """
        return list(self.tunnels.values())

    def get_active_tunnels(self) -> list[TunnelEdge]:
        """Get all active tunnels.

        Returns:
            List of active tunnel edges
        """
        return [t for t in self.tunnels.values() if t.is_active()]

    def validate_no_cycles(self) -> bool:
        """Check for circular dependencies using DFS.

        Returns:
            True if no cycles detected, False otherwise
        """
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(node: str) -> bool:
            """DFS helper to detect cycles."""
            visited.add(node)
            rec_stack.add(node)

            for neighbor, _tunnel_id in self.adjacency.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    logger.warning(f"Cycle detected: {node} -> {neighbor}")
                    return True

            rec_stack.remove(node)
            return False

        for segment_id in self.segments:
            if segment_id not in visited:
                if has_cycle(segment_id):
                    return False

        return True

    def clear(self) -> None:
        """Clear all segments and tunnels from the graph."""
        self.segments.clear()
        self.tunnels.clear()
        self.adjacency.clear()
        logger.debug("Cleared network graph")

    def sync_from_database(self) -> None:
        """Sync graph from database tunnels.

        Rebuilds the graph structure from database state.
        """
        if not self.database:
            logger.warning("Cannot sync: no database configured")
            return

        from amp.storage.schema import Tunnel

        with self.database.session() as session:
            tunnels = session.query(Tunnel).all()

            # Clear existing
            self.clear()

            logger.info(f"Syncing {len(tunnels)} tunnels from database")

            # Rebuild from database
            for tunnel in tunnels:
                try:
                    # Convert to TunnelType and TunnelStatus enums
                    tunnel_type = TunnelType(tunnel.tunnel_type)
                    tunnel_status = TunnelStatus(tunnel.status)

                    # Add segments if they don't exist
                    if tunnel.local_host not in self.segments:
                        self.add_segment(
                            segment_id=tunnel.local_host,
                            cidr=f"{tunnel.local_host}/32",
                            segment_type=SegmentType.INTERNAL,
                            name=f"Local-{tunnel.local_host}",
                        )

                    if tunnel.remote_host not in self.segments:
                        self.add_segment(
                            segment_id=tunnel.remote_host,
                            cidr=f"{tunnel.remote_host}/32",
                            segment_type=SegmentType.INTERNAL,
                            name=f"Remote-{tunnel.remote_host}",
                        )

                    # Add tunnel edge
                    self.add_tunnel(
                        tunnel_id=tunnel.id,
                        source_segment=tunnel.local_host,
                        target_segment=tunnel.remote_host,
                        tunnel_type=tunnel_type,
                        status=tunnel_status,
                        metadata={
                            "name": tunnel.name,
                            "local_port": tunnel.local_port,
                            "remote_port": tunnel.remote_port,
                            "process_pid": tunnel.process_pid,
                        },
                    )

                except Exception as e:
                    logger.error(f"Failed to sync tunnel {tunnel.id}: {e}")

            logger.info(f"Synced graph: {len(self.segments)} segments, {len(self.tunnels)} tunnels")

    def get_stats(self) -> dict[str, Any]:
        """Get network graph statistics.

        If database is configured, syncs first and returns database stats.
        Otherwise returns in-memory stats.

        Returns:
            Dictionary with graph statistics
        """
        if self.database:
            # Sync from database first
            self.sync_from_database()

            from amp.storage.schema import Tunnel

            with self.database.session() as session:
                total = session.query(Tunnel).count()
                active = session.query(Tunnel).filter(
                    Tunnel.status == TunnelStatus.ACTIVE.value
                ).count()

                return {
                    "total_segments": len(self.segments),
                    "total_tunnels": total,
                    "active_tunnels": active,
                }
        else:
            # Use in-memory stats
            return {
                "total_segments": len(self.segments),
                "total_tunnels": len(self.tunnels),
                "active_tunnels": len(self.get_active_tunnels()),
            }
