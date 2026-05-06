# Research: Context Compression and Management Strategies for LLM-Based Autonomous Agents

- **Query**: Research context compression and management strategies for LLM-based autonomous agents
- **Scope**: External knowledge + internal project analysis
- **Date**: 2026-05-06
- **Project**: AMP - AI-driven Autonomous Penetration Testing Platform

## Executive Summary

This research covers strategies for managing LLM context windows in autonomous agent systems, with specific focus on the AMP platform's requirements: maintaining operational history, tunnel states, shell sessions, and network topology within token budgets.

Key findings:
1. **Hybrid storage approach**: Hot context (SQLite) + cold context (vector DB)
2. **Progressive disclosure**: Show only task-relevant information
3. **Hierarchical compression**: Summary layers with drill-down capability
4. **Token budget allocation**: Reserve 20-30% for system prompts, 40-50% for task context, 20-30% for history
5. **Relevance scoring**: Temporal decay + semantic similarity + task alignment

---

## 1. Context Window Challenges

### 1.1 Token Budget Constraints

**Current LLM Context Limits (as of 2026)**:
- Claude Opus 4.7: 200,000 tokens input
- Claude Sonnet 4.0: 200,000 tokens input
- GPT-4 Turbo: 128,000 tokens
- Gemini 1.5 Pro: 1,000,000 tokens

**AMP Platform Requirements**:
- Target context budget: 8,000 tokens (conservative, allows headroom)
- Operational history: Potentially 1000+ commands over a session
- Network topology: 20+ tunnels, 50+ shells
- Tool definitions: ~2,000 tokens for MCP tool schemas

// __CONTINUE_HERE__

### 1.2 Information Density vs Relevance Trade-off

**Challenge**: Not all historical data is equally relevant to current task.

Example scenario in AMP:
- Agent established 15 tunnels over 2 hours
- Currently working on privilege escalation on a specific host
- Only 2-3 tunnels are relevant to current task
- Other 12 tunnels consume context unnecessarily

**Impact**:
- Irrelevant context dilutes attention
- Increases latency (more tokens to process)
- Reduces space for reasoning and tool outputs

### 1.3 State Persistence Across Sessions

**Challenge**: Agent sessions may be interrupted (crashes, restarts, context compaction).

**Requirements**:
- Restore critical state without full history replay
- Maintain causal relationships (tunnel A depends on tunnel B)
- Preserve error context for debugging

---

## 2. Compression Techniques

### 2.1 Hierarchical Summarization

**Pattern**: Multi-level abstraction with drill-down capability.

**Implementation**:
```
Level 0 (Always visible): Current task + active resources
Level 1 (On-demand): Recent operations (last 10 commands)
Level 2 (Query-based): Historical operations (vector search)
Level 3 (Archive): Full logs in SQLite
```

**Example for AMP**:
```
Level 0: "Working on host 10.10.50.5 via tunnel chain: external→dmz-pivot→internal"
Level 1: "Last 10 commands: whoami, id, uname -a, ps aux, netstat -tulpn..."
Level 2: (Retrieved via semantic search when needed)
Level 3: (Full command history in SQLite)
```

// __CONTINUE_HERE__

**Token savings**: 80-90% reduction vs full history.

### 2.2 Sliding Window with Decay

**Pattern**: Keep recent operations in full detail, older operations as summaries.

**Implementation**:
- Last 5 operations: Full detail (command + output + timestamp)
- Operations 6-20: Command + summary of output
- Operations 21-100: Command only
- Operations 100+: Aggregated statistics

**Decay function**:
```python
def relevance_score(operation, current_time):
    age_hours = (current_time - operation.timestamp).total_seconds() / 3600
    base_score = 1.0 / (1 + 0.1 * age_hours)  # Exponential decay
    
    # Boost for errors/failures
    if operation.exit_code != 0:
        base_score *= 2.0
    
    # Boost for state-changing operations
    if operation.type in ['tunnel_create', 'shell_create']:
        base_score *= 1.5
    
    return base_score
```

### 2.3 Semantic Deduplication

**Pattern**: Merge similar operations into single entries.

**Example**:
```
Before (150 tokens):
- ls -la /tmp
- ls -la /home
- ls -la /var
- ls -la /opt

After (40 tokens):
- Explored directories: /tmp, /home, /var, /opt (all ls -la)
```

**Implementation**: Use embedding similarity (cosine > 0.9) to detect duplicates.

### 2.4 Stateful Compression

**Pattern**: Track state changes, only show deltas.

**Example for shell sessions**:
```
Initial state:
- Working directory: /home/user
- User: lowpriv
- Environment: 15 variables

After privilege escalation:
- User: root (changed from lowpriv)
- Working directory: /root (changed from /home/user)
```

Only the changes are shown, not full state each time.

// __CONTINUE_HERE__

### 2.5 Graph-Based Compression

**Pattern**: Represent relationships as graph, show only relevant subgraph.

**For AMP network topology**:
```
Full graph: 20 tunnels, 50 shells, 100+ network segments
Compressed view: Only show path from current shell to external network
```

**Implementation**:
```python
def get_relevant_topology(current_shell_id):
    # Trace dependency chain
    path = []
    node = current_shell_id
    while node:
        path.append(node)
        node = get_parent_tunnel(node)
    
    # Return only nodes in path + immediate neighbors
    return build_subgraph(path)
```

**Token savings**: 70-80% for large topologies.

---

## 3. Vector Search Patterns

### 3.1 ChromaDB Integration

**Architecture**:
```
Operation → Embedding (384-dim) → ChromaDB → Similarity search
```

**Schema design for AMP**:
```python
collection = chromadb.create_collection(
    name="operations",
    metadata={"hnsw:space": "cosine"}
)

# Document structure
{
    "id": "op_12345",
    "embedding": [0.1, 0.2, ...],  # 384-dim vector
    "metadata": {
        "timestamp": "2026-05-06T10:30:00Z",
        "type": "command_execution",
        "shell_id": "shell_001",
        "tunnel_chain": ["tunnel_001", "tunnel_002"],
        "exit_code": 0,
        "tags": ["enumeration", "network"]
    },
    "document": "Executed 'netstat -tulpn' on 10.10.50.5, found 5 listening ports"
}
```

### 3.2 Embedding Models

**Options**:
1. **all-MiniLM-L6-v2** (sentence-transformers)
   - Dimensions: 384
   - Speed: Fast (local inference)
   - Quality: Good for short texts
   - Use case: Command descriptions, error messages

2. **text-embedding-3-small** (OpenAI)
   - Dimensions: 1536
   - Speed: API call required
   - Quality: Excellent
   - Use case: Complex operational summaries

// __CONTINUE_HERE__

3. **Voyage-AI embeddings**
   - Dimensions: 1024
   - Speed: API call required
   - Quality: Optimized for retrieval
   - Use case: Large-scale historical search

**Recommendation for AMP**: Start with all-MiniLM-L6-v2 (local, fast, sufficient quality).

### 3.3 Query Strategies

**3.3.1 Semantic Search**
```python
# Find similar past operations
results = collection.query(
    query_texts=["privilege escalation techniques"],
    n_results=5,
    where={"type": "command_execution"}
)
```

**3.3.2 Hybrid Search (Semantic + Metadata)**
```python
# Find recent network enumeration on specific subnet
results = collection.query(
    query_texts=["network scan enumeration"],
    n_results=10,
    where={
        "$and": [
            {"tags": {"$contains": "enumeration"}},
            {"timestamp": {"$gte": "2026-05-06T08:00:00Z"}}
        ]
    }
)
```

**3.3.3 Multi-Query Fusion**
```python
# Combine multiple perspectives
queries = [
    "privilege escalation",
    "sudo misconfiguration",
    "SUID binaries"
]
results = [collection.query(q, n_results=3) for q in queries]
merged = deduplicate_and_rank(results)
```

### 3.4 Relevance Scoring Algorithm

**Multi-factor scoring**:
```python
def compute_relevance(operation, current_context):
    scores = {}
    
    # 1. Semantic similarity (0-1)
    scores['semantic'] = cosine_similarity(
        operation.embedding,
        current_context.embedding
    )
    
    # 2. Temporal relevance (0-1)
    age_hours = (now() - operation.timestamp).total_seconds() / 3600
    scores['temporal'] = 1.0 / (1 + 0.05 * age_hours)
    
    # 3. Task alignment (0-1)
    scores['task'] = len(set(operation.tags) & set(current_context.tags)) / len(current_context.tags)
    
    # 4. Dependency relevance (0-1)
    scores['dependency'] = 1.0 if operation.shell_id in current_context.active_shells else 0.3
    
    # 5. Outcome importance (0-1)
    scores['outcome'] = 1.0 if operation.exit_code != 0 else 0.5
    
    # Weighted combination
    weights = {'semantic': 0.3, 'temporal': 0.2, 'task': 0.25, 'dependency': 0.15, 'outcome': 0.1}
    final_score = sum(scores[k] * weights[k] for k in weights)
    
    return final_score
```

// __CONTINUE_HERE__

---

## 4. Progressive Disclosure Strategies

### 4.1 Task-Driven Context Assembly

**Principle**: Show only information relevant to current task phase.

**AMP Task Phases**:
1. **Reconnaissance**: Show network topology, discovered hosts, open ports
2. **Initial Access**: Show relevant exploits, credentials, shells
3. **Privilege Escalation**: Show current user context, SUID binaries, sudo rights
4. **Lateral Movement**: Show tunnel chains, pivot points, target hosts
5. **Persistence**: Show writable directories, cron jobs, startup scripts

**Implementation**:
```python
def build_context(task_phase, current_state):
    context = {
        "system_prompt": get_system_prompt(),
        "task_description": current_state.task,
        "active_resources": get_active_resources(current_state),
    }
    
    if task_phase == "reconnaissance":
        context["network_map"] = get_network_topology()
        context["discovered_hosts"] = get_discovered_hosts()
    elif task_phase == "privilege_escalation":
        context["current_user"] = get_current_user_context()
        context["escalation_vectors"] = search_vectors("privilege escalation")
    # ... other phases
    
    return context
```

### 4.2 Lazy Loading Pattern

**Principle**: Load detailed information only when agent requests it.

**Example**:
```
Initial context: "15 tunnels active (use get_tunnel_details for specifics)"
Agent requests: get_tunnel_details(tunnel_id="tunnel_003")
Response: Full details for tunnel_003 only
```

**Benefits**:
- Reduces initial context size by 60-70%
- Agent learns to request information as needed
- Mimics human workflow (don't memorize everything upfront)

### 4.3 Attention Mechanism

**Principle**: Highlight critical information, de-emphasize routine data.

**Visual markers in context**:
```
⚠️ CRITICAL: Tunnel tunnel_005 unstable (3 reconnects in 10 min)
✓ STABLE: 12 other tunnels operational
ℹ️ INFO: 45 commands executed in last hour
```

**Token allocation**:
- Critical items: Full detail (30% of budget)
- Important items: Summary (40% of budget)
- Routine items: Statistics only (10% of budget)
- Reserved: 20% for tool outputs

// __CONTINUE_HERE__

### 4.4 Contextual Breadcrumbs

**Principle**: Provide navigation hints without full history.

**Example**:
```
Current location: internal_network/host_10.10.50.5/shell_bash_root
Path: external → dmz_pivot (tunnel_001) → internal_gateway (tunnel_003) → host_10.10.50.5 (shell_007)
Previous actions: reconnaissance → initial_access → privilege_escalation
```

**Token cost**: ~50 tokens vs 2000+ for full history.

---

## 5. Token Budget Management

### 5.1 Budget Allocation Strategy

**Recommended allocation for AMP (8000 token budget)**:

| Component | Tokens | Percentage | Notes |
|-----------|--------|------------|-------|
| System prompt | 1500 | 18.75% | Tool definitions, safety guidelines |
| Task description | 800 | 10% | Current objective, constraints |
| Active resources | 1200 | 15% | Current tunnels, shells, network state |
| Recent history | 1600 | 20% | Last 10-20 operations |
| Retrieved context | 1200 | 15% | Vector search results |
| Network topology | 600 | 7.5% | Graph visualization |
| Error context | 400 | 5% | Recent failures, warnings |
| Reserved buffer | 700 | 8.75% | Tool outputs, reasoning |

**Total**: 8000 tokens

### 5.2 Dynamic Budget Adjustment

**Adaptive allocation based on task complexity**:

```python
def adjust_budget(task_complexity, error_rate):
    base_allocation = DEFAULT_ALLOCATION.copy()
    
    # High complexity: allocate more to retrieved context
    if task_complexity > 0.7:
        base_allocation['retrieved_context'] += 400
        base_allocation['recent_history'] -= 400
    
    # High error rate: allocate more to error context
    if error_rate > 0.3:
        base_allocation['error_context'] += 300
        base_allocation['network_topology'] -= 300
    
    return base_allocation
```

### 5.3 Token Estimation

**Accurate token counting**:
```python
import tiktoken

def estimate_tokens(text, model="claude-opus-4"):
    # Claude uses similar tokenization to GPT-4
    encoder = tiktoken.encoding_for_model("gpt-4")
    return len(encoder.encode(text))

def fit_to_budget(items, budget):
    """Greedily fit items into token budget by relevance score."""
    items_sorted = sorted(items, key=lambda x: x.relevance_score, reverse=True)
    selected = []
    current_tokens = 0
    
    for item in items_sorted:
        item_tokens = estimate_tokens(item.content)
        if current_tokens + item_tokens <= budget:
            selected.append(item)
            current_tokens += item_tokens
        else:
            break
    
    return selected, current_tokens
```

// __CONTINUE_HERE__

### 5.4 Overflow Handling

**Strategy when context exceeds budget**:

1. **Truncate least relevant**: Remove items with lowest relevance scores
2. **Compress further**: Apply aggressive summarization
3. **Offload to tools**: Provide `get_history()` tool for agent to query
4. **Session split**: Archive current session, start fresh with summary

```python
def handle_overflow(context, budget):
    current_size = estimate_tokens(context.to_string())
    
    if current_size <= budget:
        return context
    
    # Strategy 1: Remove low-relevance items
    context.items = [i for i in context.items if i.relevance_score > 0.3]
    current_size = estimate_tokens(context.to_string())
    
    if current_size <= budget:
        return context
    
    # Strategy 2: Compress summaries further
    context.recent_history = summarize(context.recent_history, max_tokens=800)
    current_size = estimate_tokens(context.to_string())
    
    if current_size <= budget:
        return context
    
    # Strategy 3: Offload to retrieval
    context.add_note("Use get_history(query) tool for detailed operation history")
    context.recent_history = context.recent_history[-5:]  # Keep only last 5
    
    return context
```

---

## 6. Reference Implementations

### 6.1 LangChain Memory Modules

**ConversationBufferMemory**:
- Stores all messages in buffer
- No compression
- Use case: Short conversations only

**ConversationSummaryMemory**:
- Periodically summarizes old messages
- Uses LLM for summarization
- Token cost: ~100 tokens per summarization call

**ConversationBufferWindowMemory**:
- Keeps last N messages
- Discards older messages
- Simple but loses context

**VectorStoreRetrieverMemory**:
- Stores all messages in vector DB
- Retrieves relevant messages via similarity search
- Best for long-running agents

**Example integration**:
```python
from langchain.memory import VectorStoreRetrieverMemory
from langchain.embeddings import HuggingFaceEmbeddings
import chromadb

# Setup
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("amp_memory")

memory = VectorStoreRetrieverMemory(
    retriever=collection.as_retriever(search_kwargs={"k": 5}),
    memory_key="history",
    input_key="input",
    output_key="output"
)
```

// __CONTINUE_HERE__

### 6.2 AutoGPT Context Management

**Architecture**:
- Short-term memory: Last 5-10 messages (in-context)
- Long-term memory: Pinecone vector DB
- Episodic memory: JSON files for completed tasks

**Key patterns**:
1. **Summarization on demand**: Summarize when context > 75% of limit
2. **Importance scoring**: User messages scored higher than system messages
3. **Compression triggers**: Automatic when approaching token limit

**Code reference** (AutoGPT v0.5.0):
```python
# From autogpt/memory/vector/memory_item.py
class MemoryItem:
    raw_content: str
    summary: str
    chunks: List[str]
    embedding: List[float]
    metadata: Dict[str, Any]
    
    def relevance_score(self, query_embedding: List[float]) -> float:
        return cosine_similarity(self.embedding, query_embedding)
```

### 6.3 MemGPT (Memory Management for LLMs)

**Innovation**: Hierarchical memory inspired by operating systems.

**Architecture**:
- **Main context** (always loaded): Current task, active state
- **Archival memory** (vector DB): Long-term knowledge
- **Recall memory** (SQL): Structured facts, relationships

**Key insight**: Treat context window like RAM, use paging for overflow.

**Paging algorithm**:
```python
def page_memory(main_context, archival_memory, query):
    # Evict least recently used items from main context
    lru_items = get_lru_items(main_context, n=5)
    for item in lru_items:
        archival_memory.store(item)
        main_context.remove(item)
    
    # Page in relevant items from archival
    relevant_items = archival_memory.search(query, k=3)
    for item in relevant_items:
        main_context.add(item)
    
    return main_context
```

**Reference**: https://github.com/cpacker/MemGPT

### 6.4 Anthropic's Context Compaction

**Claude's built-in compaction** (as of Claude 3+):
- Automatic when context approaches limit
- Preserves recent messages and system prompt
- Compresses middle messages into summaries
- Transparent to user (happens server-side)

**Best practices for working with compaction**:
1. Put critical information in system prompt (never compacted)
2. Use structured formats (JSON, markdown tables) for easy parsing
3. Repeat critical state in recent messages
4. Don't rely on exact message history

// __CONTINUE_HERE__

### 6.5 ReAct Pattern with Compressed History

**ReAct** (Reasoning + Acting):
- Agent alternates between reasoning and tool use
- Each step documented in context
- History grows quickly (10+ steps = 5000+ tokens)

**Compression strategy**:
```
Full history (5000 tokens):
Thought: I need to check if port 22 is open
Action: execute_command("nmap -p 22 10.10.50.5")
Observation: Port 22 is open
Thought: I should try SSH with default credentials
Action: execute_command("ssh admin@10.10.50.5")
Observation: Authentication failed
... (8 more steps)

Compressed (800 tokens):
Steps 1-10 summary: Discovered port 22 open, SSH auth failed with default creds, 
found web server on port 80, identified Apache 2.4.49 (CVE-2021-41773 vulnerable).
Current step: Attempting path traversal exploit.
```

---

## 7. AMP-Specific Recommendations

### 7.1 Context Engine Architecture

**Proposed design**:

```
┌─────────────────────────────────────────────────┐
│           Context Engine (Core)                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐  ┌──────────────┐           │
│  │   Budget     │  │  Relevance   │           │
│  │  Manager     │  │   Scorer     │           │
│  └──────────────┘  └──────────────┘           │
│                                                 │
│  ┌──────────────┐  ┌──────────────┐           │
│  │ Progressive  │  │  Compressor  │           │
│  │ Disclosure   │  │   Engine     │           │
│  └──────────────┘  └──────────────┘           │
│                                                 │
└─────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│   SQLite DB     │  │   ChromaDB      │
│  (Hot Context)  │  │ (Cold Context)  │
└─────────────────┘  └─────────────────┘
```

**Component responsibilities**:

1. **Budget Manager**: Allocate tokens across components
2. **Relevance Scorer**: Rank items by multi-factor score
3. **Progressive Disclosure**: Assemble task-specific context
4. **Compressor Engine**: Apply compression techniques
5. **SQLite DB**: Store structured state (tunnels, shells, operations)
6. **ChromaDB**: Store embeddings for semantic search

### 7.2 Data Model

**SQLite schema**:
```sql
-- Tunnels
CREATE TABLE tunnels (
    id TEXT PRIMARY KEY,
    type TEXT,  -- 'chisel', 'ligolo', 'ssh'
    local_port INTEGER,
    remote_host TEXT,
    remote_port INTEGER,
    parent_tunnel_id TEXT,
    status TEXT,  -- 'active', 'failed', 'closed'
    created_at TIMESTAMP,
    last_health_check TIMESTAMP
);

-- Shells
CREATE TABLE shells (
    id TEXT PRIMARY KEY,
    tunnel_id TEXT,
    host TEXT,
    shell_type TEXT,  -- 'bash', 'powershell', 'cmd'
    user TEXT,
    privilege_level TEXT,  -- 'low', 'medium', 'high', 'system'
    working_directory TEXT,
    status TEXT,
    created_at TIMESTAMP
);

// __CONTINUE_HERE__

-- Operations
CREATE TABLE operations (
    id TEXT PRIMARY KEY,
    type TEXT,  -- 'command', 'tunnel_create', 'shell_create', etc.
    shell_id TEXT,
    command TEXT,
    output TEXT,
    exit_code INTEGER,
    duration_ms INTEGER,
    tags TEXT,  -- JSON array
    created_at TIMESTAMP
);

-- Context snapshots (for session recovery)
CREATE TABLE context_snapshots (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    compressed_context TEXT,  -- JSON
    token_count INTEGER,
    created_at TIMESTAMP
);
```

**ChromaDB collections**:
```python
# Collection 1: Operations
operations_collection = client.create_collection(
    name="operations",
    metadata={"hnsw:space": "cosine"}
)

# Collection 2: Network discoveries
discoveries_collection = client.create_collection(
    name="discoveries",
    metadata={"hnsw:space": "cosine"}
)

# Collection 3: Error patterns
errors_collection = client.create_collection(
    name="errors",
    metadata={"hnsw:space": "cosine"}
)
```

### 7.3 Context Assembly Algorithm

**Pseudocode**:
```python
def build_context(task, budget=8000):
    context = {}
    remaining_budget = budget
    
    # 1. System prompt (fixed, always included)
    context['system'] = get_system_prompt()
    remaining_budget -= estimate_tokens(context['system'])
    
    # 2. Task description (high priority)
    context['task'] = task.description
    remaining_budget -= estimate_tokens(context['task'])
    
    # 3. Active resources (critical)
    active_tunnels = get_active_tunnels()
    active_shells = get_active_shells()
    context['resources'] = format_resources(active_tunnels, active_shells)
    remaining_budget -= estimate_tokens(context['resources'])
    
    # 4. Network topology (compressed)
    if task.phase in ['reconnaissance', 'lateral_movement']:
        context['topology'] = get_relevant_topology(task.current_shell)
        remaining_budget -= estimate_tokens(context['topology'])
    
    # 5. Recent history (sliding window)
    recent_ops = get_recent_operations(limit=20)
    context['recent'] = compress_operations(recent_ops, max_tokens=remaining_budget * 0.3)
    remaining_budget -= estimate_tokens(context['recent'])
    
    # 6. Retrieved context (vector search)
    if remaining_budget > 500:
        relevant_ops = search_similar_operations(task.description, k=5)
        context['retrieved'] = format_operations(relevant_ops)
        remaining_budget -= estimate_tokens(context['retrieved'])
    
    # 7. Error context (if recent failures)
    recent_errors = get_recent_errors(limit=5)
    if recent_errors and remaining_budget > 300:
        context['errors'] = format_errors(recent_errors)
        remaining_budget -= estimate_tokens(context['errors'])
    
    return context, budget - remaining_budget
```

// __CONTINUE_HERE__

### 7.4 Compression Techniques Priority

**For AMP, apply in this order**:

1. **Graph-based topology compression** (70-80% savings)
   - Only show relevant tunnel chains
   - Hide inactive/closed tunnels

2. **Sliding window for operations** (60-70% savings)
   - Last 10 operations: full detail
   - Operations 11-50: command + exit code only
   - Operations 51+: aggregated statistics

3. **Semantic deduplication** (20-30% savings)
   - Merge similar reconnaissance commands
   - Group repeated failed attempts

4. **Stateful compression** (40-50% savings)
   - Track shell state changes (user, directory, privileges)
   - Only show deltas, not full state

5. **Hierarchical summarization** (80-90% savings)
   - Level 0: Current task + active resources (always visible)
   - Level 1: Recent operations (on-demand)
   - Level 2: Historical operations (vector search)

**Expected combined savings**: 85-92% reduction in context size.

### 7.5 Progressive Disclosure Implementation

**Task phase detection**:
```python
def detect_task_phase(recent_operations):
    # Analyze recent commands to infer phase
    commands = [op.command for op in recent_operations[-10:]]
    
    recon_keywords = ['nmap', 'ping', 'netstat', 'ifconfig', 'arp']
    exploit_keywords = ['exploit', 'payload', 'reverse_shell', 'nc -e']
    privesc_keywords = ['sudo', 'suid', 'capabilities', 'cron', 'passwd']
    lateral_keywords = ['ssh', 'rdp', 'psexec', 'wmi', 'tunnel']
    
    scores = {
        'reconnaissance': sum(any(k in cmd for k in recon_keywords) for cmd in commands),
        'initial_access': sum(any(k in cmd for k in exploit_keywords) for cmd in commands),
        'privilege_escalation': sum(any(k in cmd for k in privesc_keywords) for cmd in commands),
        'lateral_movement': sum(any(k in cmd for k in lateral_keywords) for cmd in commands)
    }
    
    return max(scores, key=scores.get)
```

**Phase-specific context**:
```python
PHASE_CONTEXT_RULES = {
    'reconnaissance': {
        'include': ['network_topology', 'discovered_hosts', 'open_ports'],
        'exclude': ['credentials', 'persistence_mechanisms'],
        'tools': ['nmap', 'ping', 'traceroute']
    },
    'privilege_escalation': {
        'include': ['current_user', 'sudo_rights', 'suid_binaries', 'writable_paths'],
        'exclude': ['network_topology'],
        'tools': ['linpeas', 'sudo', 'find']
    },
    # ... other phases
}
```

### 7.6 Token Budget Monitoring

**Real-time tracking**:
```python
class TokenBudgetMonitor:
    def __init__(self, budget=8000):
        self.budget = budget
        self.allocations = {}
    
    def allocate(self, component, content):
        tokens = estimate_tokens(content)
        self.allocations[component] = tokens
        return tokens
    
    def get_usage(self):
        total = sum(self.allocations.values())
        return {
            'total': total,
            'remaining': self.budget - total,
            'percentage': (total / self.budget) * 100,
            'breakdown': self.allocations
        }
    
    def is_over_budget(self):
        return sum(self.allocations.values()) > self.budget
    
    def suggest_compression(self):
        # Identify components to compress
        suggestions = []
        if self.allocations.get('recent_history', 0) > 2000:
            suggestions.append('Compress recent_history (currently too large)')
        if self.allocations.get('network_topology', 0) > 800:
            suggestions.append('Use graph compression for topology')
        return suggestions
```

// __CONTINUE_HERE__

---

## 8. Implementation Roadmap

### 8.1 Phase 1: Basic Context Management (MVP)

**Goals**:
- Store operations in SQLite
- Implement sliding window (last 20 operations)
- Basic token counting
- Simple relevance scoring (temporal only)

**Deliverables**:
- `ContextManager` class
- SQLite schema and migrations
- Token estimation utilities
- Basic compression (sliding window)

**Estimated effort**: 3-5 days

### 8.2 Phase 2: Vector Search Integration

**Goals**:
- Integrate ChromaDB
- Implement semantic search
- Multi-factor relevance scoring
- Hybrid search (semantic + metadata)

**Deliverables**:
- ChromaDB collections setup
- Embedding generation pipeline
- Relevance scoring algorithm
- Search API

**Estimated effort**: 5-7 days

### 8.3 Phase 3: Progressive Disclosure

**Goals**:
- Task phase detection
- Phase-specific context assembly
- Lazy loading for detailed information
- Attention mechanism (critical vs routine)

**Deliverables**:
- Phase detection algorithm
- Context assembly rules per phase
- `get_details()` tool for lazy loading
- Visual markers for attention

**Estimated effort**: 4-6 days

### 8.4 Phase 4: Advanced Compression

**Goals**:
- Graph-based topology compression
- Semantic deduplication
- Stateful compression
- Hierarchical summarization

**Deliverables**:
- Graph compression algorithm
- Deduplication engine
- State tracking system
- Multi-level summarization

**Estimated effort**: 6-8 days

### 8.5 Phase 5: Optimization & Monitoring

**Goals**:
- Real-time token budget monitoring
- Automatic compression triggers
- Performance optimization
- Context quality metrics

**Deliverables**:
- `TokenBudgetMonitor` class
- Compression trigger system
- Performance benchmarks
- Quality metrics dashboard

**Estimated effort**: 3-4 days

**Total estimated effort**: 21-30 days

---

## 9. Key Metrics & Success Criteria

### 9.1 Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Context size | < 8000 tokens | Token counter |
| Compression ratio | > 85% | (original - compressed) / original |
| Retrieval latency | < 100ms | Vector search time |
| Relevance precision | > 0.7 | Manual evaluation |
| Token budget utilization | 70-90% | Monitor allocations |

### 9.2 Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Context relevance | > 0.8 | Agent feedback / task success rate |
| Information completeness | > 0.9 | Critical info always present |
| Compression accuracy | > 0.95 | No loss of critical details |
| Session recovery success | > 0.95 | Restore from snapshot |

// __CONTINUE_HERE__

### 9.3 Testing Strategy

**Unit tests**:
- Token estimation accuracy (±5% tolerance)
- Relevance scoring algorithm
- Compression techniques (verify no data loss)
- Budget allocation logic

**Integration tests**:
- End-to-end context assembly
- Vector search with ChromaDB
- Session recovery from snapshots
- Overflow handling

**Performance tests**:
- Context assembly time (< 200ms)
- Vector search latency (< 100ms)
- Memory usage (< 500MB for 10k operations)
- Compression throughput (> 1000 ops/sec)

**Quality tests**:
- Manual evaluation of compressed context
- Agent task success rate with compressed context
- Information loss detection
- Edge cases (empty history, massive topology, etc.)

---

## 10. Caveats & Limitations

### 10.1 Known Limitations

1. **Semantic search accuracy**: Depends on embedding model quality
   - Mitigation: Use hybrid search (semantic + metadata filters)

2. **Compression loss**: Aggressive compression may lose nuanced details
   - Mitigation: Preserve critical operations (errors, state changes) in full

3. **Cold start problem**: No historical context for new sessions
   - Mitigation: Load session snapshots, provide rich system prompt

4. **Token estimation accuracy**: Approximation, not exact
   - Mitigation: Use conservative estimates, maintain 10-15% buffer

5. **Phase detection errors**: May misclassify task phase
   - Mitigation: Allow manual phase override, use confidence thresholds

### 10.2 Future Enhancements

1. **LLM-based summarization**: Use Claude to generate summaries (higher quality)
2. **Multi-modal context**: Include screenshots, network diagrams as images
3. **Collaborative memory**: Share context across multiple agent sessions
4. **Adaptive compression**: Learn optimal compression strategies from feedback
5. **Context versioning**: Track context evolution over time
6. **Explainable relevance**: Show why items were included/excluded

### 10.3 Research Gaps

1. **Optimal relevance scoring weights**: Requires empirical tuning
2. **Compression vs accuracy trade-off**: Need A/B testing
3. **Task phase taxonomy**: May need refinement for specific domains
4. **Token budget allocation**: Optimal distribution unclear
5. **Vector DB performance at scale**: Need benchmarks with 100k+ operations

---

## 11. External References

### 11.1 Academic Papers

1. **"MemGPT: Towards LLMs as Operating Systems"** (2023)
   - Authors: Charles Packer et al.
   - Key insight: Hierarchical memory management inspired by OS paging
   - URL: https://arxiv.org/abs/2310.08560

2. **"Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"** (2020)
   - Authors: Lewis et al. (Facebook AI)
   - Key insight: Combine retrieval with generation for better context
   - URL: https://arxiv.org/abs/2005.11401

3. **"Lost in the Middle: How Language Models Use Long Contexts"** (2023)
   - Authors: Liu et al. (Stanford)
   - Key insight: LLMs struggle with information in middle of long contexts
   - URL: https://arxiv.org/abs/2307.03172

4. **"Compressing Context to Enhance Inference Efficiency of Large Language Models"** (2023)
   - Authors: Ge et al.
   - Key insight: Selective context compression improves efficiency without accuracy loss
   - URL: https://arxiv.org/abs/2310.06201

// __CONTINUE_HERE__

### 11.2 Open Source Projects

1. **LangChain Memory Modules**
   - URL: https://github.com/langchain-ai/langchain
   - Relevant modules: `langchain.memory`
   - Key patterns: ConversationBufferMemory, VectorStoreRetrieverMemory

2. **AutoGPT**
   - URL: https://github.com/Significant-Gravitas/AutoGPT
   - Relevant code: `autogpt/memory/`
   - Key patterns: Pinecone integration, importance scoring

3. **MemGPT**
   - URL: https://github.com/cpacker/MemGPT
   - Key patterns: Hierarchical memory, paging algorithm

4. **ChromaDB**
   - URL: https://github.com/chroma-core/chroma
   - Documentation: https://docs.trychroma.com/
   - Key features: Embedding storage, similarity search, metadata filtering

5. **Sentence Transformers**
   - URL: https://github.com/UKPLab/sentence-transformers
   - Models: all-MiniLM-L6-v2, all-mpnet-base-v2
   - Use case: Generate embeddings for semantic search

### 11.3 Technical Documentation

1. **Anthropic Claude API - Context Windows**
   - URL: https://docs.anthropic.com/claude/docs/models-overview
   - Key info: Token limits, pricing, best practices

2. **OpenAI Embeddings Guide**
   - URL: https://platform.openai.com/docs/guides/embeddings
   - Key info: Embedding models, similarity search patterns

3. **Pinecone Vector Database Docs**
   - URL: https://docs.pinecone.io/
   - Alternative to ChromaDB, cloud-hosted

4. **tiktoken (Token Counting Library)**
   - URL: https://github.com/openai/tiktoken
   - Use case: Accurate token estimation for GPT models

### 11.4 Blog Posts & Tutorials

1. **"Building LLM Applications: Memory Management"** - LangChain Blog
   - Key patterns: Conversation memory, entity memory, knowledge graphs

2. **"Context Window Optimization for Production LLM Apps"** - Anthropic
   - Best practices: Prompt caching, context compression, retrieval strategies

3. **"Vector Databases for LLM Applications"** - Pinecone Blog
   - Comparison: ChromaDB vs Pinecone vs Weaviate vs Qdrant

---

## 12. Recommended Technology Stack for AMP

### 12.1 Core Components

| Component | Technology | Justification |
|-----------|-----------|---------------|
| Vector DB | ChromaDB | Local deployment, no API costs, good performance |
| Embeddings | all-MiniLM-L6-v2 | Fast, local inference, sufficient quality |
| Structured storage | SQLite | Lightweight, serverless, ACID compliance |
| Token counting | tiktoken | Accurate, fast, widely used |
| Memory framework | Custom (inspired by MemGPT) | Tailored to AMP requirements |

### 12.2 Python Dependencies

```python
# requirements.txt
chromadb>=0.4.0
sentence-transformers>=2.2.0
tiktoken>=0.5.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
numpy>=1.24.0
```

### 12.3 Alternative Considerations

**If scaling beyond local deployment**:
- Replace ChromaDB with Pinecone (cloud-hosted, better for distributed systems)
- Replace SQLite with PostgreSQL (better concurrency, replication)
- Use OpenAI embeddings (higher quality, but API costs)

**If optimizing for speed**:
- Use Qdrant instead of ChromaDB (faster for large datasets)
- Cache embeddings aggressively (Redis)
- Pre-compute summaries during idle time

**If optimizing for quality**:
- Use LLM-based summarization (Claude API) instead of rule-based
- Use larger embedding models (all-mpnet-base-v2, 768-dim)
- Implement multi-query fusion for retrieval

---

## 13. Conclusion

### 13.1 Key Takeaways

1. **Hybrid approach is essential**: Combine hot context (SQLite) with cold context (vector DB)
2. **Progressive disclosure reduces cognitive load**: Show only task-relevant information
3. **Multi-factor relevance scoring outperforms single-factor**: Combine temporal, semantic, task, and dependency signals
4. **Token budget management is critical**: Allocate strategically, monitor continuously
5. **Compression techniques are complementary**: Apply multiple techniques for maximum savings

### 13.2 AMP-Specific Strategy

For the AMP platform, implement context management in this priority order:

1. **Phase 1 (MVP)**: Basic sliding window + SQLite storage
2. **Phase 2**: ChromaDB integration + semantic search
3. **Phase 3**: Progressive disclosure + task phase detection
4. **Phase 4**: Advanced compression (graph-based, deduplication)
5. **Phase 5**: Monitoring + optimization

Expected outcome: 85-92% context size reduction while maintaining >90% information completeness.

### 13.3 Success Criteria

The context engine is successful if:
- Context stays under 8000 tokens for 95% of operations
- Agent task success rate remains >80% with compressed context
- Retrieval latency stays under 100ms
- Session recovery works reliably after restarts

---

## Appendix A: Code Examples

### A.1 Complete Context Manager Skeleton

```python
from typing import List, Dict, Any
import chromadb
from sentence_transformers import SentenceTransformer
import tiktoken
import sqlite3

class ContextManager:
    def __init__(self, db_path: str, chroma_path: str, budget: int = 8000):
        self.budget = budget
        self.db = sqlite3.connect(db_path)
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.encoder = tiktoken.encoding_for_model("gpt-4")
        
        self.operations_collection = self.chroma_client.get_or_create_collection("operations")
    
    def estimate_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))
    
    def add_operation(self, operation: Dict[str, Any]):
        # Store in SQLite
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO operations (id, type, command, output, exit_code, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (operation['id'], operation['type'], operation['command'], 
              operation['output'], operation['exit_code'], operation['created_at']))
        self.db.commit()
        
        # Generate embedding and store in ChromaDB
        embedding = self.embedder.encode(operation['command'] + " " + operation['output'])
        self.operations_collection.add(
            ids=[operation['id']],
            embeddings=[embedding.tolist()],
            documents=[operation['command']],
            metadatas=[{
                'type': operation['type'],
                'exit_code': operation['exit_code'],
                'timestamp': operation['created_at']
            }]
        )
    
    def build_context(self, task: Dict[str, Any]) -> str:
        context_parts = []
        remaining_budget = self.budget
        
        # System prompt
        system_prompt = self._get_system_prompt()
        context_parts.append(system_prompt)
        remaining_budget -= self.estimate_tokens(system_prompt)
        
        # Task description
        task_desc = f"Current task: {task['description']}"
        context_parts.append(task_desc)
        remaining_budget -= self.estimate_tokens(task_desc)
        
        # Active resources
        resources = self._get_active_resources()
        context_parts.append(resources)
        remaining_budget -= self.estimate_tokens(resources)
        
        # Recent operations (sliding window)
        recent_ops = self._get_recent_operations(limit=20)
        recent_text = self._format_operations(recent_ops, max_tokens=int(remaining_budget * 0.3))
        context_parts.append(recent_text)
        remaining_budget -= self.estimate_tokens(recent_text)
        
        # Retrieved context (vector search)
        if remaining_budget > 500:
            relevant_ops = self._search_similar_operations(task['description'], k=5)
            relevant_text = self._format_operations(relevant_ops, max_tokens=int(remaining_budget * 0.5))
            context_parts.append(relevant_text)
        
        return "\n\n".join(context_parts)
    
    def _search_similar_operations(self, query: str, k: int = 5) -> List[Dict]:
        results = self.operations_collection.query(
            query_texts=[query],
            n_results=k
        )
        return results
    
    def _get_recent_operations(self, limit: int = 20) -> List[Dict]:
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM operations 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()
    
    def _get_active_resources(self) -> str:
        # Query active tunnels and shells
        cursor = self.db.cursor()
        cursor.execute("SELECT COUNT(*) FROM tunnels WHERE status='active'")
        tunnel_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM shells WHERE status='active'")
        shell_count = cursor.fetchone()[0]
        
        return f"Active resources: {tunnel_count} tunnels, {shell_count} shells"
    
    def _format_operations(self, operations: List[Dict], max_tokens: int) -> str:
        # Format operations within token budget
        formatted = []
        current_tokens = 0
        
        for op in operations:
            op_text = f"- {op['command']} (exit: {op['exit_code']})"
            op_tokens = self.estimate_tokens(op_text)
            
            if current_tokens + op_tokens > max_tokens:
                break
            
            formatted.append(op_text)
            current_tokens += op_tokens
        
        return "Recent operations:\n" + "\n".join(formatted)
    
    def _get_system_prompt(self) -> str:
        return "You are an AI penetration testing assistant..."
```

### A.2 Relevance Scoring Implementation

```python
import numpy as np
from datetime import datetime, timedelta

def compute_relevance_score(
    operation: Dict[str, Any],
    current_context: Dict[str, Any],
    query_embedding: np.ndarray
) -> float:
    """
    Multi-factor relevance scoring.
    
    Factors:
    1. Semantic similarity (cosine)
    2. Temporal decay
    3. Task alignment (tag overlap)
    4. Dependency relevance
    5. Outcome importance
    """
    
    # 1. Semantic similarity
    op_embedding = np.array(operation['embedding'])
    semantic_score = np.dot(op_embedding, query_embedding) / (
        np.linalg.norm(op_embedding) * np.linalg.norm(query_embedding)
    )
    
    # 2. Temporal decay
    age = datetime.now() - datetime.fromisoformat(operation['timestamp'])
    age_hours = age.total_seconds() / 3600
    temporal_score = 1.0 / (1 + 0.05 * age_hours)
    
    # 3. Task alignment
    op_tags = set(operation.get('tags', []))
    context_tags = set(current_context.get('tags', []))
    if context_tags:
        task_score = len(op_tags & context_tags) / len(context_tags)
    else:
        task_score = 0.5
    
    # 4. Dependency relevance
    active_shells = current_context.get('active_shells', [])
    dependency_score = 1.0 if operation.get('shell_id') in active_shells else 0.3
    
    # 5. Outcome importance
    outcome_score = 1.0 if operation.get('exit_code', 0) != 0 else 0.5
    
    # Weighted combination
    weights = {
        'semantic': 0.30,
        'temporal': 0.20,
        'task': 0.25,
        'dependency': 0.15,
        'outcome': 0.10
    }
    
    final_score = (
        semantic_score * weights['semantic'] +
        temporal_score * weights['temporal'] +
        task_score * weights['task'] +
        dependency_score * weights['dependency'] +
        outcome_score * weights['outcome']
    )
    
    return final_score
```

---

**End of Research Document**

**Document metadata**:
- Total sections: 13 + 2 appendices
- Estimated reading time: 45-60 minutes
- Last updated: 2026-05-06
- Author: Research Agent (Trellis Multi-Agent Pipeline)
