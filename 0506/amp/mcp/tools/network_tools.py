"""Network topology tools for MCP."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global component instances (initialized by registry)
_network_graph = None
_topology_visualizer = None
_route_calculator = None


def set_network_components(
    network_graph: Any,
    topology_visualizer: Any,
    route_calculator: Any,
) -> None:
    """Set network component instances.

    Args:
        network_graph: NetworkGraph instance
        topology_visualizer: TopologyVisualizer instance
        route_calculator: RouteCalculator instance
    """
    global _network_graph, _topology_visualizer, _route_calculator
    _network_graph = network_graph
    _topology_visualizer = topology_visualizer
    _route_calculator = route_calculator


async def visualize_topology(
    format: str = "mermaid",
    highlight_route_source: str | None = None,
    highlight_route_target: str | None = None,
) -> dict[str, Any]:
    """Generate network topology visualization.

    Args:
        format: Output format (mermaid, ascii, summary)
        highlight_route_source: Optional source segment to highlight route
        highlight_route_target: Optional target segment to highlight route

    Returns:
        Response dict with topology diagram
    """
    try:
        if not _topology_visualizer:
            return {
                "success": False,
                "error": "Topology visualizer not initialized",
                "error_type": "initialization_error",
            }

        # Find route to highlight if specified
        highlight_route = None
        if highlight_route_source and highlight_route_target and _route_calculator:
            try:
                highlight_route = _route_calculator.find_route(
                    source=highlight_route_source,
                    target=highlight_route_target,
                    active_only=True,
                )
            except Exception as e:
                logger.warning(f"Failed to find highlight route: {e}")

        # Generate visualization based on format
        if format == "mermaid":
            diagram = _topology_visualizer.generate_mermaid(
                highlight_route=highlight_route
            )
            output_type = "diagram"
        elif format == "ascii":
            diagram = _topology_visualizer.generate_ascii()
            output_type = "diagram"
        elif format == "summary":
            diagram = _topology_visualizer.generate_summary()
            output_type = "summary"
        else:
            return {
                "success": False,
                "error": f"Invalid format: {format}",
                "error_type": "validation_error",
            }

        logger.debug(f"Generated topology visualization in {format} format")

        return {
            "success": True,
            "data": {
                "format": format,
                "output_type": output_type,
                "content": diagram,
            },
        }

    except Exception as e:
        logger.error(f"Unexpected error visualizing topology: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def find_route(
    source: str,
    target: str,
    active_only: bool = True,
    find_all: bool = False,
    max_hops: int = 10,
) -> dict[str, Any]:
    """Find route between network segments.

    Args:
        source: Source segment ID
        target: Target segment ID
        active_only: Only consider active tunnels
        find_all: Find all possible routes (not just optimal)
        max_hops: Maximum number of hops to consider

    Returns:
        Response dict with route information
    """
    try:
        if not _route_calculator:
            return {
                "success": False,
                "error": "Route calculator not initialized",
                "error_type": "initialization_error",
            }

        if find_all:
            # Find all routes
            routes = _route_calculator.find_all_routes(
                source=source,
                target=target,
                active_only=active_only,
                max_hops=max_hops,
            )

            if not routes:
                return {
                    "success": True,
                    "data": {
                        "routes": [],
                        "count": 0,
                        "message": f"No routes found from {source} to {target}",
                    },
                }

            # Convert routes to dict format
            route_list = []
            for route in routes:
                metadata = _route_calculator.get_route_metadata(route)
                route_list.append({
                    "source": route.source,
                    "target": route.target,
                    "hop_count": route.hop_count,
                    "segments": route.segments,
                    "tunnels": route.tunnels,
                    "is_active": _route_calculator.is_route_active(route),
                    "metadata": metadata,
                })

            logger.debug(f"Found {len(route_list)} routes from {source} to {target}")

            return {
                "success": True,
                "data": {
                    "routes": route_list,
                    "count": len(route_list),
                },
            }

        else:
            # Find optimal route
            route = _route_calculator.find_route(
                source=source,
                target=target,
                active_only=active_only,
            )

            if not route:
                return {
                    "success": True,
                    "data": {
                        "route": None,
                        "message": f"No route found from {source} to {target}",
                    },
                }

            # Get route metadata
            metadata = _route_calculator.get_route_metadata(route)

            # Generate route diagram if visualizer available
            route_diagram = None
            if _topology_visualizer:
                try:
                    route_diagram = _topology_visualizer.generate_route_diagram(route)
                except Exception as e:
                    logger.warning(f"Failed to generate route diagram: {e}")

            logger.debug(f"Found route from {source} to {target}: {route.hop_count} hops")

            return {
                "success": True,
                "data": {
                    "route": {
                        "source": route.source,
                        "target": route.target,
                        "hop_count": route.hop_count,
                        "segments": route.segments,
                        "tunnels": route.tunnels,
                        "is_active": _route_calculator.is_route_active(route),
                        "metadata": metadata,
                    },
                    "diagram": route_diagram,
                },
            }

    except Exception as e:
        logger.error(f"Unexpected error finding route: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def get_affected_segments(tunnel_id: str) -> dict[str, Any]:
    """Get segments affected by tunnel failure.

    Args:
        tunnel_id: Tunnel ID to analyze

    Returns:
        Response dict with affected segments
    """
    try:
        if not _route_calculator:
            return {
                "success": False,
                "error": "Route calculator not initialized",
                "error_type": "initialization_error",
            }

        # Get affected segments
        affected = _route_calculator.get_affected_segments(tunnel_id)

        # Get segment details if graph available
        segment_details = []
        if _network_graph:
            for segment_id in affected:
                segment = _network_graph.segments.get(segment_id)
                if segment:
                    segment_details.append({
                        "segment_id": segment.id,
                        "name": segment.name,
                        "cidr": segment.cidr,
                        "segment_type": segment.segment_type.value,
                    })

        logger.debug(f"Tunnel {tunnel_id} failure would affect {len(affected)} segments")

        return {
            "success": True,
            "data": {
                "tunnel_id": tunnel_id,
                "affected_segment_ids": affected,
                "affected_segments": segment_details,
                "count": len(affected),
            },
        }

    except Exception as e:
        logger.error(f"Unexpected error getting affected segments: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }
