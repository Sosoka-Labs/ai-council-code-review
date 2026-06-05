# 5. DeepAgents SDK

> **Version Context:** This section reflects DeepAgents SDK as of June 2026 (latest stable: v0.6.7). The SDK is under active development with frequent releases. Check [PyPI](https://pypi.org/project/deepagents/) and the [GitHub repository](https://github.com/langchain-ai/deepagents) for the latest version.

---

## 5.1 What Is DeepAgents SDK?

**DeepAgents SDK** is LangChain's "batteries-included" agent harness — an opinionated framework for building autonomous AI agents that can plan, delegate, manage context via a virtual filesystem, and spawn sub-agents to handle complex multi-step tasks. It is built on top of **LangGraph** (the graph runtime) and **LangChain's `create_agent`** (the minimal agent harness), adding a layered middleware stack that provides production-ready capabilities out of the box.

> **Official Description:** *"General purpose 'deep agent' with sub-agent spawning, todo list capabilities, and mock file system. Built on LangGraph."* — [PyPI](https://pypi.org/project/deepagents/)

### Relationship to LangChain / LangGraph

The LangChain ecosystem has three layers relevant here:

| Layer | Role | What It Provides |
|-------|------|----------------|
| **LangGraph** | Graph runtime | Stateful graph execution, cycles, checkpoints, streaming |
| **`langchain.agents.create_agent`** | Minimal harness | Basic ReAct loop with tool calling on top of LangGraph |
| **DeepAgents SDK** | Batteries-included harness | Planning, filesystem, sub-agents, memory, skills, summarization — all bundled |

> **Key Insight:** DeepAgents does not replace LangChain or LangGraph. It is a *higher-level abstraction* that composes them. You can still drop down to raw LangGraph or `create_agent` whenever you need finer control.

### The "Deep Agent" Pattern

The term "deep agent" refers to an agent architecture popularized by systems like **Claude Code**, **OpenAI's Deep Research**, and **Manus** — agents that:

1. **Plan** before acting (break tasks into subtasks)
2. **Use a workspace** (filesystem for notes, code, artifacts)
3. **Delegate** to specialized sub-agents
4. **Iterate** until the goal is achieved

DeepAgents SDK democratizes this pattern, letting you build similar agents in a few lines of Python.

---

## 5.2 Core Concepts and Architecture

### 5.2.1 The Middleware Stack

DeepAgents' power comes from its **middleware architecture**. When you call `create_deep_agent()`, the SDK automatically registers a stack of middleware layers that intercept and augment the agent's behavior:

```
┌─────────────────────────────────────────────────────────────┐
│                    DeepAgent Middleware Stack                │
├─────────────────────────────────────────────────────────────┤
│  1. TodoListMiddleware        → Planning (write_todos tool)   │
│  2. MemoryMiddleware          → Load AGENTS.md into prompt    │
│  3. SkillsMiddleware          → Dynamic skill loading         │
│  4. FilesystemMiddleware      → ls, read_file, write_file   │
│  5. SubAgentMiddleware        → task() tool for delegation  │
│  6. AsyncSubAgentMiddleware   → Async subagent spawning      │
│  7. SummarizationMiddleware   → Auto-compress long history   │
│  8. AnthropicPromptCachingMiddleware → Cost optimization     │
│  9. PatchToolCallsMiddleware  → Fix dangling tool calls       │
└─────────────────────────────────────────────────────────────┘
```

Each middleware layer:
- **Extends the state schema** (e.g., `SummarizationMiddleware` adds `_summarization_event`)
- **Injects tools** into the agent's tool loop
- **Modifies prompts** (e.g., loading memory files or skills into the system prompt)
- **Intercepts tool calls** to add behavior (e.g., the `task` tool spawns a subagent)

### 5.2.2 State Management: DeepAgentState

DeepAgents uses a built-in state schema called `DeepAgentState` (extends LangGraph's base state). You can customize it:

```python
from deepagents.graph import DeepAgentState

class MyState(DeepAgentState):
    page_url: str
    file_urls: list[str]

agent = create_deep_agent(
    model="openai:gpt-5.4",
    tools=[my_tools],
    state_schema=MyState,  # Custom state
)
```

### 5.2.3 The Virtual Filesystem

A defining feature of DeepAgents is its **virtual filesystem backend**. Agents can read, write, and edit files to manage context, store intermediate results, and build artifacts.

**Built-in filesystem tools:**

| Tool | Purpose |
|------|---------|
| `ls` | List files in a directory |
| `read_file` | Read file contents |
| `write_file` | Create or overwrite a file |
| `edit_file` | Apply targeted edits (search/replace style) |
| `glob` | Find files by pattern |
| `grep` | Search within files |

The filesystem is backed by a **pluggable backend**:
- `FilesystemBackend(root_dir="./")` — Local filesystem
- `CompositeBackend` — Combine multiple backends (e.g., local + remote)
- Custom backends — Implement your own for S3, databases, etc.

### 5.2.4 Planning with `write_todos`

Every deep agent has access to a `write_todos` tool that lets it create, update, and check off a todo list. This is the planning layer — the agent breaks complex tasks into subtasks before executing them.

```
User: "Build a Python web scraper for Hacker News"

Agent (via write_todos):
  1. [ ] Research Hacker News HTML structure
  2. [ ] Design scraper architecture
  3. [ ] Implement requests + BeautifulSoup
  4. [ ] Add error handling and retries
  5. [ ] Test and save final script

Agent then executes each todo, checking them off as it goes.
```

### 5.2.5 Sub-Agent Delegation

The `task` tool lets a deep agent spawn a **sub-agent** to handle a specific task. Sub-agents are isolated agents with their own system prompt, tools, and (optionally) model.

**Key behaviors:**
- Every deep agent has a **general-purpose sub-agent** available by default
- You can define **custom sub-agents** with specialized roles
- Sub-agents inherit the parent's middleware stack (with some caveats — see [Known Limitations](#57-known-limitations-and-caveats))
- Sub-agents run in their own tool loop and return results to the parent

---

## 5.3 Installation and Setup

### 5.3.1 Prerequisites

- **Python 3.11+** (required)
- API keys for at least one LLM provider (OpenAI, Anthropic, Google, etc.)
- Optional: Tavily API key for web search tools

### 5.3.2 Installation

```bash
# Create a virtual environment
python -m venv deepagents-env
source deepagents-env/bin/activate  # macOS/Linux
# deepagents-env\Scripts\activate   # Windows

# Install core package
pip install deepagents

# Install model providers (pick what you need)
pip install langchain-openai langchain-anthropic langchain-google-genai

# Optional: web search, utilities
pip install tavily-python python-dotenv
```

### 5.3.3 Environment Configuration

Create a `.env` file:

```bash
# Required: at least one LLM provider
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Optional: for web search tools
TAVILY_API_KEY=tvly-...
```

Load it in your Python code:

```python
from dotenv import load_dotenv
load_dotenv()
```

### 5.3.4 Verify Installation

```python
import deepagents
print(f"DeepAgents version: {deepagents.__version__}")

from deepagents import create_deep_agent
print("✅ DeepAgents imported successfully")
```

---

## 5.4 Creating Agents with DeepAgents

### 5.4.1 The Simplest Deep Agent

```python
from deepagents import create_deep_agent

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

agent = create_deep_agent(
    model="openai:gpt-5.4",  # Provider shorthand: "provider:model"
    tools=[get_weather],
    system_prompt="You are a helpful weather assistant.",
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "What's the weather in Phoenix?"}]
})
print(result)
```

### 5.4.2 Using a Custom Model Instance

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from deepagents import create_deep_agent

# Option 1: Pass a model instance directly
openai_model = ChatOpenAI(model="gpt-5.4", temperature=0.2)

agent = create_deep_agent(
    model=openai_model,
    tools=[my_tool],
)

# Option 2: Ollama / local models
from langchain_ollama import ChatOllama
local_model = ChatOllama(model="llama3.2")

agent = create_deep_agent(
    model=local_model,
    tools=[my_tool],
)
```

### 5.4.3 Agent with Filesystem Backend

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

agent = create_deep_agent(
    model="openai:gpt-5.4",
    tools=[web_search, code_executor],
    system_prompt="You are a research assistant. Use the filesystem to take notes.",
    backend=FilesystemBackend(root_dir="./workspace"),
)

# The agent can now:
# - write_file("notes.txt", "...")
# - read_file("notes.txt")
# - ls("./")
# - edit_file("notes.txt", old="...", new="...")
```

### 5.4.4 Agent with Memory (AGENTS.md Pattern)

```python
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=[my_tools],
    memory=["./AGENTS.md"],  # Loaded into system prompt
)
```

The `AGENTS.md` file is a living document that the agent reads on every invocation. Use it for:
- Project context and conventions
- Persistent instructions
- Agent self-documentation

### 5.4.5 Agent with Skills

```python
agent = create_deep_agent(
    model="openai:gpt-5.4",
    tools=[my_tools],
    skills=["./skills/"],  # Directory of skill definitions
)
```

Skills are loaded on-demand and injected into the system prompt. They let you define reusable capabilities (e.g., "how to query this specific database").

### 5.4.6 Full-Featured Agent Example

```python
import os
from typing import Literal
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from tavily import TavilyClient
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

load_dotenv()

# --- Tools ---
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> dict:
    """Search the web for current information."""
    return tavily.search(query, max_results=max_results, topic=topic)

def generate_summary(text: str) -> str:
    """Summarize a body of text."""
    return f"Summary: {text[:200]}..."

# --- Agent ---
agent = create_deep_agent(
    model=ChatOpenAI(model="gpt-5.4", temperature=0.1),
    tools=[internet_search, generate_summary],
    system_prompt=(
        "You are a research assistant. When given a topic:\n"
        "1. Plan your research with write_todos\n"
        "2. Search for information\n"
        "3. Save notes to the filesystem\n"
        "4. Synthesize and return a final report"
    ),
    backend=FilesystemBackend(root_dir="./research_workspace"),
    memory=["./AGENTS.md"],
    skills=["./skills/"],
)

# --- Invoke ---
result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "Research the latest advances in quantum computing in 2026"
    }]
})
```

---

## 5.5 Multi-Agent Orchestration Patterns

### 5.5.1 Custom Sub-Agent Definitions

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="openai:gpt-5.4",
    tools=[internet_search],
    subagents=[
        {
            "name": "code-writer",
            "description": "Writes clean, tested Python code.",
            "system_prompt": "You are an expert Python developer. Write code with type hints and docstrings.",
            "tools": [code_executor, linter],
            "model": "openai:gpt-5.5-codex",  # Different model for coding
        },
        {
            "name": "fact-checker",
            "description": "Verifies claims against web sources.",
            "system_prompt": "You are a meticulous fact-checker. Verify every claim with sources.",
            "tools": [internet_search, calculator],
            "model": "anthropic:claude-sonnet-4-5",
        },
    ],
)
```

When the parent agent calls `task(name="code-writer", prompt="Write a FastAPI endpoint...")`, the sub-agent is spawned with its own configuration.

### 5.5.2 Overriding the General-Purpose Sub-Agent

Every deep agent has a default "general-purpose" sub-agent. You can override it:

```python
agent = create_deep_agent(
    model="google_genai:gemini-3.5-flash",
    tools=[internet_search],
    subagents=[
        {
            "name": "general-purpose",  # Override the default
            "description": "General-purpose agent for research and multi-step tasks",
            "system_prompt": "You are a general-purpose assistant.",
            "tools": [internet_search],
            "model": "openai:gpt-5.4",  # Different model for delegated tasks
        },
    ],
)
```

### 5.5.3 Async Sub-Agent Server Pattern

For production deployments, you can run sub-agents as **async servers** that the parent agent calls via HTTP:

```python
# supervisor.py
from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic

agent = create_deep_agent(
    model=ChatAnthropic(model="claude-sonnet-4-5"),
    system_prompt="You are a supervisor agent that delegates to specialist workers.",
    tools=[orchestration_tool],
    # Sub-agents are external async services
)
```

See the [async-subagent-server example](https://github.com/langchain-ai/deepagents/tree/main/examples/async-subagent-server) in the official repo for a complete implementation.

### 5.5.4 Hierarchical Task Decomposition

```
User Request
    │
    ▼
┌─────────────────┐
│  Supervisor     │ ← Deep Agent (planning + delegation)
│  Agent          │
└────────┬────────┘
         │
    ┌────┴────┬────────┬────────┐
    ▼         ▼        ▼        ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│Research│ │Code   │ │Test   │ │Deploy │
│Sub-Agent│ │Sub-Agent│ │Sub-Agent│ │Sub-Agent│
└───────┘ └───────┘ └───────┘ └───────┘
    │         │        │        │
    └─────────┴────────┴────────┘
              │
              ▼
    ┌─────────────────┐
    │  Synthesis &    │
    │  Final Output   │
    └─────────────────┘
```

---

## 5.6 Integration with Existing LangChain Components

### 5.6.1 Using DeepAgents Middleware with `create_agent`

You don't have to use `create_deep_agent`. You can apply individual middleware layers to a standard LangChain agent:

```python
from langchain.agents import create_agent
from deepagents.middleware.subagents import SubAgentMiddleware

@tool
def get_weather(city: str) -> str:
    """Get the weather in a city."""
    return f"The weather in {city} is sunny."

agent = create_agent(
    model="claude-sonnet-4-5-20250929",
    middleware=[
        SubAgentMiddleware(
            default_model="claude-sonnet-4-5-20250929",
            default_tools=[],
            subagents=[
                {
                    "name": "weather",
                    "description": "This subagent can get weather in cities.",
                    "system_prompt": "Use the get_weather tool to get the weather in a city.",
                    "tools": [get_weather],
                    "model": "gpt-4.1",
                    "middleware": [],
                }
            ],
        )
    ],
)
```

### 5.6.2 Compatibility with LangGraph Checkpointers

DeepAgents graphs are compiled LangGraph graphs, so they work with LangGraph checkpointers for persistence:

```python
from langgraph.checkpoint.memory import InMemorySaver
from deepagents import create_deep_agent

checkpointer = InMemorySaver()

agent = create_deep_agent(
    model="openai:gpt-5.4",
    tools=[my_tools],
    checkpointer=checkpointer,
)

# Invoke with thread_id for persistence
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Hello"}]},
    config={"configurable": {"thread_id": "thread-123"}}
)
```

### 5.6.3 Streaming and Async

DeepAgents supports LangGraph's streaming and async APIs:

```python
# Streaming
async for event in agent.astream_events(
    {"messages": [{"role": "user", "content": "Plan a trip to Japan"}]},
    version="v2",
):
    print(event)

# Async invoke
result = await agent.ainvoke({
    "messages": [{"role": "user", "content": "Research quantum computing"}]
})
```

### 5.6.4 MCP (Model Context Protocol) Integration

DeepAgents can work with MCP tools via the LangChain MCP Adapter:

```bash
pip install langchain-mcp-adapters
```

```python
from langchain_mcp_adapters import load_mcp_tools
from deepagents import create_deep_agent

mcp_tools = load_mcp_tools("./mcp_config.json")

agent = create_deep_agent(
    model="openai:gpt-5.4",
    tools=mcp_tools,
)
```

---

## 5.7 Current State, Maturity, and Community Adoption

### 5.7.1 Version History and Stability

| Version | Date | Notes |
|---------|------|-------|
| 0.0.1 — 0.0.10 | Late 2024 — Early 2025 | Early alpha, API experimentation |
| 0.5.x | Mid 2025 | Beta, middleware architecture stabilized |
| 0.6.0 | Early 2026 | Major release — harness-layer improvements, benchmark gains |
| 0.6.6 | May 2026 | Latest stable (as of June 2026) |
| 0.6.7 | June 2026 | Current PyPI version |

> **Important:** The SDK uses **0.x versioning**, which by SemVer convention means the API may still change. However, the core `create_deep_agent` API has been stable since v0.5.x.

### 5.7.2 Benchmark Improvements (v0.6)

LangChain's own testing showed significant gains from v0.6 harness-layer improvements:

| Model | Benchmark | Before | After |
|-------|-----------|--------|-------|
| GPT-5.2 Codex | Terminal-Bench 2.0 | 52.8% | 66.5% (Top 30 → Top 5) |
| GPT-5.3 Codex | tau2-bench | — | +20% improvement |
| Opus-4.7 | tau2-bench | — | +10% improvement |

### 5.7.3 Community and Ecosystem

- **GitHub Stars:** Growing rapidly (langchain-ai/deepagents)
- **PyPI Downloads:** Steady growth; included in LangChain's official ecosystem
- **Documentation:** [Official Docs](https://docs.langchain.com/oss/python/deepagents/overview)
- **Examples:** [Official Examples Repo](https://github.com/langchain-ai/deepagents/tree/main/examples)
- **CLI Tool:** `deepagents-cli` available for terminal-based agent interaction
- **JavaScript Port:** `deepagentsjs` for Node.js/server environments

### 5.7.4 Known Limitations and Caveats

1. **Custom Middleware Propagation:** As of mid-2026, custom middleware passed to `create_deep_agent` is applied to the parent agent only. The auto-installed general-purpose sub-agent runs with a hardcoded default stack, not your custom middleware. Track [Issue #2744](https://github.com/langchain-ai/deepagents/issues/2744).

2. **`config.configurable` Not Propagated to Subagents:** Configurable parameters (like `user_id`, `conversation_id`) passed to the parent agent may not be forwarded to sub-agents. Track [Issue #1251](https://github.com/langchain-ai/deepagents/issues/1251).

3. **Python 3.11+ Required:** The SDK does not support Python 3.10 or earlier.

4. **Model Compatibility:** Any model that supports tool calling works — frontier APIs (OpenAI, Anthropic, Google), open-weight models (via Baseten, Fireworks), and self-hosted models (Ollama, vLLM, llama.cpp).

5. **Filesystem is "Mock":** The filesystem is virtualized through the backend. It is not a real OS filesystem unless you use `FilesystemBackend` with a local root directory.

---

## 5.8 When to Use DeepAgents vs. Standard LangChain

### Use DeepAgents When...

| Scenario | Why DeepAgents Fits |
|----------|---------------------|
| **Complex multi-step tasks** | Built-in planning (`write_todos`) and sub-agent delegation |
| **Long-running sessions** | Summarization middleware auto-compresses history; filesystem offloads context |
| **Research / coding assistants** | Claude Code-style pattern: plan → search → write → test → iterate |
| **Teams of specialized agents** | Easy sub-agent definition with different models/tools per agent |
| **Need filesystem workspace** | Virtual filesystem for notes, artifacts, code, logs |
| **Human-in-the-loop workflows** | Built-in support for pausing at critical decision points |
| **Production agent deployments** | Middleware stack handles edge cases (dangling tool calls, prompt caching) |

### Use Standard `create_agent` / Raw LangGraph When...

| Scenario | Why Standard Fits |
|----------|-----------------|
| **Simple tool-calling agent** | No need for planning, filesystem, or delegation overhead |
| **Custom graph topology** | You need a specific node/edge structure that DeepAgents' opinionated harness doesn't support |
| **Minimal dependencies** | DeepAgents pulls in multiple middleware dependencies |
| **Full control over prompts** | DeepAgents injects its own system prompt layers |
| **Learning LangGraph fundamentals** | Understanding the base layer before using abstractions |

### Decision Flowchart

```
┌─────────────────────────────────────┐
│  Do you need planning / todo lists? │
└──────────────┬──────────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
   Yes                 No
      │                 │
      ▼                 ▼
┌─────────────┐   ┌─────────────────────────┐
│ DeepAgents  │   │ Need sub-agent delegation?│
│  ✓          │   └────────────┬──────────────┘
└─────────────┘                │
                      ┌────────┴────────┐
                      ▼                 ▼
                   Yes                 No
                      │                 │
                      ▼                 ▼
               ┌─────────────┐   ┌─────────────────────┐
               │ DeepAgents  │   │ Need filesystem /   │
               │  ✓          │   │ persistent workspace? │
               └─────────────┘   └────────────┬────────┘
                                              │
                                     ┌────────┴────────┐
                                     ▼                 ▼
                                  Yes                 No
                                     │                 │
                                     ▼                 ▼
                              ┌─────────────┐   ┌─────────────┐
                              │ DeepAgents  │   │ Standard    │
                              │  ✓          │   │ create_agent│
                              └─────────────┘   │  ✓          │
                                                └─────────────┘
```

---

## 5.9 Complete Working Example: Research Assistant

```python
"""
DeepAgents Research Assistant
A complete, runnable example of a deep agent that researches a topic,
takes notes in a virtual filesystem, and produces a final report.
"""

import os
from typing import Literal
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from tavily import TavilyClient
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

# ─── Configuration ───
load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ─── Tools ───
tavily = TavilyClient(api_key=TAVILY_API_KEY)

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> dict:
    """Search the web for current information. Use this for research."""
    return tavily.search(query, max_results=max_results, topic=topic)

def save_note(filename: str, content: str) -> str:
    """Save a note to the filesystem. The agent uses this internally via write_file."""
    return f"Note saved to {filename}"

# ─── Agent ───
agent = create_deep_agent(
    model=ChatOpenAI(model="gpt-5.4", temperature=0.2, api_key=OPENAI_API_KEY),
    tools=[internet_search],
    system_prompt="""You are a research assistant. Your workflow:

1. PLAN: Use write_todos to break the research into steps
2. GATHER: Use internet_search to find information
3. NOTE: Save findings to the filesystem with write_file
4. SYNTHESIZE: Read your notes and produce a final report
5. SAVE: Write the final report to report.md

Always check off todos as you complete them.""",
    backend=FilesystemBackend(root_dir="./research_output"),
)

# ─── Run ───
if __name__ == "__main__":
    topic = "Latest advances in fusion energy research in 2026"

    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Research and write a report on: {topic}"}]
    })

    print("=" * 60)
    print("AGENT OUTPUT")
    print("=" * 60)
    print(result)

    # Check what files the agent created
    print("\n" + "=" * 60)
    print("FILES CREATED")
    print("=" * 60)
    import os
    for f in os.listdir("./research_output"):
        print(f"  📄 {f}")
```

### Expected Behavior

When you run this script, the agent will:

1. **Create a todo list** via `write_todos` (e.g., "Search for fusion energy news", "Find recent breakthroughs", "Synthesize findings")
2. **Search the web** using `internet_search`
3. **Write notes** to files like `notes_1.txt`, `notes_2.txt` in `./research_output/`
4. **Check off todos** as it progresses
5. **Write a final report** to `report.md`
6. **Return the conversation** including all tool calls and final response

---

## 5.10 Further Resources

| Resource | Link |
|----------|------|
| **Official Documentation** | [docs.langchain.com/oss/python/deepagents](https://docs.langchain.com/oss/python/deepagents) |
| **GitHub Repository** | [github.com/langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) |
| **PyPI Package** | [pypi.org/project/deepagents](https://pypi.org/project/deepagents/) |
| **API Reference** | [reference.langchain.com/python/deepagents](https://reference.langchain.com/python/deepagents) |
| **Official Examples** | [github.com/langchain-ai/deepagents/tree/main/examples](https://github.com/langchain-ai/deepagents/tree/main/examples) |
| **DeepWiki Mirror** | [deepwiki.com/langchain-ai/deepagents](https://deepwiki.com/langchain-ai/deepagents) |
| **Talk Python Podcast** | Episode #543: Deep Agents — [talkpython.fm/episodes/show/543](https://talkpython.fm/episodes/show/543) |
| **LangChain Blog (v0.6)** | [langchain.com/blog/deep-agents-0-6](https://www.langchain.com/blog/deep-agents-0-6) |

---

## 5.11 Summary

**DeepAgents SDK** is LangChain's answer to the "deep agent" pattern — a high-level, opinionated harness that bundles planning, filesystem management, sub-agent delegation, memory, skills, and summarization into a single `create_deep_agent()` call. It sits atop LangGraph and `create_agent`, adding middleware layers that handle the complexity of long-running, multi-step agentic workflows.

**Key takeaways:**

- **One call, full harness:** `create_deep_agent()` gives you planning, filesystem, sub-agents, and context management instantly
- **Middleware is modular:** You can use individual middleware layers with standard `create_agent` if you don't want the full harness
- **Built for complex tasks:** Research assistants, coding agents, data pipelines — anything that requires planning and iteration
- **Active development:** Rapid release cycle (now at v0.6.7), with proven benchmark improvements
- **Not a replacement:** It complements LangChain/LangGraph; use standard `create_agent` for simpler needs

> **Bottom line:** If you're building a simple tool-calling agent, stick with `create_agent`. If you're building a Claude Code-style autonomous assistant that plans, writes files, and delegates to specialists — DeepAgents is the fastest path to production.
