"""Similarity search for operation history."""

import logging
from datetime import datetime
from typing import Any

from amp.core.context.vector_store import VectorStore

logger = logging.getLogger(__name__)


class SimilaritySearch:
    """Search for similar operations using vector similarity."""

    def __init__(self, vector_store: VectorStore):
        """Initialize similarity search.

        Args:
            vector_store: VectorStore instance
        """
        self.vector_store = vector_store

    def find_similar_commands(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Find operations with similar commands.

        Args:
            query: Command query text
            top_k: Maximum number of results
            threshold: Minimum similarity threshold (0-1, lower distance = higher similarity)

        Returns:
            List of similar operations with metadata
        """
        try:
            results = self.vector_store.search_by_command(query, top_k=top_k)

            # Filter by threshold (ChromaDB returns cosine distance, 0 = identical)
            filtered = [
                result for result in results
                if result["distance"] <= threshold
            ]

            logger.debug(
                f"Found {len(filtered)} similar commands (threshold={threshold})"
            )

            return filtered

        except Exception as e:
            logger.error(f"Failed to find similar commands: {e}")
            return []

    def find_similar_outputs(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Find operations with similar outputs.

        Args:
            query: Output query text
            top_k: Maximum number of results
            threshold: Minimum similarity threshold

        Returns:
            List of similar operations with metadata
        """
        try:
            results = self.vector_store.search_by_output(query, top_k=top_k)

            # Filter by threshold
            filtered = [
                result for result in results
                if result["distance"] <= threshold
            ]

            logger.debug(
                f"Found {len(filtered)} similar outputs (threshold={threshold})"
            )

            return filtered

        except Exception as e:
            logger.error(f"Failed to find similar outputs: {e}")
            return []

    def find_by_context(
        self,
        shell_id: str | None = None,
        tunnel_id: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Find operations by context (shell or tunnel).

        Args:
            shell_id: Filter by shell ID
            tunnel_id: Filter by tunnel ID
            top_k: Maximum number of results

        Returns:
            List of operations matching context
        """
        try:
            filters = {}
            if shell_id:
                filters["shell_id"] = shell_id
            if tunnel_id:
                filters["tunnel_id"] = tunnel_id

            if not filters:
                logger.warning("No context filters provided")
                return []

            results = self.vector_store.search_by_metadata(filters, top_k=top_k)

            logger.debug(
                f"Found {len(results)} operations for context: {filters}"
            )

            return results

        except Exception as e:
            logger.error(f"Failed to find by context: {e}")
            return []

    def rank_by_relevance(
        self,
        results: list[dict[str, Any]],
        query: str,
        recency_weight: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Rank results by relevance score combining similarity and recency.

        Args:
            results: Search results from vector store
            query: Original query (for logging)
            recency_weight: Weight for recency score (0-1)

        Returns:
            Ranked list of results with relevance scores
        """
        try:
            now = datetime.utcnow()
            ranked = []

            for result in results:
                # Similarity score (convert distance to similarity: 1 - distance)
                similarity = 1.0 - result["distance"]

                # Recency score
                recency = 0.0
                if "timestamp" in result["metadata"]:
                    try:
                        timestamp = datetime.fromisoformat(
                            result["metadata"]["timestamp"]
                        )
                        age_hours = (now - timestamp).total_seconds() / 3600
                        # Decay function: 1.0 for recent, approaches 0 for old
                        recency = 1.0 / (1.0 + age_hours / 24.0)
                    except Exception as e:
                        logger.debug(f"Failed to parse timestamp: {e}")

                # Combined relevance score
                relevance = (
                    (1.0 - recency_weight) * similarity +
                    recency_weight * recency
                )

                ranked.append({
                    **result,
                    "relevance_score": relevance,
                    "similarity_score": similarity,
                    "recency_score": recency,
                })

            # Sort by relevance (descending)
            ranked.sort(key=lambda x: x["relevance_score"], reverse=True)

            logger.debug(
                f"Ranked {len(ranked)} results by relevance "
                f"(recency_weight={recency_weight})"
            )

            return ranked

        except Exception as e:
            logger.error(f"Failed to rank by relevance: {e}")
            # Return original results if ranking fails
            return results
