"""Unit tests for storage layer."""


import pytest

from amp.exceptions import TunnelNotFound
from amp.storage.database import Database
from amp.storage.models import (
    OperationType,
    OSType,
    PrivilegeLevel,
    SegmentType,
    ShellProgram,
    ShellStatus,
    ShellType,
    TunnelStatus,
    TunnelType,
)
from amp.storage.repository import (
    NetworkSegmentRepository,
    OperationRepository,
    ShellRepository,
    TunnelRepository,
)


@pytest.fixture
def db():
    """Create in-memory database for testing."""
    database = Database("sqlite:///:memory:")
    database.create_tables()
    return database


@pytest.fixture
def tunnel_repo(db):
    """Create tunnel repository."""
    with db.session() as session:
        yield TunnelRepository(session)


@pytest.fixture
def shell_repo(db):
    """Create shell repository."""
    with db.session() as session:
        yield ShellRepository(session)


@pytest.fixture
def operation_repo(db):
    """Create operation repository."""
    with db.session() as session:
        yield OperationRepository(session)


@pytest.fixture
def segment_repo(db):
    """Create network segment repository."""
    with db.session() as session:
        yield NetworkSegmentRepository(session)


class TestTunnelRepository:
    """Test tunnel repository."""

    def test_create_tunnel(self, db):
        """Test creating a tunnel."""
        with db.session() as session:
            repo = TunnelRepository(session)
            tunnel = repo.create({
                "name": "test-tunnel",
                "tunnel_type": TunnelType.CHISEL.value,
                "status": TunnelStatus.ACTIVE.value,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "192.168.1.100",
                "remote_port": 22,
                "config": {},
            })

            assert tunnel.id is not None
            assert tunnel.name == "test-tunnel"
            assert tunnel.tunnel_type == TunnelType.CHISEL
            assert tunnel.status == TunnelStatus.ACTIVE

    def test_get_tunnel(self, db):
        """Test getting a tunnel by ID."""
        with db.session() as session:
            repo = TunnelRepository(session)
            created = repo.create({
                "name": "test-tunnel",
                "tunnel_type": TunnelType.CHISEL.value,
                "status": TunnelStatus.ACTIVE.value,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "192.168.1.100",
                "remote_port": 22,
                "config": {},
            })

            retrieved = repo.get(created.id)
            assert retrieved is not None
            assert retrieved.id == created.id
            assert retrieved.name == created.name

    def test_get_nonexistent_tunnel(self, db):
        """Test getting a nonexistent tunnel."""
        with db.session() as session:
            repo = TunnelRepository(session)
            tunnel = repo.get("nonexistent-id")
            assert tunnel is None

    def test_get_or_raise(self, db):
        """Test get_or_raise with nonexistent tunnel."""
        with db.session() as session:
            repo = TunnelRepository(session)
            with pytest.raises(TunnelNotFound):
                repo.get_or_raise("nonexistent-id")

    def test_list_active_tunnels(self, db):
        """Test listing active tunnels."""
        with db.session() as session:
            repo = TunnelRepository(session)

            # Create active tunnel
            repo.create({
                "name": "active-tunnel",
                "tunnel_type": TunnelType.CHISEL.value,
                "status": TunnelStatus.ACTIVE.value,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "192.168.1.100",
                "remote_port": 22,
                "config": {},
            })

            # Create stopped tunnel
            repo.create({
                "name": "stopped-tunnel",
                "tunnel_type": TunnelType.CHISEL.value,
                "status": TunnelStatus.STOPPED.value,
                "local_host": "127.0.0.1",
                "local_port": 8081,
                "remote_host": "192.168.1.101",
                "remote_port": 22,
                "config": {},
            })

            active = repo.list_active()
            assert len(active) == 1
            assert active[0].name == "active-tunnel"

    def test_update_status(self, db):
        """Test updating tunnel status."""
        with db.session() as session:
            repo = TunnelRepository(session)
            tunnel = repo.create({
                "name": "test-tunnel",
                "tunnel_type": TunnelType.CHISEL.value,
                "status": TunnelStatus.ACTIVE.value,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "192.168.1.100",
                "remote_port": 22,
                "config": {},
            })

            updated = repo.update_status(tunnel.id, TunnelStatus.DISCONNECTED)
            assert updated.status == TunnelStatus.DISCONNECTED

    def test_update_heartbeat(self, db):
        """Test updating tunnel heartbeat."""
        with db.session() as session:
            repo = TunnelRepository(session)
            tunnel = repo.create({
                "name": "test-tunnel",
                "tunnel_type": TunnelType.CHISEL.value,
                "status": TunnelStatus.ACTIVE.value,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "192.168.1.100",
                "remote_port": 22,
                "config": {},
            })

            assert tunnel.last_heartbeat is None
            updated = repo.update_heartbeat(tunnel.id)
            assert updated.last_heartbeat is not None

    def test_delete_tunnel(self, db):
        """Test deleting a tunnel."""
        with db.session() as session:
            repo = TunnelRepository(session)
            tunnel = repo.create({
                "name": "test-tunnel",
                "tunnel_type": TunnelType.CHISEL.value,
                "status": TunnelStatus.ACTIVE.value,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "192.168.1.100",
                "remote_port": 22,
                "config": {},
            })

            repo.delete(tunnel.id)
            deleted = repo.get(tunnel.id)
            assert deleted is None

    def test_nested_tunnels(self, db):
        """Test nested tunnel relationships."""
        with db.session() as session:
            repo = TunnelRepository(session)

            # Create parent tunnel
            parent = repo.create({
                "name": "parent-tunnel",
                "tunnel_type": TunnelType.CHISEL.value,
                "status": TunnelStatus.ACTIVE.value,
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "192.168.1.100",
                "remote_port": 22,
                "config": {},
            })

            # Create child tunnel
            child = repo.create({
                "name": "child-tunnel",
                "tunnel_type": TunnelType.CHISEL.value,
                "status": TunnelStatus.ACTIVE.value,
                "local_host": "127.0.0.1",
                "local_port": 8081,
                "remote_host": "10.0.0.100",
                "remote_port": 22,
                "parent_tunnel_id": parent.id,
                "config": {},
            })

            children = repo.get_children(parent.id)
            assert len(children) == 1
            assert children[0].id == child.id


class TestShellRepository:
    """Test shell repository."""

    def test_create_shell(self, db):
        """Test creating a shell."""
        with db.session() as session:
            repo = ShellRepository(session)
            shell = repo.create({
                "name": "test-shell",
                "shell_type": ShellType.REVERSE.value,
                "os_type": OSType.LINUX.value,
                "shell_program": ShellProgram.BASH.value,
                "status": ShellStatus.ACTIVE.value,
                "target_host": "192.168.1.100",
                "privilege_level": PrivilegeLevel.USER.value,
                "config": {},
            })

            assert shell.id is not None
            assert shell.name == "test-shell"
            assert shell.os_type == OSType.LINUX

    def test_update_working_directory(self, db):
        """Test updating shell working directory."""
        with db.session() as session:
            repo = ShellRepository(session)
            shell = repo.create({
                "name": "test-shell",
                "shell_type": ShellType.REVERSE.value,
                "os_type": OSType.LINUX.value,
                "shell_program": ShellProgram.BASH.value,
                "status": ShellStatus.ACTIVE.value,
                "target_host": "192.168.1.100",
                "privilege_level": PrivilegeLevel.USER.value,
                "config": {},
            })

            updated = repo.update_working_directory(shell.id, "/tmp")
            assert updated.working_directory == "/tmp"


class TestOperationRepository:
    """Test operation repository."""

    def test_create_operation(self, db):
        """Test creating an operation."""
        with db.session() as session:
            repo = OperationRepository(session)
            operation = repo.create({
                "operation_type": OperationType.COMMAND.value,
                "command": "ls -la",
                "stdout": "file1\nfile2",
                "stderr": "",
                "exit_code": 0,
                "duration_ms": 100,
                "success": True,
            })

            assert operation.id is not None
            assert operation.command == "ls -la"
            assert operation.success is True

    def test_list_recent_operations(self, db):
        """Test listing recent operations."""
        with db.session() as session:
            repo = OperationRepository(session)

            # Create multiple operations
            for i in range(5):
                repo.create({
                    "operation_type": OperationType.COMMAND.value,
                    "command": f"command-{i}",
                    "success": True,
                })

            recent = repo.list_recent(limit=3)
            assert len(recent) == 3


class TestNetworkSegmentRepository:
    """Test network segment repository."""

    def test_create_segment(self, db):
        """Test creating a network segment."""
        with db.session() as session:
            repo = NetworkSegmentRepository(session)
            segment = repo.create({
                "name": "DMZ",
                "cidr": "192.168.1.0/24",
                "segment_type": SegmentType.DMZ.value,
            })

            assert segment.id is not None
            assert segment.name == "DMZ"
            assert segment.cidr == "192.168.1.0/24"
