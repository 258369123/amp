"""Simple blackboard for shared state - fast, reliable, no blocking.

This replaces the complex ChromaDB + embeddings context system with a simple
state query pattern. No vector search, no model downloads, no blocking operations.
"""

import logging
from typing import Any

from amp.storage.database import Database

logger = logging.getLogger(__name__)


class Blackboard:
    """Shared state blackboard - tells AI what's currently available.

    This is a simple query-based state provider that replaces the complex
    vector search system. It provides fast, synchronous access to current
    system state without any blocking operations.
    """

    def __init__(self, database: Database) -> None:
        """Initialize blackboard.

        Args:
            database: Database instance
        """
        self.db = database

    def get_state(self) -> dict[str, Any]:
        """Get current complete state.

        Returns:
            Dictionary containing all current state:
            - tunnels: List of tunnel states
            - shells: List of shell states
            - network: Network topology summary
            - recent_operations: Recent operations (last 20)
        """
        return {
            "tunnels": self._get_tunnels(),
            "shells": self._get_shells(),
            "network": self._get_network(),
            "recent_operations": self._get_recent_operations(limit=20),
        }

    def _get_tunnels(self) -> list[dict[str, Any]]:
        """Get all tunnel states - simple DB query.

        Returns:
            List of tunnel state dictionaries
        """
        from amp.storage.schema import Tunnel

        with self.db.session() as session:
            tunnels = session.query(Tunnel).all()
            return [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "type": t.tunnel_type,
                    "status": t.status,
                    "local_port": t.local_port,
                    "remote": f"{t.remote_host}:{t.remote_port}",
                    "parent_id": str(t.parent_tunnel_id) if t.parent_tunnel_id else None,
                }
                for t in tunnels
            ]

    def _get_shells(self) -> list[dict[str, Any]]:
        """Get all shell states.

        Returns:
            List of shell state dictionaries
        """
        from amp.storage.schema import Shell

        with self.db.session() as session:
            shells = session.query(Shell).all()
            return [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "type": s.shell_type,
                    "status": s.status,
                    "target": s.target_host,
                    "os": s.os_type,
                }
                for s in shells
            ]

    def _get_network(self) -> dict[str, Any]:
        """Get network topology summary.

        Returns:
            Network topology summary
        """
        from amp.storage.schema import NetworkSegment

        with self.db.session() as session:
            segments = session.query(NetworkSegment).all()
            return {
                "segments": [s.name for s in segments],
                "segment_count": len(segments),
            }

    def _get_recent_operations(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent operations - simple query, no vector search.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of recent operation dictionaries
        """
        from amp.storage.schema import Operation

        with self.db.session() as session:
            ops = (
                session.query(Operation)
                .order_by(Operation.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "command": op.command,
                    "output": op.stdout[:200] if op.stdout else "",
                    "timestamp": op.created_at.isoformat(),
                    "shell_id": str(op.shell_id) if op.shell_id else None,
                }
                for op in ops
            ]
