"""Tests for Blackboard state management."""

import pytest
from datetime import datetime

from amp.core.blackboard import Blackboard
from amp.storage.database import Database
from amp.storage.schema import Operation, Shell, Tunnel, NetworkSegment


@pytest.fixture
def database():
    """Create in-memory test database."""
    db = Database("sqlite:///:memory:")
    db.create_tables()
    return db


@pytest.fixture
def blackboard(database):
    """Create blackboard instance."""
    return Blackboard(database)


def test_blackboard_empty_state(blackboard):
    """Test blackboard with empty database."""
    state = blackboard.get_state()

    assert state["tunnels"] == []
    assert state["shells"] == []
    assert state["network"]["segment_count"] == 0
    assert state["recent_operations"] == []


def test_blackboard_with_tunnels(blackboard, database):
    """Test blackboard with tunnels."""
    # Add test tunnel
    with database.session() as session:
        tunnel = Tunnel(
            id="test-tunnel-1",
            name="Test Tunnel",
            tunnel_type="chisel",
            status="active",
            local_host="127.0.0.1",
            local_port=8080,
            remote_host="192.168.1.1",
            remote_port=22,
            config={},
        )
        session.add(tunnel)

    state = blackboard.get_state()

    assert len(state["tunnels"]) == 1
    assert state["tunnels"][0]["name"] == "Test Tunnel"
    assert state["tunnels"][0]["type"] == "chisel"
    assert state["tunnels"][0]["status"] == "active"


def test_blackboard_with_shells(blackboard, database):
    """Test blackboard with shells."""
    # Add test shell
    with database.session() as session:
        shell = Shell(
            id="test-shell-1",
            name="Test Shell",
            shell_type="ssh",
            os_type="linux",
            shell_program="bash",
            status="active",
            target_host="192.168.1.1",
            privilege_level="user",
            config={},
        )
        session.add(shell)

    state = blackboard.get_state()

    assert len(state["shells"]) == 1
    assert state["shells"][0]["name"] == "Test Shell"
    assert state["shells"][0]["type"] == "ssh"
    assert state["shells"][0]["os"] == "linux"


def test_blackboard_with_operations(blackboard, database):
    """Test blackboard with operations."""
    # Add test operations
    with database.session() as session:
        for i in range(5):
            op = Operation(
                id=f"test-op-{i}",
                operation_type="command",
                command=f"ls -la /tmp/{i}",
                stdout=f"output {i}",
                exit_code=0,
                success=True,
            )
            session.add(op)

    state = blackboard.get_state()

    assert len(state["recent_operations"]) == 5
    assert state["recent_operations"][0]["command"] == "ls -la /tmp/4"  # Most recent first


def test_blackboard_operations_limit(blackboard, database):
    """Test blackboard respects operation limit."""
    # Add 30 operations
    with database.session() as session:
        for i in range(30):
            op = Operation(
                id=f"test-op-{i}",
                operation_type="command",
                command=f"command {i}",
                stdout=f"output {i}",
                exit_code=0,
                success=True,
            )
            session.add(op)

    state = blackboard.get_state()

    # Should only return 20 most recent
    assert len(state["recent_operations"]) == 20


def test_blackboard_with_network_segments(blackboard, database):
    """Test blackboard with network segments."""
    # Add test segments
    with database.session() as session:
        for i in range(3):
            segment = NetworkSegment(
                id=f"test-segment-{i}",
                name=f"Segment {i}",
                cidr=f"192.168.{i}.0/24",
                segment_type="internal",
            )
            session.add(segment)

    state = blackboard.get_state()

    assert state["network"]["segment_count"] == 3
    assert len(state["network"]["segments"]) == 3
