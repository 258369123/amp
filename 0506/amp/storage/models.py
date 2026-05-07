"""Pydantic models for AMP."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TunnelType(str, Enum):
    """Tunnel type enumeration."""
    CHISEL = "chisel"
    LIGOLO = "ligolo"
    SSH = "ssh"


class TunnelStatus(str, Enum):
    """Tunnel status enumeration."""
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    STOPPED = "stopped"


class ShellType(str, Enum):
    """Shell type enumeration."""
    REVERSE = "reverse"
    BIND = "bind"
    SSH = "ssh"


class OSType(str, Enum):
    """Operating system type."""
    LINUX = "linux"
    WINDOWS = "windows"


class ShellProgram(str, Enum):
    """Shell program enumeration."""
    BASH = "bash"
    SH = "sh"
    POWERSHELL = "powershell"
    CMD = "cmd"


class ShellStatus(str, Enum):
    """Shell status enumeration."""
    ACTIVE = "active"
    DEAD = "dead"
    ZOMBIE = "zombie"


class PrivilegeLevel(str, Enum):
    """Privilege level enumeration."""
    USER = "user"
    ROOT = "root"
    SYSTEM = "system"


class OperationType(str, Enum):
    """Operation type enumeration."""
    COMMAND = "command"
    SCAN = "scan"
    UPLOAD = "upload"
    DOWNLOAD = "download"


class SegmentType(str, Enum):
    """Network segment type."""
    EXTERNAL = "external"
    DMZ = "dmz"
    INTERNAL = "internal"
    DOMAIN = "domain"


class TunnelModel(BaseModel):
    """Tunnel data model."""
    id: str
    name: str
    tunnel_type: TunnelType
    status: TunnelStatus
    local_host: str
    local_port: int
    remote_host: str
    remote_port: int
    parent_tunnel_id: str | None = None
    process_pid: int | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_heartbeat: datetime | None = None

    class Config:
        from_attributes = True


class ShellModel(BaseModel):
    """Shell session data model."""
    id: str
    name: str
    shell_type: ShellType
    os_type: OSType
    shell_program: ShellProgram
    status: ShellStatus
    tunnel_id: str | None = None
    target_host: str
    target_port: int | None = None
    tmux_session: str | None = None
    working_directory: str | None = None
    privilege_level: PrivilegeLevel
    environment: dict[str, str] | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_activity: datetime | None = None

    class Config:
        from_attributes = True


class OperationModel(BaseModel):
    """Operation history data model."""
    id: str
    operation_type: OperationType
    shell_id: str | None = None
    command: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    success: bool
    extra_data: dict[str, Any] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class NetworkSegmentModel(BaseModel):
    """Network segment data model."""
    id: str
    name: str
    cidr: str
    segment_type: SegmentType
    parent_segment_id: str | None = None
    extra_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Request/Response models for API

class CreateTunnelRequest(BaseModel):
    """Request to create a tunnel."""
    name: str
    tunnel_type: TunnelType
    local_host: str = "127.0.0.1"
    local_port: int
    remote_host: str
    remote_port: int
    parent_tunnel_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class CreateShellRequest(BaseModel):
    """Request to create a shell."""
    name: str
    shell_type: ShellType
    os_type: OSType
    shell_program: ShellProgram
    tunnel_id: str | None = None
    target_host: str
    target_port: int | None = None
    use_tmux: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class ExecuteCommandRequest(BaseModel):
    """Request to execute a command."""
    shell_id: str
    command: str
    timeout: int = 30


class ExecuteCommandResponse(BaseModel):
    """Response from command execution."""
    operation_id: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    success: bool
