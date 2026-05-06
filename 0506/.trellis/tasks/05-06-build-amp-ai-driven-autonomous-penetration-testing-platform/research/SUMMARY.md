# Research Findings Summary

## Overview

This document summarizes key findings from 4 parallel research investigations conducted for the AMP platform.

---

## 1. Shell Session Management

**Research File**: `research/shell-session-management.md`

### Key Takeaways

**Linux Targets:**
- Use tmux for persistent sessions with `tmux new-session -d -s <name>`
- PTY allocation via `pty.spawn()` for full TTY features
- Shell upgrade pattern: `python -c 'import pty; pty.spawn("/bin/bash")'`

**Windows Targets:**
- PowerShell preferred: `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass`
- WinRM for remote sessions: `Enter-PSSession -ComputerName target`
- UAC bypass techniques: fodhelper, eventvwr, DLL hijacking
- AMSI bypass: memory patching, obfuscation, reflection

**Command Execution:**
- Use subprocess with timeout for reliability
- Async execution for long-running commands
- Stream output capture to prevent memory overflow
- Process group management for complete cleanup

**State Tracking:**
- Persist working directory, environment variables, privilege level
- Detect zombie processes using psutil
- Implement graceful degradation with fallback shells

**C2 Framework Patterns:**
- Empire: Python-based agents with staging
- Covenant: C# Grunts with task-based execution
- PoshC2: PowerShell runspaces for in-memory execution

---

## 2. MCP Protocol Best Practices

**Research File**: `research/mcp-best-practices.md`

### Key Takeaways

**Architecture:**
- Use stdio transport for single-user local deployment (simpler, more secure)
- Implement stateful server with SQLite persistence
- Single responsibility: focus on penetration testing infrastructure

**Tool Design:**
- Clear naming: verb_noun pattern (create_tunnel, execute_command)
- Comprehensive parameter validation with Pydantic
- Structured error responses with error codes and retry guidance
- Idempotent operations where possible (create_tunnel checks if exists)

**Long-Running Operations:**
- Use async pattern with operation IDs for network scans
- Return operation ID immediately, provide status query tool
- Implement timeout with configurable limits

**Security:**
- Input validation to prevent command injection
- Token-based authentication for MCP server
- Resource limits (max 20 tunnels, 50 shells)
- Audit logging for all operations

**State Management:**
- Store state in SQLite for restart recovery
- Implement signal handlers for graceful shutdown
- Provide tools to query current state (get_context, list_tunnels)

**Reference Implementations:**
- mcp-server-filesystem (file operations)
- mcp-server-postgres (database operations)
- mcp-server-docker (container management)

---

## 3. Tunnel Management Patterns

**Research File**: `research/tunnel-management-patterns.md`

### Key Takeaways

**Technology Comparison:**
- **Chisel**: HTTP/SOCKS5, easy to use, good for most scenarios
- **Ligolo-ng**: Layer 3 tunneling, more stealthy, requires root
- **Metasploit**: Mature routing, heavy framework
- **Cobalt Strike**: Commercial, beacon chaining
- **Sliver**: Modern, gRPC-based, multiplexing

**Health Monitoring:**
- **Hybrid approach**: Passive monitoring (track last activity) + Active probing (fallback)
- Heartbeat interval: 30 seconds
- Failure threshold: 3 missed heartbeats
- Avoid aggressive probing to maintain stealth

**Failure Handling:**
- Automatic reconnection with exponential backoff (1s, 2s, 4s, 8s, 16s)
- Max 5 retry attempts before marking as dead
- Cascade failure cleanup: track dependency graph in SQLite
- Notify AI agent when tunnel cannot be recovered

**Performance Optimization:**
- Connection pooling: 10 connections per tunnel
- Limit tunnel chains to 3 hops maximum (latency amplification)
- Use compression for large data transfers
- Multiplexing: single tunnel for multiple streams

**Resource Limits:**
- Hard limit: 20 concurrent tunnels
- Port range: 10000-20000 for dynamic allocation
- Prevent port exhaustion with proper cleanup

**Common Pitfalls:**
- Stale routes after tunnel dies → implement route cleanup
- Zombie processes → use process groups and SIGKILL
- Firewall state table exhaustion → limit connection rate

**Recommended Architecture:**
- State machine: CREATING → ACTIVE → DISCONNECTED → RECONNECTING → DEAD
- SQLite schema: tunnels table with status, parent_id, created_at, last_heartbeat
- Dependency graph for cascade cleanup

---

## 4. Context Compression Strategies

**Research File**: `research/context-compression-strategies.md`

### Key Takeaways

**Context Window Challenges:**
- Target budget: 8,000 tokens (conservative for Claude Opus 4.7's 200K limit)
- AMP requirements: operational history (1000+ commands), network topology (20 tunnels, 50 shells), tool definitions (~2K tokens)
- Information density vs relevance trade-off: not all history is relevant to current task

**Compression Techniques:**
- **Hierarchical summarization**: Multi-level abstraction (L0: current task, L1: recent ops, L2: vector search, L3: SQLite archive)
- **Sliding window with decay**: Full detail for last 5 ops, summaries for 6-20, commands only for 21-100, stats for 100+
- **Semantic deduplication**: Merge similar operations (e.g., multiple `ls` commands)
- **Stateful compression**: Track state changes only, not full command outputs
- **Graph-based compression**: Represent tunnel/shell dependencies as graph, show only relevant subgraph

**Token Savings**: 85-92% reduction in context size

**Vector Search Patterns:**
- **ChromaDB** for vector storage (lightweight, embedded)
- **all-MiniLM-L6-v2** for embeddings (384 dimensions, fast, good quality)
- **Hybrid search**: Semantic similarity (30%) + temporal decay (20%) + task alignment (25%) + dependency (15%) + outcome (10%)
- **Query strategies**: Task-driven retrieval, error-context retrieval, dependency-aware retrieval

**Progressive Disclosure:**
- **Task-driven assembly**: Show only resources relevant to current task
- **Lazy loading**: Load detailed history on-demand via vector search
- **Attention mechanisms**: Highlight critical state changes (privilege escalation, new network segment)
- **Contextual breadcrumbs**: Show path to current state (tunnel chain, shell history)

**Token Budget Allocation** (8000 tokens total):
- System prompts: 18.75% (1500 tokens)
- Current task: 10% (800 tokens)
- Active resources: 15% (1200 tokens) - tunnels, shells
- Recent history: 20% (1600 tokens) - last 10-20 operations
- Retrieved context: 15% (1200 tokens) - vector search results
- Network topology: 7.5% (600 tokens) - graph visualization
- Error context: 5% (400 tokens) - recent failures
- Buffer: 8.75% (700 tokens) - overflow protection

**Reference Implementations:**
- **LangChain**: ConversationBufferWindowMemory, ConversationSummaryMemory
- **AutoGPT**: Rolling context with summarization
- **MemGPT**: Virtual context management with paging
- **Anthropic's compaction**: Automatic context compression in Claude API
- **ReAct pattern**: Thought-Action-Observation loop with selective history

**AMP-Specific Architecture:**
```python
class ContextEngine:
    def __init__(self):
        self.hot_storage = SQLite()      # Recent operations (last 100)
        self.cold_storage = ChromaDB()   # Historical operations (vector search)
        self.token_budget = 8000
        
    def build_context(self, task: str) -> str:
        # 1. Always include: current task + active resources
        # 2. Recent history: last 10 operations (full detail)
        # 3. Retrieved context: vector search for task-relevant history
        # 4. Network topology: relevant tunnel/shell subgraph
        # 5. Error context: recent failures
        pass
```

**Implementation Priorities:**
1. Phase 1: Basic storage (SQLite for operations)
2. Phase 2: Vector search (ChromaDB integration)
3. Phase 3: Relevance scoring (multi-factor algorithm)
4. Phase 4: Progressive disclosure (task-driven assembly)
5. Phase 5: Token budget monitoring (overflow protection)

**Success Criteria:**
- Context stays under 8000 tokens for 95% of operations
- Retrieval latency < 100ms for vector search
- Compression ratio: 85-92% reduction
- No loss of critical information (tunnel dependencies, error context)

---

## Cross-Cutting Recommendations

### For AMP Platform

1. **Architecture**
   - Use stdio MCP server (simpler for single-user)
   - SQLite for state persistence
   - tmux for Linux shells, PowerShell remoting for Windows
   - Chisel as primary tunnel, Ligolo-ng as fallback

2. **Reliability**
   - Hybrid health monitoring (passive + active)
   - Automatic reconnection with exponential backoff
   - Cascade failure cleanup with dependency tracking
   - Session persistence (survive restarts)

3. **Security**
   - Token-based MCP authentication
   - Input validation to prevent injection
   - Resource limits (20 tunnels, 50 shells)
   - Audit logging (immutable SQLite log)
   - Docker isolation for all operations

4. **Performance**
   - Connection pooling (10 per tunnel)
   - Limit tunnel chains to 3 hops
   - Async execution for long operations
   - Stream output capture to prevent memory overflow

5. **User Experience**
   - Structured error messages with retry guidance
   - Idempotent operations where possible
   - Progressive disclosure (show relevant info only)
   - Clear tool naming (verb_noun pattern)

---

## Implementation Priorities

Based on research findings, the recommended implementation order is:

1. **Phase 1: Foundation**
   - SQLite schema and models
   - Chisel wrapper with basic lifecycle
   - Health monitoring (passive only)

2. **Phase 2: Reliability**
   - Automatic reconnection
   - Cascade failure handling
   - tmux backend for Linux shells

3. **Phase 3: Cross-Platform**
   - Ligolo-ng wrapper
   - PowerShell remoting for Windows
   - Windows-specific payload generation

4. **Phase 4: Intelligence**
   - Context engine with vector search
   - Progressive disclosure logic
   - Token budget management

5. **Phase 5: Polish**
   - MCP server with all tools
   - Web UI for topology visualization
   - Docker test environment

---

## Next Steps

1. Wait for context compression research to complete
2. Review all findings with user
3. Update PRD with technical decisions
4. Run `task.py start` to enter implementation phase
5. Begin Phase 1 development
