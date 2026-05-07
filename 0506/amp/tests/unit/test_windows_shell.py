"""Unit tests for Windows shell functionality."""

import base64
import unittest
from unittest.mock import Mock, patch

import pexpect

from amp.core.shell.windows_executor import WindowsExecutor
from amp.core.shell.windows_payloads import WindowsPayloads
from amp.exceptions import CommandExecutionFailed, ShellTimeout
from amp.storage.models import PrivilegeLevel


class TestWindowsExecutor(unittest.TestCase):
    """Test WindowsExecutor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.executor = WindowsExecutor()

    @patch("amp.core.shell.windows_executor.pexpect.spawn")
    def test_spawn_powershell(self, mock_spawn):
        """Test spawning PowerShell session."""
        # Mock pexpect spawn
        mock_child = Mock()
        mock_child.expect = Mock(return_value=0)
        mock_spawn.return_value = mock_child

        # Spawn PowerShell
        self.executor.spawn_powershell("test-shell-1")

        # Verify spawn was called correctly
        mock_spawn.assert_called_once_with(
            "powershell.exe -NoProfile -NoLogo",
            encoding="utf-8",
            echo=False,
            timeout=30,
        )

        # Verify session was stored
        self.assertIn("test-shell-1", self.executor._sessions)
        self.assertEqual(self.executor._shell_types["test-shell-1"], "powershell")

    @patch("amp.core.shell.windows_executor.pexpect.spawn")
    def test_spawn_cmd(self, mock_spawn):
        """Test spawning CMD session."""
        # Mock pexpect spawn
        mock_child = Mock()
        mock_child.expect = Mock(return_value=0)
        mock_spawn.return_value = mock_child

        # Spawn CMD
        self.executor.spawn_cmd("test-shell-2")

        # Verify spawn was called correctly
        mock_spawn.assert_called_once_with(
            "cmd.exe",
            encoding="utf-8",
            echo=False,
            timeout=30,
        )

        # Verify session was stored
        self.assertIn("test-shell-2", self.executor._sessions)
        self.assertEqual(self.executor._shell_types["test-shell-2"], "cmd")

    def test_execute_powershell_success(self):
        """Test successful PowerShell command execution."""
        # Mock session
        mock_child = Mock()
        mock_child.sendline = Mock()
        mock_child.expect = Mock(side_effect=[0, 0])  # Command output, then exit code
        mock_child.before = "Hello World"
        self.executor._sessions["test-shell"] = mock_child
        self.executor._shell_types["test-shell"] = "powershell"

        # Execute command
        result = self.executor.execute_powershell("test-shell", "Write-Host 'Hello World'")

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Hello", result.stdout)

    def test_execute_powershell_timeout(self):
        """Test PowerShell command timeout."""
        # Mock session with timeout
        mock_child = Mock()
        mock_child.sendline = Mock()
        mock_child.expect = Mock(side_effect=pexpect.TIMEOUT("timeout"))
        self.executor._sessions["test-shell"] = mock_child
        self.executor._shell_types["test-shell"] = "powershell"

        # Execute command and expect timeout
        with self.assertRaises(ShellTimeout):
            self.executor.execute_powershell("test-shell", "Start-Sleep 100", timeout=1)

    def test_execute_cmd_success(self):
        """Test successful CMD command execution."""
        # Mock session
        mock_child = Mock()
        mock_child.sendline = Mock()
        mock_child.expect = Mock(side_effect=[0, 0])  # Command output, then exit code
        mock_child.before = "Hello World"
        self.executor._sessions["test-shell"] = mock_child
        self.executor._shell_types["test-shell"] = "cmd"

        # Execute command
        result = self.executor.execute_cmd("test-shell", "echo Hello World")

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Hello", result.stdout)

    def test_execute_shell_not_found(self):
        """Test executing command on non-existent shell."""
        with self.assertRaises(CommandExecutionFailed) as ctx:
            self.executor.execute_powershell("nonexistent", "whoami")

        # Check the stderr contains the error message
        self.assertEqual(ctx.exception.stderr, "Shell nonexistent not found")

    def test_close_shell(self):
        """Test closing Windows shell."""
        # Mock session
        mock_child = Mock()
        mock_child.sendline = Mock()
        mock_child.close = Mock()
        self.executor._sessions["test-shell"] = mock_child
        self.executor._shell_types["test-shell"] = "powershell"

        # Close shell
        self.executor.close_shell("test-shell")

        # Verify session was removed
        self.assertNotIn("test-shell", self.executor._sessions)
        self.assertNotIn("test-shell", self.executor._shell_types)
        mock_child.sendline.assert_called_once_with("exit")
        mock_child.close.assert_called_once()

    def test_is_alive(self):
        """Test checking if shell is alive."""
        # Mock alive session
        mock_child = Mock()
        mock_child.isalive = Mock(return_value=True)
        self.executor._sessions["test-shell"] = mock_child

        # Check if alive
        self.assertTrue(self.executor.is_alive("test-shell"))

        # Check non-existent shell
        self.assertFalse(self.executor.is_alive("nonexistent"))

    def test_encode_powershell_command(self):
        """Test PowerShell command encoding."""
        command = "Write-Host 'Hello'"
        encoded = WindowsExecutor.encode_powershell_command(command)

        # Verify encoding
        self.assertIsInstance(encoded, str)
        # Decode and verify
        decoded = base64.b64decode(encoded).decode("utf-16le")
        self.assertEqual(decoded, command)

    def test_build_encoded_powershell_command(self):
        """Test building encoded PowerShell command."""
        command = "Write-Host 'Hello'"
        full_command = WindowsExecutor.build_encoded_powershell_command(command)

        # Verify format
        self.assertIn("powershell.exe -EncodedCommand", full_command)


class TestWindowsPayloads(unittest.TestCase):
    """Test WindowsPayloads class."""

    def test_powershell_reverse_shell(self):
        """Test PowerShell reverse shell payload generation."""
        payload = WindowsPayloads.powershell_reverse_shell("192.168.1.100", 4444)

        # Verify payload contains required elements
        self.assertIn("192.168.1.100", payload)
        self.assertIn("4444", payload)
        self.assertIn("TCPClient", payload)
        self.assertIn("powershell", payload.lower())

    def test_powershell_reverse_shell_encoded(self):
        """Test encoded PowerShell reverse shell payload generation."""
        payload = WindowsPayloads.powershell_reverse_shell_encoded("192.168.1.100", 4444)

        # Verify payload is encoded
        self.assertIn("powershell -EncodedCommand", payload)
        # Should not contain plaintext IP (it's encoded)
        parts = payload.split()
        encoded_part = parts[-1]
        self.assertTrue(len(encoded_part) > 100)  # Encoded payload should be long

    def test_cmd_reverse_shell(self):
        """Test CMD reverse shell payload generation."""
        payload = WindowsPayloads.cmd_reverse_shell("192.168.1.100", 4444)

        # Verify payload contains required elements
        self.assertIn("192.168.1.100", payload)
        self.assertIn("4444", payload)
        self.assertIn("powershell", payload.lower())  # CMD uses PowerShell for networking

    def test_powershell_download_cradle_to_file(self):
        """Test PowerShell download cradle to file."""
        payload = WindowsPayloads.powershell_download_cradle(
            "http://example.com/payload.exe",
            "C:\\temp\\payload.exe"
        )

        # Verify payload
        self.assertIn("Invoke-WebRequest", payload)
        self.assertIn("http://example.com/payload.exe", payload)
        self.assertIn("C:\\temp\\payload.exe", payload)

    def test_powershell_download_cradle_in_memory(self):
        """Test PowerShell download cradle in memory."""
        payload = WindowsPayloads.powershell_download_cradle(
            "http://example.com/script.ps1"
        )

        # Verify payload
        self.assertIn("IEX", payload)
        self.assertIn("DownloadString", payload)
        self.assertIn("http://example.com/script.ps1", payload)

    def test_powershell_download_execute(self):
        """Test PowerShell download and execute."""
        payload = WindowsPayloads.powershell_download_execute(
            "http://example.com/payload.exe",
            "C:\\temp\\payload.exe"
        )

        # Verify payload
        self.assertIn("Invoke-WebRequest", payload)
        self.assertIn("Start-Process", payload)

    def test_wmi_shell(self):
        """Test WMI shell payload generation."""
        payload = WindowsPayloads.wmi_shell("192.168.1.100", 4444)

        # Verify payload
        self.assertIn("192.168.1.100", payload)
        self.assertIn("4444", payload)
        self.assertIn("Invoke-WmiMethod", payload)

    def test_powershell_bind_shell(self):
        """Test PowerShell bind shell payload generation."""
        payload = WindowsPayloads.powershell_bind_shell(4444)

        # Verify payload
        self.assertIn("4444", payload)
        self.assertIn("TcpListener", payload)
        self.assertIn("AcceptTcpClient", payload)

    def test_certutil_download(self):
        """Test certutil download payload."""
        payload = WindowsPayloads.certutil_download(
            "http://example.com/file.exe",
            "C:\\temp\\file.exe"
        )

        # Verify payload
        self.assertIn("certutil", payload)
        self.assertIn("http://example.com/file.exe", payload)
        self.assertIn("C:\\temp\\file.exe", payload)

    def test_bitsadmin_download(self):
        """Test bitsadmin download payload."""
        payload = WindowsPayloads.bitsadmin_download(
            "http://example.com/file.exe",
            "C:\\temp\\file.exe"
        )

        # Verify payload
        self.assertIn("bitsadmin", payload)
        self.assertIn("http://example.com/file.exe", payload)
        self.assertIn("C:\\temp\\file.exe", payload)

    def test_get_windows_payload_powershell(self):
        """Test getting Windows payload by type."""
        payload = WindowsPayloads.get_windows_payload("powershell", "192.168.1.100", 4444)

        # Verify payload
        self.assertIn("192.168.1.100", payload)
        self.assertIn("4444", payload)

    def test_get_windows_payload_invalid_type(self):
        """Test getting Windows payload with invalid type."""
        with self.assertRaises(ValueError) as ctx:
            WindowsPayloads.get_windows_payload("invalid", "192.168.1.100", 4444)

        self.assertIn("Unknown Windows payload type", str(ctx.exception))

    def test_get_download_payload_powershell(self):
        """Test getting download payload."""
        payload = WindowsPayloads.get_download_payload(
            "powershell",
            "http://example.com/file.exe",
            "C:\\temp\\file.exe"
        )

        # Verify payload
        self.assertIn("Invoke-WebRequest", payload)

    def test_get_download_payload_certutil_no_output(self):
        """Test getting certutil download without output path."""
        with self.assertRaises(ValueError) as ctx:
            WindowsPayloads.get_download_payload("certutil", "http://example.com/file.exe")

        self.assertIn("output_path required", str(ctx.exception))

    def test_get_download_payload_invalid_method(self):
        """Test getting download payload with invalid method."""
        with self.assertRaises(ValueError) as ctx:
            WindowsPayloads.get_download_payload("invalid", "http://example.com/file.exe")

        self.assertIn("Unknown download method", str(ctx.exception))


class TestWindowsStateDetection(unittest.TestCase):
    """Test Windows-specific state detection."""

    def test_detect_windows_privilege_system(self):
        """Test detecting SYSTEM privilege."""
        from amp.core.shell.state import ShellState

        state = ShellState()

        # Test SYSTEM detection
        output = "NT AUTHORITY\\SYSTEM"
        privilege = state.detect_windows_privilege(output)
        self.assertEqual(privilege, PrivilegeLevel.SYSTEM)

    def test_detect_windows_privilege_admin(self):
        """Test detecting Administrator privilege."""
        from amp.core.shell.state import ShellState

        state = ShellState()

        # Test Administrator detection
        output = "DESKTOP-ABC\\Administrator"
        privilege = state.detect_windows_privilege(output)
        self.assertEqual(privilege, PrivilegeLevel.ROOT)

    def test_detect_windows_privilege_user(self):
        """Test detecting user privilege."""
        from amp.core.shell.state import ShellState

        state = ShellState()

        # Test user detection
        output = "DESKTOP-ABC\\john"
        privilege = state.detect_windows_privilege(output)
        self.assertEqual(privilege, PrivilegeLevel.USER)

    def test_detect_windows_privilege_access_denied(self):
        """Test detecting non-admin from access denied."""
        from amp.core.shell.state import ShellState

        state = ShellState()

        # Test access denied detection
        output = "Access is denied."
        privilege = state.detect_windows_privilege(output)
        self.assertEqual(privilege, PrivilegeLevel.USER)

    def test_detect_uac_enabled(self):
        """Test detecting UAC enabled."""
        from amp.core.shell.state import ShellState

        state = ShellState()

        # Test UAC enabled
        output = "EnableLUA    REG_DWORD    0x1"
        uac_enabled = state.detect_uac_status(output)
        self.assertTrue(uac_enabled)

    def test_detect_uac_disabled(self):
        """Test detecting UAC disabled."""
        from amp.core.shell.state import ShellState

        state = ShellState()

        # Test UAC disabled
        output = "EnableLUA    REG_DWORD    0x0"
        uac_enabled = state.detect_uac_status(output)
        self.assertFalse(uac_enabled)

    def test_parse_windows_env(self):
        """Test parsing Windows environment variables."""
        from amp.core.shell.state import ShellState

        state = ShellState()

        # Test parsing Windows env
        output = """
        COMPUTERNAME=DESKTOP-ABC
        USERNAME=john
        USERPROFILE=C:\\Users\\john
        """
        env = state.parse_windows_env(output)

        self.assertEqual(env["COMPUTERNAME"], "DESKTOP-ABC")
        self.assertEqual(env["USERNAME"], "john")
        self.assertEqual(env["USERPROFILE"], "C:\\Users\\john")


if __name__ == "__main__":
    unittest.main()
