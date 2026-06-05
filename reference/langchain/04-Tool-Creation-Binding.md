# Section 4: LangChain Tool Creation and Binding

> **Prerequisites:** Basic Python, familiarity with LangChain core concepts (Chains, LLMs, Prompts). If you're new to LangChain, read Sections 1–3 first.

---

## Table of Contents

1. [What Are Tools and Why They Matter](#what-are-tools-and-why-they-matter)
2. [Creating Custom Tools with `@tool` Decorator](#creating-custom-tools-with-tool-decorator)
3. [Structured Tools with `StructuredTool`](#structured-tools-with-structuredtool)
4. [Tool Schemas and Pydantic Models](#tool-schemas-and-pydantic-models)
5. [Binding Tools to Agents](#binding-tools-to-agents)
6. [Tool Error Handling and Retries](#tool-error-handling-and-retries)
7. [Tool Descriptions and Agent Behavior](#tool-descriptions-and-agent-behavior)
8. [Async Tools and Performance](#async-tools-and-performance)
9. [Best Practices for Tool Design](#best-practices-for-tool-design)

---

## What Are Tools and Why They Matter

In LangChain, a **Tool** is a function that an agent can invoke to perform actions beyond text generation. Tools are the bridge between an LLM's reasoning and the real world. Without them, an LLM is just a very sophisticated text predictor. With them, it becomes a system that can search the web, query databases, call APIs, run code, and manipulate files.

### Why Tools Are Critical

| Capability | Without Tools | With Tools |
|------------|---------------|------------|
| **Current information** | Stuck at training cutoff | Live web search, API calls |
| **Structured computation** | Unreliable arithmetic | Calculator, Python REPL |
| **Data access** | Only what's in the prompt | SQL queries, document retrieval |
| **External actions** | None | Send emails, create tickets, deploy code |
| **Verification** | Hallucination-prone | Ground truth from external sources |

### The Tool Interface

Every LangChain tool implements a simple contract:

```python
class BaseTool(ABC):
    name: str                    # Unique identifier for the tool
    description: str             # Explains what the tool does (LLM reads this!)
    args_schema: Optional[Type[BaseModel]]  # Pydantic model for validation
    
    def _run(self, *args, **kwargs) -> str:
        """Synchronous execution."""
        ...
    
    async def _arun(self, *args, **kwargs) -> str:
        """Asynchronous execution."""
        ...
```

The LLM doesn't "run" the tool itself. Instead, it **decides** which tool to use and **generates the arguments** based on the tool's schema. LangChain's agent framework then executes the tool and feeds the result back to the LLM.

### Built-in Tools vs. Custom Tools

LangChain ships with a growing toolbox of pre-built integrations:

```python
from langchain_community.tools import WikipediaQueryRun, DuckDuckGoSearchRun
from langchain_community.utilities import WikipediaAPIWrapper

# Pre-built tools — ready to use
search = DuckDuckGoSearchRun()
wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
```

But the real power comes from **custom tools** tailored to your domain. The rest of this section focuses on building those.

---

## Creating Custom Tools with `@tool` Decorator

The simplest way to create a tool is the `@tool` decorator from `langchain_core.tools`. It inspects your function's signature and docstring to automatically generate the tool's name, description, and argument schema.

### Minimal Example

```python
from langchain_core.tools import tool

@tool
def calculate_bmi(weight_kg: float, height_m: float) -> str:
    """Calculate Body Mass Index (BMI) from weight and height.
    
    Args:
        weight_kg: Weight in kilograms.
        height_m: Height in meters.
    """
    bmi = weight_kg / (height_m ** 2)
    category = (
        "underweight" if bmi < 18.5
        else "normal" if bmi < 25
        else "overweight" if bmi < 30
        else "obese"
    )
    return f"BMI: {bmi:.1f} ({category})"

# The decorator turns a plain function into a BaseTool instance
print(calculate_bmi.name)        # "calculate_bmi"
print(calculate_bmi.description)   # The docstring
print(calculate_bmi.args_schema.schema())  # Auto-generated Pydantic schema
```

### What `@tool` Does Under the Hood

1. **Extracts the name** from the function name
2. **Extracts the description** from the docstring
3. **Builds a Pydantic model** from type hints in the function signature
4. **Wraps the function** in a `BaseTool` subclass with `_run()` and `_arun()` methods

### Customizing Tool Metadata

Sometimes the auto-generated metadata isn't ideal. Override it:

```python
from langchain_core.tools import tool

@tool(
    name="stock_price_lookup",           # Override the default name
    description="Fetch the current stock price for a given ticker symbol. "
                "Use this when the user asks about stock prices or market data. "
                "Input must be a valid ticker like AAPL, TSLA, or MSFT.",
    return_direct=True,                   # Skip LLM re-processing; return tool output directly
)
def get_price(ticker: str) -> str:
    """Internal docstring — not used as the tool description when overridden above."""
    # In production, you'd call a real API
    prices = {"AAPL": 187.50, "TSLA": 248.30, "MSFT": 415.20}
    price = prices.get(ticker.upper())
    if price is None:
        return f"Unknown ticker: {ticker}. Try AAPL, TSLA, or MSFT."
    return f"${price:.2f}"
```

> **⚠️ Warning:** `return_direct=True` is useful for simple lookups but bypasses the agent's ability to synthesize the result with other information. Use sparingly.

### Tools with No Arguments

```python
@tool
def get_current_timestamp() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

# The schema will have no required fields
print(get_current_timestamp.args_schema.schema())
# {'title': 'get_current_timestamp', 'type': 'object', 'properties': {}}
```

### Tools with Optional Arguments

```python
from typing import Optional

@tool
def greet(name: str, language: Optional[str] = "en") -> str:
    """Greet a person in their preferred language.
    
    Args:
        name: The person's name.
        language: ISO 639-1 language code (default: en).
    """
    greetings = {
        "en": f"Hello, {name}!",
        "es": f"¡Hola, {name}!",
        "fr": f"Bonjour, {name}!",
        "de": f"Hallo, {name}!",
    }
    return greetings.get(language, greetings["en"])
```

> **💡 Tip:** Always use `Optional[...]` with a default value rather than `| None` without a default. The schema generator handles defaults better this way.

---

## Structured Tools with `StructuredTool`

The `@tool` decorator works well for simple functions, but it has limitations:

- Single return value (always a string)
- No complex nested argument types
- Limited control over the generated schema

For production-grade tools, use **`StructuredTool`** or subclass **`BaseTool`** directly.

### Using `StructuredTool.from_function`

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class WeatherInput(BaseModel):
    """Input schema for the weather tool."""
    city: str = Field(description="City name, e.g., 'San Francisco'")
    units: str = Field(default="metric", description="'metric' or 'imperial'")
    include_forecast: bool = Field(
        default=False,
        description="If True, include a 3-day forecast"
    )

def fetch_weather(city: str, units: str, include_forecast: bool) -> dict:
    """Fetch weather data. Returns a dict (will be JSON-stringified)."""
    # Simulated API response
    result = {
        "city": city,
        "temperature": 22 if units == "metric" else 72,
        "units": units,
        "condition": "sunny",
    }
    if include_forecast:
        result["forecast"] = [
            {"day": "tomorrow", "temp": 21, "condition": "partly cloudy"},
            {"day": "day after", "temp": 19, "condition": "rain"},
        ]
    return result

weather_tool = StructuredTool.from_function(
    func=fetch_weather,
    name="weather_lookup",
    description="Get current weather and optional forecast for a city.",
    args_schema=WeatherInput,
    return_direct=False,  # Let the LLM process the result
)

# The tool can be invoked like any other
result = weather_tool.invoke({
    "city": "Berlin",
    "units": "metric",
    "include_forecast": True,
})
print(result)
# {"city": "Berlin", "temperature": 22, "units": "metric", "condition": "sunny", ...}
```

> **Key difference:** `StructuredTool` allows you to define a **custom Pydantic input schema** with `Field()` descriptions, defaults, validation rules, and nested types. The LLM uses these descriptions to generate correct arguments.

### Subclassing `BaseTool` for Full Control

For maximum control—custom initialization, shared state, or complex lifecycle management—subclass `BaseTool`:

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

class DatabaseQueryInput(BaseModel):
    """Input for database queries."""
    query: str = Field(description="SQL SELECT query to execute")
    max_rows: int = Field(default=100, ge=1, le=1000, description="Maximum rows to return")

class DatabaseQueryTool(BaseTool):
    name: str = "db_query"
    description: str = "Execute a read-only SQL query against the company database."
    args_schema: Type[BaseModel] = DatabaseQueryInput
    
    # Custom instance attributes
    connection_string: str = ""
    
    def __init__(self, connection_string: str, **kwargs):
        super().__init__(**kwargs)
        self.connection_string = connection_string
    
    def _run(self, query: str, max_rows: int = 100) -> str:
        """Execute the query synchronously."""
        # In production: use sqlalchemy, psycopg2, etc.
        # This is a simplified example
        if not query.strip().upper().startswith("SELECT"):
            return "Error: Only SELECT queries are allowed."
        
        # Simulated result
        return f"Executed: {query[:50]}... | Rows: {max_rows}"
    
    async def _arun(self, query: str, max_rows: int = 100) -> str:
        """Async execution — delegate to sync for simplicity, or use async DB driver."""
        # For true async, use asyncpg, aiomysql, etc.
        return self._run(query, max_rows)

# Instantiate with configuration
db_tool = DatabaseQueryTool(connection_string="postgresql://localhost/mydb")
result = db_tool.invoke({"query": "SELECT * FROM users LIMIT 10", "max_rows": 50})
```

### When to Use Which Approach

| Approach | Best For | Complexity |
|----------|----------|------------|
| `@tool` decorator | Quick prototypes, simple functions | Low |
| `StructuredTool.from_function()` | Custom schemas, nested inputs, validation | Medium |
| Subclass `BaseTool` | Shared state, complex lifecycle, custom initialization | High |

---

## Tool Schemas and Pydantic Models

The **schema** is the contract between your tool and the LLM. A well-designed schema is the difference between an agent that works and one that hallucinates arguments.

### Schema Generation Deep Dive

When you define a tool, LangChain generates a JSON Schema that is passed to the LLM. The LLM uses this schema to decide:

1. **Whether to use the tool** at all (based on `description`)
2. **What arguments to pass** (based on `properties` and `Field` descriptions)

Here's what the LLM actually sees for a well-designed tool:

```python
from pydantic import BaseModel, Field

class SearchDocumentsInput(BaseModel):
    """Input for searching the document database."""
    query: str = Field(
        description="The search query. Use specific keywords for better results."
    )
    filters: dict = Field(
        default={},
        description="Optional metadata filters. Example: {'author': 'Smith', 'year': 2024}"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return (1-20)."
    )

# Generated schema (what the LLM receives):
# {
#   "name": "search_documents",
#   "description": "Search the internal document database...",
#   "parameters": {
#     "type": "object",
#     "properties": {
#       "query": {
#         "description": "The search query. Use specific keywords...",
#         "type": "string"
#       },
#       "filters": {
#         "default": {},
#         "description": "Optional metadata filters...",
#         "type": "object"
#       },
#       "top_k": {
#         "default": 5,
#         "description": "Number of results to return (1-20).",
#         "type": "integer"
#       }
#     },
#     "required": ["query"]
#   }
# }
```

### Writing Effective `Field` Descriptions

The LLM reads your `Field` descriptions. Write them as instructions, not just labels:

| ❌ Bad | ✅ Good |
|--------|---------|
| `"The query"` | `"Search query with specific keywords. Avoid vague terms like 'stuff' or 'things'."` |
| `"Date"` | `"Start date in ISO 8601 format (YYYY-MM-DD). Only use if the user specifies a date range."` |
| `"Count"` | `"Maximum number of items to return. Default 10. Increase only if the user asks for 'all' or 'many' results."` |

### Validation with Pydantic

Pydantic validates arguments **before** the tool runs. This catches errors early and prevents bad data from reaching your business logic:

```python
from pydantic import BaseModel, Field, validator
from typing import Literal

class SendEmailInput(BaseModel):
    """Input for sending an email."""
    recipient: str = Field(description="Email address of the recipient")
    subject: str = Field(description="Email subject line", max_length=200)
    body: str = Field(description="Email body text")
    priority: Literal["low", "normal", "high"] = Field(
        default="normal",
        description="Email priority level"
    )
    
    @validator("recipient")
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v.lower()
    
    @validator("body")
    def validate_body_length(cls, v):
        if len(v) < 10:
            raise ValueError("Email body must be at least 10 characters")
        return v

# If the LLM generates invalid input, Pydantic catches it:
# SendEmailInput(recipient="not-an-email", subject="Hi", body="Hey")
# → ValidationError: Invalid email address
```

### Nested Models and Complex Types

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class Address(BaseModel):
    street: str
    city: str
    zip_code: str

class CreateOrderInput(BaseModel):
    """Input for creating a new order."""
    customer_id: str = Field(description="Internal customer ID")
    items: List[dict] = Field(
        description="List of items. Each item: {'sku': str, 'quantity': int, 'price': float}"
    )
    shipping_address: Address = Field(description="Where to ship the order")
    gift_wrap: bool = Field(default=False, description="Whether to gift-wrap the order")
    notes: Optional[str] = Field(default=None, description="Optional order notes")
```

> **⚠️ Warning:** Not all LLMs handle deeply nested schemas equally well. OpenAI's GPT-4 and Claude handle them well; smaller models may struggle with nesting beyond 2–3 levels. Test with your target model.

---

## Binding Tools to Agents

Creating tools is only half the battle. You need to **bind** them to an agent so the LLM can discover and invoke them.

### Tool Binding Overview

In modern LangChain (0.1+), tools are bound to the **LLM** using `.bind_tools()`. The LLM then receives the tool schemas in its context and can generate tool calls.

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

@tool
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

llm = ChatOpenAI(model="gpt-4", temperature=0)

# Bind tools to the LLM
llm_with_tools = llm.bind_tools([multiply, add])

# Now the LLM can generate tool calls
response = llm_with_tools.invoke("What is 7 times 8?")
print(response.tool_calls)
# [{'name': 'multiply', 'args': {'a': 7.0, 'b': 8.0}, 'id': 'call_abc123'}]
```

### `create_react_agent` — The ReAct Framework

The ReAct (Reasoning + Acting) agent is the most widely used pattern. It explicitly shows its reasoning process:

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    # In production: use DuckDuckGo, SerpAPI, etc.
    return f"Search results for '{query}': [simulated result]"

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    try:
        # Use a safe evaluation method in production
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"

llm = ChatOpenAI(model="gpt-4", temperature=0)
tools = [search_web, calculator]

# ReAct prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Use tools to answer questions. "
               "Always explain your reasoning before using a tool."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Create the agent
agent = create_react_agent(llm, tools, prompt)

# Wrap in an executor with error handling
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10,        # Prevent infinite loops
    handle_parsing_errors=True,  # Gracefully handle malformed LLM outputs
)

# Run
result = executor.invoke({"input": "What is the population of Tokyo divided by 1000?"})
print(result["output"])
```

### `create_openai_functions_agent` — Native Function Calling

If you're using OpenAI models (or other models that support native function calling), this agent type is more efficient than ReAct:

```python
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny, 25°C in {city}"

llm = ChatOpenAI(model="gpt-4", temperature=0)
tools = [get_weather]

# Functions agent prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful weather assistant."),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_openai_functions_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

result = executor.invoke({"input": "What's the weather in Paris?"})
```

> **Why use `create_openai_functions_agent`?** It uses the model's native function-calling API, which is more reliable than parsing ReAct-style text output. The model is trained to emit structured tool calls, reducing parsing errors.

### `create_tool_calling_agent` — The Modern Standard (LangChain 0.2+)

LangChain 0.2+ introduces a unified `create_tool_calling_agent` that works across multiple providers:

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def get_stock_price(ticker: str) -> str:
    """Get the current stock price for a ticker."""
    prices = {"AAPL": 187.50, "GOOGL": 142.30, "MSFT": 415.20}
    return f"${prices.get(ticker.upper(), 'N/A')}"

llm = ChatOpenAI(model="gpt-4", temperature=0)
tools = [get_stock_price]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a financial assistant."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

result = executor.invoke({"input": "What is Apple's stock price?"})
```

### Agent Type Comparison

| Agent Type | Best For | Model Support | Reliability | Speed |
|------------|----------|---------------|-------------|-------|
| `create_react_agent` | Debugging, transparency, any model | Universal | Medium | Slower |
| `create_openai_functions_agent` | OpenAI models, production | OpenAI only | High | Fast |
| `create_tool_calling_agent` | Multi-provider, modern LangChain | Anthropic, OpenAI, Mistral, etc. | High | Fast |

### Common Binding Error: `AttributeError: 'OpenAI' has no attribute 'bind_tools'`

This is the #1 error when starting with LangChain tools. It happens when you pass a non-chat model to an agent constructor:

```python
# ❌ WRONG — uses the legacy completions API
from langchain_openai import OpenAI
llm = OpenAI(model="gpt-3.5-turbo-instruct")  # No .bind_tools()!

# ✅ CORRECT — uses the chat completions API
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4")  # Has .bind_tools()
```

> **Rule:** Always use `ChatOpenAI`, `ChatAnthropic`, `ChatGoogleGenerativeAI`, etc.—never the legacy `OpenAI`, `Anthropic`, etc. classes.

---

## Tool Error Handling and Retries

Tools fail. APIs timeout, databases go down, and users send garbage input. A robust agent handles these gracefully.

### Wrapping Tools with Try/Except

```python
from langchain_core.tools import tool
import requests

@tool
def fetch_api_data(endpoint: str) -> str:
    """Fetch data from an internal API endpoint."""
    try:
        response = requests.get(
            f"https://api.internal.com{endpoint}",
            timeout=10
        )
        response.raise_for_status()
        return response.text
    except requests.Timeout:
        return "Error: API request timed out after 10 seconds. Try again later."
    except requests.HTTPError as e:
        return f"Error: API returned status {e.response.status_code}."
    except Exception as e:
        return f"Error: Unexpected failure — {str(e)}"
```

### Retry Decorator for Tools

```python
import time
from functools import wraps
from typing import Callable, Any

def retry_tool(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator that adds retry logic to any tool function."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            # All retries exhausted
            return f"Error: Failed after {max_retries} attempts. Last error: {str(last_exception)}"
        
        return wrapper
    return decorator

# Apply to a tool
@tool
@retry_tool(max_retries=3, delay=1.0)
def flaky_api_call(query: str) -> str:
    """Call an API that occasionally fails."""
    import random
    if random.random() < 0.5:
        raise ConnectionError("Simulated API failure")
    return f"Results for: {query}"
```

### LangChain's Built-in `handle_tool_error`

For `StructuredTool` and `BaseTool` subclasses, you can set `handle_tool_error=True`:

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class QueryInput(BaseModel):
    sql: str = Field(description="SQL query to execute")

def run_query(sql: str) -> str:
    # This might raise an exception
    if "DROP" in sql.upper():
        raise ValueError("DROP statements are not allowed")
    return f"Executed: {sql}"

safe_query_tool = StructuredTool.from_function(
    func=run_query,
    name="safe_query",
    description="Execute a safe SQL query.",
    args_schema=QueryInput,
    handle_tool_error=True,  # Catches exceptions and returns them as strings
)

# Instead of crashing, the tool returns the error as a string
result = safe_query_tool.invoke({"sql": "DROP TABLE users"})
print(result)  # "Error: DROP statements are not allowed"
```

### Custom Error Handling Callback

For fine-grained control, provide a callback function:

```python
def log_and_return_error(error: Exception) -> str:
    """Custom error handler that logs and returns a user-friendly message."""
    import logging
    logging.error(f"Tool error: {error}")
    
    if isinstance(error, ConnectionError):
        return "The external service is unavailable. Please try again in a few minutes."
    elif isinstance(error, ValueError):
        return f"Invalid input: {str(error)}"
    else:
        return "An unexpected error occurred. The team has been notified."

safe_query_tool = StructuredTool.from_function(
    func=run_query,
    name="safe_query",
    description="Execute a safe SQL query.",
    args_schema=QueryInput,
    handle_tool_error=log_and_return_error,  # Custom callback
)
```

### Agent-Level Error Handling

Set `handle_parsing_errors=True` in `AgentExecutor` to catch malformed LLM outputs:

```python
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,  # Catches bad LLM output format
    max_iterations=10,           # Prevents infinite loops
    max_execution_time=60,       # Hard timeout in seconds
)
```

---

## Tool Descriptions and Agent Behavior

The **description** is the most important piece of metadata for a tool. It directly controls when and how the LLM uses it.

### How LLMs Choose Tools

When an agent receives a user query, the LLM:

1. Reads the query
2. Reads all tool descriptions
3. Decides which tool (if any) is relevant
4. Generates arguments based on the tool's schema

A bad description leads to:
- **Underuse:** The LLM never calls the tool when it should
- **Overuse:** The LLM calls the tool for irrelevant queries
- **Wrong arguments:** The LLM generates incorrect parameter values

### Writing Effective Tool Descriptions

Follow this formula:

```
[What it does] + [When to use it] + [Input format] + [Output format]
```

```python
@tool
def search_company_kb(query: str) -> str:
    """Search the internal company knowledge base for documents, policies, and procedures.
    
    Use this tool when the user asks about:
    - Company policies (HR, IT, security)
    - Internal procedures or workflows
    - Product documentation
    - Past project information
    
    Do NOT use this tool for:
    - General knowledge questions (use web_search instead)
    - Real-time data like stock prices or weather
    - Personal or external topics
    
    Input: A specific search query with keywords. Be concise (3-10 words).
    Output: A list of relevant document snippets with titles and source URLs.
    """
    # Implementation...
    return "..."
```

### Description Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|--------------|--------------|-----|
| `"A search tool"` | Too vague — LLM doesn't know when to use it | Add specific use cases and exclusions |
| `"Use this for everything"` | LLM overuses it, ignoring better tools | Define clear boundaries |
| `"Takes a string"` | Doesn't explain what the string should contain | Describe the expected format with examples |
| `"Returns data"` | Doesn't help the LLM plan next steps | Explain the output format and how to use it |
| **No description** | `@tool` without docstring → empty description | Always write a docstring |

### A/B Testing Tool Descriptions

If your agent consistently makes wrong tool choices, iterate on descriptions:

```python
# Version A — vague
@tool
def lookup_user(user_id: str) -> str:
    """Look up a user."""
    ...

# Version B — specific
@tool
def lookup_user(user_id: str) -> str:
    """Retrieve user profile information from the CRM database.
    
    Use ONLY when the user explicitly mentions a user ID or asks about
    a specific user's details. Input must be a valid UUID or email address.
    Returns JSON with name, email, plan, and last_login.
    """
    ...
```

> **💡 Tip:** Log which tools the agent calls and for what queries. If a tool is never used, its description is probably too vague or the agent doesn't understand when to use it.

### Tool Naming Conventions

Names also matter. The LLM sees them alongside descriptions:

| ❌ Bad Name | ✅ Good Name | Why |
|-------------|-------------|-----|
| `tool_1` | `search_web` | Descriptive and self-documenting |
| `get_data` | `get_customer_order` | Specifies what data and from where |
| `process` | `send_notification_email` | Describes the action clearly |
| `api_call` | `fetch_stock_price` | Indicates the domain and purpose |

Use `snake_case` and keep names under 30 characters if possible.

---

## Async Tools and Performance

Synchronous tools block the event loop. For I/O-bound operations (API calls, database queries, file operations), async tools can dramatically improve throughput.

### Creating Async Tools

```python
import aiohttp
from langchain_core.tools import tool

@tool
async def fetch_weather_async(city: str) -> str:
    """Fetch weather data asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.weather.com/v1/current?city={city}",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            data = await response.json()
            return f"{city}: {data['temperature']}°C, {data['condition']}"
```

> **Note:** The `@tool` decorator detects `async def` and automatically implements `_arun()`. You don't need to subclass `BaseTool` manually.

### Running Async Agents

```python
import asyncio
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
async def async_search(query: str) -> str:
    """Async search."""
    await asyncio.sleep(0.1)  # Simulate async I/O
    return f"Results for '{query}'"

llm = ChatOpenAI(model="gpt-4", temperature=0)
tools = [async_search]
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "{input}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

async def main():
    result = await executor.ainvoke({"input": "Search for LangChain tutorials"})
    print(result["output"])

asyncio.run(main())
```

### Mixed Sync/Async Tool Sets

You can mix sync and async tools in the same agent. LangChain handles the dispatch:

```python
from langchain_core.tools import tool

# Sync tool — CPU-bound or simple operations
@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

# Async tool — I/O-bound
@tool
async def fetch_data(url: str) -> str:
    """Fetch data from a URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

# Both can be used together
tools = [calculator, fetch_data]
```

### Performance Considerations

| Scenario | Recommendation |
|----------|---------------|
| Single user, simple tools | Sync is fine — simpler code |
| High-throughput API | Async + connection pooling |
| CPU-bound operations (ML inference, heavy computation) | Use `run_in_executor` to offload from event loop |
| Mixed workloads | Profile first; optimize the bottleneck |

### Offloading CPU-Bound Work

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
from langchain_core.tools import tool

_executor = ProcessPoolExecutor(max_workers=4)

@tool
async def heavy_computation(data: str) -> str:
    """Run a CPU-intensive task without blocking the event loop."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _cpu_intensive_function, data)
    return result

def _cpu_intensive_function(data: str) -> str:
    # This runs in a separate process
    import time
    time.sleep(2)  # Simulate heavy work
    return f"Processed: {data}"
```

---

## Best Practices for Tool Design

### 1. Design for the LLM, Not Just for Humans

Your tool's primary user is the LLM. Every design decision should consider:

- **Will the LLM understand when to use this?** (description clarity)
- **Can the LLM generate valid arguments?** (schema simplicity)
- **Will the LLM know what to do with the output?** (return format)

### 2. Keep Tools Focused and Atomic

| ❌ Bad — Swiss Army Knife Tool | ✅ Good — Focused Tools |
|-------------------------------|------------------------|
| `manage_database(action, table, data, filters, sort)` | `query_database(sql)`, `insert_record(table, data)`, `update_record(table, id, data)` |

Focused tools are easier to describe, less error-prone, and more reusable.

### 3. Return Structured, Parseable Output

```python
# ❌ Bad — unstructured text
return "The user John Smith has 5 orders totaling $1,250."

# ✅ Good — structured data (LLM can reason about it)
import json
return json.dumps({
    "user": "John Smith",
    "order_count": 5,
    "total_value": 1250.00,
    "currency": "USD"
})
```

### 4. Validate Aggressively

```python
from pydantic import BaseModel, Field, validator

class TransferInput(BaseModel):
    from_account: str = Field(description="Source account ID")
    to_account: str = Field(description="Destination account ID")
    amount: float = Field(description="Amount to transfer", gt=0)
    
    @validator("from_account")
    def accounts_must_differ(cls, v, values):
        if "to_account" in values and v == values["to_account"]:
            raise ValueError("Source and destination accounts must be different")
        return v
```

### 5. Fail Gracefully, Never Crash the Agent

Every tool should catch exceptions and return a meaningful error string. The agent can then decide how to proceed (retry, try another tool, or ask the user).

### 6. Log and Monitor Tool Usage

```python
import logging
from langchain_core.tools import tool

logger = logging.getLogger("tools")

@tool
def monitored_search(query: str) -> str:
    """Search with logging and metrics."""
    logger.info(f"Tool invoked: search | query={query}")
    
    start = time.time()
    try:
        result = _perform_search(query)
        logger.info(f"Tool success: search | duration={time.time()-start:.2f}s")
        return result
    except Exception as e:
        logger.error(f"Tool failure: search | error={e} | duration={time.time()-start:.2f}s")
        return f"Search failed: {str(e)}"
```

### 7. Version Your Tools

As your system evolves, tool schemas change. Version them to avoid breaking existing agents:

```python
@tool(name="search_v2")
def search_documents_v2(
    query: str,
    filters: dict = {},
    semantic_search: bool = False  # New parameter
) -> str:
    """Search documents (v2). Supports semantic search."""
    ...
```

### 8. Test Tools Independently

Before binding a tool to an agent, test it in isolation:

```python
# Unit test your tool
assert calculate_bmi.invoke({"weight_kg": 70, "height_m": 1.75}) == "BMI: 22.9 (normal)"

# Test edge cases
assert calculate_bmi.invoke({"weight_kg": -5, "height_m": 1.75}).startswith("Error")

# Test with realistic LLM-generated inputs (may be slightly malformed)
assert calculate_bmi.invoke({"weight_kg": "70", "height_m": "1.75"})  # Pydantic coerces types
```

### 9. Limit Tool Count per Agent

Agents with too many tools struggle to choose correctly. As a rule of thumb:

| Agent Complexity | Max Tools | Strategy |
|----------------|-----------|----------|
| Simple | 3–5 | Direct binding |
| Moderate | 5–10 | Group related tools, use sub-agents |
| Complex | 10+ | Router agent + specialized sub-agents |

### 10. Document Tool Dependencies

If tools depend on external services, document it:

```python
@tool
def query_snowflake(sql: str) -> str:
    """Execute a read-only query against the Snowflake data warehouse.
    
    **Dependencies:**
    - Requires SNOWFLAKE_CONNECTION_STRING env var
    - Network access to Snowflake (snowflakecomputing.com)
    - Max query timeout: 30 seconds
    
    **Returns:** JSON array of result rows.
    """
    ...
```

---

## Quick Reference: Tool Creation Patterns

```python
from langchain_core.tools import tool, StructuredTool, BaseTool
from pydantic import BaseModel, Field
from typing import Type

# ── Pattern 1: @tool decorator (simplest) ──
@tool
def simple_tool(query: str) -> str:
    """Description here."""
    return f"Result: {query}"

# ── Pattern 2: StructuredTool (custom schema) ──
class MyInput(BaseModel):
    field: str = Field(description="...")

def my_func(field: str) -> str:
    return "..."

tool = StructuredTool.from_function(
    func=my_func,
    name="my_tool",
    description="...",
    args_schema=MyInput,
)

# ── Pattern 3: BaseTool subclass (full control) ──
class MyTool(BaseTool):
    name: str = "my_tool"
    description: str = "..."
    args_schema: Type[BaseModel] = MyInput
    
    def _run(self, field: str) -> str:
        return "..."
    
    async def _arun(self, field: str) -> str:
        return self._run(field)

# ── Pattern 4: Async @tool ──
@tool
async def async_tool(query: str) -> str:
    """Async tool."""
    await asyncio.sleep(1)
    return f"Async result: {query}"

# ── Pattern 5: With retry wrapper ──
@tool
@retry_tool(max_retries=3)
def flaky_tool(query: str) -> str:
    """Tool with automatic retry."""
    ...
```

---

## Summary

| Topic | Key Takeaway |
|-------|-------------|
| **What tools are** | Functions that extend LLM capabilities into the real world |
| **@tool decorator** | Quickest way to create tools from functions; auto-generates schema from type hints |
| **StructuredTool** | Use when you need custom Pydantic schemas, nested types, or validation |
| **BaseTool subclass** | Use for shared state, complex initialization, or full lifecycle control |
| **Pydantic schemas** | The contract between LLM and tool; write descriptions as instructions |
| **Binding to agents** | Use `.bind_tools()` on chat models; choose agent type based on your model |
| **Error handling** | Wrap tools in try/except; use `handle_tool_error`; never crash the agent |
| **Descriptions** | The most important metadata; write them for the LLM, not for humans |
| **Async tools** | Use for I/O-bound operations; mix sync/async freely; offload CPU work to executors |
| **Best practices** | Keep tools focused, return structured data, validate aggressively, monitor usage |

---

> **Next Section:** Section 5 covers **Memory and Conversation Management** — how to give your agents context across multi-turn interactions.
