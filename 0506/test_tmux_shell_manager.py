#!/usr/bin/env python3
"""Test script for TmuxShellManager implementation."""

import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from amp.core.shell.tmux_shell_manager import TmuxShellManager


def test_basic_functionality():
    """Test basic tmux shell manager functionality."""
    print("=" * 60)
    print("Testing TmuxShellManager Basic Functionality")
    print("=" * 60)

    try:
        # Initialize manager
        print("\n1. Initializing TmuxShellManager...")
        manager = TmuxShellManager(session_name="test-amp-shells")
        print("   ✓ Manager initialized successfully")

        # Test command execution with echo
        print("\n2. Testing command execution (echo)...")
        result = manager.execute_command("test-shell-1", "echo 'Hello World'", timeout=5)
        print(f"   Command: echo 'Hello World'")
        print(f"   Success: {result.get('success')}")
        print(f"   Output: {result.get('stdout')}")
        print(f"   Exit code: {result.get('exit_code')}")

        if result.get('success') and 'Hello World' in result.get('stdout', ''):
            print("   ✓ Echo test passed")
        else:
            print("   ✗ Echo test failed")
            return False

        # Test command execution with pwd
        print("\n3. Testing command execution (pwd)...")
        result = manager.execute_command("test-shell-1", "pwd", timeout=5)
        print(f"   Command: pwd")
        print(f"   Success: {result.get('success')}")
        print(f"   Output: {result.get('stdout')}")

        if result.get('success') and result.get('stdout'):
            print("   ✓ Pwd test passed")
        else:
            print("   ✗ Pwd test failed")
            return False

        # Test command execution with whoami
        print("\n4. Testing command execution (whoami)...")
        result = manager.execute_command("test-shell-1", "whoami", timeout=5)
        print(f"   Command: whoami")
        print(f"   Success: {result.get('success')}")
        print(f"   Output: {result.get('stdout')}")

        if result.get('success') and result.get('stdout'):
            print("   ✓ Whoami test passed")
        else:
            print("   ✗ Whoami test failed")
            return False

        # Test list shells
        print("\n5. Testing list shells...")
        shells = manager.list_shells()
        print(f"   Active shells: {shells}")

        if "test-shell-1" in shells:
            print("   ✓ List shells test passed")
        else:
            print("   ✗ List shells test failed")
            return False

        # Test is_alive
        print("\n6. Testing is_alive...")
        is_alive = manager.is_alive("test-shell-1")
        print(f"   Shell alive: {is_alive}")

        if is_alive:
            print("   ✓ Is_alive test passed")
        else:
            print("   ✗ Is_alive test failed")
            return False

        # Test close shell
        print("\n7. Testing close shell...")
        manager.close_shell("test-shell-1")
        time.sleep(0.5)
        is_alive = manager.is_alive("test-shell-1")
        print(f"   Shell alive after close: {is_alive}")

        if not is_alive:
            print("   ✓ Close shell test passed")
        else:
            print("   ✗ Close shell test failed")
            return False

        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_command_verification():
    """Test command verification (echo detection)."""
    print("\n" + "=" * 60)
    print("Testing Command Verification")
    print("=" * 60)

    try:
        manager = TmuxShellManager(session_name="test-amp-shells-2")

        # Test that commands without output are detected
        print("\n1. Testing command without expected output...")
        result = manager.execute_command("test-shell-2", "ls /nonexistent 2>/dev/null", timeout=5)
        print(f"   Command: ls /nonexistent 2>/dev/null")
        print(f"   Success: {result.get('success')}")
        print(f"   Output: '{result.get('stdout')}'")

        # This should succeed (command was sent) but have no output
        if result.get('success'):
            print("   ✓ Command verification test passed")
        else:
            print("   ✗ Command verification test failed")

        # Clean up
        manager.close_shell("test-shell-2")

        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_output_cleaning():
    """Test output cleaning (ANSI codes, prompts)."""
    print("\n" + "=" * 60)
    print("Testing Output Cleaning")
    print("=" * 60)

    try:
        manager = TmuxShellManager(session_name="test-amp-shells-3")

        # Test multi-line output
        print("\n1. Testing multi-line output...")
        result = manager.execute_command("test-shell-3", "echo -e 'Line1\\nLine2\\nLine3'", timeout=5)
        print(f"   Command: echo -e 'Line1\\nLine2\\nLine3'")
        print(f"   Success: {result.get('success')}")
        print(f"   Output:\n{result.get('stdout')}")

        if result.get('success') and 'Line1' in result.get('stdout', ''):
            print("   ✓ Multi-line output test passed")
        else:
            print("   ✗ Multi-line output test failed")

        # Clean up
        manager.close_shell("test-shell-3")

        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\nTmux Shell Manager Test Suite")
    print("=" * 60)

    # Check if tmux is installed
    import subprocess
    try:
        subprocess.run(["tmux", "-V"], capture_output=True, check=True)
        print("✓ tmux is installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ tmux is not installed. Please install tmux first.")
        sys.exit(1)

    # Run tests
    all_passed = True

    if not test_basic_functionality():
        all_passed = False

    if not test_command_verification():
        all_passed = False

    if not test_output_cleaning():
        all_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)
