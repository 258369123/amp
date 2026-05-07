"""Route calculation for network topology."""

import logging
from collections import deque
from typing import Any

from .graph import NetworkGraph

logger = logging.getLogger(__name__)


class Route:
    """Represents a route through the network."""

    def __init__(self, segments: list[str], tunnels: list[str]):
        """Initialize route.

        Args:
            segments: Ordered list of segment IDs in the route
            tunnels: Ordered list of tunnel IDs connecting the segments
        """
        self.segments = segments
        self.tunnels = tunnels

    @property
    def hop_count(self) -> int:
        """Get number of hops in the route."""
        return len(self.tunnels)

    @property
    def source(self) -> str:
        """Get source segment ID."""
        return self.segments[0] if self.segments else ""

    @property
    def target(self) -> str:
        """Get target segment ID."""
        return self.segments[-1] if self.segments else ""

    def __repr__(self) -> str:
        path = " -> ".join(self.segments)
        return f"Route({path}, hops={self.hop_count})"


class RouteCalculator:
    """Calculate routes through network topology."""

    def __init__(self, graph: NetworkGraph):
        """Initialize route calculator.

        Args:
            graph: Network graph to calculate routes on
        """
        self.graph = graph

    def find_route(
        self, source: str, target: str, active_only: bool = True
    ) -> Route | None:
        """Find optimal route between two segments using BFS.

        Args:
            source: Source segment ID
            target: Target segment ID
            active_only: Only consider active tunnels

        Returns:
            Optimal route or None if no route found
        """
        if source not in self.graph.segments:
            logger.warning(f"Source segment {source} not found")
            return None

        if target not in self.graph.segments:
            logger.warning(f"Target segment {target} not found")
            return None

        if source == target:
            return Route([source], [])

        # BFS to find shortest path
        queue: deque[tuple[str, list[str], list[str]]] = deque()
        queue.append((source, [source], []))
        visited: set[str] = {source}

        while queue:
            current, path, tunnel_path = queue.popleft()

            # Get neighbors
            for neighbor, tunnel_id in self.graph.adjacency.get(current, []):
                # Check if tunnel is active if required
                if active_only:
                    tunnel = self.graph.tunnels.get(tunnel_id)
                    if not tunnel or not tunnel.is_active():
                        continue

                if neighbor == target:
                    # Found target
                    final_path = path + [neighbor]
                    final_tunnels = tunnel_path + [tunnel_id]
                    route = Route(final_path, final_tunnels)
                    logger.debug(f"Found route: {route}")
                    return route

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor], tunnel_path + [tunnel_id]))

        logger.debug(f"No route found from {source} to {target}")
        return None

    def find_all_routes(
        self, source: str, target: str, active_only: bool = True, max_hops: int = 10
    ) -> list[Route]:
        """Find all possible routes between two segments using DFS.

        Args:
            source: Source segment ID
            target: Target segment ID
            active_only: Only consider active tunnels
            max_hops: Maximum number of hops to consider

        Returns:
            List of all possible routes
        """
        if source not in self.graph.segments or target not in self.graph.segments:
            return []

        if source == target:
            return [Route([source], [])]

        routes: list[Route] = []

        def dfs(
            current: str,
            path: list[str],
            tunnel_path: list[str],
            visited: set[str],
        ) -> None:
            """DFS helper to find all paths."""
            if len(tunnel_path) >= max_hops:
                return

            for neighbor, tunnel_id in self.graph.adjacency.get(current, []):
                # Check if tunnel is active if required
                if active_only:
                    tunnel = self.graph.tunnels.get(tunnel_id)
                    if not tunnel or not tunnel.is_active():
                        continue

                if neighbor == target:
                    # Found a route
                    routes.append(Route(path + [neighbor], tunnel_path + [tunnel_id]))
                elif neighbor not in visited:
                    # Continue searching
                    dfs(
                        neighbor,
                        path + [neighbor],
                        tunnel_path + [tunnel_id],
                        visited | {neighbor},
                    )

        dfs(source, [source], [], {source})
        logger.debug(f"Found {len(routes)} routes from {source} to {target}")
        return routes

    def calculate_hop_count(self, route: Route) -> int:
        """Calculate number of hops in a route.

        Args:
            route: Route to calculate hops for

        Returns:
            Number of hops
        """
        return route.hop_count

    def is_route_active(self, route: Route) -> bool:
        """Check if all tunnels in a route are active.

        Args:
            route: Route to check

        Returns:
            True if all tunnels are active, False otherwise
        """
        for tunnel_id in route.tunnels:
            tunnel = self.graph.tunnels.get(tunnel_id)
            if not tunnel or not tunnel.is_active():
                return False
        return True

    def get_affected_segments(self, tunnel_id: str) -> list[str]:
        """Get segments that would be affected by tunnel failure.

        This finds all segments that are only reachable through this tunnel.

        Args:
            tunnel_id: Tunnel identifier

        Returns:
            List of affected segment IDs
        """
        tunnel = self.graph.tunnels.get(tunnel_id)
        if not tunnel:
            return []

        source = tunnel.source

        # Temporarily remove the tunnel
        original_adjacency = self.graph.adjacency.get(source, []).copy()
        if source in self.graph.adjacency:
            self.graph.adjacency[source] = [
                (n, t) for n, t in self.graph.adjacency[source] if t != tunnel_id
            ]

        # Find all segments reachable from source without this tunnel
        reachable: set[str] = set()
        queue: deque[str] = deque([source])
        reachable.add(source)

        while queue:
            current = queue.popleft()
            for neighbor, tid in self.graph.adjacency.get(current, []):
                t = self.graph.tunnels.get(tid)
                if t and t.is_active() and neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)

        # Restore adjacency
        if source in self.graph.adjacency:
            self.graph.adjacency[source] = original_adjacency

        # Find segments that were reachable before but not now
        all_segments = set(self.graph.segments.keys())
        affected = []

        for segment_id in all_segments:
            if segment_id not in reachable and segment_id != source:
                # Check if this segment was reachable before
                route = self.find_route(source, segment_id, active_only=True)
                if route and tunnel_id in route.tunnels:
                    affected.append(segment_id)

        logger.debug(f"Tunnel {tunnel_id} failure would affect {len(affected)} segments")
        return affected

    def get_route_metadata(self, route: Route) -> dict[str, Any]:
        """Get metadata about a route.

        Args:
            route: Route to get metadata for

        Returns:
            Dictionary with route metadata
        """
        tunnels_info = []
        for tunnel_id in route.tunnels:
            tunnel = self.graph.tunnels.get(tunnel_id)
            if tunnel:
                tunnels_info.append(
                    {
                        "id": tunnel.id,
                        "type": tunnel.tunnel_type.value,
                        "status": tunnel.status.value,
                        "source": tunnel.source,
                        "target": tunnel.target,
                    }
                )

        segments_info = []
        for segment_id in route.segments:
            segment = self.graph.segments.get(segment_id)
            if segment:
                segments_info.append(
                    {
                        "id": segment.id,
                        "name": segment.name,
                        "cidr": segment.cidr,
                        "type": segment.segment_type.value,
                    }
                )

        return {
            "source": route.source,
            "target": route.target,
            "hop_count": route.hop_count,
            "is_active": self.is_route_active(route),
            "segments": segments_info,
            "tunnels": tunnels_info,
        }
