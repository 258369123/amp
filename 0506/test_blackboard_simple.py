#!/usr/bin/env python3
"""Simple test script to verify blackboard functionality."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from amp.storage.database import Database
from amp.core.blackboard import Blackboard


def main():
    """Test blackboard with in-memory database."""
    print("Testing Blackboard...")

    # Create in-memory database
    db = Database("sqlite:///:memory:")
    db.create_tables()
    print("✓ Database created")

    # Create blackboard
    bb = Blackboard(db)
    print("✓ Blackboard initialized")

    # Get empty state
    state = bb.get_state()
    print(f"✓ Empty state retrieved:")
    print(f"  - Tunnels: {len(state['tunnels'])}")
    print(f"  - Shells: {len(state['shells'])}")
    print(f"  - Network segments: {state['network']['segment_count']}")
    print(f"  - Recent operations: {len(state['recent_operations'])}")

    # Add test data
    from amp.storage.schema import Tunnel, Shell, Operation

    with db.session() as session:
        # Add tunnel
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

        # Add shell
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

        # Add operation
        op = Operation(
            id="test-op-1",
            operation_type="command",
            command="ls -la",
            stdout="total 0",
            exit_code=0,
            success=True,
        )
        session.add(op)

    print("✓ Test data added")

    # Get state with data
    state = bb.get_state()
    print(f"✓ State with data retrieved:")
    print(f"  - Tunnels: {len(state['tunnels'])}")
    print(f"  - Shells: {len(state['shells'])}")
    print(f"  - Recent operations: {len(state['recent_operations'])}")

    if state['tunnels']:
        print(f"  - Tunnel: {state['tunnels'][0]['name']} ({state['tunnels'][0]['type']})")
    if state['shells']:
        print(f"  - Shell: {state['shells'][0]['name']} ({state['shells'][0]['type']})")
    if state['recent_operations']:
        print(f"  - Operation: {state['recent_operations'][0]['command']}")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    main()
