"""Web API endpoints for topology visualization."""

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from amp.core.network.graph import NetworkGraph
from amp.core.network.router import RouteCalculator
from amp.core.network.visualizer import TopologyVisualizer
from amp.storage.database import Database
from amp.storage.models import TunnelStatus
from amp.storage.repository import ShellRepository, TunnelRepository

logger = logging.getLogger(__name__)

# Global component instances
_database: Database | None = None
_network_graph: NetworkGraph | None = None
_topology_visualizer: TopologyVisualizer | None = None
_route_calculator: RouteCalculator | None = None


def set_web_components(
    database: Database,
    network_graph: NetworkGraph,
    topology_visualizer: TopologyVisualizer,
    route_calculator: RouteCalculator,
) -> None:
    """Set component instances for web API.

    Args:
        database: Database instance
        network_graph: Network graph instance
        topology_visualizer: Topology visualizer instance
        route_calculator: Route calculator instance
    """
    global _database, _network_graph, _topology_visualizer, _route_calculator
    _database = database
    _network_graph = network_graph
    _topology_visualizer = topology_visualizer
    _route_calculator = route_calculator
    logger.info("Web components initialized")


def setup_web_routes(app: FastAPI) -> None:
    """Setup web UI routes.

    Args:
        app: FastAPI application
    """
    # Get static files directory
    web_dir = Path(__file__).parent
    static_dir = web_dir / "static"

    # Mount static files
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info(f"Mounted static files from {static_dir}")

    @app.get("/", tags=["Web UI"], response_model=None)
    async def serve_ui() -> FileResponse | JSONResponse:
        """Serve the main UI page.

        Returns:
            HTML file response or error JSON
        """
        index_path = static_dir / "index.html"
        if not index_path.exists():
            return JSONResponse(
                status_code=404,
                content={"error": "UI not found", "message": "index.html does not exist"},
            )
        return FileResponse(str(index_path))

    @app.get("/api/topology", tags=["Web UI"])
    async def get_topology() -> dict[str, Any]:
        """Get current network topology as JSON.

        Returns:
            Topology data with nodes and links
        """
        try:
            if not _network_graph:
                return {
                    "success": False,
                    "error": "Network graph not initialized",
                }

            # Build nodes (segments)
            nodes = []
            for segment in _network_graph.get_all_segments():
                nodes.append({
                    "id": segment.id,
                    "name": segment.name,
                    "cidr": segment.cidr,
                    "type": segment.segment_type.value,
                    "metadata": segment.metadata,
                })

            # Build links (tunnels)
            links = []
            for tunnel in _network_graph.get_all_tunnels():
                links.append({
                    "id": tunnel.id,
                    "source": tunnel.source,
                    "target": tunnel.target,
                    "type": tunnel.tunnel_type.value,
                    "status": tunnel.status.value,
                    "metadata": tunnel.metadata,
                })

            logger.debug(f"Topology: {len(nodes)} nodes, {len(links)} links")

            return {
                "success": True,
                "data": {
                    "nodes": nodes,
                    "links": links,
                },
            }

        except Exception as e:
            logger.error(f"Error getting topology: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @app.get("/api/status", tags=["Web UI"])
    async def get_status() -> dict[str, Any]:
        """Get system status and statistics.

        Returns:
            System status data
        """
        try:
            if not _database or not _network_graph:
                return {
                    "success": False,
                    "error": "Components not initialized",
                }

            with _database.session() as session:
                # Get tunnel statistics
                tunnel_repo = TunnelRepository(session)
                all_tunnels = tunnel_repo.list_all()
                active_tunnels = [t for t in all_tunnels if t.status == TunnelStatus.ACTIVE]

                # Get shell statistics
                shell_repo = ShellRepository(session)
                all_shells = shell_repo.list_all()
                active_shells = [s for s in all_shells if s.status.value == "active"]

                # Get recent operations (last 10)
                from amp.storage.repository import OperationRepository
                op_repo = OperationRepository(session)
                recent_operations = op_repo.list_recent(limit=10)
                operations_data = []
                for op in recent_operations:
                    operations_data.append({
                        "id": op.id,
                        "operation_type": op.operation_type.value,
                        "status": op.status.value if hasattr(op.status, 'value') else str(op.status),
                        "created_at": op.created_at.isoformat(),
                        "completed_at": op.completed_at.isoformat() if hasattr(op, 'completed_at') and op.completed_at else None,
                        "error_message": op.error_message if hasattr(op, 'error_message') else None,
                    })

            logger.debug("Status retrieved successfully")

            return {
                "success": True,
                "data": {
                    "tunnels": {
                        "total": len(all_tunnels),
                        "active": len(active_tunnels),
                    },
                    "shells": {
                        "total": len(all_shells),
                        "active": len(active_shells),
                    },
                    "segments": {
                        "total": len(_network_graph.get_all_segments()),
                    },
                    "recent_operations": operations_data,
                },
            }

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @app.get("/api/segment/{segment_id}", tags=["Web UI"])
    async def get_segment_details(segment_id: str) -> dict[str, Any]:
        """Get detailed information about a segment.

        Args:
            segment_id: Segment identifier

        Returns:
            Segment details
        """
        try:
            if not _network_graph or not _database:
                return {
                    "success": False,
                    "error": "Components not initialized",
                }

            segment = _network_graph.get_segment(segment_id)
            if not segment:
                return {
                    "success": False,
                    "error": f"Segment {segment_id} not found",
                }

            # Get connected tunnels
            connected_tunnels = []
            for tunnel in _network_graph.get_all_tunnels():
                if tunnel.source == segment_id or tunnel.target == segment_id:
                    connected_tunnels.append({
                        "id": tunnel.id,
                        "source": tunnel.source,
                        "target": tunnel.target,
                        "type": tunnel.tunnel_type.value,
                        "status": tunnel.status.value,
                    })

            # Get shells in this segment
            with _database.session() as session:
                shell_repo = ShellRepository(session)
                all_shells = shell_repo.list_all()
                segment_shells = [
                    {
                        "id": s.id,
                        "shell_type": s.shell_type.value,
                        "target_host": s.target_host,
                        "is_active": s.status.value == "active",
                    }
                    for s in all_shells
                    if s.config.get("segment_id") == segment_id
                ]

            return {
                "success": True,
                "data": {
                    "segment": {
                        "id": segment.id,
                        "name": segment.name,
                        "cidr": segment.cidr,
                        "type": segment.segment_type.value,
                        "metadata": segment.metadata,
                    },
                    "connected_tunnels": connected_tunnels,
                    "shells": segment_shells,
                },
            }

        except Exception as e:
            logger.error(f"Error getting segment details: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @app.get("/api/tunnel/{tunnel_id}", tags=["Web UI"])
    async def get_tunnel_details(tunnel_id: str) -> dict[str, Any]:
        """Get detailed information about a tunnel.

        Args:
            tunnel_id: Tunnel identifier

        Returns:
            Tunnel details
        """
        try:
            if not _database:
                return {
                    "success": False,
                    "error": "Database not initialized",
                }

            with _database.session() as session:
                tunnel_repo = TunnelRepository(session)
                tunnel = tunnel_repo.get(tunnel_id)

            if not tunnel:
                return {
                    "success": False,
                    "error": f"Tunnel {tunnel_id} not found",
                }

            return {
                "success": True,
                "data": {
                    "tunnel": {
                        "id": tunnel.id,
                        "tunnel_type": tunnel.tunnel_type.value,
                        "status": tunnel.status.value,
                        "local_host": tunnel.local_host,
                        "local_port": tunnel.local_port,
                        "remote_host": tunnel.remote_host,
                        "remote_port": tunnel.remote_port,
                        "source_segment": tunnel.config.get("source_segment") if tunnel.config else None,
                        "target_segment": tunnel.config.get("target_segment") if tunnel.config else None,
                        "created_at": tunnel.created_at.isoformat(),
                        "last_health_check": (
                            tunnel.last_heartbeat.isoformat()
                            if tunnel.last_heartbeat
                            else None
                        ),
                        "metadata": tunnel.config if tunnel.config else {},
                    },
                },
            }

        except Exception as e:
            logger.error(f"Error getting tunnel details: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    logger.info("Web routes configured")
