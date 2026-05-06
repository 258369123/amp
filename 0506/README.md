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

- Docker and Docker Compose
- Python 3.11+ (for development)
- Claude Code CLI

### Installation

```bash
# Pull the Docker image
docker pull amp-pentest:latest

# Or build from source
git clone https://github.com/yourusername/amp-pentest.git
cd amp-pentest
docker-compose up -d
```

### Usage

1. Start the AMP MCP server:
```bash
docker run -d -p 8765:8765 amp-pentest:latest
```

2. Configure Claude Code to use AMP MCP server (add to `~/.claude/settings.json`):
```json
{
  "mcp": {
    "servers": {
      "amp": {
        "url": "http://localhost:8765",
        "auth_token": "your-token-here"
      }
    }
  }
}
```

3. Use Claude Code to interact with AMP:
```
> I need to test the security of 192.168.1.100 through a DMZ host at 10.0.0.5
```

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

## License

MIT License - See LICENSE file for details

## Disclaimer

This tool is provided for educational and authorized security testing purposes only. The authors are not responsible for misuse or damage caused by this tool. Always ensure you have explicit permission before testing any systems you do not own.
