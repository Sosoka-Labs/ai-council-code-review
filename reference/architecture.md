# AI Code Review System — Brainstorm & Architecture Design

## Reference Repo Analysis: `AleksandrFurmenkovOfficial/ai-code-review`

### What It Does Well
| Feature | Implementation |
|---------|---------------|
| **Multi-provider support** | OpenAI, Anthropic, Google, DeepSeek, X, Perplexity — each as a subclass of `BaseAIAgent` |
| **Tool-calling pattern** | LLM gets 3 tools: `get_file_content`, `add_review_comment`, `mark_as_done` — iterative loop until done |
| **Incremental review** | Tracks last-reviewed commit in PR comments; only re-reviews changes since then |
| **File caching** | Simple in-memory cache with mutex, line-span context (±20 lines) |
| **GitHub-native** | Posts inline review comments + summary comment on the PR |
| **Filtering** | Include/exclude by extension and path |
| **Custom rules** | Optional rules file injected into system prompt |

### Its Limitations (Our Opportunity)
| Limitation | Impact |
|-----------|--------|
| **Single monolithic reviewer** | One agent tries to catch bugs, security, typos — misses nuance |
| **No codebase persistence** | Every PR starts from zero; no memory of architecture, conventions, past decisions |
| **No cross-file awareness** | Agent only sees files it explicitly requests; misses dependency chains |
| **Fixed review depth** | Can't dial between "quick sanity check" and "exhaustive audit" |
| **No specialized expertise** | Security review by generalist = missed CVE patterns, crypto misuse, auth bypasses |
| **No learning** | Same mistakes get flagged repeatedly; no feedback loop |
| **Stateless** | No history of: "we decided X pattern in PR #42, this violates it" |

---

## Our Vision: The Multi-Agent Persistent Code Review System

### Core Philosophy
> **"A code review should know your codebase like a senior engineer who's been on the team for 2 years."**

Instead of a single AI glancing at diffs, we build a **council of specialized agents** with **persistent memory** of the codebase, **orchestrated** by LangGraph.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRIGGER LAYER                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ GitHub      │  │ GitLab      │  │ CLI Tool    │  │ IDE Plugin      │ │
│  │ Webhook     │  │ Webhook     │  │ (local)     │  │ (real-time)     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         └─────────────────┴─────────────────┴─────────────────┘         │
│                              │                                           │
└──────────────────────────────┼───────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────────┐
│                      ORCHESTRATION LAYER (LangGraph)                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  State Machine: PR_RECEIVED → ANALYZE → ROUTE → REVIEW → SYNTHESIZE │   │
│  │                                                                     │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │   │
│  │  │ Router   │───→│ Security │───→│ Quality  │───→│ Synthesis│    │   │
│  │  │ Agent    │    │ Agent    │    │ Agent    │    │ Agent    │    │   │
│  │  │          │───→│ UX Agent │    │ Perf     │    │          │    │   │
│  │  │          │    │          │    │ Agent    │    │          │    │   │
│  │  │          │    │ Arch     │    │ Maintain │    │          │    │   │
│  │  │          │    │ Agent    │    │ Agent    │    │          │    │   │
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────────────┐
│                      PERSISTENCE LAYER                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐   │
│  │ Vector Store    │  │ Graph DB        │  │ Relational DB           │   │
│  │ (Codebase       │  │ (Dependencies,   │  │ (Review History,         │   │
│  │  Embeddings)    │  │  Call Graphs)    │  │  Decisions, Config)      │   │
│  │  Chroma/PGVector │  │  NetworkX/Neo4j  │  │  PostgreSQL/SQLite       │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The Agent Council

Each agent is a **specialized LLM instance** with its own system prompt, tools, and expertise area.

### 1. Router Agent (LangGraph Entry Node)
**Job**: Analyze the PR diff and decide which specialist agents to invoke.
- Reads changed files, file types, size of diff
- Checks persistence layer for "hot areas" (files with frequent changes, known complexity)
- Outputs: `agents_needed = ["security", "quality", "ux"]`, `review_depth = "standard"`
- Configurable: user can force agents or let router decide

### 2. Security Agent
**Focus**: Vulnerabilities, auth, crypto, injection, secrets leakage
**Special tools**:
- `scan_for_secrets(diff)` — regex + entropy detection
- `check_dependency_vulnerabilities(changed_packages)` — OSV/Snyk integration
- `analyze_auth_flow(changed_auth_files)` — trace auth logic
- `check_cwe_patterns(code)` — known CWE pattern matching
**Memory**: CVE database, project's security history, past false positives

### 3. UX/UI Agent
**Focus**: User-facing changes, API ergonomics, error messages, accessibility
**Special tools**:
- `check_a11y(html_changes)` — axe-core integration
- `analyze_api_surface(changed_interfaces)` — breaking change detection
- `review_error_messages(changed_strings)` — user-friendly error check
- `check_responsive_css(changed_styles)` — mobile viewport checks
**Memory**: Design system docs, component library, user complaint patterns

### 4. Code Quality Agent
**Focus**: Bugs, logic errors, type safety, test coverage, edge cases
**Special tools**:
- `run_static_analysis(files)` — mypy, pylint, eslint, etc.
- `check_test_coverage(changed_files)` — coverage delta
- `analyze_complexity(ast)` — cyclomatic complexity
- `detect_race_conditions(async_code)` — concurrency analysis
**Memory**: Project's type conventions, test patterns, known flaky areas

### 5. Performance Agent
**Focus**: N+1 queries, memory leaks, algorithmic complexity, bundle size
**Special tools**:
- `detect_n_plus_1(changed_queries)` — ORM pattern matching
- `analyze_big_o(changed_algorithms)` — complexity estimation
- `check_bundle_size_delta(changed_imports)` — webpack/vite analysis
- `profile_memory_patterns(changed_allocations)` — allocation tracking
**Memory**: Performance benchmarks, known slow paths, SLA requirements

### 6. Maintainability Agent
**Focus**: Documentation, naming, modularity, technical debt, refactoring needs
**Special tools**:
- `check_doc_coverage(changed_public_apis)` — docstring/missing docs
- `analyze_coupling(changed_files)` — dependency graph analysis
- `detect_code_duplication(changed_blocks)` — clone detection
- `check_naming_conventions(names)` — project-specific conventions
**Memory**: ADRs (Architecture Decision Records), refactoring history, tech debt log

### 7. Architecture Agent
**Focus**: System-level impact, cross-service changes, data model changes, API versioning
**Special tools**:
- `trace_cross_service_impact(changed_files)` — service dependency graph
- `check_backward_compatibility(api_changes)` — schema evolution
- `analyze_data_migration(changed_models)` — migration safety
- `review_event_contracts(changed_events)` — async contract validation
**Memory**: C4 diagrams, service catalog, API contracts, event schemas

### 8. Synthesis Agent (LangGraph Exit Node)
**Job**: Merge all agent outputs into a coherent review
- Deduplicates overlapping findings
- Resolves conflicts (e.g., Security says "add validation" vs Performance says "remove validation")
- Prioritizes by severity + project context
- Generates executive summary for PR description
- Decides: Approve / Request Changes / Comment

---

## Persistence Layer: The "Codebase Brain"

### Why Persistence Matters
The reference repo is **stateless**. Every PR review starts with zero context. A senior engineer knows:
- "We use Repository pattern, not direct DB access"
- "File X is critical path, any change needs extra scrutiny"
- "PR #42 established this convention"
- "This module has 3 known bugs we haven't fixed yet"

### Layer 1: Vector Store (Semantic Codebase Memory)
**Purpose**: Semantic search across the entire codebase
**Implementation**: ChromaDB or PostgreSQL with pgvector
**Contents**:
- File-level embeddings (chunked, with metadata: path, language, imports, last_modified)
- Function/class-level embeddings
- Commit message embeddings (for "why was this written this way?")
- PR review comment embeddings (for "what have we criticized before?")

**Usage during review**:
```python
# When reviewing a changed file, find similar patterns elsewhere
similar_files = vector_store.similarity_search(
    query=changed_file_embedding,
    filter={"language": "python", "path": {"$not": {"$contains": "test"}}},
    k=5
)
# "Here are 5 places we solved similar problems — check for consistency"
```

**Update strategy**: Incremental — only re-embed changed files on each PR merge

### Layer 2: Graph Database (Structural Memory)
**Purpose**: Understand relationships — imports, inheritance, calls, data flow
**Implementation**: NetworkX (in-memory) or Neo4j (persistent)
**Nodes**: Files, functions, classes, modules, services, APIs
**Edges**: imports, calls, inherits, reads, writes, depends_on

**Usage during review**:
```python
# When file A changes, what breaks?
affected = graph_db.traverse(
    from_node="file:A.py",
    edge_types=["imports", "calls", "depends_on"],
    depth=3
)
# "Changing this utility function affects 12 call sites across 4 services"
```

**Update strategy**: AST parsing on merge; incremental updates for changed files

### Layer 3: Relational Database (Review History & Decisions)
**Purpose**: Track decisions, patterns, and feedback loops
**Implementation**: PostgreSQL or SQLite
**Tables**:
- `reviews` — PR number, commit, timestamp, overall verdict
- `findings` — individual issues found (file, line, severity, agent, message)
- `decisions` — ADRs and team decisions ("We use async/await, not callbacks")
- `false_positives` — findings that were rejected (to train agents)
- `conventions` — project-specific rules ("All API endpoints must have rate limiting")
- `agent_configs` — per-project/agent configuration

**Usage during review**:
```python
# Check if we've flagged this pattern before
previous = db.query("""
    SELECT * FROM findings 
    WHERE pattern_hash = ? AND resolution = 'false_positive'
""", pattern_hash)
# "We previously decided this pattern is OK in this context — skipping"
```

---

## Compute & Token Optimization Strategies

### The Problem
The reference repo sends the **entire diff** to the LLM in one shot. For large PRs, this:
- Exceeds context windows
- Wastes tokens on unchanged context
- Reduces quality (LLM gets overwhelmed)

### Our Solutions

#### 1. Chunked Review with Context Awareness
Instead of one giant prompt, break the PR into logical chunks:
```python
chunks = chunk_by(
    changed_files,
    strategy="dependency_graph",  # group related files
    max_tokens=8000,              # per chunk
    overlap_context=3             # shared files between chunks
)
# Each chunk gets reviewed by relevant agents
```

#### 2. Hierarchical Summarization
```
Level 1: File-level summary (what changed, why)
Level 2: Module-level summary (impact on subsystem)
Level 3: PR-level summary (overall impact)
```
Lower levels are cached; only re-compute changed portions.

#### 3. Smart Context Retrieval (RAG)
Instead of sending full file content, retrieve only relevant context:
```python
# For a changed function, get:
context = {
    "function_signature": "def process_payment(user, amount):",
    "docstring": "...",
    "callers": ["checkout.py:42", "billing.py:88"],  # from graph DB
    "similar_implementations": vector_store.similarity_search(function_embedding),
    "tests": ["test_payments.py:15"],
    "last_review": "Previous review found race condition here"
}
# Total: ~500 tokens instead of 5000 for full file
```

#### 4. Caching & Memoization
- **Embedding cache**: File hash → embedding (skip re-embedding unchanged files)
- **AST cache**: File hash → AST (skip re-parsing)
- **Review cache**: (file_hash, agent_config_hash) → findings (skip re-reviewing unchanged files)
- **LLM response cache**: Similar diffs → similar findings (with semantic similarity)

#### 5. Tiered Review Depth
```yaml
review_depths:
  quick:
    agents: [quality]           # Only code quality
    max_tokens_per_file: 2000
    tools: [basic_lint]
    cost_estimate: "$0.02/PR"
    
  standard:
    agents: [quality, security, maintainability]
    max_tokens_per_file: 4000
    tools: [all_static_analysis]
    cost_estimate: "$0.08/PR"
    
  exhaustive:
    agents: [all]
    max_tokens_per_file: 8000
    tools: [all + custom_checks]
    graph_depth: 3
    cost_estimate: "$0.25/PR"
    
  custom:
    # User-defined agent selection + depth
```

#### 6. Model Selection per Task
Not all agents need GPT-5.2:
```python
agent_models = {
    "router": "gpt-4.1-mini",      # Cheap, fast classification
    "security": "claude-sonnet-4.5",  # Best at reasoning about vulnerabilities
    "quality": "gpt-4.1",            # Good balance
    "ux": "gpt-4.1-mini",           # Simple pattern matching
    "synthesis": "claude-opus-4.5",  # Complex reasoning, conflict resolution
}
```

---

## LangGraph State Machine

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional

class ReviewState(TypedDict):
    pr_metadata: dict           # PR number, repo, branch, author
    changed_files: List[dict]   # File diffs
    codebase_context: dict      # Retrieved from persistence layer
    agent_outputs: dict         # {agent_name: [findings]}
    synthesis: Optional[str]   # Final review comment
    verdict: str               # "approve" | "request_changes" | "comment"
    github_comments: List[dict] # Inline comments to post
    
# Define the graph
workflow = StateGraph(ReviewState)

# Nodes
workflow.add_node("ingest", ingest_pr)           # Fetch PR, parse diffs
workflow.add_node("retrieve", retrieve_context)     # Query persistence layer
workflow.add_node("route", router_agent)           # Decide which agents to run
workflow.add_node("security", security_agent)
workflow.add_node("quality", quality_agent)
workflow.add_node("ux", ux_agent)
workflow.add_node("performance", performance_agent)
workflow.add_node("maintainability", maintainability_agent)
workflow.add_node("architecture", architecture_agent)
workflow.add_node("synthesize", synthesis_agent)  # Merge findings
workflow.add_node("post", post_to_github)          # Publish comments

# Edges
workflow.set_entry_point("ingest")
workflow.add_edge("ingest", "retrieve")
workflow.add_edge("retrieve", "route")

# Conditional routing
workflow.add_conditional_edges(
    "route",
    lambda state: state["agents_needed"],
    {
        "security": "security",
        "quality": "quality",
        # ... etc
    }
)

# Parallel agent execution (LangGraph supports this!)
workflow.add_edge(["security", "quality", "ux"], "synthesize")
workflow.add_edge("synthesize", "post")
workflow.add_edge("post", END)

# Compile
app = workflow.compile()

# Run
result = app.invoke({
    "pr_metadata": {"repo": "my-org/my-repo", "pr_number": 42},
    # ... initial state
})
```

---

## Implementation Difficulty Assessment

### Phase 1: MVP (2-3 weeks)
**Scope**: Single-agent system with persistence, matching reference repo + extras
- [ ] LangGraph orchestration with one generalist agent
- [ ] Vector store for semantic search (ChromaDB)
- [ ] GitHub webhook integration
- [ ] Basic persistence (SQLite): review history, false positives
- [ ] Configurable review depth (quick/standard/exhaustive)
- [ ] **Difficulty**: Medium — mostly plumbing, LangGraph is well-documented

### Phase 2: Multi-Agent (3-4 weeks)
**Scope**: Full agent council with specialization
- [ ] Router agent with intelligent dispatch
- [ ] 3-4 specialized agents (Security, Quality, UX, Maintainability)
- [ ] Graph DB for dependency tracking (NetworkX)
- [ ] Agent-specific tools and prompts
- [ ] Cross-agent conflict resolution in synthesis
- [ ] **Difficulty**: Medium-Hard — prompt engineering for each agent, tool design

### Phase 3: Intelligence (4-6 weeks)
**Scope**: Learning, optimization, advanced features
- [ ] False positive learning loop (feedback from devs)
- [ ] Automatic convention detection ("this project uses X pattern")
- [ ] Predictive hot-path analysis ("this file changes frequently, be extra careful")
- [ ] Custom agent creation (user-defined agents with YAML config)
- [ ] IDE integration (VS Code extension)
- [ ] **Difficulty**: Hard — requires feedback data, iterative improvement

### Phase 4: Scale (ongoing)
- [ ] Multi-repo support with shared learning
- [ ] Team-level and org-level policy enforcement
- [ ] Integration with CI/CD pipelines (block merge on security findings)
- [ ] **Difficulty**: Hard — enterprise features, compliance

### Total Estimate: 2-3 months for a solid v1.0

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Orchestration** | LangGraph | Native multi-agent support, state machines, conditional edges, parallel execution |
| **LLM Interface** | LangChain | Unified interface for multiple providers, tool calling, callbacks |
| **Vector Store** | ChromaDB / pgvector | Lightweight, local-first option; pgvector for production |
| **Graph DB** | NetworkX (dev) / Neo4j (prod) | NetworkX for prototyping, Neo4j for persistence at scale |
| **Relational DB** | PostgreSQL / SQLite | SQLite for MVP, PostgreSQL for production |
| **Embedding Model** | sentence-transformers / OpenAI `text-embedding-3-small` | Local option + cloud option |
| **AST Parsing** | tree-sitter | Multi-language, fast, incremental |
| **Git Integration** | PyGithub / GitPython | GitHub API + local repo operations |
| **Webhooks** | FastAPI + uvicorn | Async webhook handling |
| **Deployment** | Docker + GitHub Actions | Containerized + native CI integration |

---

## Key Differentiators vs. Reference Repo

| Feature | Reference Repo | Our System |
|---------|---------------|------------|
| Agents | 1 generalist | 6+ specialists + router + synthesis |
| Memory | Stateless (in-memory cache only) | 3-layer persistence (vector + graph + relational) |
| Context | Explicit file requests | Proactive retrieval via RAG + dependency graph |
| Depth | Fixed | Configurable (quick → exhaustive) |
| Learning | None | False positive tracking, convention detection |
| Cross-file | None | Full dependency graph traversal |
| Cost control | None | Tiered depth, model selection, caching |
| Integration | GitHub Actions only | GitHub, GitLab, CLI, API, IDE |

---

## Open Questions for Discussion

1. **Hosting model**: Self-hosted (Docker in your infra) or SaaS?
2. **Privacy**: Can we send code to cloud LLMs? Need local LLM option (Ollama)?
3. **Feedback loop**: How do developers mark false positives? GitHub reactions? Config file?
4. **Pricing**: Open source + paid hosted version? Pure open source?
5. **Scope creep**: Start with Python only, or multi-language from day one?
6. **LangGraph vs. custom**: LangGraph is powerful but adds complexity — worth it?

---

## Next Steps (If We Proceed)

1. **Prototype Phase 1 MVP** (1 week spike)
   - LangGraph + one agent + ChromaDB + GitHub webhook
   - Test on a real repo
   
2. **Measure baseline**
   - Token usage per PR
   - Review quality (manual grading of 20 PRs)
   - False positive rate
   
3. **Iterate to Phase 2**
   - Add router + 2 specialist agents
   - A/B test vs. single-agent

---

*Document version: 1.0*
*Date: 2026-05-31*
*Status: Brainstorm / Architecture Design*
