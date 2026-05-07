"""Prompt formatting utilities for context engine."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PromptFormatter:
    """Format operations, tunnels, and shells for prompt inclusion."""

    @staticmethod
    def format_operation(operation: dict[str, Any]) -> str:
        """Format a single operation for prompt.

        Args:
            operation: Operation dict with metadata

        Returns:
            Formatted operation string
        """
        try:
            metadata = operation.get("metadata", {})
            command = metadata.get("command", "")
            output_preview = metadata.get("output_preview", "")
            timestamp = metadata.get("timestamp", "")
            shell_id = metadata.get("shell_id", "")
            relevance = operation.get("relevance_score", 0.0)

            # Format timestamp
            time_str = ""
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    time_str = timestamp

            # Build formatted string
            lines = []
            lines.append(f"Command: {command}")
            if output_preview:
                lines.append(f"Output: {output_preview}")
            if time_str:
                lines.append(f"Time: {time_str}")
            if shell_id:
                lines.append(f"Shell: {shell_id}")
            lines.append(f"Relevance: {relevance:.2f}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to format operation: {e}")
            return "Error formatting operation"

    @staticmethod
    def format_operations(operations: list[dict[str, Any]]) -> str:
        """Format multiple operations for prompt.

        Args:
            operations: List of operation dicts

        Returns:
            Formatted operations string
        """
        if not operations:
            return "No recent operations"

        formatted = []
        for i, op in enumerate(operations, 1):
            formatted.append(f"## Operation {i}")
            formatted.append(PromptFormatter.format_operation(op))
            formatted.append("")  # Blank line between operations

        return "\n".join(formatted)

    @staticmethod
    def format_tunnel(tunnel: dict[str, Any]) -> str:
        """Format a single tunnel for prompt.

        Args:
            tunnel: Tunnel dict with tunnel info

        Returns:
            Formatted tunnel string
        """
        try:
            tunnel_id = tunnel.get("id", "")
            name = tunnel.get("name", "")
            tunnel_type = tunnel.get("tunnel_type", "")
            status = tunnel.get("status", "")
            local = f"{tunnel.get('local_host', '')}:{tunnel.get('local_port', '')}"
            remote = f"{tunnel.get('remote_host', '')}:{tunnel.get('remote_port', '')}"
            parent_id = tunnel.get("parent_tunnel_id")

            lines = [
                f"- {name} ({tunnel_id})",
                f"  Type: {tunnel_type}",
                f"  Status: {status}",
                f"  Local: {local}",
                f"  Remote: {remote}",
            ]

            if parent_id:
                lines.append(f"  Parent: {parent_id}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to format tunnel: {e}")
            return "Error formatting tunnel"

    @staticmethod
    def format_tunnels(tunnels: list[dict[str, Any]]) -> str:
        """Format multiple tunnels for prompt.

        Args:
            tunnels: List of tunnel dicts

        Returns:
            Formatted tunnels string
        """
        if not tunnels:
            return "No active tunnels"

        formatted = []
        for tunnel in tunnels:
            formatted.append(PromptFormatter.format_tunnel(tunnel))
            formatted.append("")  # Blank line between tunnels

        return "\n".join(formatted)

    @staticmethod
    def format_shell(shell: dict[str, Any]) -> str:
        """Format a single shell for prompt.

        Args:
            shell: Shell dict with shell info

        Returns:
            Formatted shell string
        """
        try:
            shell_id = shell.get("id", "")
            name = shell.get("name", "")
            shell_type = shell.get("shell_type", "")
            os_type = shell.get("os_type", "")
            status = shell.get("status", "")
            target = f"{shell.get('target_host', '')}:{shell.get('target_port', '')}"
            tunnel_id = shell.get("tunnel_id")
            working_dir = shell.get("working_directory", "")
            privilege = shell.get("privilege_level", "")

            lines = [
                f"- {name} ({shell_id})",
                f"  Type: {shell_type} ({os_type})",
                f"  Status: {status}",
                f"  Target: {target}",
            ]

            if tunnel_id:
                lines.append(f"  Tunnel: {tunnel_id}")
            if working_dir:
                lines.append(f"  Working Dir: {working_dir}")
            if privilege:
                lines.append(f"  Privilege: {privilege}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to format shell: {e}")
            return "Error formatting shell"

    @staticmethod
    def format_shells(shells: list[dict[str, Any]]) -> str:
        """Format multiple shells for prompt.

        Args:
            shells: List of shell dicts

        Returns:
            Formatted shells string
        """
        if not shells:
            return "No active shells"

        formatted = []
        for shell in shells:
            formatted.append(PromptFormatter.format_shell(shell))
            formatted.append("")  # Blank line between shells

        return "\n".join(formatted)

    @staticmethod
    def format_topology(tunnels: list[dict[str, Any]]) -> str:
        """Format network topology as Mermaid diagram.

        Args:
            tunnels: List of tunnel dicts

        Returns:
            Mermaid diagram string
        """
        if not tunnels:
            return "```mermaid\ngraph LR\n  Attacker[Attacker]\n```"

        try:
            lines = ["```mermaid", "graph LR", "  Attacker[Attacker]"]

            # Build tunnel graph
            for tunnel in tunnels:
                tunnel_id = tunnel.get("id", "")
                name = tunnel.get("name", "")
                parent_id = tunnel.get("parent_tunnel_id")
                status = tunnel.get("status", "")

                # Sanitize name for Mermaid (remove special chars)
                safe_name = name.replace("[", "").replace("]", "").replace("(", "").replace(")", "")

                # Choose node style based on status
                if status == "active":
                    node_label = f"{safe_name}"
                else:
                    node_label = f"{safe_name} (inactive)"

                # Create edge
                if parent_id is None:
                    # Root tunnel connects to attacker
                    lines.append(f"  Attacker --> T{tunnel_id}[{node_label}]")
                else:
                    # Nested tunnel connects to parent
                    lines.append(f"  T{parent_id} --> T{tunnel_id}[{node_label}]")

            lines.append("```")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to format topology: {e}")
            return "```mermaid\ngraph LR\n  Attacker[Attacker]\n  Error[Error generating topology]\n```"
