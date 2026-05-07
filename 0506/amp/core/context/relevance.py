"""Relevance scoring for operation history."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class RelevanceScorer:
    """Score operations by relevance combining similarity, recency, and context."""

    def __init__(
        self,
        similarity_weight: float = 0.5,
        recency_weight: float = 0.3,
        context_weight: float = 0.2,
    ):
        """Initialize relevance scorer.

        Args:
            similarity_weight: Weight for similarity score (0-1)
            recency_weight: Weight for recency score (0-1)
            context_weight: Weight for context match score (0-1)
        """
        self.similarity_weight = similarity_weight
        self.recency_weight = recency_weight
        self.context_weight = context_weight

        # Validate weights sum to 1.0
        total = similarity_weight + recency_weight + context_weight
        if not (0.99 <= total <= 1.01):  # Allow small floating point error
            logger.warning(
                f"Weights sum to {total}, not 1.0. "
                f"Normalizing: {similarity_weight}, {recency_weight}, {context_weight}"
            )
            self.similarity_weight = similarity_weight / total
            self.recency_weight = recency_weight / total
            self.context_weight = context_weight / total

    def score_operation(
        self,
        operation: dict[str, Any],
        query: str,
        context: dict[str, Any] | None = None,
    ) -> float:
        """Score a single operation by relevance.

        Args:
            operation: Operation dict with metadata and distance
            query: Query text (for logging)
            context: Context dict with shell_id, tunnel_id, etc.

        Returns:
            Relevance score (0-1, higher is more relevant)
        """
        try:
            # Similarity score (convert distance to similarity: 1 - distance)
            similarity = self.calculate_similarity_score(operation, query)

            # Recency score
            recency = self.calculate_recency_score(operation)

            # Context match score
            context_match = self.calculate_context_score(operation, context or {})

            # Combined relevance score
            relevance = (
                self.similarity_weight * similarity
                + self.recency_weight * recency
                + self.context_weight * context_match
            )

            return relevance

        except Exception as e:
            logger.error(f"Failed to score operation: {e}")
            return 0.0

    def score_operations(
        self,
        operations: list[dict[str, Any]],
        query: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Score all operations and add relevance scores.

        Args:
            operations: List of operations from vector store
            query: Query text
            context: Context dict with shell_id, tunnel_id, etc.

        Returns:
            List of operations with added relevance_score field
        """
        scored = []

        for op in operations:
            score = self.score_operation(op, query, context)
            scored.append({
                **op,
                "relevance_score": score,
            })

        # Sort by relevance (descending)
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)

        logger.debug(
            f"Scored {len(scored)} operations "
            f"(weights: sim={self.similarity_weight:.2f}, "
            f"rec={self.recency_weight:.2f}, ctx={self.context_weight:.2f})"
        )

        return scored

    def calculate_similarity_score(
        self,
        operation: dict[str, Any],
        query: str,
    ) -> float:
        """Calculate similarity score from vector distance.

        Args:
            operation: Operation dict with distance field
            query: Query text (for logging)

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        # ChromaDB returns cosine distance (0 = identical, 2 = opposite)
        # Convert to similarity: 1 - (distance / 2)
        distance = float(operation.get("distance", 1.0))
        similarity = max(0.0, 1.0 - (distance / 2.0))

        return similarity

    def calculate_recency_score(self, operation: dict[str, Any]) -> float:
        """Calculate recency score based on operation age.

        Args:
            operation: Operation dict with metadata containing timestamp

        Returns:
            Recency score (0-1, higher is more recent)
        """
        try:
            metadata = operation.get("metadata", {})
            timestamp_str = metadata.get("timestamp")

            if not timestamp_str:
                # No timestamp, assume old
                return 0.1

            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str)
            now = datetime.utcnow()

            # Calculate age in hours
            age_hours = (now - timestamp).total_seconds() / 3600

            # Decay function: 1.0 for recent, approaches 0 for old
            # Half-life of 24 hours
            recency = 1.0 / (1.0 + age_hours / 24.0)

            return recency

        except Exception as e:
            logger.debug(f"Failed to calculate recency: {e}")
            return 0.1

    def calculate_context_score(
        self,
        operation: dict[str, Any],
        context: dict[str, Any],
    ) -> float:
        """Calculate context match score.

        Args:
            operation: Operation dict with metadata
            context: Context dict with shell_id, tunnel_id, etc.

        Returns:
            Context match score (0-1, higher is better match)
        """
        if not context:
            # No context filter, all operations equally relevant
            return 0.5

        metadata = operation.get("metadata", {})
        score = 0.0
        matches = 0
        total_filters = 0

        # Check shell_id match
        if "shell_id" in context:
            total_filters += 1
            if metadata.get("shell_id") == context["shell_id"]:
                score += 1.0
                matches += 1
            else:
                score += 0.3  # Partial credit for different shell

        # Check tunnel_id match
        if "tunnel_id" in context:
            total_filters += 1
            if metadata.get("tunnel_id") == context["tunnel_id"]:
                score += 1.0
                matches += 1
            else:
                score += 0.3  # Partial credit for different tunnel

        # Check operation_type match
        if "operation_type" in context:
            total_filters += 1
            if metadata.get("operation_type") == context["operation_type"]:
                score += 1.0
                matches += 1

        # Normalize by number of filters
        if total_filters > 0:
            return score / total_filters
        else:
            return 0.5
