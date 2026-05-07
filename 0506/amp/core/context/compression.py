"""Context compression for managing token budgets."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ContextCompressor:
    """Compress operation history to fit within token budgets."""

    def __init__(self, max_tokens: int = 8000, threshold: float = 0.7):
        """Initialize context compressor.

        Args:
            max_tokens: Maximum token budget
            threshold: Minimum relevance threshold for inclusion (0-1)
        """
        self.max_tokens = max_tokens
        self.threshold = threshold

    def compress_operations(
        self,
        operations: list[dict[str, Any]],
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """Compress operation list to fit token budget.

        Args:
            operations: List of operations with relevance scores
            query: Optional query context for logging

        Returns:
            Compressed list of operations
        """
        try:
            # Filter by relevance threshold
            filtered = self.filter_by_relevance(operations, self.threshold)

            # Select top operations within token budget
            selected = self.select_top_operations(filtered, self.max_tokens)

            logger.info(
                f"Compressed {len(operations)} operations to {len(selected)} "
                f"(threshold={self.threshold}, max_tokens={self.max_tokens})"
            )

            return selected

        except Exception as e:
            logger.error(f"Failed to compress operations: {e}")
            # Return empty list on failure to avoid context overflow
            return []

    def filter_by_relevance(
        self,
        operations: list[dict[str, Any]],
        threshold: float,
    ) -> list[dict[str, Any]]:
        """Filter operations by relevance score.

        Args:
            operations: List of operations with relevance scores
            threshold: Minimum relevance threshold

        Returns:
            Filtered list of operations
        """
        filtered = []

        for op in operations:
            # Check for relevance score (from SimilaritySearch.rank_by_relevance)
            relevance = op.get("relevance_score", 0.0)

            if relevance >= threshold:
                filtered.append(op)

        logger.debug(
            f"Filtered {len(operations)} operations to {len(filtered)} "
            f"(threshold={threshold})"
        )

        return filtered

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses rough approximation: ~4 characters per token.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        # Rough estimation: 4 characters per token
        # This is conservative for English text
        return len(text) // 4

    def select_top_operations(
        self,
        operations: list[dict[str, Any]],
        max_tokens: int,
    ) -> list[dict[str, Any]]:
        """Select top operations within token budget.

        Args:
            operations: List of operations (should be sorted by relevance)
            max_tokens: Maximum token budget

        Returns:
            Selected operations within budget
        """
        selected = []
        total_tokens = 0

        for op in operations:
            # Estimate tokens for this operation
            # Include command, output preview, and metadata
            metadata = op.get("metadata", {})
            command = metadata.get("command", "") if metadata else ""
            output_preview = metadata.get("output_preview", "") if metadata else ""
            document = op.get("document", "")

            # Use document if available, otherwise combine command + output
            text = document if document else f"{command}\n{output_preview}"
            op_tokens = self.estimate_tokens(text)

            # Check if adding this operation would exceed budget
            if total_tokens + op_tokens > max_tokens:
                logger.debug(
                    f"Stopping at {len(selected)} operations "
                    f"(would exceed budget: {total_tokens + op_tokens} > {max_tokens})"
                )
                break

            selected.append(op)
            total_tokens += op_tokens

        logger.debug(
            f"Selected {len(selected)} operations "
            f"(estimated tokens: {total_tokens}/{max_tokens})"
        )

        return selected

    def get_compression_stats(
        self,
        original: list[dict[str, Any]],
        compressed: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Get compression statistics.

        Args:
            original: Original operation list
            compressed: Compressed operation list

        Returns:
            Dictionary with compression stats
        """
        original_count = len(original)
        compressed_count = len(compressed)

        # Estimate tokens
        original_tokens = sum(
            self.estimate_tokens(op.get("document", ""))
            for op in original
        )
        compressed_tokens = sum(
            self.estimate_tokens(op.get("document", ""))
            for op in compressed
        )

        compression_ratio = (
            compressed_count / original_count if original_count > 0 else 0.0
        )

        return {
            "original_count": original_count,
            "compressed_count": compressed_count,
            "compression_ratio": compression_ratio,
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "token_budget": self.max_tokens,
            "threshold": self.threshold,
        }
