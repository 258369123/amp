# Quick Reference: Tmux Shell Management

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      ShellManager                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  use_tmux=True (default)                             │   │
│  │  ┌────────────────┐      ┌──────────────────┐       │   │
│  │  │ TmuxShellMgr   │      │ CommandExecutor  │       │   │
│  │  │ (new, reliable)│      │ (pexpect, old)   │       │   │
│  │  └────────────────┘      └──────────────────┘       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. TmuxShellManager (`amp/core/shell/tmux_shell_manager.py`)

**Core Strategy:**
- Each shell = one tmux window
- No prompt detection (uses pane capture)
- Command verification via echo detection
- Output stabilization before capture

**Key Methods:**
```python
create_shell(shell_id, shell_type, **kwargs)
  → Creates tmux window and starts shell

execute_command(shell_id, command, timeout)
  → Executes command with verification
  → Returns: {success, stdout, stderr, exit_code}

close_shell(shell_id)
  → Kills tmux window

list_shells()
  → Returns list of active shell IDs

is_alive(shell_id)
  → Checks if shell window exists
```

### 2. ShellManager Integration (`amp/core/shell/manager.py`)

**Initialization:**
```python
ShellManager(database, use_tmux=True)
  → Tries to init TmuxShellManager
  → Falls back to pexpect if tmux unavailable
```

**Routing Logic:**
```python
if self.use_tmux and self.tmux_manager:
    # Use tmux manager (reliable)
    result = self.tmux_manager.execute_command(...)
else:
    # Use pexpect (fallback)
    result = self.executor.execute(...)
```

### 3. Config System (`amp/config.py`)

**Binary Path Resolution Priority:**
```
1. Environment Variable (CHISEL_PATH / LIGOLO_PATH)
   ↓
2. Absolute Path in Config (chisel_binary / ligolo_binary)
   ↓
3. Search in PATH (shutil.which)
   ↓
4. FileNotFoundError (with helpful message)
```

**Usage:**
```python
# Via environment
export CHISEL_PATH=/custom/path/chisel

# Via config property
settings.tunnel.chisel_path  # Auto-resolves

# Via MCP tool parameter
start_tunnel_server('chisel', 8080, binary_path='/custom/path/chisel')
```

## Command Execution Flow

### Tmux-Based Execution

```
1. Clear pane history
   └─ tmux clear-history

2. Send command
   └─ tmux send-keys "command" Enter

3. Wait for stable output
   └─ Capture repeatedly until same 2x

4. Verify command echo
   └─ Check if command appears in output
   └─ FAIL if not found (command not sent)

5. Clean output
   └─ Remove ANSI codes
   └─ Remove command echo
   └─ Remove prompt lines

6. Verify expected output
   └─ For commands like echo, ls, pwd
   └─ FAIL if no output when expected

7. Return result
   └─ {success, stdout, stderr, exit_code}
```

### Pexpect-Based Execution (Fallback)

```
1. Send command
   └─ child.sendline(command)

2. Wait for prompt
   └─ child.expect(PROMPT_PATTERNS)
   └─ Uses regex patterns (fragile)

3. Get output
   └─ child.before

4. Clean output
   └─ Remove ANSI codes
   └─ Remove command echo

5. Return result
   └─ {success, stdout, stderr, exit_code}
```

## Problem → Solution Mapping

| Problem | Old Approach | New Approach |
|---------|-------------|--------------|
| Prompt detection fails | Regex patterns on bash -li | No prompt detection needed |
| Output incomplete | Read until prompt | Wait for stable output |
| False success | Command not sent but returns 0 | Verify command echo |
| Complex process mgmt | pexpect spawn/expect | tmux handles I/O |
| No persistence | Process dies = lost | tmux session persists |

## Configuration Examples

### Environment Variables
```bash
# Set custom binary paths
export CHISEL_PATH=/home/kali/Desktop/Chisel/chisel
export LIGOLO_PATH=/opt/ligolo-ng/ligolo-ng

# Disable tmux (force pexpect)
export AMP_USE_TMUX=false
```

### Python Code
```python
# Use tmux (default)
manager = ShellManager(db)

# Force pexpect
manager = ShellManager(db, use_tmux=False)

# Custom binary via MCP
await start_tunnel_server(
    'chisel', 
    8080,
    binary_path='/custom/chisel'
)
```

### Config File (.env)
```ini
AMP_TUNNEL__CHISEL_BINARY=/usr/local/bin/chisel
AMP_TUNNEL__LIGOLO_BINARY=/usr/local/bin/ligolo-ng
```

## Testing

### Unit Tests
```bash
# Test tmux shell manager
python test_tmux_shell_manager.py

# Test shell manager integration
python -m pytest amp/tests/unit/test_shell_manager.py
```

### Manual Testing
```python
from amp.core.shell.tmux_shell_manager import TmuxShellManager

mgr = TmuxShellManager()

# Test echo
result = mgr.execute_command("test-1", "echo 'Hello'")
assert result['success']
assert 'Hello' in result['stdout']

# Test pwd
result = mgr.execute_command("test-1", "pwd")
assert result['success']
assert result['stdout']  # Should have output

# Test invalid command
result = mgr.execute_command("test-1", "invalidcmd")
# Should still succeed (command was sent)
# But stderr may contain error
```

## Troubleshooting

### Tmux Not Available
```
Error: "tmux is not installed or not in PATH"
Solution: Install tmux or set use_tmux=False
```

### Binary Not Found
```
Error: "Chisel not found. Set CHISEL_PATH env var..."
Solution: 
  1. Set CHISEL_PATH=/path/to/chisel
  2. Or pass binary_path parameter
  3. Or install in PATH
```

### Command Not Echoed
```
Error: "Command not echoed - not sent"
Cause: Command was not actually sent to shell
Solution: Check shell is alive, retry command
```

### Expected Output Missing
```
Error: "Expected output but got none"
Cause: Command like 'echo' produced no output
Solution: Check command syntax, shell state
```

## Performance Considerations

### Tmux Overhead
- Minimal: ~10-50ms per command
- Benefit: Reliability >> overhead

### Output Stabilization
- Default: 0.3s between captures
- Timeout: 30s default (configurable)
- Stable after: 2 identical captures

### Memory Usage
- Tmux session: ~1-2MB per shell
- Pane history: Limited by tmux config
- Cleanup: Automatic on close_shell()

## Migration Path

### Phase 1: Parallel Operation (Current)
- Both tmux and pexpect available
- Tmux used by default
- Pexpect as fallback

### Phase 2: Tmux Primary (Future)
- Tmux required for new features
- Pexpect deprecated but available

### Phase 3: Tmux Only (Future)
- Remove pexpect dependency
- Tmux required

## API Compatibility

All existing code continues to work:
```python
# Old code (still works)
manager = ShellManager(db)
shell = manager.create_bind_shell(...)
result = manager.execute_command(shell.id, "whoami")

# New code (same API)
manager = ShellManager(db, use_tmux=True)
shell = manager.create_bind_shell(...)
result = manager.execute_command(shell.id, "whoami")
```

No breaking changes to:
- ShellManager API
- MCP tools API
- Database schema
- Shell models
