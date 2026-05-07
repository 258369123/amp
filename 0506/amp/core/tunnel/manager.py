"""Tunnel manager for creating and managing network tunnels."""

import logging
from datetime import datetime, timedelta
from typing import Any

from amp.config import settings
from amp.exceptions import (
    TunnelCreationFailed,
    TunnelDisconnected,
    TunnelLimitExceeded,
    TunnelNotFound,
)
from amp.storage.database import Database
from amp.storage.models import TunnelModel, TunnelStatus, TunnelType
from amp.storage.repository import TunnelRepository
from amp.storage.schema import Tunnel

from .chisel import ChiselProcess

logger = logging.getLogger(__name__)


class TunnelManager:
    """Manager for tunnel lifecycle and health monitoring."""

    def __init__(self, database: Database):
        """Initialize tunnel manager.

        Args:
            database: Database instance for persistence
        """
        self.database = database
        self._processes: dict[str, ChiselProcess] = {}

    def create_tunnel(
        self,
        name: str,
        tunnel_type: TunnelType,
        local_port: int,
        remote_host: str,
        remote_port: int,
        local_host: str = "127.0.0.1",
        parent_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> TunnelModel:
        """Create a new tunnel (register in DB, but don't start yet).

        Args:
            name: Tunnel name
            tunnel_type: Type of tunnel (chisel, ligolo, ssh)
            local_port: Local port to bind
            remote_host: Remote host to connect to
            remote_port: Remote port to connect to
            local_host: Local host to bind (default: 127.0.0.1)
            parent_id: Parent tunnel ID for nested tunnels
            config: Additional configuration

        Returns:
            Created tunnel model

        Raises:
            TunnelLimitExceeded: If max tunnels limit reached
            TunnelCreationFailed: If tunnel creation fails
        """
        with self.database.session() as session:
            repo = TunnelRepository(session)

            # Check tunnel limit
            active_count = len(repo.list_active())
            if active_count >= settings.tunnel.max_tunnels:
                raise TunnelLimitExceeded(active_count, settings.tunnel.max_tunnels)

            # Validate parent tunnel exists if specified
            if parent_id:
                parent = repo.get(parent_id)
                if not parent:
                    raise TunnelNotFound(parent_id)
                if parent.status != TunnelStatus.ACTIVE:
                    raise TunnelCreationFailed(
                        f"Parent tunnel {parent_id} is not active",
                        retry_possible=False,
                    )

            # Create tunnel record
            tunnel_data = {
                "name": name,
                "tunnel_type": tunnel_type.value,
                "status": TunnelStatus.STOPPED.value,
                "local_host": local_host,
                "local_port": local_port,
                "remote_host": remote_host,
                "remote_port": remote_port,
                "parent_tunnel_id": parent_id,
                "config": config or {},
            }

            tunnel = repo.create(tunnel_data)
            session.commit()

            logger.info(f"Created tunnel {tunnel.id} ({name})")
            return tunnel

    def start_tunnel(self, tunnel_id: str) -> TunnelModel:
        """Start a tunnel (spawn process and update status).

        Args:
            tunnel_id: Tunnel ID to start

        Returns:
            Updated tunnel model

        Raises:
            TunnelNotFound: If tunnel not found
            TunnelCreationFailed: If process fails to start
        """
        with self.database.session() as session:
            repo = TunnelRepository(session)
            tunnel = repo.get_or_raise(tunnel_id)

            if tunnel.status == TunnelStatus.ACTIVE:
                logger.warning(f"Tunnel {tunnel_id} already active")
                return tunnel

            # Only support Chisel for now
            if tunnel.tunnel_type != TunnelType.CHISEL:
                raise TunnelCreationFailed(
                    f"Tunnel type {tunnel.tunnel_type} not yet supported",
                    retry_possible=False,
                )

            # Create and start Chisel process
            try:
                process = ChiselProcess(
                    chisel_binary=settings.tunnel.chisel_binary,
                    mode="client",
                    local_host=tunnel.local_host,
                    local_port=tunnel.local_port,
                    remote_host=tunnel.remote_host,
                    remote_port=tunnel.remote_port,
                    auth=tunnel.config.get("auth"),
                    keepalive=tunnel.config.get("keepalive", 30),
                    extra_args=tunnel.config.get("extra_args", []),
                )

                pid = process.start()

                # Store process reference
                self._processes[tunnel_id] = process

                # Update tunnel in database
                tunnel_orm = session.query(Tunnel).filter(Tunnel.id == tunnel_id).first()
                if tunnel_orm:
                    tunnel_orm.process_pid = pid
                    tunnel_orm.status = TunnelStatus.ACTIVE.value
                    tunnel_orm.last_heartbeat = datetime.utcnow()
                    tunnel_orm.updated_at = datetime.utcnow()

                session.commit()

                updated = repo.get_or_raise(tunnel_id)
                logger.info(f"Started tunnel {tunnel_id} with PID {pid}")
                return updated

            except TunnelCreationFailed:
                raise
            except Exception as e:
                logger.error(f"Failed to start tunnel {tunnel_id}: {e}")
                raise TunnelCreationFailed(str(e), retry_possible=True) from e

    def stop_tunnel(self, tunnel_id: str) -> TunnelModel:
        """Stop a tunnel (terminate process and update status).

        Args:
            tunnel_id: Tunnel ID to stop

        Returns:
            Updated tunnel model

        Raises:
            TunnelNotFound: If tunnel not found
        """
        with self.database.session() as session:
            repo = TunnelRepository(session)
            repo.get_or_raise(tunnel_id)

            # Stop process if exists
            if tunnel_id in self._processes:
                process = self._processes[tunnel_id]
                process.stop()
                del self._processes[tunnel_id]
                logger.info(f"Stopped process for tunnel {tunnel_id}")

            # Update status in database
            updated = repo.update_status(tunnel_id, TunnelStatus.STOPPED)
            session.commit()

            logger.info(f"Stopped tunnel {tunnel_id}")
            return updated

    def delete_tunnel(self, tunnel_id: str) -> None:
        """Delete a tunnel (stop if running, then remove from DB).

        Args:
            tunnel_id: Tunnel ID to delete

        Raises:
            TunnelNotFound: If tunnel not found
        """
        with self.database.session() as session:
            repo = TunnelRepository(session)
            tunnel = repo.get_or_raise(tunnel_id)

            # Stop tunnel if active
            if tunnel.status == TunnelStatus.ACTIVE:
                self.stop_tunnel(tunnel_id)

            # Check for child tunnels
            children = repo.get_children(tunnel_id)
            if children:
                logger.warning(
                    f"Tunnel {tunnel_id} has {len(children)} child tunnels, "
                    "stopping them first"
                )
                for child in children:
                    self.delete_tunnel(child.id)

            # Delete from database
            repo.delete(tunnel_id)
            session.commit()

            logger.info(f"Deleted tunnel {tunnel_id}")

    def get_tunnel(self, tunnel_id: str) -> TunnelModel:
        """Get tunnel by ID.

        Args:
            tunnel_id: Tunnel ID

        Returns:
            Tunnel model

        Raises:
            TunnelNotFound: If tunnel not found
        """
        with self.database.session() as session:
            repo = TunnelRepository(session)
            return repo.get_or_raise(tunnel_id)

    def list_active_tunnels(self) -> list[TunnelModel]:
        """List all active tunnels.

        Returns:
            List of active tunnel models
        """
        with self.database.session() as session:
            repo = TunnelRepository(session)
            return repo.list_active()

    def list_all_tunnels(self) -> list[TunnelModel]:
        """List all tunnels.

        Returns:
            List of all tunnel models
        """
        with self.database.session() as session:
            repo = TunnelRepository(session)
            return repo.list_all()

    def health_check(self, tunnel_id: str) -> bool:
        """Check if tunnel is healthy (process alive).

        Args:
            tunnel_id: Tunnel ID to check

        Returns:
            True if tunnel is healthy

        Raises:
            TunnelNotFound: If tunnel not found
            TunnelDisconnected: If tunnel is disconnected
        """
        with self.database.session() as session:
            repo = TunnelRepository(session)
            tunnel = repo.get_or_raise(tunnel_id)

            if tunnel.status != TunnelStatus.ACTIVE:
                return False

            # Check if process is alive
            if tunnel_id in self._processes:
                process = self._processes[tunnel_id]
                is_alive = process.is_alive()

                if is_alive:
                    # Update heartbeat
                    repo.update_heartbeat(tunnel_id)
                    session.commit()
                    return True
                else:
                    # Process died, update status
                    logger.error(f"Tunnel {tunnel_id} process died")
                    repo.update_status(tunnel_id, TunnelStatus.DISCONNECTED)
                    session.commit()

                    # Clean up process reference
                    del self._processes[tunnel_id]

                    raise TunnelDisconnected(
                        tunnel_id,
                        tunnel.last_heartbeat or tunnel.updated_at,
                    )
            else:
                # Process not in memory, check if it should be
                if tunnel.process_pid:
                    logger.warning(
                        f"Tunnel {tunnel_id} has PID but no process reference, "
                        "marking as disconnected"
                    )
                    repo.update_status(tunnel_id, TunnelStatus.DISCONNECTED)
                    session.commit()

                return False

    def health_check_all(self) -> dict[str, bool]:
        """Run health check on all active tunnels.

        Returns:
            Dictionary mapping tunnel_id to health status
        """
        results = {}
        active_tunnels = self.list_active_tunnels()

        for tunnel in active_tunnels:
            try:
                results[tunnel.id] = self.health_check(tunnel.id)
            except TunnelDisconnected:
                results[tunnel.id] = False
            except Exception as e:
                logger.error(f"Health check failed for tunnel {tunnel.id}: {e}")
                results[tunnel.id] = False

        return results

    def get_tunnel_stats(self, tunnel_id: str) -> dict[str, Any]:
        """Get tunnel process statistics.

        Args:
            tunnel_id: Tunnel ID

        Returns:
            Dictionary with process stats

        Raises:
            TunnelNotFound: If tunnel not found
        """
        self.get_tunnel(tunnel_id)

        if tunnel_id not in self._processes:
            return {"status": "no_process"}

        process = self._processes[tunnel_id]
        stats = process.get_stats()
        logs = process.get_logs()

        return {
            "status": "running" if process.is_alive() else "dead",
            "stats": stats,
            "logs": logs,
        }

    def cleanup_stale_tunnels(self, max_age_hours: int = 24) -> int:
        """Clean up stale disconnected tunnels.

        Args:
            max_age_hours: Maximum age in hours for disconnected tunnels

        Returns:
            Number of tunnels cleaned up
        """
        with self.database.session() as session:
            repo = TunnelRepository(session)
            all_tunnels = repo.list_all()

            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            cleaned = 0

            for tunnel in all_tunnels:
                if (
                    tunnel.status == TunnelStatus.DISCONNECTED
                    and tunnel.updated_at < cutoff_time
                ):
                    try:
                        self.delete_tunnel(tunnel.id)
                        cleaned += 1
                    except Exception as e:
                        logger.error(f"Failed to cleanup tunnel {tunnel.id}: {e}")

            logger.info(f"Cleaned up {cleaned} stale tunnels")
            return cleaned

    def shutdown(self) -> None:
        """Shutdown tunnel manager (stop all tunnels)."""
        logger.info("Shutting down tunnel manager")

        # Stop all active tunnels
        for tunnel_id in list(self._processes.keys()):
            try:
                self.stop_tunnel(tunnel_id)
            except Exception as e:
                logger.error(f"Error stopping tunnel {tunnel_id}: {e}")

        self._processes.clear()
        logger.info("Tunnel manager shutdown complete")
