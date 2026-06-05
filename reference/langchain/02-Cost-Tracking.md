# Section 2: LangChain Cost Tracking

> **Prerequisites:** Basic Python, familiarity with LangChain chains and LLM wrappers. This section assumes you know how to create a simple `ChatOpenAI` instance and run a chain.

---

## Table of Contents

1. [How Token Pricing Works](#1-how-token-pricing-works)
2. [Quick Start: `get_openai_callback`](#2-quick-start-get_openai_callback)
3. [Custom Callback Handlers](#3-custom-callback-handlers)
4. [Multi-Provider Cost Tracking](#4-multi-provider-cost-tracking)
5. [Tracking Costs Across Chains and Agents](#5-tracking-costs-across-chains-and-agents)
6. [Estimating Costs Before API Calls](#6-estimating-costs-before-api-calls)
7. [LangSmith Integration for Cost Analytics](#7-langsmith-integration-for-cost-analytics)
8. [Budget Management Patterns and Alerts](#8-budget-management-patterns-and-alerts)
9. [Best Practices Summary](#9-best-practices-summary)

---

## 1. How Token Pricing Works

Before tracking costs, you need to understand the pricing model. LLM providers charge by the **token** — a unit of text roughly equal to a word or part of a word. Costs are split into:

| Component | Description |
|-----------|-------------|
| **Input tokens** (prompt) | The text you send to the model |
| **Output tokens** (completion) | The text the model generates |

The total cost for a single API call is:

```
Cost = (input_tokens × input_price_per_token) + (output_tokens × output_price_per_token)
```

**Example pricing (as of 2025–2026, check current rates):**

| Model | Input ($/1K tokens) | Output ($/1K tokens) |
|-------|---------------------|----------------------|
| GPT-4o | $0.005 | $0.015 |
| GPT-4o-mini | $0.00015 | $0.0006 |
| Claude 3.5 Sonnet | $0.003 | $0.015 |
| Claude 3 Haiku | $0.00025 | $0.00125 |

> **Tip:** Always check the provider's official pricing page. Rates change frequently, and newer models are often dramatically cheaper.

---

## 2. Quick Start: `get_openai_callback`

LangChain provides a built-in context manager for tracking OpenAI token usage and costs: `get_openai_callback`. It wraps your LLM calls and automatically counts tokens and estimates spend.

### Basic Usage

```python
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import get_openai_callback

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

with get_openai_callback() as cb:
    response = llm.invoke("Explain quantum computing in one paragraph.")
    print(f"Response: {response.content}")
    print(f"---")
    print(f"Prompt tokens:     {cb.prompt_tokens}")
    print(f"Completion tokens: {cb.completion_tokens}")
    print(f"Total tokens:      {cb.total_tokens}")
    print(f"Estimated cost:    ${cb.total_cost:.6f}")
```

**Sample output:**

```
Response: Quantum computing uses quantum bits (qubits) that can exist in...
---
Prompt tokens:     12
Completion tokens: 89
Total tokens:      101
Estimated cost:    $0.000077
```

### What `get_openai_callback` Tracks

The callback object (`cb`) exposes these attributes:

| Attribute | Description |
|-----------|-------------|
| `cb.total_tokens` | Total tokens consumed (prompt + completion) |
| `cb.prompt_tokens` | Tokens in the prompt sent to the model |
| `cb.completion_tokens` | Tokens in the model's response |
| `cb.total_cost` | Estimated cost in USD (based on built-in pricing tables) |
| `cb.successful_requests` | Number of successful API calls |
| `cb.total_requests` | Total number of API calls attempted |

### Tracking Multiple Calls

The context manager accumulates across all calls within its scope:

```python
with get_openai_callback() as cb:
    # First call
    r1 = llm.invoke("What is the capital of France?")
    
    # Second call
    r2 = llm.invoke("What is the capital of Germany?")
    
    # Third call
    r3 = llm.invoke("What is the capital of Italy?")

print(f"All calls combined:")
print(f"  Total tokens: {cb.total_tokens}")
print(f"  Total cost:   ${cb.total_cost:.6f}")
print(f"  Requests:     {cb.successful_requests}")
```

### Using It with Chains

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import LLMChain

prompt = ChatPromptTemplate.from_template("Translate the following to French: {text}")
chain = prompt | llm

with get_openai_callback() as cb:
    result = chain.invoke({"text": "Hello, how are you today?"})
    print(f"Cost: ${cb.total_cost:.6f} for {cb.total_tokens} tokens")
```

> **Note:** `get_openai_callback` is **OpenAI-specific**. It works with `ChatOpenAI`, `OpenAI` (legacy), and OpenAI-compatible endpoints. For Anthropic, Google, or other providers, you need custom handlers (see Section 3 and 4).

---

## 3. Custom Callback Handlers

When you need more control — tracking across providers, logging to a database, or triggering alerts — build a custom callback handler by extending `BaseCallbackHandler`.

### Anatomy of a Callback Handler

```python
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

class CostTrackingCallback(BaseCallbackHandler):
    """Tracks token usage and cost for any LLM call."""
    
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        """Called when an LLM call begins."""
        self.calls += 1
        print(f"[Call #{self.calls}] LLM call started")
    
    def on_llm_end(self, response: LLMResult, **kwargs):
        """Called when an LLM call completes."""
        # Extract token usage from the response
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            self.prompt_tokens += usage.get("prompt_tokens", 0)
            self.completion_tokens += usage.get("completion_tokens", 0)
            self.total_tokens += usage.get("total_tokens", 0)
            print(f"[Call #{self.calls}] Tokens: {usage.get('total_tokens', 0)}")
    
    def on_llm_error(self, error, **kwargs):
        """Called if an LLM call fails."""
        print(f"[Call #{self.calls}] ERROR: {error}")
    
    def get_summary(self):
        """Return a summary of all tracked calls."""
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }
```

### Using Your Custom Handler

```python
from langchain_openai import ChatOpenAI

callback = CostTrackingCallback()
llm = ChatOpenAI(model="gpt-4o-mini", callbacks=[callback])

# Run some calls
llm.invoke("What is machine learning?")
llm.invoke("Explain neural networks.")

# Check the summary
summary = callback.get_summary()
print(f"\n=== Summary ===")
print(f"Calls: {summary['calls']}")
print(f"Total tokens: {summary['total_tokens']}")
```

### A More Robust Handler with Cost Calculation

```python
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Dict

# Pricing table: cost per token (not per 1K tokens)
PRICING = {
    "gpt-4o": {"input": 0.005 / 1000, "output": 0.015 / 1000},
    "gpt-4o-mini": {"input": 0.00015 / 1000, "output": 0.0006 / 1000},
    "gpt-4-turbo": {"input": 0.01 / 1000, "output": 0.03 / 1000},
    "claude-3-5-sonnet": {"input": 0.003 / 1000, "output": 0.015 / 1000},
    "claude-3-haiku": {"input": 0.00025 / 1000, "output": 0.00125 / 1000},
}

class DetailedCostCallback(BaseCallbackHandler):
    """Tracks tokens and calculates costs for multiple providers."""
    
    def __init__(self):
        self.calls: list[dict] = []
    
    def on_llm_end(self, response: LLMResult, **kwargs):
        # Try to identify the model from the response metadata
        model_name = "unknown"
        if response.llm_output:
            model_name = response.llm_output.get("model_name", "unknown")
        
        # Extract token usage
        usage = {}
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
        
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        
        # Calculate cost
        pricing = PRICING.get(model_name, {})
        input_cost = prompt_tokens * pricing.get("input", 0)
        output_cost = completion_tokens * pricing.get("output", 0)
        total_cost = input_cost + output_cost
        
        call_data = {
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": total_cost,
        }
        self.calls.append(call_data)
    
    def get_total_cost(self) -> float:
        return sum(c["cost"] for c in self.calls)
    
    def get_total_tokens(self) -> int:
        return sum(c["total_tokens"] for c in self.calls)
    
    def get_report(self) -> str:
        lines = ["=== Cost Report ==="]
        for i, call in enumerate(self.calls, 1):
            lines.append(
                f"  Call {i}: {call['model']} | "
                f"{call['total_tokens']} tokens | "
                f"${call['cost']:.6f}"
            )
        lines.append(f"\nTotal: {self.get_total_tokens()} tokens | ${self.get_total_cost():.6f}")
        return "\n".join(lines)
```

---

## 4. Multi-Provider Cost Tracking

Modern applications often use multiple LLM providers. Here's how to track costs across OpenAI, Anthropic, and others.

### Tracking Anthropic Costs

Anthropic models return token usage in a slightly different format. Here's a handler that works with `ChatAnthropic`:

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

class AnthropicCostCallback(BaseCallbackHandler):
    """Tracks Anthropic Claude token usage and costs."""
    
    # Claude pricing (per token)
    PRICING = {
        "claude-3-5-sonnet": {"input": 0.003 / 1000, "output": 0.015 / 1000},
        "claude-3-haiku": {"input": 0.00025 / 1000, "output": 0.00125 / 1000},
        "claude-3-opus": {"input": 0.015 / 1000, "output": 0.075 / 1000},
    }
    
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
    
    def on_llm_end(self, response: LLMResult, **kwargs):
        # Anthropic returns usage in response.generations[0].generation_info
        if response.generations:
            gen_info = response.generations[0][0].generation_info or {}
            usage = gen_info.get("usage", {})
            
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            
            # Try to determine model from metadata
            model = gen_info.get("model", "claude-3-5-sonnet")
            
            pricing = self.PRICING.get(model, self.PRICING["claude-3-5-sonnet"])
            cost = (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])
            
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += cost
    
    def get_summary(self):
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "cost": self.total_cost,
        }

# Usage
anthropic_cb = AnthropicCostCallback()
claude = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    callbacks=[anthropic_cb]
)

claude.invoke("What is the theory of relativity?")
print(anthropic_cb.get_summary())
```

### Unified Multi-Provider Tracker

For applications using multiple providers, create a unified tracker:

```python
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Dict, Optional

class UnifiedCostTracker(BaseCallbackHandler):
    """Tracks costs across OpenAI, Anthropic, and other providers."""
    
    # Pricing per token
    PRICING: Dict[str, Dict[str, float]] = {
        # OpenAI
        "gpt-4o": {"input": 0.005 / 1000, "output": 0.015 / 1000},
        "gpt-4o-mini": {"input": 0.00015 / 1000, "output": 0.0006 / 1000},
        "gpt-4-turbo": {"input": 0.01 / 1000, "output": 0.03 / 1000},
        # Anthropic
        "claude-3-5-sonnet": {"input": 0.003 / 1000, "output": 0.015 / 1000},
        "claude-3-haiku": {"input": 0.00025 / 1000, "output": 0.00125 / 1000},
    }
    
    def __init__(self):
        self.calls = []
        self._current_model = None
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        # Try to capture model name from serialized info
        if serialized and "kwargs" in serialized:
            self._current_model = serialized["kwargs"].get("model", "unknown")
    
    def on_llm_end(self, response: LLMResult, **kwargs):
        model = self._current_model or "unknown"
        
        # Extract usage — try multiple formats
        usage = self._extract_usage(response, model)
        
        pricing = self.PRICING.get(model, {"input": 0, "output": 0})
        cost = (usage["input"] * pricing["input"]) + (usage["output"] * pricing["output"])
        
        self.calls.append({
            "model": model,
            "input_tokens": usage["input"],
            "output_tokens": usage["output"],
            "cost": cost,
        })
    
    def _extract_usage(self, response: LLMResult, model: str) -> Dict[str, int]:
        """Extract token usage from response, handling provider differences."""
        
        # OpenAI format
        if response.llm_output and "token_usage" in response.llm_output:
            tu = response.llm_output["token_usage"]
            return {
                "input": tu.get("prompt_tokens", 0),
                "output": tu.get("completion_tokens", 0),
            }
        
        # Anthropic format
        if response.generations:
            gen_info = response.generations[0][0].generation_info or {}
            usage = gen_info.get("usage", {})
            if "input_tokens" in usage:
                return {
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                }
        
        return {"input": 0, "output": 0}
    
    def get_summary(self) -> Dict:
        total_cost = sum(c["cost"] for c in self.calls)
        total_input = sum(c["input_tokens"] for c in self.calls)
        total_output = sum(c["output_tokens"] for c in self.calls)
        
        # Breakdown by model
        by_model = {}
        for c in self.calls:
            model = c["model"]
            if model not in by_model:
                by_model[model] = {"calls": 0, "tokens": 0, "cost": 0.0}
            by_model[model]["calls"] += 1
            by_model[model]["tokens"] += c["input_tokens"] + c["output_tokens"]
            by_model[model]["cost"] += c["cost"]
        
        return {
            "total_calls": len(self.calls),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost": total_cost,
            "by_model": by_model,
        }
```

---

## 5. Tracking Costs Across Chains and Agents

Chains and agents make multiple LLM calls internally. You need to track at the **outermost level** to capture everything.

### Tracking a Simple Chain

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.callbacks import get_openai_callback

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "{question}"),
])
chain = prompt | llm

with get_openai_callback() as cb:
    result = chain.invoke({"question": "What is the speed of light?"})
    print(f"Answer: {result.content}")
    print(f"Chain cost: ${cb.total_cost:.6f} ({cb.total_tokens} tokens)")
```

### Tracking an Agent (Multiple Tool Calls)

Agents are where costs can explode — each tool call may trigger another LLM invocation. Always wrap the agent execution:

```python
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.tools import Tool
from langchain_community.callbacks import get_openai_callback
from langchain import hub

# Define a simple tool
def multiply(a: str, b: str) -> str:
    """Multiply two numbers."""
    return str(float(a) * float(b))

tools = [
    Tool(
        name="multiply",
        func=lambda x: multiply(*x.split(",")),
        description="Multiply two numbers. Input: 'a,b'",
    )
]

# Create agent
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
prompt = hub.pull("hwchase17/react")
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

# Track ALL agent activity
with get_openai_callback() as cb:
    result = agent_executor.invoke({
        "input": "What is 123 times 456? Use the multiply tool."
    })
    print(f"Result: {result['output']}")
    print(f"---")
    print(f"Agent made {cb.successful_requests} LLM calls")
    print(f"Total tokens: {cb.total_tokens}")
    print(f"Total cost: ${cb.total_cost:.6f}")
```

### Tracking a RAG Pipeline

RAG pipelines often involve an embedding call + an LLM call. Track them together:

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_community.callbacks import get_openai_callback

# Setup
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o-mini")

# Create a simple vector store
docs = ["Paris is the capital of France.", "Berlin is the capital of Germany."]
vectorstore = FAISS.from_texts(docs, embeddings)
retriever = vectorstore.as_retriever()

# RAG prompt
prompt = ChatPromptTemplate.from_template("""
Use the following context to answer the question.
Context: {context}
Question: {question}
Answer:
""")

# Build chain
rag_chain = (
    {"context": retriever | (lambda docs: "\n".join(d.page_content for d in docs)),
     "question": lambda x: x}
    | prompt
    | llm
)

with get_openai_callback() as cb:
    result = rag_chain.invoke("What is the capital of France?")
    print(f"Answer: {result.content}")
    print(f"---")
    print(f"Total tokens: {cb.total_tokens}")
    print(f"Total cost: ${cb.total_cost:.6f}")
    # Note: embedding costs are tracked separately if you need them
```

> **Important:** `get_openai_callback` tracks OpenAI LLM calls. Embedding calls through `OpenAIEmbeddings` are also tracked. If you use a different embedding provider, add a custom handler for it.

---

## 6. Estimating Costs Before API Calls

Sometimes you want to know the cost *before* you spend the money. You can estimate by counting tokens in the prompt and predicting output length.

### Counting Tokens with Tiktoken

```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in a string for a given model."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")  # Fallback
    return len(encoding.encode(text))

# Example
prompt = "Explain the theory of general relativity in simple terms."
tokens = count_tokens(prompt, "gpt-4o")
print(f"Prompt tokens: {tokens}")

# Estimate cost
input_price = 0.005 / 1000  # gpt-4o input
# Assume output will be ~200 tokens
estimated_output = 200
output_price = 0.015 / 1000  # gpt-4o output

estimated_cost = (tokens * input_price) + (estimated_output * output_price)
print(f"Estimated cost: ${estimated_cost:.6f}")
```

### Estimating Chain Costs

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import tiktoken

class CostEstimator:
    """Estimates cost before running a chain."""
    
    PRICING = {
        "gpt-4o": {"input": 0.005 / 1000, "output": 0.015 / 1000},
        "gpt-4o-mini": {"input": 0.00015 / 1000, "output": 0.0006 / 1000},
    }
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        self.pricing = self.PRICING.get(model, self.PRICING["gpt-4o-mini"])
    
    def estimate(self, prompt_text: str, expected_output_tokens: int = 150) -> dict:
        input_tokens = len(self.encoding.encode(prompt_text))
        input_cost = input_tokens * self.pricing["input"]
        output_cost = expected_output_tokens * self.pricing["output"]
        
        return {
            "input_tokens": input_tokens,
            "expected_output_tokens": expected_output_tokens,
            "estimated_input_cost": input_cost,
            "estimated_output_cost": output_cost,
            "estimated_total_cost": input_cost + output_cost,
        }

# Usage
estimator = CostEstimator("gpt-4o-mini")

prompt = ChatPromptTemplate.from_template("Summarize this article: {article}")
formatted = prompt.format(article="This is a long article about quantum physics..." * 50)

estimate = estimator.estimate(formatted, expected_output_tokens=100)
print(f"Estimated input tokens: {estimate['input_tokens']}")
print(f"Estimated cost: ${estimate['estimated_total_cost']:.6f}")

# Now decide if you want to run it
if estimate["estimated_total_cost"] > 0.01:
    print("Warning: This call may cost more than $0.01")
```

### Pre-Call Budget Check

```python
class BudgetGuard:
    """Prevents API calls that would exceed a budget."""
    
    def __init__(self, max_cost_per_call: float = 0.05):
        self.max_cost = max_cost_per_call
        self.estimator = CostEstimator()
    
    def check(self, prompt: str, expected_output: int = 200) -> bool:
        estimate = self.estimator.estimate(prompt, expected_output)
        if estimate["estimated_total_cost"] > self.max_cost:
            print(f"BUDGET BLOCK: Estimated cost ${estimate['estimated_total_cost']:.6f} "
                  f"exceeds max ${self.max_cost:.6f}")
            return False
        return True

# Usage
guard = BudgetGuard(max_cost_per_call=0.01)

long_prompt = "Write a 10,000 word essay on..." * 1000
if guard.check(long_prompt, expected_output=5000):
    # Safe to run
    pass
else:
    # Reject or use cheaper model
    print("Consider using gpt-4o-mini or truncating prompt")
```

---

## 7. LangSmith Integration for Cost Analytics

LangSmith is LangChain's observability platform. It automatically tracks costs, tokens, and latency for every run — no custom code required for basic tracking.

### Setting Up LangSmith

```python
import os

# Set environment variables (or use a .env file)
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "ls-your-api-key-here"
os.environ["LANGCHAIN_PROJECT"] = "cost-tracking-demo"  # Optional: group runs by project
```

Once set, all LangChain calls are automatically traced:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")

# This call is automatically traced in LangSmith
result = llm.invoke("What is the capital of Australia?")
```

### What LangSmith Tracks Automatically

| Metric | Description |
|--------|-------------|
| **Token counts** | Prompt, completion, and total tokens per call |
| **Estimated cost** | Calculated from provider pricing tables |
| **Latency** | Time from request to response |
| **Model name** | Which model was used |
| **Full trace** | Nested view of chains, tools, and agents |

### Viewing Costs in the LangSmith UI

1. Go to [smith.langchain.com](https://smith.langchain.com)
2. Navigate to your project
3. Click on any run to see token counts and estimated cost
4. Use the **Monitoring** tab for aggregate cost dashboards

### Adding Metadata for Cost Attribution

Tag runs with metadata to analyze costs by feature, user, or experiment:

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_template("Answer: {question}")
chain = prompt | llm

# Add metadata to the run
result = chain.invoke(
    {"question": "What is photosynthesis?"},
    config={
        "metadata": {
            "user_id": "user-123",
            "feature": "qa-bot",
            "experiment": "v2-prompt",
        }
    }
)
```

In LangSmith, you can filter and aggregate by these metadata fields.

### Programmatic Cost Retrieval

Fetch cost data via the LangSmith API for external dashboards:

```python
from langsmith import Client

client = Client()

# List runs for a project
runs = client.list_runs(
    project_name="cost-tracking-demo",
    start_time="2025-01-01T00:00:00Z",
    end_time="2025-01-31T23:59:59Z",
)

total_cost = 0.0
total_tokens = 0

for run in runs:
    if run.total_tokens:
        total_tokens += run.total_tokens
    # LangSmith stores estimated cost in the run
    if hasattr(run, 'extra') and run.extra:
        cost = run.extra.get('estimated_cost', 0)
        total_cost += cost

print(f"Project total: {total_tokens} tokens, ${total_cost:.4f}")
```

### Custom Pricing in LangSmith

If you have negotiated rates with a provider, override the default pricing:

```python
# In LangSmith UI:
# Settings → Projects → [Your Project] → Cost Tracking → Custom Pricing
# Or via API:

from langsmith import Client

client = Client()
client.update_project(
    project_name="cost-tracking-demo",
    custom_price_per_token={
        "gpt-4o": {"input": 0.004 / 1000, "output": 0.012 / 1000},
    }
)
```

---

## 8. Budget Management Patterns and Alerts

For production applications, you need active cost controls — not just tracking.

### Pattern 1: Per-Request Budget Limit

```python
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import get_openai_callback

class BudgetExceededError(Exception):
    pass

def invoke_with_budget(llm, prompt: str, max_cost: float = 0.01):
    """Invoke an LLM with a strict per-call budget."""
    with get_openai_callback() as cb:
        result = llm.invoke(prompt)
        
        if cb.total_cost > max_cost:
            raise BudgetExceededError(
                f"Call cost ${cb.total_cost:.6f} exceeded budget ${max_cost:.6f}"
            )
    
    return result

# Usage
llm = ChatOpenAI(model="gpt-4o")
try:
    result = invoke_with_budget(llm, "Write a novel.", max_cost=0.01)
except BudgetExceededError as e:
    print(f"Budget exceeded: {e}")
    # Fallback to cheaper model
    cheap_llm = ChatOpenAI(model="gpt-4o-mini")
    result = cheap_llm.invoke("Write a novel.")
```

### Pattern 2: Daily/Monthly Budget Tracker

```python
import json
from datetime import datetime, date
from pathlib import Path

class DailyBudgetTracker:
    """Tracks cumulative daily spend and enforces limits."""
    
    def __init__(self, budget_file: str = "budget.json", daily_limit: float = 5.0):
        self.budget_file = Path(budget_file)
        self.daily_limit = daily_limit
        self._today = str(date.today())
        self._spent_today = self._load_spent()
    
    def _load_spent(self) -> float:
        if not self.budget_file.exists():
            return 0.0
        data = json.loads(self.budget_file.read_text())
        if data.get("date") == self._today:
            return data.get("spent", 0.0)
        return 0.0
    
    def _save_spent(self):
        self.budget_file.write_text(json.dumps({
            "date": self._today,
            "spent": self._spent_today,
        }))
    
    def can_spend(self, estimated_cost: float) -> bool:
        return (self._spent_today + estimated_cost) <= self.daily_limit
    
    def record_spend(self, cost: float):
        self._spent_today += cost
        self._save_spent()
    
    def get_remaining(self) -> float:
        return max(0, self.daily_limit - self._spent_today)

# Usage with LangChain
tracker = DailyBudgetTracker(daily_limit=10.0)
llm = ChatOpenAI(model="gpt-4o-mini")

with get_openai_callback() as cb:
    result = llm.invoke("Tell me a joke.")
    tracker.record_spend(cb.total_cost)

print(f"Remaining budget today: ${tracker.get_remaining():.2f}")

# Check before a big call
if tracker.can_spend(0.05):
    with get_openai_callback() as cb:
        result = llm.invoke("Write a detailed analysis...")
        tracker.record_spend(cb.total_cost)
else:
    print("Daily budget exhausted. Try again tomorrow.")
```

### Pattern 3: Alert on Threshold

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cost-alerts")

class AlertingCallback:
    """Wraps any callback and adds threshold alerts."""
    
    def __init__(self, callback, alert_threshold: float = 1.0):
        self.callback = callback
        self.alert_threshold = alert_threshold
        self._alerted = False
    
    def on_llm_end(self, response, **kwargs):
        self.callback.on_llm_end(response, **kwargs)
        
        # Check if we crossed the threshold
        total_cost = getattr(self.callback, 'total_cost', 0)
        if total_cost >= self.alert_threshold and not self._alerted:
            logger.warning(
                f"COST ALERT: Total spend ${total_cost:.4f} exceeded "
                f"threshold ${self.alert_threshold:.4f}"
            )
            self._alerted = True
            # In production: send email, Slack, PagerDuty, etc.

# Usage with get_openai_callback
from langchain_community.callbacks import get_openai_callback

with get_openai_callback() as cb:
    alerting = AlertingCallback(cb, alert_threshold=0.50)
    
    # Run many calls
    for i in range(100):
        llm.invoke(f"Question {i}")
        alerting.on_llm_end(None)  # Trigger check
```

### Pattern 4: Circuit Breaker for Runaway Costs

```python
class CostCircuitBreaker:
    """Stops all LLM calls after a cost threshold is hit."""
    
    def __init__(self, max_cost: float = 50.0):
        self.max_cost = max_cost
        self.total_cost = 0.0
        self._tripped = False
    
    def check(self, estimated_cost: float = 0) -> bool:
        if self._tripped:
            return False
        if (self.total_cost + estimated_cost) > self.max_cost:
            self._tripped = True
            logger.error(f"CIRCUIT BREAKER TRIPPED at ${self.total_cost:.4f}")
            return False
        return True
    
    def record(self, cost: float):
        self.total_cost += cost
    
    @property
    def is_open(self) -> bool:
        return not self._tripped

# Usage
breaker = CostCircuitBreaker(max_cost=10.0)
llm = ChatOpenAI(model="gpt-4o-mini")

for i in range(1000):
    if not breaker.check():
        print("Circuit breaker open. Stopping.")
        break
    
    with get_openai_callback() as cb:
        llm.invoke(f"Generate text batch {i}")
        breaker.record(cb.total_cost)
```

---

## 9. Best Practices Summary

| Practice | Why It Matters |
|----------|---------------|
| **Always wrap agent execution** | Agents make unpredictable numbers of LLM calls. Without tracking, a single request can cost dollars. |
| **Use `get_openai_callback` for OpenAI** | It's built-in, accurate, and requires zero configuration. |
| **Build custom handlers for multi-provider apps** | Each provider returns token usage differently. One unified handler keeps your code clean. |
| **Estimate before expensive calls** | Use `tiktoken` to count prompt tokens and decide if a call is worth it. |
| **Set daily/monthly budgets** | Production apps need hard limits. Persist budget state to a file or database. |
| **Use LangSmith for observability** | Automatic tracing, dashboards, and cost attribution with minimal code. |
| **Alert on thresholds** | Don't discover a runaway cost at the end of the month. Alert in real time. |
| **Track by metadata** | Tag runs with user_id, feature, experiment_id. This lets you find which parts of your app are expensive. |
| **Use cheaper models for simple tasks** | gpt-4o-mini is ~30x cheaper than gpt-4o. Not every task needs the best model. |
| **Review costs regularly** | Weekly cost reviews catch drift before it becomes a problem. |

---

## Quick Reference: Cost Tracking Cheat Sheet

```python
# === OpenAI: Quick tracking ===
from langchain_community.callbacks import get_openai_callback

with get_openai_callback() as cb:
    result = llm.invoke("Hello")
    print(f"${cb.total_cost:.6f} | {cb.total_tokens} tokens")

# === Custom handler: Multi-provider ===
from langchain_core.callbacks import BaseCallbackHandler

class MyTracker(BaseCallbackHandler):
    def on_llm_end(self, response, **kwargs):
        # Extract and log usage
        pass

llm = ChatOpenAI(callbacks=[MyTracker()])

# === Pre-call estimate ===
import tiktoken
enc = tiktoken.encoding_for_model("gpt-4o")
tokens = len(enc.encode(prompt))
cost = tokens * (0.005 / 1000)

# === LangSmith: Automatic tracing ===
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "..."
# All calls traced automatically

# === Budget guard ===
class BudgetGuard:
    def check(self, estimated_cost: float) -> bool:
        return estimated_cost <= self.max_cost
```

---

*Next Section: [Section 3: LangChain Performance Optimization](../sections/03-performance-optimization.md)*
