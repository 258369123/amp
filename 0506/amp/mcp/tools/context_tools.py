"""Context query tools for MCP - simplified with Blackboard pattern."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global blackboard instance (initialized by registry)
_blackboard = None


def set_context_components(
    blackboard: Any,
) -> None:
    """Set blackboard instance.

    Args:
        blackboard: Blackboard instance
    """
    global _blackboard
    _blackboard = blackboard


async def get_relevant_operations(
    query: str,
    shell_id: str | None = None,
    tunnel_id: str | None = None,
    limit: int = 10,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Get relevant operation history - simplified to recent operations.

    Args:
        query: Query text (ignored in simplified version)
        shell_id: Optional shell ID filter
        tunnel_id: Optional tunnel ID filter
        limit: Maximum number of operations to return
        threshold: Minimum similarity threshold (ignored in simplified version)

    Returns:
        Response dict with recent operations
    """
    try:
        if not _blackboard:
            return {
                "success": False,
                "error": "Blackboard not initialized",
                "error_type": "initialization_error",
            }

        # Get current state
        state = _blackboard.get_state()
        operations = state.get("recent_operations", [])

        # Simple filtering by shell_id if provided
        if shell_id:
            operations = [op for op in operations if op.get("shell_id") == shell_id]

        # Limit results
        operations = operations[:limit]

        logger.debug(f"Found {len(operations)} recent operations")

        return {
            "success": True,
            "data": {
                "operations": operations,
                "count": len(operations),
                "query": query,
            },
        }

    except Exception as e:
        logger.error(f"Unexpected error getting operations: {e}")
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
    """Build dynamic prompt with context - simplified with blackboard.

    Args:
        query: Current task/query
        shell_id: Optional shell ID for context (ignored)
        tunnel_id: Optional tunnel ID for context (ignored)
        include_topology: Include network topology (simplified)
        include_tunnels: Include active tunnels list
        include_shells: Include active shells list
        include_operations: Include recent operation history
        max_operations: Maximum number of operations to include

    Returns:
        Response dict with formatted prompt
    """
    try:
        if not _blackboard:
            return {
                "success": False,
                "error": "Blackboard not initialized",
                "error_type": "initialization_error",
            }

        # Get current state
        state = _blackboard.get_state()

        # Build prompt sections
        sections = []

        sections.append("Current AMP State:\n")

        if include_tunnels:
            tunnels = state.get("tunnels", [])
            sections.append(f"\nTunnels ({len(tunnels)}):")
            if tunnels:
                for t in tunnels:
                    sections.append(
                        f"  - {t['name']}: {t['type']} {t['local_port']} -> {t['remote']} [{t['status']}]"
                    )
            else:
                sections.append("  (none)")

        if include_shells:
            shells = state.get("shells", [])
            sections.append(f"\nShells ({len(shells)}):")
            if shells:
                for s in shells:
                    sections.append(
                        f"  - {s['name']}: {s['type']} {s['target']} ({s['os']}) [{s['status']}]"
                    )
            else:
                sections.append("  (none)")

        if include_topology:
            network = state.get("network", {})
            segment_count = network.get("segment_count", 0)
            sections.append(f"\nNetwork: {segment_count} segments")

        if include_operations:
            operations = state.get("recent_operations", [])[:max_operations]
            sections.append(f"\nRecent Operations ({len(operations)}):")
            if operations:
                for op in operations:
                    cmd = op.get("command", "")[:50]
                    output = op.get("output", "")[:50]
                    sections.append(f"  - {cmd}... -> {output}...")
            else:
                sections.append("  (none)")

        sections.append(f"\nQuery: {query}")

        prompt = "\n".join(sections)

        # Simple token estimation (4 chars per token)
        token_count = len(prompt) // 4

        logger.info(f"Built prompt: ~{token_count} tokens, {len(prompt)} chars")

        return {
            "success": True,
            "data": {
                "prompt": prompt,
                "token_count": token_count,
                "stats": {
                    "tunnels": len(state.get("tunnels", [])),
                    "shells": len(state.get("shells", [])),
                    "operations": len(state.get("recent_operations", [])),
                },
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
    """Compress context to fit token budget - simplified version.

    Args:
        operations: List of operations to compress
        query: Current query for relevance scoring (ignored)
        max_tokens: Maximum token budget
        threshold: Minimum relevance threshold (ignored)

    Returns:
        Response dict with compressed operations
    """
    try:
        # Simple compression: just truncate to fit token budget
        final_ops = []
        current_tokens = 0

        for op in operations:
            # Estimate tokens (4 chars per token)
            op_tokens = len(str(op)) // 4
            if current_tokens + op_tokens <= max_tokens:
                final_ops.append(op)
                current_tokens += op_tokens
            else:
                break

        logger.debug(
            f"Compressed {len(operations)} operations to {len(final_ops)} "
            f"(~{current_tokens} tokens)"
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
