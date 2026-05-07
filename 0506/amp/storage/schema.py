"""SQLAlchemy database schema for AMP."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Tunnel(Base):
    """Tunnel entity."""

    __tablename__ = "tunnels"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    tunnel_type = Column(String(50), nullable=False)  # chisel, ligolo, ssh
    status = Column(String(50), nullable=False)  # active, disconnected, stopped
    local_host = Column(String(255), nullable=False)
    local_port = Column(Integer, nullable=False)
    remote_host = Column(String(255), nullable=False)
    remote_port = Column(Integer, nullable=False)
    parent_tunnel_id = Column(String(36), ForeignKey("tunnels.id"), nullable=True)
    process_pid = Column(Integer, nullable=True)
    config = Column(JSON, nullable=False)  # tunnel-specific config
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_heartbeat = Column(DateTime, nullable=True)

    # Relationships
    parent = relationship("Tunnel", remote_side=[id], backref="children")
    shells = relationship("Shell", back_populates="tunnel", cascade="all, delete-orphan")


class Shell(Base):
    """Shell session entity."""

    __tablename__ = "shells"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    shell_type = Column(String(50), nullable=False)  # reverse, bind, ssh
    os_type = Column(String(50), nullable=False)  # linux, windows
    shell_program = Column(String(50), nullable=False)  # bash, sh, powershell, cmd
    status = Column(String(50), nullable=False)  # active, dead, zombie
    tunnel_id = Column(String(36), ForeignKey("tunnels.id"), nullable=True)
    target_host = Column(String(255), nullable=False)
    target_port = Column(Integer, nullable=True)
    tmux_session = Column(String(255), nullable=True)
    working_directory = Column(String(1024), nullable=True)
    privilege_level = Column(String(50), nullable=False)  # user, root, system
    environment = Column(JSON, nullable=True)  # env vars
    config = Column(JSON, nullable=False)  # shell-specific config
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity = Column(DateTime, nullable=True)

    # Relationships
    tunnel = relationship("Tunnel", back_populates="shells")
    operations = relationship("Operation", back_populates="shell", cascade="all, delete-orphan")


class Operation(Base):
    """Operation history entity."""

    __tablename__ = "operations"

    id = Column(String(36), primary_key=True)
    operation_type = Column(String(50), nullable=False)  # command, scan, upload, download
    shell_id = Column(String(36), ForeignKey("shells.id"), nullable=True)
    command = Column(Text, nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False)
    extra_data = Column(JSON, nullable=True)  # operation-specific metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    shell = relationship("Shell", back_populates="operations")


class NetworkSegment(Base):
    """Network segment entity."""

    __tablename__ = "network_segments"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    cidr = Column(String(50), nullable=False)
    segment_type = Column(String(50), nullable=False)  # external, dmz, internal, domain
    parent_segment_id = Column(String(36), ForeignKey("network_segments.id"), nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parent = relationship("NetworkSegment", remote_side=[id], backref="children")


def create_tables(engine):
    """Create all tables."""
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """Drop all tables."""
    Base.metadata.drop_all(engine)
