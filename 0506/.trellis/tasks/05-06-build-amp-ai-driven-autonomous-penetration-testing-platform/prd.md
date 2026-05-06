# Build AMP - AI-driven Autonomous Penetration Testing Platform

## Goal

Build an AI-driven autonomous penetration testing platform (AMP) that integrates Claude Code CLI with multi-layer network proxy management, shell session orchestration, and intelligent context disclosure. The platform enables AI agents to perform authorized security testing across complex network topologies (external → DMZ → internal networks) with automatic tunnel management, persistent shell sessions, and progressive context awareness.

## What I Already Know

### From User Requirements
- Target use case: AD domain penetration testing with multi-hop network traversal
- Core problem: Managing multi-layer proxy chains from external networks to internal targets
- Key requirement: Tools should be created on-demand (not pre-configured Python commands)
- Need to manage multiple shell environments and local command windows for reverse shells
- Must use context engineering to remind AI of tunnel states, shell sessions, and network topology
- Should embody progressive disclosure principles (reveal information as needed)

### Architecture Decisions (Confirmed by User)
- **Deployment mode**: Hybrid (local AMP Core + remote VPS tunnel nodes)
- **Tunnel technology**: Chisel (primary) + Ligolo-ng (secondary)
- **Shell management**: Mixed mode (important shells in tmux, temporary shells in background)
- **Security isolation**: Docker container isolation (Level 2)
- **Context management**: Dynamic compression based on relevance scoring

### Technical Stack (Confirmed)
- **Language**: Python 3.11+
- **Framework**: FastAPI (MCP Server + Web API)
- **AI Integration**: Anthropic SDK + LangChain
- **Tunnel Tools**: Chisel, Ligolo-ng, SSH tunnels
- **Shell Management**: tmux, pexpect, paramiko
- **Storage**: SQLite (state), ChromaDB (vectors), Redis (cache, optional)
- **Containerization**: Docker + Docker Compose

### Repository Context
- This is a fresh Trellis-managed project (initialized at `/home/xp/test/0506`)
- No existing codebase - greenfield development
- Trellis workflow system is configured and active
- Developer name: 0506

## Assumptions (To Validate)

- User has authorized penetration testing context (legal/ethical use)
- Target deployment environment: Linux (WSL2 detected)
- User has Docker installed or can install it
- User wants MVP first, then iterative enhancements
- Web UI is optional for MVP (can be added later)

## Decisions Made

✅ **Visualization**: Hybrid mode - CLI for status/logs, Web UI only for network topology visualization
✅ **Target OS Support**: Linux + Windows (full support for both platforms)
✅ **Implementation Priority**: Tunnel Manager → Shell Manager → MCP Integration → Context Engine
✅ **Test Environment**: Docker-based mock targets with multi-layer network topology
✅ **Distribution**: Docker image (all dependencies bundled)
✅ **User Mode**: Single-user local deployment

## Open Questions

### MVP Scope Boundary
1. Should MVP support Windows targets, or Linux-only initially?
2. What's the priority order: (a) tunnel management, (b) shell management, (c) context engine, (d) MCP integration?

### Testing & Validation
3. Do you have a test environment (lab network) for validation, or should we include Docker-based mock targets?
4. What's the acceptable test coverage threshold for MVP?

### Deployment & Distribution
5. Should this be packaged as a Python package (pip install), Docker image, or both?
6. Do you need multi-user support, or single-user local deployment only?

## Requirements (Evolving)

### Core Modules (MVP)

**1. Tunnel Manager**
- Create/destroy Chisel and Ligolo-ng tunnels
- Health check with automatic reconnection
- Persist tunnel state to SQLite (support restart recovery)
- Support nested tunnels (multi-hop)
- Automatic route selection based on target IP
- Cascade failure handling (auto-cleanup downstream tunnels)
- Resource limits (max 20 concurrent tunnels)

**2. Shell Manager**
- Create reverse/bind/SSH shells through tunnels
- Support both Linux (bash/sh) and Windows (PowerShell/CMD) targets
- Manage tmux sessions for persistent shells
- Execute commands with timeout and output capture
- Track shell state (working directory, environment variables, privilege level)
- Persist shell sessions to SQLite (support restart recovery)
- Zombie process detection and cleanup
- Resource limits (max 50 concurrent shells)

**3. Context Engine**
- Build dynamic prompts for Claude Code based on current task
- Store operation history in ChromaDB with vector embeddings
- Implement smart compression (relevance-based filtering)
- Generate network topology summaries
- Progressive disclosure: only show relevant tunnels/shells
- Keep context under 8000 tokens

**4. MCP Server**
- Expose tools to Claude Code via MCP protocol
- Tools: `create_tunnel`, `execute_command`, `get_context`, `scan_network`, `create_shell`, `upload_file`, `visualize_topology`
- Handle authentication (simple token-based)
- Error handling with retry logic
- Graceful degradation on tool failures

**5. Network Topology Graph**
- Maintain in-memory graph of network segments
- Auto-infer optimal tunnel paths
- Visualize as Mermaid diagram (CLI) or interactive graph (Web UI)
- Track dependencies between tunnels

**6. Storage Layer**
- SQLite schema for tunnels, shells, operations
- ChromaDB for vector search of historical operations
- Session persistence (survive restarts)

**7. Docker Test Environment**
- Multi-layer network topology (External → DMZ → Internal → AD Domain)
- Mock Linux targets (Ubuntu, CentOS)
- Mock Windows targets (Windows Server with AD)
- Automated setup via Docker Compose

### Non-Functional Requirements

- **Security**: All operations in Docker containers with network isolation
- **Reliability**: Automatic tunnel recovery on disconnect
- **Observability**: Structured logging (JSON format)
- **Performance**: Command execution < 5s for local targets
- **Usability**: Clear error messages with suggested fixes

## Acceptance Criteria

- [ ] Can create a Chisel tunnel to a remote host
- [ ] Can establish a reverse shell through the tunnel
- [ ] Can execute commands in the shell and retrieve output
- [ ] Context engine generates relevant prompts (< 8000 tokens)
- [ ] MCP server exposes all 7 core tools
- [ ] Tunnel auto-recovers after simulated disconnect
- [ ] All operations logged to SQLite
- [ ] Docker isolation prevents host network access
- [ ] Integration tests pass for basic workflow (tunnel → shell → command)
- [ ] Documentation includes setup guide and usage examples

## Definition of Done

- Unit tests for core modules (≥80% coverage)
- Integration tests for end-to-end workflows
- Lint (ruff) and type-check (mypy) pass
- Docker Compose setup for local development
- README with installation and quickstart
- Security audit checklist completed
- Example usage scenarios documented

## Out of Scope (Explicit)

- Web UI for status/logs (only topology visualization)
- Multi-user authentication and authorization
- Multi-agent collaboration (single AI agent only)
- Plugin system for custom tools
- Offline mode (assumes internet connectivity)
- Advanced anti-detection features (basic tunnel encryption only)
- Automated penetration testing report generation (manual log export)
- Cloud provider integrations (manual VPS setup)
- Distributed deployment across multiple hosts

## Technical Notes

### Constraints
- Must run on Linux (WSL2 compatible)
- Python 3.11+ required for modern async features
- Docker required for isolation
- Chisel and Ligolo-ng binaries must be available

### Files to Create
```
amp/
├── core/
│   ├── tunnel/
│   ├── shell/
│   ├── context/
│   └── network/
├── mcp/
├── storage/
├── cli/
├── tests/
├── docker/
└── docs/
```

### External Dependencies
- Chisel (https://github.com/jpillora/chisel)
- Ligolo-ng (https://github.com/nicocha30/ligolo-ng)
- tmux, nmap (system packages)

### Research References
(To be populated by trellis-research sub-agents)

## Implementation Plan

### Phase 1: Foundation (Week 1-2)
**PR1: Project scaffolding + Storage layer**
- SQLite schema and models (Tunnel, Shell, Operation)
- Repository pattern for data access
- Basic configuration management
- Exception hierarchy
- Unit tests for storage layer

**PR2: Tunnel Manager - Core**
- Chisel wrapper (spawn, monitor, kill)
- Tunnel lifecycle management
- Health check mechanism
- Basic tests with mock processes

### Phase 2: Execution Layer (Week 3-4)
**PR3: Tunnel Manager - Advanced**
- Ligolo-ng wrapper
- Nested tunnel support
- Auto-recovery on disconnect
- Cascade failure handling
- Integration tests with real Chisel/Ligolo

**PR4: Shell Manager - Linux**
- tmux backend implementation
- Command execution with pexpect
- Shell state tracking
- Reverse/bind/SSH shell creation
- Linux-specific tests

**PR5: Shell Manager - Windows**
- PowerShell/CMD support
- Windows-specific payload generation
- UAC and privilege handling
- Cross-platform integration tests

### Phase 3: Intelligence Layer (Week 5-6)
**PR6: Context Engine - Storage**
- ChromaDB integration
- Vector embedding for operations
- Similarity search implementation
- Basic compression logic

**PR7: Context Engine - Prompt Builder**
- Dynamic prompt generation
- Progressive disclosure logic
- Token budget management
- Relevance scoring algorithm

**PR8: Network Topology**
- In-memory graph structure
- Route calculation
- Topology visualization (Mermaid)
- Dependency tracking

### Phase 4: Integration (Week 7-8)
**PR9: MCP Server - Core**
- FastAPI server setup
- Tool registration framework
- Authentication middleware
- Error handling and logging

**PR10: MCP Tools - Implementation**
- Implement all 7 tools (create_tunnel, execute_command, etc.)
- Input validation
- Timeout handling
- Tool-specific tests

**PR11: Web UI - Topology Visualization**
- Vue 3 + D3.js setup
- WebSocket connection
- Real-time topology graph
- Basic styling

### Phase 5: Testing & Polish (Week 9-10)
**PR12: Docker Test Environment**
- Multi-layer network topology
- Mock Linux targets (Ubuntu, CentOS)
- Mock Windows targets (Windows Server + AD)
- Docker Compose orchestration

**PR13: End-to-End Tests**
- Full workflow tests (tunnel → shell → command)
- Multi-hop scenarios
- Failure recovery tests
- Performance benchmarks

**PR14: Documentation & Packaging**
- API documentation
- Usage examples
- Docker image build
- CI/CD pipeline (GitHub Actions)

## Research References

Research is currently in progress. Sub-agents are investigating:
- Context compression strategies for LLMs → `research/context-compression-strategies.md`
- Shell session management patterns → `research/shell-session-management.md`
- MCP protocol best practices → `research/mcp-best-practices.md`
- Tunnel management patterns → `research/tunnel-management-patterns.md`

These files will be populated once research completes.
