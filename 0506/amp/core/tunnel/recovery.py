"""Auto-recovery logic for tunnel management."""

import asyncio
import logging
from typing import TYPE_CHECKING

from amp.config import settings
from amp.exceptions import TunnelCreationFailed, TunnelNotFound

if TYPE_CHECKING:
    from amp.core.tunnel.manager import TunnelManager

logger = logging.getLogger(__name__)


class TunnelRecovery:
    """Handles automatic recovery of disconnected tunnels."""

    def __init__(self, tunnel_manager: "TunnelManager"):
        """Initialize tunnel recovery handler.

        Args:
            tunnel_manager: TunnelManager instance
        """
        self.tunnel_manager = tunnel_manager
        self._recovery_tasks: dict[str, asyncio.Task] = {}
        self._recovery_enabled: set[str] = set()

    def enable_auto_recovery(self, tunnel_id: str) -> None:
        """Enable auto-recovery for a tunnel.

        Args:
            tunnel_id: Tunnel ID to enable recovery for
        """
        self._recovery_enabled.add(tunnel_id)
        logger.info(f"Auto-recovery enabled for tunnel {tunnel_id}")

    def disable_auto_recovery(self, tunnel_id: str) -> None:
        """Disable auto-recovery for a tunnel.

        Args:
            tunnel_id: Tunnel ID to disable recovery for
        """
        if tunnel_id in self._recovery_enabled:
            self._recovery_enabled.remove(tunnel_id)
            logger.info(f"Auto-recovery disabled for tunnel {tunnel_id}")

        # Cancel any pending recovery task
        self.cancel_recovery(tunnel_id)

    def is_recovery_enabled(self, tunnel_id: str) -> bool:
        """Check if auto-recovery is enabled for a tunnel.

        Args:
            tunnel_id: Tunnel ID to check

        Returns:
            True if auto-recovery is enabled
        """
        return tunnel_id in self._recovery_enabled

    async def attempt_recovery(
        self,
        tunnel_id: str,
        max_attempts: int | None = None,
        delay: int | None = None,
    ) -> bool:
        """Attempt to recover a disconnected tunnel.

        Args:
            tunnel_id: Tunnel ID to recover
            max_attempts: Maximum recovery attempts (default from config)
            delay: Base delay between attempts in seconds (default from config)

        Returns:
            True if recovery successful, False otherwise
        """
        if max_attempts is None:
            max_attempts = settings.tunnel.reconnect_attempts
        if delay is None:
            delay = settings.tunnel.reconnect_delay

        logger.info(
            f"Starting recovery for tunnel {tunnel_id} "
            f"(max_attempts={max_attempts}, delay={delay}s)"
        )

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Recovery attempt {attempt}/{max_attempts} for tunnel {tunnel_id}")

                # Stop existing process if any
                try:
                    self.tunnel_manager.stop_tunnel(tunnel_id)
                except Exception as e:
                    logger.warning(f"Error stopping tunnel during recovery: {e}")

                # Wait with exponential backoff
                wait_time = delay * (2 ** (attempt - 1))
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

                # Try to restart tunnel
                self.tunnel_manager.start_tunnel(tunnel_id)

                # Verify connection with health check
                if self.tunnel_manager.health_check(tunnel_id):
                    logger.info(
                        f"Recovery successful for tunnel {tunnel_id} "
                        f"after {attempt} attempt(s)"
                    )
                    return True
                else:
                    logger.warning(
                        f"Tunnel {tunnel_id} started but health check failed"
                    )

            except TunnelNotFound:
                logger.error(f"Tunnel {tunnel_id} not found, cannot recover")
                return False
            except TunnelCreationFailed as e:
                logger.warning(
                    f"Recovery attempt {attempt} failed for tunnel {tunnel_id}: {e.reason}"
                )
                if not e.retry_possible:
                    logger.error(
                        f"Recovery not possible for tunnel {tunnel_id}: {e.reason}"
                    )
                    return False
            except Exception as e:
                logger.error(
                    f"Unexpected error during recovery attempt {attempt} "
                    f"for tunnel {tunnel_id}: {e}"
                )

        logger.error(
            f"Recovery failed for tunnel {tunnel_id} after {max_attempts} attempts"
        )
        return False

    def schedule_recovery(self, tunnel_id: str) -> None:
        """Schedule asynchronous recovery for a tunnel.

        Args:
            tunnel_id: Tunnel ID to schedule recovery for
        """
        # Cancel existing recovery task if any
        self.cancel_recovery(tunnel_id)

        # Create new recovery task
        task = asyncio.create_task(self._recovery_wrapper(tunnel_id))
        self._recovery_tasks[tunnel_id] = task
        logger.info(f"Scheduled recovery task for tunnel {tunnel_id}")

    async def _recovery_wrapper(self, tunnel_id: str) -> None:
        """Wrapper for recovery task with cleanup.

        Args:
            tunnel_id: Tunnel ID to recover
        """
        try:
            success = await self.attempt_recovery(tunnel_id)
            if success:
                logger.info(f"Recovery task completed successfully for tunnel {tunnel_id}")
            else:
                logger.error(f"Recovery task failed for tunnel {tunnel_id}")
        except Exception as e:
            logger.error(f"Recovery task error for tunnel {tunnel_id}: {e}")
        finally:
            # Clean up task reference
            if tunnel_id in self._recovery_tasks:
                del self._recovery_tasks[tunnel_id]

    def cancel_recovery(self, tunnel_id: str) -> None:
        """Cancel pending recovery task for a tunnel.

        Args:
            tunnel_id: Tunnel ID to cancel recovery for
        """
        if tunnel_id in self._recovery_tasks:
            task = self._recovery_tasks[tunnel_id]
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled recovery task for tunnel {tunnel_id}")
            del self._recovery_tasks[tunnel_id]

    def get_recovery_status(self, tunnel_id: str) -> dict[str, bool]:
        """Get recovery status for a tunnel.

        Args:
            tunnel_id: Tunnel ID to check

        Returns:
            Dictionary with recovery status information
        """
        return {
            "enabled": tunnel_id in self._recovery_enabled,
            "in_progress": tunnel_id in self._recovery_tasks,
        }

    async def shutdown(self) -> None:
        """Shutdown recovery handler and cancel all pending tasks."""
        logger.info("Shutting down tunnel recovery handler")

        # Cancel all pending recovery tasks
        for tunnel_id in list(self._recovery_tasks.keys()):
            self.cancel_recovery(tunnel_id)

        # Wait for all tasks to complete
        if self._recovery_tasks:
            await asyncio.gather(*self._recovery_tasks.values(), return_exceptions=True)

        self._recovery_enabled.clear()
        logger.info("Tunnel recovery handler shutdown complete")
