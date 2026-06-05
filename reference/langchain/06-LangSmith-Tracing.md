# 6. LangSmith Tracing

> **Prerequisites:** Basic Python, familiarity with LangChain (helpful but not required).  
> **Estimated reading time:** 25 minutes  
> **Companion code:** All examples are runnable with `langsmith>=0.1.0` and `langchain>=0.2.0`.

---

## 6.1 What LangSmith Is and Why Tracing Matters

### The Problem: Black-Box LLM Applications

Building with LLMs is deceptively simple. A few lines of Python and you have a chatbot, a retrieval pipeline, or an agent. But when something goes wrong in production—when a customer sees a hallucinated answer, when latency spikes, when costs balloon—you're often staring at a black box.

Consider a typical RAG pipeline:

```
User Query → Retrieval (vector DB) → Prompt Construction → LLM Call → Post-processing → Response
```

If the final answer is wrong, which step failed? Was the retrieval irrelevant? Was the prompt misleading? Did the model simply hallucinate? Without tracing, you're reduced to `print()` debugging and educated guessing.

### What LangSmith Provides

**LangSmith** is an observability platform built by the LangChain team for LLM applications. It captures every step of execution—inputs, outputs, token usage, latencies, errors—and presents them as structured, queryable traces.

Key capabilities:

| Capability | What It Gives You |
|------------|-------------------|
| **Execution Tracing** | Hierarchical view of every function call, LLM invocation, and tool use |
| **Prompt Debugging** | Inspect the exact prompt sent to the model, including templated variables |
| **Performance Monitoring** | Token counts, latency per step, end-to-end duration |
| **Cost Analysis** | Break down spend by model, feature, user segment, or environment |
| **Evaluation & Experiments** | Run datasets against different prompts/models and compare results |
| **Feedback & Annotation** | Capture human or automated feedback on traces to build training datasets |

### Why Tracing Is Non-Negotiable

1. **Non-determinism:** LLMs produce different outputs for identical inputs. You need to see *what actually happened* for a specific user request.

2. **Composition complexity:** Modern LLM apps chain retrieval, tool calls, multiple model invocations, and post-processing. A flat log is insufficient—you need the tree structure.

3. **Cost opacity:** A single agent loop might call an LLM 5–10 times. Without per-step tracking, you cannot optimize spending.

4. **Regression detection:** When you change a prompt or swap a model, you need before/after comparisons on real data.

---

## 6.2 Setting Up LangSmith

### 6.2.1 Installation

```bash
pip install langsmith
# If using LangChain:
pip install langchain langsmith
```

### 6.2.2 API Keys and Environment Configuration

LangSmith requires an API key. Sign up at [smith.langchain.com](https://smith.langchain.com), create an organization, and generate a key.

Configure via environment variables (recommended for all applications):

```bash
export LANGCHAIN_API_KEY="ls-your-api-key-here"
export LANGCHAIN_TRACING_V2="true"          # Enable tracing globally
export LANGCHAIN_PROJECT="my-app-prod"      # Default project name
export LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"  # Optional: custom endpoint
```

Or in Python (useful for notebooks or multi-tenant setups):

```python
import os

os.environ["LANGCHAIN_API_KEY"] = "ls-your-api-key-here"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "my-app-prod"
```

### 6.2.3 Project Configuration

Projects in LangSmith isolate traces. Common patterns:

| Project Name | Purpose |
|-------------|---------|
| `my-app-dev` | Local development and experimentation |
| `my-app-staging` | Pre-production validation |
| `my-app-prod` | Production traffic |
| `my-app-eval` | Evaluation runs and regression tests |

Switch projects at runtime:

```python
from langchain.callbacks.tracers import LangChainTracer

# Override the project for a specific run
tracer = LangChainTracer(project_name="my-app-eval")
```

### 6.2.4 Verifying Your Setup

```python
from langsmith import Client

client = Client()

# List recent runs to confirm connectivity
runs = list(client.list_runs(project_name="my-app-prod", limit=5))
print(f"Connected! Found {len(runs)} recent runs.")
```

If this executes without errors and returns run data, your setup is correct.

---

## 6.3 Automatic Tracing with `@traceable`

The `@traceable` decorator is the fastest way to instrument your code. Wrap any function, and LangSmith captures its inputs, outputs, execution time, and exceptions automatically.

### 6.3.1 Basic Usage

```python
from langsmith import traceable

@traceable(name="generate_greeting")
def generate_greeting(name: str, tone: str = "friendly") -> str:
    """Generate a personalized greeting."""
    greetings = {
        "friendly": f"Hey {name}, great to see you!",
        "formal": f"Good day, {name}. Welcome.",
        "excited": f"WOW, {name} is HERE! 🎉"
    }
    return greetings.get(tone, greetings["friendly"])

# This call is automatically traced
result = generate_greeting("Alice", tone="excited")
print(result)
```

In the LangSmith dashboard, you'll see:
- **Run name:** `generate_greeting`
- **Inputs:** `{"name": "Alice", "tone": "excited"}`
- **Outputs:** `{"output": "WOW, Alice is HERE! 🎉"}`
- **Latency:** ~0.001s
- **Status:** Success

### 6.3.2 Tracing LLM Calls

```python
from langsmith import traceable
from openai import OpenAI

client = OpenAI()

@traceable(name="ask_llm", run_type="llm")
def ask_llm(question: str, model: str = "gpt-4o-mini") -> str:
    """Ask a question to an LLM."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

answer = ask_llm("What is the capital of Estonia?")
print(answer)
```

**Key parameter:** `run_type="llm"` tells LangSmith this is an LLM invocation, enabling token usage tracking and model-specific analytics.

### 6.3.3 Nested Tracing

When `@traceable` functions call each other, LangSmith builds a hierarchical trace tree automatically:

```python
from langsmith import traceable

@traceable(name="retrieve_context")
def retrieve_context(query: str) -> list[str]:
    """Simulate document retrieval."""
    return [
        f"Document about {query} - part 1",
        f"Document about {query} - part 2"
    ]

@traceable(name="build_prompt")
def build_prompt(query: str, context: list[str]) -> str:
    """Build a RAG-style prompt."""
    context_str = "\n\n".join(context)
    return f"Context:\n{context_str}\n\nQuestion: {query}\nAnswer:"

@traceable(name="rag_pipeline")
def rag_pipeline(query: str) -> str:
    """End-to-end RAG pipeline."""
    context = retrieve_context(query)
    prompt = build_prompt(query, context)
    # In a real app, you'd call an LLM here
    return f"[Simulated LLM response for: {prompt[:50]}...]"

result = rag_pipeline("quantum computing")
```

The resulting trace in LangSmith:

```
rag_pipeline (root)
├── retrieve_context
│   └── Input: "quantum computing"
│   └── Output: ["Document about quantum computing - part 1", ...]
├── build_prompt
│   └── Input: "quantum computing", ["Document...", "Document..."]
│   └── Output: "Context:\nDocument about quantum..."
└── Output: "[Simulated LLM response for: ...]"
```

### 6.3.4 Advanced `@traceable` Options

```python
from langsmith import traceable

@traceable(
    name="complex_function",
    run_type="chain",           # "llm", "chain", "tool", "retriever", "agent"
    tags=["production", "v2"],  # Tags for filtering
    metadata={                  # Custom key-value pairs
        "version": "2.1.0",
        "team": "search"
    }
)
def complex_function(user_id: str, query: str) -> dict:
    """A function with full tracing metadata."""
    return {"user_id": user_id, "result": f"Processed: {query}"}
```

---

## 6.4 Manual Tracing with `RunTree`

For fine-grained control—when you need to start, end, and nest runs explicitly—use the `RunTree` API.

### 6.4.1 Creating a Manual Run

```python
from langsmith import Client
from langsmith.run_trees import RunTree

client = Client()

# Create a root run
run = RunTree(
    name="manual_pipeline",
    run_type="chain",
    inputs={"query": "machine learning trends"},
    client=client
)

# Execute your logic
result = f"Analysis of: {run.inputs['query']}"

# End the run with outputs
run.end(outputs={"result": result})

# Persist to LangSmith
run.post()

print(f"Run posted: {run.id}")
```

### 6.4.2 Nesting Child Runs

```python
from langsmith import Client
from langsmith.run_trees import RunTree

client = Client()

# Root run
root = RunTree(
    name="data_processing_pipeline",
    run_type="chain",
    inputs={"raw_data": [1, 2, 3, 4, 5]},
    client=client
)

# Child run: extraction step
extraction = RunTree(
    name="extract_features",
    run_type="chain",
    inputs={"data": [1, 2, 3, 4, 5]},
    parent=root  # Link to parent
)

features = [x * 2 for x in extraction.inputs["data"]]
extraction.end(outputs={"features": features})

# Child run: validation step
validation = RunTree(
    name="validate_features",
    run_type="chain",
    inputs={"features": features},
    parent=root
)

is_valid = all(f > 0 for f in validation.inputs["features"])
validation.end(outputs={"valid": is_valid})

# End root and post everything
root.end(outputs={"features": features, "valid": is_valid})
root.post()
```

### 6.4.3 When to Use `RunTree` Over `@traceable`

| Use `@traceable` when... | Use `RunTree` when... |
|--------------------------|------------------------|
| You have discrete functions with clear inputs/outputs | You need to trace non-function boundaries (loops, async tasks) |
| You want minimal code changes | You need to add child runs dynamically based on runtime conditions |
| The call tree matches your function call tree | You need to trace across process or service boundaries |
| You're prototyping quickly | You need to attach runs to existing external trace IDs |

---

## 6.5 Tracing Chains, Agents, and Custom Functions

### 6.5.1 Tracing LangChain Chains

LangChain chains trace automatically when `LANGCHAIN_TRACING_V2=true` is set:

```python
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "chain-examples"

# Define a simple chain
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a concise technical writer."),
    ("user", "Explain {topic} in one sentence.")
])

model = ChatOpenAI(model="gpt-4o-mini")
parser = StrOutputParser()

chain = prompt | model | parser

# This entire pipeline is traced automatically
result = chain.invoke({"topic": "vector databases"})
print(result)
```

In LangSmith, you'll see:
- The `ChatPromptTemplate` invocation with resolved variables
- The `ChatOpenAI` call with full messages and token usage
- The `StrOutputParser` transformation

### 6.5.2 Tracing Agents

Agents are particularly valuable to trace because they involve loops, tool calls, and decision-making:

```python
import os
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "agent-examples"

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def search(query: str) -> str:
    """Search for information. Returns simulated results."""
    return f"Simulated search results for: {query}"

tools = [calculator, search]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant with access to tools."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

model = ChatOpenAI(model="gpt-4o", temperature=0)
agent = create_openai_tools_agent(model, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# This agent loop is fully traced
result = executor.invoke({"input": "What is 1234 * 5678? Also, what's the weather like?"})
print(result["output"])
```

The LangSmith trace will show:
- Each agent iteration (thought → action → observation)
- Individual tool calls with inputs and outputs
- The final agent response
- Token usage and latency per iteration

### 6.5.3 Tracing Custom Functions in Complex Workflows

For non-LangChain code, combine `@traceable` with custom logic:

```python
from langsmith import traceable
from openai import OpenAI
import time

client = OpenAI()

@traceable(name="fetch_data", run_type="retriever")
def fetch_data(source: str, query: str) -> dict:
    """Simulate fetching data from an external source."""
    time.sleep(0.1)  # Simulate network latency
    return {
        "source": source,
        "results": [f"Result 1 for {query}", f"Result 2 for {query}"]
    }

@traceable(name="enrich_query", run_type="chain")
def enrich_query(raw_query: str) -> str:
    """Expand a user query with context."""
    return f"Detailed analysis of: {raw_query}"

@traceable(name="generate_with_context", run_type="llm")
def generate_with_context(query: str, context: dict) -> str:
    """Generate a response using fetched context."""
    context_str = "\n".join(context["results"])
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Use the provided context to answer."},
            {"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {query}"}
        ]
    )
    return response.choices[0].message.content

@traceable(name="full_workflow", run_type="chain")
def full_workflow(user_query: str) -> dict:
    """Orchestrate the complete workflow."""
    enriched = enrich_query(user_query)
    data = fetch_data("knowledge_base", enriched)
    answer = generate_with_context(enriched, data)
    
    return {
        "query": user_query,
        "enriched_query": enriched,
        "answer": answer,
        "sources": data["results"]
    }

# Execute and trace
result = full_workflow("renewable energy trends")
print(result["answer"])
```

---

## 6.6 Grouping Related Traces with Metadata and Tags

### 6.6.1 Tags for Filtering

Tags are string labels you can apply to runs for filtering in the LangSmith UI:

```python
from langsmith import traceable

@traceable(name="classify_email", tags=["production", "classification", "v1.2"])
def classify_email(email_body: str) -> str:
    """Classify an email as spam or not spam."""
    return "not_spam"  # Simplified

# You can also add tags at invocation time
from langchain.callbacks.tracers import LangChainTracer

tracer = LangChainTracer(
    project_name="my-app",
    tags=["urgent", "customer-request"]
)
```

In the LangSmith dashboard, filter by:
- `tag:production` — all production runs
- `tag:classification` — all classification tasks
- `tag:v1.2` — specific version

### 6.6.2 Metadata for Structured Context

Metadata accepts arbitrary key-value pairs for richer querying:

```python
from langsmith import traceable

@traceable(
    name="process_order",
    metadata={
        "service": "order-processing",
        "version": "2.1.0",
        "environment": "production",
        "team": "commerce"
    }
)
def process_order(order_id: str, items: list) -> dict:
    """Process a customer order."""
    return {"order_id": order_id, "status": "processed", "item_count": len(items)}

# Metadata is also available on LangChain runs
from langchain_core.runnables import RunnableConfig

config = RunnableConfig(
    metadata={
        "user_id": "user_12345",
        "session_id": "sess_abc",
        "feature": "chat_support"
    }
)

# Pass config to any LangChain invoke
# chain.invoke(input, config=config)
```

### 6.6.3 Querying Runs by Metadata

```python
from langsmith import Client

client = Client()

# Find all runs from a specific service version
runs = client.list_runs(
    project_name="my-app",
    filter='eq(metadata["version"], "2.1.0")',
    limit=50
)

# Find runs for a specific user
user_runs = client.list_runs(
    project_name="my-app",
    filter='eq(metadata["user_id"], "user_12345")'
)

# Complex filter: production classification runs in v1.2
filtered = client.list_runs(
    project_name="my-app",
    filter='and(eq(metadata["environment"], "production"), eq(metadata["version"], "1.2"))'
)
```

### 6.6.4 Grouping Related Runs with IDs

For multi-step workflows that span separate processes or services, use a shared trace ID:

```python
from langsmith import Client
from langsmith.run_trees import RunTree
import uuid

client = Client()

# Generate a shared trace ID
shared_trace_id = str(uuid.uuid4())

# Step 1: Ingestion service
ingestion_run = RunTree(
    name="ingest_request",
    run_type="chain",
    inputs={"raw_request": "Book a flight to Paris"},
    id=shared_trace_id,  # This becomes the root trace ID
    client=client
)
ingestion_run.end(outputs={"parsed": {"intent": "book_flight", "destination": "Paris"}})
ingestion_run.post()

# Step 2: Booking service (separate process/machine)
booking_run = RunTree(
    name="process_booking",
    run_type="chain",
    inputs={"parsed_request": {"intent": "book_flight", "destination": "Paris"}},
    parent_id=shared_trace_id,  # Link to the same trace
    client=client
)
booking_run.end(outputs={"confirmation": "ABC123", "status": "confirmed"})
booking_run.post()
```

Both runs appear under the same trace in LangSmith, giving you end-to-end visibility across services.

---

## 6.7 Debugging with LangSmith

### 6.7.1 Viewing Prompts

One of the most common debugging tasks is inspecting the exact prompt sent to an LLM. LangSmith captures the fully rendered prompt, including all template variables:

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a {role}. Be {tone}."),
    ("user", "Tell me about {topic}.")
])

model = ChatOpenAI(model="gpt-4o-mini")
chain = prompt | model

result = chain.invoke({
    "role": "scientist",
    "tone": "concise",
    "topic": "photosynthesis"
})
```

In LangSmith, click on the `ChatPromptTemplate` step to see:

```
System: You are a scientist. Be concise.
User: Tell me about photosynthesis.
```

This is invaluable for debugging prompt injection issues, template errors, or unexpected formatting.

### 6.7.2 Token Usage Analysis

Token usage is captured automatically for supported LLM providers:

```python
from langsmith import Client

client = Client()

# Get the most recent run
runs = list(client.list_runs(project_name="my-app", limit=1))
if runs:
    run = runs[0]
    print(f"Run: {run.name}")
    print(f"Input tokens: {run.inputs.get('token_usage', {}).get('prompt_tokens', 'N/A')}")
    print(f"Output tokens: {run.inputs.get('token_usage', {}).get('completion_tokens', 'N/A')}")
    print(f"Total tokens: {run.inputs.get('token_usage', {}).get('total_tokens', 'N/A')}")
```

For OpenAI models, token usage is also visible in the LangSmith UI under each LLM run step.

### 6.7.3 Latency Breakdown

Identify bottlenecks by examining per-step latency:

```python
from langsmith import Client

client = Client()

# Get a specific trace with all child runs
trace = client.read_run("run-id-here")

print(f"Total trace latency: {trace.end_time - trace.start_time}")

# List child runs
children = list(client.list_runs(trace_id=trace.trace_id))
for child in children:
    duration = child.end_time - child.start_time if child.end_time else None
    print(f"  {child.name}: {duration}")
```

Typical latency patterns:

| Step | Typical Latency | Optimization Target |
|------|----------------|---------------------|
| Retrieval | 50–500ms | Vector DB indexing, caching |
| Prompt construction | 1–10ms | Usually negligible |
| LLM call | 500ms–5s | Model selection, streaming |
| Post-processing | 10–100ms | Parser efficiency |

### 6.7.4 Error Tracing

Exceptions are captured automatically. In LangSmith, failed runs are marked with a red status and include the stack trace:

```python
from langsmith import traceable

@traceable(name="risky_operation")
def risky_operation(should_fail: bool) -> str:
    if should_fail:
        raise ValueError("Simulated failure!")
    return "Success"

# This run will appear with Error status in LangSmith
try:
    risky_operation(True)
except ValueError:
    pass  # Exception is already logged in LangSmith
```

---

## 6.8 Evaluating Runs and Comparing Experiments

### 6.8.1 Creating Datasets

Datasets in LangSmith are collections of test cases for systematic evaluation:

```python
from langsmith import Client

client = Client()

# Create a dataset
dataset = client.create_dataset(
    name="qa_eval_dataset",
    description="Question-answering evaluation cases"
)

# Add examples
examples = [
    {
        "inputs": {"question": "What is the capital of France?"},
        "outputs": {"answer": "Paris"}
    },
    {
        "inputs": {"question": "Who wrote '1984'?"},
        "outputs": {"answer": "George Orwell"}
    },
    {
        "inputs": {"question": "What is the speed of light?"},
        "outputs": {"answer": "299,792,458 meters per second"}
    }
]

for example in examples:
    client.create_example(
        inputs=example["inputs"],
        outputs=example["outputs"],
        dataset_id=dataset.id
    )

print(f"Dataset created: {dataset.id}")
```

### 6.8.2 Running Evaluations

Evaluate your application against a dataset using custom evaluators or LLM-as-a-judge:

```python
from langsmith import Client
from langsmith.evaluation import evaluate
from langchain_openai import ChatOpenAI

client = Client()

# Your function to evaluate
def answer_question(inputs: dict) -> dict:
    """Production QA function."""
    question = inputs["question"]
    
    # In production, this would call your RAG pipeline
    model = ChatOpenAI(model="gpt-4o-mini")
    response = model.invoke(f"Answer concisely: {question}")
    
    return {"answer": response.content}

# Custom evaluator: exact match
def exact_match_evaluator(run, example) -> dict:
    """Check if the predicted answer matches the expected answer."""
    predicted = run.outputs.get("answer", "").lower().strip()
    expected = example.outputs.get("answer", "").lower().strip()
    
    return {
        "score": 1.0 if predicted == expected else 0.0,
        "comment": f"Predicted: {predicted}, Expected: {expected}"
    }

# Run evaluation
eval_results = evaluate(
    answer_question,
    data="qa_eval_dataset",  # Dataset name
    evaluators=[exact_match_evaluator],
    experiment_prefix="baseline-model",
    client=client
)

print(f"Evaluation complete: {eval_results}")
```

### 6.8.3 LLM-as-a-Judge Evaluators

For subjective or complex criteria, use an LLM to evaluate outputs:

```python
from langsmith.evaluation import LangChainStringEvaluator

# Use a built-in LLM evaluator
qa_evaluator = LangChainStringEvaluator(
    "qa",
    config={
        "llm": ChatOpenAI(model="gpt-4o"),
        "criteria": "correctness"
    }
)

# Or a criteria-based evaluator
relevance_evaluator = LangChainStringEvaluator(
    "criteria",
    config={
        "criteria": {
            "relevance": "Is the output relevant to the input question?"
        }
    }
)

# Run with multiple evaluators
eval_results = evaluate(
    answer_question,
    data="qa_eval_dataset",
    evaluators=[qa_evaluator, relevance_evaluator],
    experiment_prefix="llm-judge-eval"
)
```

### 6.8.4 Comparing Experiments

Run multiple experiments and compare them in the LangSmith UI:

```python
# Experiment 1: GPT-4o-mini
def answer_with_mini(inputs: dict) -> dict:
    model = ChatOpenAI(model="gpt-4o-mini")
    response = model.invoke(inputs["question"])
    return {"answer": response.content}

evaluate(
    answer_with_mini,
    data="qa_eval_dataset",
    evaluators=[exact_match_evaluator],
    experiment_prefix="gpt-4o-mini"
)

# Experiment 2: GPT-4o
def answer_with_gpt4(inputs: dict) -> dict:
    model = ChatOpenAI(model="gpt-4o")
    response = model.invoke(inputs["question"])
    return {"answer": response.content}

evaluate(
    answer_with_gpt4,
    data="qa_eval_dataset",
    evaluators=[exact_match_evaluator],
    experiment_prefix="gpt-4o"
)
```

In LangSmith, navigate to the dataset page and click **Compare Experiments** to see:
- Side-by-side output comparison
- Aggregated scores per evaluator
- Per-example diffs
- Cost and latency comparison

---

## 6.9 Feedback and Annotation Features

### 6.9.1 Programmatic Feedback

Attach feedback to runs programmatically for later analysis:

```python
from langsmith import Client

client = Client()

# Get a run ID (from recent execution or query)
run_id = "your-run-id-here"

# Add structured feedback
client.create_feedback(
    run_id=run_id,
    key="user_rating",
    score=5,  # 1-5 scale
    comment="Accurate and concise answer",
    value="positive"
)

# Add binary feedback
client.create_feedback(
    run_id=run_id,
    key="hallucination",
    score=0,  # 0 = no hallucination detected
    comment="All facts verified against source documents"
)

# Add categorical feedback
client.create_feedback(
    run_id=run_id,
    key="tone",
    value="professional",  # Categorical value
    comment="Appropriate tone for customer service"
)
```

### 6.9.2 Using Feedback for Dataset Building

Convert production feedback into training/evaluation data:

```python
from langsmith import Client

client = Client()

# Find runs with positive feedback
positive_runs = list(client.list_runs(
    project_name="my-app",
    filter='eq(feedback_key, "user_rating")'
))

# Create a dataset from high-quality runs
dataset = client.create_dataset(name="high_quality_responses")

for run in positive_runs:
    feedback = list(client.list_feedback(run_id=run.id))
    ratings = [f for f in feedback if f.key == "user_rating"]
    
    if ratings and ratings[0].score >= 4:
        client.create_example(
            inputs=run.inputs,
            outputs=run.outputs,
            dataset_id=dataset.id
        )

print(f"Built dataset from {len(positive_runs)} high-quality runs")
```

### 6.9.3 Human Annotation Workflow

LangSmith supports human-in-the-loop annotation via the UI:

1. Navigate to a trace in the LangSmith dashboard
2. Click **Add Feedback** on any run
3. Select or create feedback keys (e.g., "correctness", "tone", "helpfulness")
4. Assign scores, categorical values, or free-text comments
5. Filter and export annotated runs for retraining or analysis

Common annotation schemas:

| Feedback Key | Type | Values | Use Case |
|-------------|------|--------|----------|
| `correctness` | Score | 0–1 | Factual accuracy |
| `helpfulness` | Score | 1–5 | User satisfaction proxy |
| `tone` | Categorical | `professional`, `casual`, `too_formal` | Style alignment |
| `hallucination` | Score | 0–1 | Hallucination detection |
| `source_quality` | Categorical | `good`, `partial`, `irrelevant` | RAG retrieval quality |

---

## 6.10 Integration Patterns: LangChain and Standalone Usage

### 6.10.1 Full LangChain Integration

When using LangChain, tracing is nearly automatic:

```python
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# Enable tracing via environment
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-api-key"
os.environ["LANGCHAIN_PROJECT"] = "full-integration"

# Everything below is automatically traced
prompt = ChatPromptTemplate.from_template("Tell me a joke about {topic}")
model = ChatOpenAI(model="gpt-4o-mini")

chain = {"topic": RunnablePassthrough()} | prompt | model

# This single invocation traces: Passthrough → PromptTemplate → ChatOpenAI
result = chain.invoke("programming")
print(result.content)
```

### 6.10.2 Standalone Usage (No LangChain)

LangSmith works independently of LangChain. Use it with any Python code:

```python
import os
from langsmith import traceable
from openai import OpenAI

os.environ["LANGCHAIN_API_KEY"] = "your-api-key"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "standalone-app"

client = OpenAI()

@traceable(name="classify_support_ticket", run_type="chain")
def classify_ticket(ticket_text: str) -> dict:
    """Classify a support ticket without LangChain."""
    
    # Step 1: Extract intent
    intent_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Classify the intent: bug, feature_request, or question."},
            {"role": "user", "content": ticket_text}
        ]
    )
    intent = intent_response.choices[0].message.content
    
    # Step 2: Determine priority
    priority_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Rate priority: low, medium, high, critical."},
            {"role": "user", "content": f"Ticket: {ticket_text}\nIntent: {intent}"}
        ]
    )
    priority = priority_response.choices[0].message.content
    
    return {
        "intent": intent,
        "priority": priority,
        "ticket_text": ticket_text
    }

result = classify_ticket("The login button doesn't work on mobile.")
print(result)
```

### 6.10.3 Hybrid Patterns: LangChain + Custom Code

Most production applications use a mix of LangChain primitives and custom logic:

```python
import os
from langsmith import traceable
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "hybrid-app"

# LangChain component for structured output
prompt = ChatPromptTemplate.from_messages([
    ("system", "Extract entities from the text as JSON."),
    ("user", "{text}")
])

model = ChatOpenAI(model="gpt-4o-mini")
parser = JsonOutputParser()

entity_chain = prompt | model | parser

# Custom function with @traceable for non-LangChain logic
@traceable(name="enrich_entities", run_type="chain")
def enrich_entities(entities: dict, source: str) -> dict:
    """Add metadata to extracted entities."""
    entities["source"] = source
    entities["extracted_at"] = "2025-01-15T10:00:00Z"
    return entities

# Combine both
@traceable(name="full_extraction_pipeline", run_type="chain")
def extract_and_enrich(text: str, source: str) -> dict:
    """Full pipeline combining LangChain and custom code."""
    entities = entity_chain.invoke({"text": text})
    enriched = enrich_entities(entities, source)
    return enriched

result = extract_and_enrich(
    "Apple Inc. was founded by Steve Jobs in Cupertino.",
    source="wikipedia"
)
print(result)
```

### 6.10.4 Async Integration

For async applications, use `atraceable` or trace manually:

```python
import asyncio
from langsmith import traceable
from openai import AsyncOpenAI

client = AsyncOpenAI()

@traceable(name="async_llm_call", run_type="llm")
async def async_llm_call(prompt: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

@traceable(name="async_pipeline", run_type="chain")
async def async_pipeline(queries: list[str]) -> list[str]:
    """Process multiple queries concurrently."""
    tasks = [async_llm_call(q) for q in queries]
    results = await asyncio.gather(*tasks)
    return results

# Run
results = asyncio.run(async_pipeline([
    "What is Python?",
    "What is JavaScript?",
    "What is Rust?"
]))
print(results)
```

---

## 6.11 Cost Analysis Through LangSmith

### 6.11.1 Understanding Cost Attribution

LangSmith captures token usage on every LLM run, enabling granular cost analysis. For OpenAI models, pricing is straightforward:

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| GPT-4o | $5.00 | $15.00 |
| GPT-4o-mini | $0.15 | $0.60 |
| GPT-4 | $30.00 | $60.00 |

### 6.11.2 Calculating Costs from Traces

```python
from langsmith import Client

client = Client()

# Define pricing (update with current rates)
PRICING = {
    "gpt-4o": {"input": 5.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4": {"input": 30.00 / 1_000_000, "output": 60.00 / 1_000_000},
}

def calculate_run_cost(run) -> float:
    """Calculate the cost of a single run."""
    extras = run.extra or {}
    usage = extras.get("usage", {})
    
    model = extras.get("invocation_params", {}).get("model", "unknown")
    input_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
    output_tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
    
    if model not in PRICING:
        return 0.0
    
    input_cost = input_tokens * PRICING[model]["input"]
    output_cost = output_tokens * PRICING[model]["output"]
    
    return input_cost + output_cost

# Aggregate costs by project
runs = client.list_runs(project_name="my-app-prod", limit=100)

total_cost = 0.0
model_breakdown = {}

for run in runs:
    cost = calculate_run_cost(run)
    total_cost += cost
    
    model = run.extra.get("invocation_params", {}).get("model", "unknown") if run.extra else "unknown"
    model_breakdown[model] = model_breakdown.get(model, 0) + cost

print(f"Total cost (last 100 runs): ${total_cost:.4f}")
print("By model:")
for model, cost in model_breakdown.items():
    print(f"  {model}: ${cost:.4f}")
```

### 6.11.3 Cost by Feature or User Segment

Use metadata to attribute costs to specific features:

```python
from langsmith import Client

client = Client()

# Query runs with metadata filtering
runs = client.list_runs(
    project_name="my-app-prod",
    filter='eq(metadata["environment"], "production")'
)

# Aggregate by feature (from metadata)
feature_costs = {}
for run in runs:
    metadata = run.extra.get("metadata", {}) if run.extra else {}
    feature = metadata.get("feature", "unknown")
    
    cost = calculate_run_cost(run)
    feature_costs[feature] = feature_costs.get(feature, 0) + cost

print("Cost by feature:")
for feature, cost in sorted(feature_costs.items(), key=lambda x: -x[1]):
    print(f"  {feature}: ${cost:.2f}")
```

### 6.11.4 Cost Optimization Strategies

Based on LangSmith cost analysis, common optimizations:

| Strategy | Implementation | Expected Savings |
|----------|---------------|------------------|
| **Model downgrade** | Use `gpt-4o-mini` for simple tasks | 60–90% |
| **Caching** | Cache common queries with exact-match or semantic similarity | 20–50% |
| **Batching** | Combine multiple requests into single API calls where possible | 10–20% |
| **Prompt compression** | Reduce prompt length through better context selection | 15–30% |
| **Streaming early termination** | Stop generation when confidence threshold is met | Variable |

### 6.11.5 Setting Cost Alerts

While LangSmith doesn't have built-in cost alerts, you can build them using the API:

```python
from langsmith import Client
import smtplib
from email.mime.text import MIMEText

client = Client()

DAILY_BUDGET = 50.00  # USD

def check_daily_budget():
    """Check if daily spend exceeds budget."""
    from datetime import datetime, timedelta
    
    start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    runs = client.list_runs(
        project_name="my-app-prod",
        start_time=start_of_day
    )
    
    daily_cost = sum(calculate_run_cost(run) for run in runs)
    
    if daily_cost > DAILY_BUDGET:
        send_alert(f"Daily budget exceeded: ${daily_cost:.2f} / ${DAILY_BUDGET}")
    
    return daily_cost

def send_alert(message: str):
    """Send budget alert (implement with your email/Slack provider)."""
    print(f"ALERT: {message}")
    # Integrate with your notification system

# Run as a cron job or scheduled task
current_spend = check_daily_budget()
print(f"Current daily spend: ${current_spend:.2f}")
```

---

## 6.12 Summary and Best Practices

### Quick Reference: When to Use What

| Pattern | Tool | Code Example |
|---------|------|-------------|
| Simple function tracing | `@traceable` | `@traceable(name="my_func")` |
| LangChain chains | Environment variable | `LANGCHAIN_TRACING_V2=true` |
| Complex manual control | `RunTree` | `RunTree(name="...", client=client)` |
| LLM-specific tracing | `@traceable(run_type="llm")` | `@traceable(name="call", run_type="llm")` |
| Cross-service tracing | Shared trace ID | `id=shared_uuid`, `parent_id=shared_uuid` |
| Production evaluation | `evaluate()` | `evaluate(func, data="dataset", evaluators=[...])` |
| Cost tracking | Token usage + metadata | `metadata={"feature": "search"}` |

### Best Practices

1. **Always trace in production.** The overhead is minimal; the debugging value is immense.

2. **Use meaningful run names.** `generate_response` is better than `func_1`.

3. **Tag by environment and version.** Filter production vs. staging easily.

4. **Attach user/session IDs in metadata.** Essential for debugging specific user issues.

5. **Create datasets from production feedback.** Turn real user interactions into evaluation data.

6. **Run evaluations before deploying prompt/model changes.** Compare experiments side-by-side.

7. **Monitor cost by feature.** Identify which product areas drive LLM spend.

8. **Use `RunTree` for distributed systems.** Maintain trace continuity across services.

---

## 6.13 Further Reading

- [LangSmith Documentation](https://docs.smith.langchain.com)
- [LangSmith Cookbook](https://github.com/langchain-ai/langsmith-cookbook)
- [LangChain Tracing Guide](https://python.langchain.com/docs/how_to/tracing/)
- [LangSmith Evaluation Concepts](https://docs.smith.langchain.com/evaluation)
- [LangSmith Pricing](https://www.langchain.com/pricing-langsmith)

---

*Last updated: 2026-06-04*  
*LangSmith version: 0.1.x+ | LangChain version: 0.2.x+*