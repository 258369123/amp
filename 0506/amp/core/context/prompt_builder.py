"""Prompt builder for generating dynamic prompts for Claude Code."""

import logging
from typing import Any

from amp.core.context.compression import ContextCompressor
from amp.core.context.formatter import PromptFormatter
from amp.core.context.relevance import RelevanceScorer
from amp.core.context.vector_store import VectorStore

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Build dynamic prompts for Claude Code with progressive disclosure."""

    def __init__(
        self,
        vector_store: VectorStore,
        tunnel_manager: Any,
        shell_manager: Any,
        max_tokens: int = 8000,
        similarity_weight: float = 0.5,
        recency_weight: float = 0.3,
        context_weight: float = 0.2,
        relevance_threshold: float = 0.3,
    ):
        """Initialize prompt builder.

        Args:
            vector_store: VectorStore instance for operation history
            tunnel_manager: TunnelManager instance
            shell_manager: ShellManager instance
            max_tokens: Maximum token budget for prompt
            similarity_weight: Weight for similarity in relevance scoring
            recency_weight: Weight for recency in relevance scoring
            context_weight: Weight for context match in relevance scoring
            relevance_threshold: Minimum relevance score for inclusion
        """
        self.vector_store = vector_store
        self.tunnel_manager = tunnel_manager
        self.shell_manager = shell_manager
        self.max_tokens = max_tokens
        self.relevance_threshold = relevance_threshold

        # Initialize components
        self.relevance_scorer = RelevanceScorer(
            similarity_weight=similarity_weight,
            recency_weight=recency_weight,
            context_weight=context_weight,
        )
        self.compressor = ContextCompressor(
            max_tokens=max_tokens,
            threshold=relevance_threshold,
        )
        self.formatter = PromptFormatter()

    def build_prompt(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        include_topology: bool = True,
        include_tunnels: bool = True,
        include_shells: bool = True,
        include_operations: bool = True,
        max_operations: int = 20,
    ) -> str:
        """Build complete prompt for Claude Code.

        Args:
            query: Current task/query
            context: Context dict with shell_id, tunnel_id, etc.
            include_topology: Include network topology diagram
            include_tunnels: Include active tunnels list
            include_shells: Include active shells list
            include_operations: Include relevant operation history
            max_operations: Maximum number of operations to include

        Returns:
            Formatted prompt string
        """
        try:
            logger.info(f"Building prompt for query: {query[:100]}...")

            sections = []

            # Section 1: Current Task
            sections.append("# Current Task")
            sections.append(query)
            sections.append("")

            # Section 2: Network Topology
            if include_topology:
                tunnels = self.get_active_tunnels(context)
                topology = self.format_network_topology(tunnels)
                sections.append("# Network Topology")
                sections.append(topology)
                sections.append("")

            # Section 3: Active Tunnels
            if include_tunnels:
                tunnels = self.get_active_tunnels(context)
                tunnels_str = self.formatter.format_tunnels(tunnels)
                sections.append("# Active Tunnels")
                sections.append(tunnels_str)
                sections.append("")

            # Section 4: Active Shells
            if include_shells:
                shells = self.get_active_shells(context)
                shells_str = self.formatter.format_shells(shells)
                sections.append("# Active Shells")
                sections.append(shells_str)
                sections.append("")

            # Section 5: Recent Operations
            if include_operations:
                operations = self.get_relevant_operations(
                    query, context, limit=max_operations
                )
                operations_str = self.formatter.format_operations(operations)
                sections.append("# Recent Operations")
                sections.append(operations_str)
                sections.append("")

            # Section 6: Context Summary
            prompt = "\n".join(sections)
            token_count = self.estimate_prompt_tokens(prompt)
            stats = self.get_context_stats(context)

            sections.append("# Context")
            sections.append(f"- Total operations: {stats['total_operations']}")
            sections.append(f"- Active tunnels: {stats['active_tunnels']}")
            sections.append(f"- Active shells: {stats['active_shells']}")
            sections.append(f"- Tokens used: {token_count}/{self.max_tokens}")
            sections.append("")

            prompt = "\n".join(sections)

            logger.info(
                f"Built prompt: {token_count} tokens, "
                f"{stats['total_operations']} operations, "
                f"{stats['active_tunnels']} tunnels, "
                f"{stats['active_shells']} shells"
            )

            return prompt

        except Exception as e:
            logger.error(f"Failed to build prompt: {e}")
            # Return minimal prompt on failure
            return f"# Current Task\n{query}\n\n# Error\nFailed to build full context: {e}\n"

    def get_relevant_operations(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get relevant operations for the query.

        Args:
            query: Query text
            context: Context dict with shell_id, tunnel_id, etc.
            limit: Maximum number of operations to return

        Returns:
            List of relevant operations with scores
        """
        try:
            # Search vector store for similar operations
            all_ops = self.vector_store.search_by_command(query, top_k=100)

            if not all_ops:
                logger.debug("No operations found in vector store")
                return []

            # Score operations by relevance
            scored_ops = self.relevance_scorer.score_operations(
                all_ops, query, context
            )

            # Compress to fit token budget
            compressed_ops = self.compressor.compress_operations(scored_ops, query)

            # Limit to max operations
            selected_ops = compressed_ops[:limit]

            logger.debug(
                f"Selected {len(selected_ops)} operations "
                f"(from {len(all_ops)} candidates)"
            )

            return selected_ops

        except Exception as e:
            logger.error(f"Failed to get relevant operations: {e}")
            return []

    def get_active_tunnels(
        self,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get active tunnels, optionally filtered by context.

        Args:
            context: Context dict with tunnel_id filter

        Returns:
            List of active tunnel dicts
        """
        try:
            # Get all active tunnels from tunnel manager
            with self.tunnel_manager.database.session() as session:
                from amp.storage.repository import TunnelRepository
                repo = TunnelRepository(session)
                tunnels = repo.list_active()

            # Convert to dicts
            tunnel_dicts = []
            for tunnel in tunnels:
                tunnel_dicts.append({
                    "id": tunnel.id,
                    "name": tunnel.name,
                    "tunnel_type": tunnel.tunnel_type,
                    "status": tunnel.status,
                    "local_host": tunnel.local_host,
                    "local_port": tunnel.local_port,
                    "remote_host": tunnel.remote_host,
                    "remote_port": tunnel.remote_port,
                    "parent_tunnel_id": tunnel.parent_tunnel_id,
                })

            # Filter by context if specified
            if context and "tunnel_id" in context:
                tunnel_id = context["tunnel_id"]
                tunnel_dicts = [t for t in tunnel_dicts if t["id"] == tunnel_id]

            logger.debug(f"Found {len(tunnel_dicts)} active tunnels")
            return tunnel_dicts

        except Exception as e:
            logger.error(f"Failed to get active tunnels: {e}")
            return []

    def get_active_shells(
        self,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get active shells, optionally filtered by context.

        Args:
            context: Context dict with shell_id filter

        Returns:
            List of active shell dicts
        """
        try:
            # Get all active shells from shell manager
            with self.shell_manager.database.session() as session:
                from amp.storage.repository import ShellRepository
                repo = ShellRepository(session)
                shells = repo.list_active()

            # Convert to dicts
            shell_dicts = []
            for shell in shells:
                shell_dicts.append({
                    "id": shell.id,
                    "name": shell.name,
                    "shell_type": shell.shell_type,
                    "os_type": shell.os_type,
                    "status": shell.status,
                    "target_host": shell.target_host,
                    "target_port": shell.target_port,
                    "tunnel_id": shell.tunnel_id,
                    "working_directory": shell.working_directory,
                    "privilege_level": shell.privilege_level,
                })

            # Filter by context if specified
            if context and "shell_id" in context:
                shell_id = context["shell_id"]
                shell_dicts = [s for s in shell_dicts if s["id"] == shell_id]

            logger.debug(f"Found {len(shell_dicts)} active shells")
            return shell_dicts

        except Exception as e:
            logger.error(f"Failed to get active shells: {e}")
            return []

    def format_network_topology(
        self,
        tunnels: list[dict[str, Any]],
    ) -> str:
        """Format network topology as Mermaid diagram.

        Args:
            tunnels: List of tunnel dicts

        Returns:
            Mermaid diagram string
        """
        return self.formatter.format_topology(tunnels)

    def estimate_prompt_tokens(self, prompt: str) -> int:
        """Estimate token count for prompt.

        Args:
            prompt: Prompt text

        Returns:
            Estimated token count
        """
        return self.compressor.estimate_tokens(prompt)

    def get_context_stats(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get context statistics.

        Args:
            context: Context dict

        Returns:
            Dictionary with context stats
        """
        try:
            # Get vector store stats
            vector_stats = self.vector_store.get_collection_stats()
            total_operations = vector_stats.get("total_operations", 0)

            # Get active tunnels count
            tunnels = self.get_active_tunnels(context)
            active_tunnels = len(tunnels)

            # Get active shells count
            shells = self.get_active_shells(context)
            active_shells = len(shells)

            return {
                "total_operations": total_operations,
                "active_tunnels": active_tunnels,
                "active_shells": active_shells,
                "max_tokens": self.max_tokens,
                "relevance_threshold": self.relevance_threshold,
            }

        except Exception as e:
            logger.error(f"Failed to get context stats: {e}")
            return {
                "total_operations": 0,
                "active_tunnels": 0,
                "active_shells": 0,
                "max_tokens": self.max_tokens,
                "relevance_threshold": self.relevance_threshold,
            }
