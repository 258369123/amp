# AMP - AI-driven Autonomous Penetration Testing Platform

> **⚠️ IMPORTANT**: This tool is designed for **authorized penetration testing only**. Unauthorized access to computer systems is illegal. Always obtain proper authorization before use.

## Overview

AMP is an AI-driven platform that integrates Claude Code CLI with multi-layer network proxy management, shell session orchestration, and intelligent context disclosure for autonomous penetration testing.

## Features

- **Multi-hop Tunnel Management**: Automatic creation and management of Chisel/Ligolo-ng tunnels
- **Cross-platform Shell Sessions**: Support for Linux (bash/sh) and Windows (PowerShell/CMD) targets
- **Intelligent Context Engine**: Progressive disclosure with vector-based relevance filtering
- **MCP Integration**: Seamless integration with Claude Code via Model Context Protocol
- **Network Topology Visualization**: Real-time visualization of network paths and tunnels
- **Session Persistence**: Survive restarts with automatic state recovery

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Claude Code CLI                             │
│                   (User Interaction + AI)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP Protocol
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AMP MCP Server                                │
│              (Tools: tunnel, shell, context, scan)               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AMP Core Engine                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ Tunnel Manager   │  │  Shell Manager   │  │ Context Engine│ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Claude Code CLI
- Docker (optional, for test environment)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/amp-pentest.git
cd amp-pentest

# Install dependencies
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Configuration

### Binary Paths

AMP requires external binaries for tunnel management. Configure paths using one of these methods:

**Method 1: Environment Variables (Recommended)**
```bash
export CHISEL_PATH=/path/to/chisel
export LIGOLO_PATH=/path/to/ligolo-ng
```

**Method 2: .env File**
```bash
# Create .env in project root (copy from .env.example)
cp .env.example .env

# Edit .env
CHISEL_PATH=/path/to/chisel
LIGOLO_PATH=/path/to/ligolo-ng
```

**Method 3: System PATH**
```bash
# Install binaries in system PATH
sudo cp chisel /usr/local/bin/
sudo cp ligolo-ng /usr/local/bin/
sudo chmod +x /usr/local/bin/chisel
sudo chmod +x /usr/local/bin/ligolo-ng
```

**Method 4: MCP Tool Parameter**
```python
# AI can specify dynamically in tool calls
start_tunnel_server(
    'chisel',
    8080,
    binary_path='/custom/path/chisel'
)
```

**Priority Order**: binary_path parameter > Environment variable > System PATH

### Shell Management

AMP uses tmux for reliable shell management:

```bash
# Install tmux (required)
sudo apt install tmux  # Ubuntu/Debian
sudo yum install tmux  # CentOS/RHEL

# Verify installation
tmux -V
```

**Benefits of tmux-based shells**:
- No prompt detection needed
- Complete output capture
- Natural persistence across sessions
- Verified command execution

### Configuration File

All settings can be configured via `.env` file or environment variables with `AMP_` prefix:

```bash
# General
AMP_DEBUG=false
AMP_LOG_LEVEL=INFO

# Tunnels
AMP_TUNNEL__MAX_TUNNELS=20
AMP_TUNNEL__HEARTBEAT_INTERVAL=30

# Shells
AMP_SHELL__MAX_SHELLS=50
AMP_SHELL__DEFAULT_TIMEOUT=30

# MCP Server
AMP_MCP__HOST=127.0.0.1
AMP_MCP__PORT=8899
AMP_MCP__AUTH_TOKEN=your-secret-token
```

See `.env.example` for all available options.

### Usage

#### Option 1: MCP Server (Recommended for Claude Code)

1. Start the AMP MCP server:
```bash
# Using the entry point
amp-mcp

# Or directly
python -m amp.mcp.run_mcp_server
```

2. Configure Claude Code MCP settings:
```json
{
  "mcpServers": {
    "amp": {
      "command": "python",
      "args": ["-m", "amp.mcp.run_mcp_server"],
      "cwd": "/path/to/amp"
    }
  }
}
```

3. Use Claude Code to interact with AMP:
```
> I need to test the security of 192.168.1.100 through a DMZ host at 10.0.0.5
```

#### Option 2: REST API + Web UI

1. Start the FastAPI server:
```bash
python amp/mcp/run_server.py

# Or using uvicorn
uvicorn amp.mcp.server:create_app --factory --host 127.0.0.1 --port 8000
```

2. Access Web UI at: http://127.0.0.1:8000

3. API documentation at: http://127.0.0.1:8000/docs

## Development

### Setup

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy amp/

# Linting
ruff check amp/
```

### Project Structure

```
amp/
├── core/           # Core modules
│   ├── tunnel/     # Tunnel management
│   ├── shell/      # Shell session management
│   ├── context/    # Context engine
│   └── network/    # Network topology
├── mcp/            # MCP server
├── storage/        # Data persistence
├── cli/            # CLI interface
└── tests/          # Test suite
```

## Testing Environment

AMP includes a Docker-based test environment with multi-layer network topology:

```bash
# Start test environment
cd docker/test-env
docker-compose up -d

# This creates:
# - External network (172.20.0.0/24)
# - DMZ network (172.21.0.0/24)
# - Internal network (172.22.0.0/24)
# - Mock AD domain (172.23.0.0/24)
```

## Security Considerations

- All operations run in isolated Docker containers
- Audit logs are written to SQLite (immutable)
- Token-based authentication for MCP server
- Resource limits prevent DoS (max 20 tunnels, 50 shells)

## Troubleshooting

For common issues and solutions, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Common issues:
- **Tunnel binary not found**: Configure `CHISEL_PATH` or `LIGOLO_PATH` environment variables
- **Shell command returns empty output**: Verify tmux is installed (`tmux -V`)
- **Reverse shell payload has 0.0.0.0**: Specify `local_ip` parameter manually
- **SSH connection failed**: Check credentials and network connectivity

Enable debug logging for detailed diagnostics:
```bash
# In .env
AMP_DEBUG=true
AMP_LOG_LEVEL=DEBUG

# Check logs
tail -f amp.log
```

## License

MIT License - See LICENSE file for details

## Disclaimer

This tool is provided for educational and authorized security testing purposes only. The authors are not responsible for misuse or damage caused by this tool. Always ensure you have explicit permission before testing any systems you do not own.
