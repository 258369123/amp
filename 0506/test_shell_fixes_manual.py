#!/usr/bin/env python3
"""Test shell fixes - verify command execution and reverse shell payload."""

import asyncio
import socket
import subprocess
import time
from pathlib import Path

# Add project to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from amp.storage.database import Database
from amp.core.shell.manager import ShellManager
from amp.storage.models import ShellType, OSType, ShellProgram


def setup_test_shells():
    """Setup test shell targets."""
    print("=" * 60)
    print("Setting up test shell targets...")
    print("=" * 60)

    # Test 1: Simple shell
    print("\n[Test 1] Starting simple shell (socat + /bin/sh -i)")
    print("Command: socat TCP-LISTEN:45700,reuseaddr,fork EXEC:'/bin/sh -i'")
    print("Run this in another terminal, then press Enter...")
    input()

    # Test 2: Bash shell
    print("\n[Test 2] Starting bash shell (socat + /bin/bash -li)")
    print("Command: socat TCP-LISTEN:45701,reuseaddr,fork EXEC:'/bin/bash -li'")
    print("Run this in another terminal, then press Enter...")
    input()

    print("\n✓ Test shells ready!")


async def test_shell_fixes():
    """Test shell fixes."""
    print("\n" + "=" * 60)
    print("Testing Shell Fixes")
    print("=" * 60)

    # Initialize
    db = Database('sqlite:///amp_test.db')
    db.create_tables()
    manager = ShellManager(db)

    results = {
        "simple_shell": {"passed": False, "details": ""},
        "bash_shell": {"passed": False, "details": ""},
        "reverse_payload": {"passed": False, "details": ""},
        "side_effect": {"passed": False, "details": ""}
    }

    # Test 1: Simple shell with output
    print("\n" + "-" * 60)
    print("[Test 1] Simple Shell - Command Execution")
    print("-" * 60)

    try:
        print("Creating bind shell to 127.0.0.1:45700...")
        shell = manager.create_bind_shell(
            name="test-simple-shell",
            target_host="127.0.0.1",
            target_port=45700,
            os_type=OSType.LINUX,
            shell_program=ShellProgram.SH
        )
        print(f"✓ Shell created: {shell.id}")

        # Execute command
        print("\nExecuting: echo SIMPLE_OK; whoami; pwd")
        result = manager.execute_command(
            shell_id=shell.id,
            command="echo SIMPLE_OK; whoami; pwd",
            timeout=10
        )

        print(f"\nResult:")
        print(f"  Success: {result.command_success}")
        print(f"  Exit code: {result.exit_code}")
        print(f"  Stdout length: {len(result.stdout)}")
        print(f"  Stdout: {result.stdout[:200]}")

        if result.command_success and result.stdout.strip():
            results["simple_shell"]["passed"] = True
            results["simple_shell"]["details"] = f"Output: {result.stdout[:100]}"
            print("\n✅ PASSED: Command executed with output")
        else:
            results["simple_shell"]["details"] = f"No output or failed: {result.stdout}"
            print("\n❌ FAILED: No output or command failed")

        # Close shell
        manager.close_shell(shell.id)

    except Exception as e:
        results["simple_shell"]["details"] = str(e)
        print(f"\n❌ FAILED: {e}")

    # Test 2: Bash shell
    print("\n" + "-" * 60)
    print("[Test 2] Bash Shell - Complex Prompt")
    print("-" * 60)

    try:
        print("Creating bind shell to 127.0.0.1:45701...")
        shell = manager.create_bind_shell(
            name="test-bash-shell",
            target_host="127.0.0.1",
            target_port=45701,
            os_type=OSType.LINUX,
            shell_program=ShellProgram.BASH
        )
        print(f"✓ Shell created: {shell.id}")

        # Execute command
        print("\nExecuting: echo BASH_OK; whoami; pwd")
        result = manager.execute_command(
            shell_id=shell.id,
            command="echo BASH_OK; whoami; pwd",
            timeout=10
        )

        print(f"\nResult:")
        print(f"  Success: {result.command_success}")
        print(f"  Exit code: {result.exit_code}")
        print(f"  Stdout: {result.stdout[:200]}")

        if result.command_success and result.stdout.strip():
            results["bash_shell"]["passed"] = True
            results["bash_shell"]["details"] = f"Output: {result.stdout[:100]}"
            print("\n✅ PASSED: Bash shell works")
        else:
            results["bash_shell"]["details"] = f"Failed: {result.stdout}"
            print("\n❌ FAILED: Bash shell failed")

        # Close shell
        manager.close_shell(shell.id)

    except Exception as e:
        results["bash_shell"]["details"] = str(e)
        print(f"\n❌ FAILED: {e}")

    # Test 3: Reverse shell payload
    print("\n" + "-" * 60)
    print("[Test 3] Reverse Shell Payload")
    print("-" * 60)

    try:
        print("Creating reverse shell...")
        shell, payload = manager.create_reverse_shell(
            name="test-reverse-shell",
            local_port=45702,
            target_host="test-target",
            payload_type="bash"
        )

        print(f"\n✓ Shell created: {shell.id}")
        print(f"Payload: {payload}")

        # Check payload
        if "0.0.0.0" in payload:
            results["reverse_payload"]["details"] = f"Still using 0.0.0.0: {payload}"
            print("\n❌ FAILED: Payload still uses 0.0.0.0")
        elif "127.0.0.1" in payload or any(c.isdigit() for c in payload.split("/dev/tcp/")[1].split(":")[0]):
            results["reverse_payload"]["passed"] = True
            results["reverse_payload"]["details"] = f"Valid IP: {payload}"
            print(f"\n✅ PASSED: Payload uses real IP")
        else:
            results["reverse_payload"]["details"] = f"Unknown format: {payload}"
            print(f"\n⚠️  WARNING: Unknown payload format")

    except Exception as e:
        results["reverse_payload"]["details"] = str(e)
        print(f"\n❌ FAILED: {e}")

    # Test 4: Side effect command
    print("\n" + "-" * 60)
    print("[Test 4] Side Effect Command")
    print("-" * 60)

    try:
        print("Creating bind shell to 127.0.0.1:45700...")
        shell = manager.create_bind_shell(
            name="test-side-effect",
            target_host="127.0.0.1",
            target_port=45700,
            os_type=OSType.LINUX,
            shell_program=ShellProgram.SH
        )
        print(f"✓ Shell created: {shell.id}")

        # Execute side effect command
        test_file = "/tmp/amp_shell_test_side_effect"
        print(f"\nExecuting: echo SIDE_EFFECT_OK > {test_file}")
        result = manager.execute_command(
            shell_id=shell.id,
            command=f"echo SIDE_EFFECT_OK > {test_file}",
            timeout=10
        )

        print(f"\nCommand result:")
        print(f"  Success: {result.command_success}")
        print(f"  Exit code: {result.exit_code}")

        # Check if file exists
        time.sleep(1)
        file_exists = Path(test_file).exists()

        if file_exists:
            content = Path(test_file).read_text().strip()
            print(f"\n✓ File created: {test_file}")
            print(f"  Content: {content}")

            if content == "SIDE_EFFECT_OK":
                results["side_effect"]["passed"] = True
                results["side_effect"]["details"] = "File created with correct content"
                print("\n✅ PASSED: Side effect command executed")
            else:
                results["side_effect"]["details"] = f"Wrong content: {content}"
                print("\n❌ FAILED: Wrong file content")

            # Cleanup
            Path(test_file).unlink()
        else:
            results["side_effect"]["details"] = "File not created"
            print(f"\n❌ FAILED: File not created at {test_file}")

        # Close shell
        manager.close_shell(shell.id)

    except Exception as e:
        results["side_effect"]["details"] = str(e)
        print(f"\n❌ FAILED: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for r in results.values() if r["passed"])
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"\n{status} - {test_name}")
        print(f"  {result['details']}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'=' * 60}")

    return passed == total


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║         AMP Shell Fixes - Test Suite                    ║
╚══════════════════════════════════════════════════════════╝

This script tests the 3 critical shell fixes:
1. Shell false success (command echo verification)
2. Reverse shell payload (real IP detection)
3. Output interference (no echo $?)

""")

    setup_test_shells()

    print("\nStarting tests...")
    success = asyncio.run(test_shell_fixes())

    sys.exit(0 if success else 1)
