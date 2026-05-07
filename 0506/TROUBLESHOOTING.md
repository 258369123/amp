# AMP Troubleshooting Guide

This guide covers common issues and their solutions when using the AMP platform.

## Table of Contents

- [Tunnel Issues](#tunnel-issues)
- [Shell Issues](#shell-issues)
- [Configuration Issues](#configuration-issues)
- [Network Issues](#network-issues)

---

## Tunnel Issues

### Tunnel Binary Not Found

**Error**: `Chisel binary not found: chisel` or `Ligolo-ng not found`

**Cause**: The tunnel binary is not in the system PATH and no custom path is configured.

**Solutions**:

1. **Set environment variable (Recommended)**:
   ```bash
   export CHISEL_PATH=/path/to/chisel
   export LIGOLO_PATH=/path/to/ligolo-ng
   ```

2. **Add to .env file**:
   ```bash
   # Add to .env in project root
   CHISEL_PATH=/path/to/chisel
   LIGOLO_PATH=/path/to/ligolo-ng
   ```

3. **Install in system PATH**:
   ```bash
   sudo cp chisel /usr/local/bin/
   sudo cp ligolo-ng /usr/local/bin/
   sudo chmod +x /usr/local/bin/chisel
   sudo chmod +x /usr/local/bin/ligolo-ng
   ```

4. **Specify in MCP tool call**:
   ```python
   # AI can specify dynamically
   start_tunnel_server(
       'chisel',
       8080,
       binary_path='/custom/path/chisel'
   )
   ```

**Verification**:
```bash
# Check if binary is accessible
which chisel
which ligolo-ng

# Or test directly
chisel --version
ligolo-ng --version
```

---

### Tunnel Connection Failed

**Error**: `Failed to start tunnel` or `Connection refused`

**Possible Causes**:
1. Server not running
2. Port already in use
3. Firewall blocking connection
4. Wrong host/port configuration

**Solutions**:

1. **Check if server is running**:
   ```bash
   # List active tunnel servers
   # Use MCP tool: list_tunnel_servers()
   
   # Check process
   ps aux | grep chisel
   ps aux | grep ligolo
   ```

2. **Check port availability**:
   ```bash
   # Check if port is in use
   netstat -tuln | grep 8080
   # or
   ss -tuln | grep 8080
   ```

3. **Check firewall**:
   ```bash
   # Ubuntu/Debian
   sudo ufw status
   sudo ufw allow 8080/tcp
   
   # CentOS/RHEL
   sudo firewall-cmd --list-all
   sudo firewall-cmd --add-port=8080/tcp --permanent
   sudo firewall-cmd --reload
   ```

4. **Verify tunnel configuration**:
   ```python
   # Get tunnel details
   get_tunnel_status(tunnel_id)
   ```

---

## Shell Issues

### Shell Command Returns Empty Output

**Error**: Command executes but returns no output

**Possible Causes**:
1. Command not actually executed
2. Tmux not installed
3. Shell died/disconnected
4. Output buffering issue

**Solutions**:

1. **Check tmux installation**:
   ```bash
   tmux -V
   # If not installed:
   sudo apt install tmux  # Ubuntu/Debian
   sudo yum install tmux  # CentOS/RHEL
   ```

2. **Check tmux sessions**:
   ```bash
   tmux ls
   # Should show: amp-shells: X windows
   ```

3. **Check shell status**:
   ```python
   # Use MCP tool
   list_shells()
   # Verify shell status is 'active'
   ```

4. **Check logs**:
   ```bash
   tail -f amp.log
   # Look for errors related to shell execution
   ```

5. **Verify shell is alive**:
   ```python
   # Use MCP tool
   execute_command(shell_id, "echo test")
   # Should return "test"
   ```

---

### Reverse Shell Payload Has 0.0.0.0

**Error**: `Cannot use 0.0.0.0 for reverse shell payload`

**Cause**: The system cannot determine the correct local IP address for the reverse shell connection.

**Solutions**:

1. **Check network interfaces**:
   ```bash
   ip addr show
   # or
   ifconfig
   ```

2. **Specify IP manually**:
   ```python
   # Use MCP tool with local_ip parameter
   create_reverse_shell(
       name="shell1",
       local_port=4444,
       target_host="10.10.10.10",
       local_ip="192.168.1.100"  # Your actual IP
   )
   ```

3. **Check routing**:
   ```bash
   ip route show
   # Verify default route exists
   ```

4. **Test connectivity**:
   ```bash
   # Ping external host to verify network
   ping -c 1 8.8.8.8
   ```

---

### SSH Shell Connection Failed

**Error**: `SSH connection not established`

**Possible Causes**:
1. Wrong credentials
2. SSH service not running on target
3. Network connectivity issue
4. SSH key permissions incorrect

**Solutions**:

1. **Verify credentials**:
   ```bash
   # Test SSH manually
   ssh user@target-host
   ```

2. **Check SSH service on target**:
   ```bash
   # On target machine
   sudo systemctl status sshd
   sudo systemctl start sshd
   ```

3. **Check SSH key permissions**:
   ```bash
   chmod 600 ~/.ssh/id_rsa
   chmod 644 ~/.ssh/id_rsa.pub
   ```

4. **Test with sshpass**:
   ```bash
   # Install sshpass if using password auth
   sudo apt install sshpass
   
   # Test connection
   sshpass -p 'password' ssh user@target-host
   ```

5. **Check network connectivity**:
   ```bash
   # Test if port 22 is reachable
   nc -zv target-host 22
   telnet target-host 22
   ```

---

## Configuration Issues

### Environment Variables Not Loaded

**Error**: Configuration not applied despite setting environment variables

**Cause**: Environment variables not exported or .env file not loaded.

**Solutions**:

1. **Export variables**:
   ```bash
   # Make sure to export
   export CHISEL_PATH=/path/to/chisel
   
   # Verify
   echo $CHISEL_PATH
   ```

2. **Check .env file location**:
   ```bash
   # .env must be in project root
   ls -la .env
   
   # Copy from example if needed
   cp .env.example .env
   ```

3. **Restart MCP server**:
   ```bash
   # Stop server
   pkill -f "amp.mcp"
   
   # Start server (loads new config)
   python -m amp.mcp.run_server
   ```

4. **Verify configuration**:
   ```python
   # Check loaded config
   from amp.config import settings
   print(settings.tunnel.chisel_path)
   ```

---

### Database Connection Issues

**Error**: `Database connection failed` or `sqlite3.OperationalError`

**Solutions**:

1. **Check database file permissions**:
   ```bash
   ls -la amp.db
   chmod 644 amp.db
   ```

2. **Check data directory**:
   ```bash
   mkdir -p ./data
   chmod 755 ./data
   ```

3. **Reset database** (WARNING: deletes all data):
   ```bash
   rm amp.db
   # Database will be recreated on next start
   ```

---

## Network Issues

### Cannot Reach Target Through Tunnel

**Error**: Connection times out when accessing target through tunnel

**Possible Causes**:
1. Tunnel not active
2. Routing not configured
3. Firewall blocking traffic
4. Wrong port forwarding

**Solutions**:

1. **Verify tunnel is active**:
   ```python
   # Use MCP tool
   get_tunnel_status(tunnel_id)
   # Status should be 'active'
   ```

2. **Check tunnel chain**:
   ```python
   # For nested tunnels
   get_tunnel_chain(tunnel_id)
   # Verify all parent tunnels are active
   ```

3. **Test connectivity**:
   ```bash
   # Test local port
   nc -zv localhost 8080
   
   # Test through tunnel
   curl http://localhost:8080
   ```

4. **Check port forwarding**:
   ```bash
   # Verify port is listening
   netstat -tuln | grep 8080
   ```

---

### Topology Stats Show Zero Tunnels

**Error**: `get_topology_stats()` returns all zeros despite active tunnels

**Cause**: Graph not synced with database.

**Solutions**:

1. **Sync topology**:
   ```python
   # Graph should auto-sync, but can be triggered manually
   # This is handled internally by get_stats()
   ```

2. **Check database**:
   ```bash
   sqlite3 amp.db "SELECT COUNT(*) FROM tunnels;"
   ```

3. **Restart services**:
   ```bash
   # Restart MCP server to reload state
   pkill -f "amp.mcp"
   python -m amp.mcp.run_server
   ```

---

## Getting Help

If you encounter issues not covered here:

1. **Check logs**:
   ```bash
   tail -f amp.log
   ```

2. **Enable debug mode**:
   ```bash
   # In .env
   AMP_DEBUG=true
   AMP_LOG_LEVEL=DEBUG
   ```

3. **Check system requirements**:
   - Python 3.11+
   - tmux installed
   - Required binaries (chisel, ligolo-ng) accessible
   - Network connectivity

4. **Report issues**:
   - Include error messages
   - Include relevant log excerpts
   - Include configuration (sanitize secrets)
   - Include steps to reproduce
