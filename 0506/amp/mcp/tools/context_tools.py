"""Context query tools for MCP."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global manager instances (initialized by registry)
_similarity_search = None
_prompt_builder = None
_context_compressor = None


def set_context_components(
    similarity_search: Any,
    prompt_builder: Any,
    context_compressor: Any,
) -> None:
    """Set context component instances.

    Args:
        similarity_search: SimilaritySearch instance
        prompt_builder: PromptBuilder instance
        context_compressor: ContextCompressor instance
    """
    global _similarity_search, _prompt_builder, _context_compressor
    _similarity_search = similarity_search
    _prompt_builder = prompt_builder
    _context_compressor = context_compressor


async def get_relevant_operations(
    query: str,
    shell_id: str | None = None,
    tunnel_id: str | None = None,
    limit: int = 10,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Get relevant operation history based on query.

    Args:
        query: Query text to search for
        shell_id: Optional shell ID filter
        tunnel_id: Optional tunnel ID filter
        limit: Maximum number of operations to return
        threshold: Minimum similarity threshold (0-1)

    Returns:
        Response dict with relevant operations
    """
    try:
        if not _similarity_search:
            return {
                "success": False,
                "error": "Similarity search not initialized",
                "error_type": "initialization_error",
            }

        # Build context filter
        context = {}
        if shell_id:
            context["shell_id"] = shell_id
        if tunnel_id:
            context["tunnel_id"] = tunnel_id

        # Search for similar commands
        results = _similarity_search.find_similar_commands(
            query=query,
            top_k=limit * 2,  # Get more candidates for ranking
            threshold=threshold,
        )

        # Rank by relevance
        ranked_results = _similarity_search.rank_by_relevance(
            results=results,
            query=query,
            recency_weight=0.3,
        )

        # Limit to requested count
        final_results = ranked_results[:limit]

        # Format results
        operations = []
        for result in final_results:
            operations.append({
                "operation_id": result.get("id"),
                "command": result.get("command"),
                "stdout": result.get("stdout", "")[:500],  # Truncate output
                "exit_code": result.get("exit_code"),
                "shell_id": result.get("metadata", {}).get("shell_id"),
                "tunnel_id": result.get("metadata", {}).get("tunnel_id"),
                "timestamp": result.get("metadata", {}).get("timestamp"),
                "relevance_score": result.get("relevance_score", 0.0),
                "similarity_score": result.get("similarity_score", 0.0),
                "recency_score": result.get("recency_score", 0.0),
            })

        logger.debug(f"Found {len(operations)} relevant operations for query: {query[:50]}...")

        return {
            "success": True,
            "data": {
                "operations": operations,
                "count": len(operations),
                "query": query,
            },
        }

    except Exception as e:
        logger.error(f"Unexpected error getting relevant operations: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def build_prompt(
    query: str,
    shell_id: str | None = None,
    tunnel_id: str | None = None,
    include_topology: bool = True,
    include_tunnels: bool = True,
    include_shells: bool = True,
    include_operations: bool = True,
    max_operations: int = 20,
) -> dict[str, Any]:
    """Build dynamic prompt with context for Claude Code.

    Args:
        query: Current task/query
        shell_id: Optional shell ID for context
        tunnel_id: Optional tunnel ID for context
        include_topology: Include network topology diagram
        include_tunnels: Include active tunnels list
        include_shells: Include active shells list
        include_operations: Include relevant operation history
        max_operations: Maximum number of operations to include

    Returns:
        Response dict with formatted prompt
    """
    try:
        if not _prompt_builder:
            return {
                "success": False,
                "error": "Prompt builder not initialized",
                "error_type": "initialization_error",
            }

        # Build context
        context = {}
        if shell_id:
            context["shell_id"] = shell_id
        if tunnel_id:
            context["tunnel_id"] = tunnel_id

        # Build prompt
        prompt = _prompt_builder.build_prompt(
            query=query,
            context=context,
            include_topology=include_topology,
            include_tunnels=include_tunnels,
            include_shells=include_shells,
            include_operations=include_operations,
            max_operations=max_operations,
        )

        # Get token count
        token_count = _prompt_builder.estimate_prompt_tokens(prompt)

        # Get context stats
        stats = _prompt_builder.get_context_stats(context)

        logger.info(f"Built prompt: {token_count} tokens, {len(prompt)} chars")

        return {
            "success": True,
            "data": {
                "prompt": prompt,
                "token_count": token_count,
                "stats": stats,
            },
        }

    except Exception as e:
        logger.error(f"Unexpected error building prompt: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }


async def compress_context(
    operations: list[dict[str, Any]],
    query: str,
    max_tokens: int = 4000,
    threshold: float = 0.3,
) -> dict[str, Any]:
    """Compress context to fit token budget.

    Args:
        operations: List of operations to compress
        query: Current query for relevance scoring
        max_tokens: Maximum token budget
        threshold: Minimum relevance threshold

    Returns:
        Response dict with compressed operations
    """
    try:
        if not _context_compressor:
            return {
                "success": False,
                "error": "Context compressor not initialized",
                "error_type": "initialization_error",
            }

        # Compress operations
        compressed = _context_compressor.compress_operations(
            operations=operations,
            query=query,
        )

        # Filter by threshold
        filtered = [
            op for op in compressed
            if op.get("relevance_score", 0.0) >= threshold
        ]

        # Truncate to fit token budget
        final_ops = []
        current_tokens = 0
        for op in filtered:
            op_tokens = _context_compressor.estimate_tokens(str(op))
            if current_tokens + op_tokens <= max_tokens:
                final_ops.append(op)
                current_tokens += op_tokens
            else:
                break

        logger.debug(
            f"Compressed {len(operations)} operations to {len(final_ops)} "
            f"({current_tokens} tokens)"
        )

        return {
            "success": True,
            "data": {
                "operations": final_ops,
                "original_count": len(operations),
                "compressed_count": len(final_ops),
                "token_count": current_tokens,
                "max_tokens": max_tokens,
            },
        }

    except Exception as e:
        logger.error(f"Unexpected error compressing context: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error",
        }
