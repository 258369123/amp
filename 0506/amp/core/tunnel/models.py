"""Data models for tunnel server management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TunnelServerType(str, Enum):
    """Tunnel server type enumeration."""
    CHISEL = "chisel"
    LIGOLO = "ligolo"


class SessionStatus(str, Enum):
    """Session status enumeration."""
    ACTIVE = "active"
    DISCONNECTED = "disconnected"


@dataclass
class ForwardStats:
    """Statistics for a port forward."""
    bytes_sent: int = 0
    bytes_received: int = 0
    connections: int = 0


@dataclass
class Forward:
    """Port forward configuration."""
    listen_addr: str
    target_addr: str
    protocol: str = "tcp"
    stats: ForwardStats = field(default_factory=ForwardStats)


@dataclass
class Route:
    """Network route configuration."""
    network: str  # CIDR notation (e.g., "10.0.0.0/24")
    interface: str  # TUN interface name


@dataclass
class SessionInfo:
    """Unified session information for tunnel servers."""
    session_id: str
    status: SessionStatus
    remote_addr: str
    connected_at: datetime
    forwards: list[Forward] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
