# AMP Project Status

## Current Phase: Planning (Brainstorm)

### Completed
✅ All key decisions confirmed with user
✅ MVP scope defined
✅ Project structure created
✅ Base configuration files written (pyproject.toml, .gitignore, README.md)
✅ Exception hierarchy defined
✅ Research agents dispatched (4 parallel investigations)

### In Progress
🔄 Research phase - 4 sub-agents investigating:
   - Context compression strategies
   - Shell session management patterns
   - MCP protocol best practices
   - Tunnel management patterns

### Next Steps
1. Wait for research completion
2. Review research findings and update PRD
3. Curate implement.jsonl and check.jsonl
4. Run `task.py start` to enter implementation phase
5. Begin Phase 1: Foundation (Storage layer + Tunnel Manager core)

## Key Decisions

| Decision | Choice |
|----------|--------|
| Visualization | Hybrid (CLI + Web UI for topology only) |
| Target OS | Linux + Windows (full support) |
| Priority | Tunnel → Shell → MCP → Context |
| Test Env | Docker-based mock targets |
| Distribution | Docker image |
| User Mode | Single-user local deployment |

## MVP Scope

**Included:**
- Multi-hop tunnel management (Chisel + Ligolo-ng)
- Cross-platform shell sessions (Linux + Windows)
- Intelligent context engine with vector search
- MCP integration with Claude Code
- Network topology visualization (Web UI)
- Session persistence (survive restarts)
- Resource limits (20 tunnels, 50 shells)
- Docker test environment

**Excluded:**
- Multi-user support
- Multi-agent collaboration
- Plugin system
- Offline mode
- Advanced anti-detection
- Automated report generation

## Timeline Estimate

- **Phase 1-2** (Foundation + Execution): 4 weeks
- **Phase 3** (Intelligence Layer): 2 weeks
- **Phase 4** (Integration): 2 weeks
- **Phase 5** (Testing & Polish): 2 weeks
- **Total**: ~10 weeks for MVP

## Project Structure

```
amp/
├── core/
│   ├── tunnel/      # Tunnel management
│   ├── shell/       # Shell session management
│   ├── context/     # Context engine
│   └── network/     # Network topology
├── mcp/             # MCP server
├── storage/         # Data persistence
├── cli/             # CLI interface
└── utils/           # Utilities

tests/
├── unit/            # Unit tests
├── integration/     # Integration tests
├── e2e/             # End-to-end tests
└── fixtures/        # Test fixtures

docker/
├── app/             # AMP Docker image
└── test-env/        # Test environment
```
