# Section 3: Binding Prompts to ReAct Agents in LangChain

> **Prerequisites:** Basic Python, familiarity with LangChain `ChatModel` and `Tool` concepts. No prior agent experience required.

---

## 3.1 What Is a ReAct Agent?

**ReAct** stands for **Reasoning + Acting**. It is a paradigm where a language model alternates between two modes:

1. **Reasoning ("Thought")** — The model internally reasons about what it knows, what it needs to know, and what step to take next.
2. **Acting ("Action")** — The model invokes an external tool (e.g., search, calculator, API call) and receives an observation.

This loop repeats until the model decides it has enough information to produce a final answer.

### The ReAct Loop

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Thought   │ --> │   Action    │ --> │ Observation │ --> │   Thought   │ --> ...
│  "I need    │     │  search("   │     │  "Paris is  │     │  "Now I     │
│  the capital│     │  capital of │     │   the capital│     │  can answer │
│  of France" │     │  France")   │     │   of France" │     │  the question"
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

The **prompt** is what teaches the model this structure. Without the prompt enforcing the `Thought/Action/Observation` format, the model would just generate free text and never call tools.

---

## 3.2 How Prompts Drive the ReAct Agent

In LangChain, a ReAct agent prompt is typically a `PromptTemplate` (or `ChatPromptTemplate`) with three critical components:

| Component | Purpose |
|-----------|---------|
| **System / Prefix** | Defines the agent's role, available tools, and the required output format (Thought/Action/Observation). |
| **User Input** | The actual question or task from the user. |
| **Agent Scratchpad** | A running log of all previous Thoughts, Actions, and Observations in the current episode. |

### The Classic ReAct Prompt Structure

```python
from langchain_core.prompts import PromptTemplate

react_template = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

react_prompt = PromptTemplate.from_template(react_template)
```

**Key observations:**
- `{tools}` and `{tool_names}` are populated at runtime with the registered tools.
- `{input}` is the user's question.
- `{agent_scratchpad}` is where the magic happens — it accumulates the loop history.

---

## 3.3 The `agent_scratchpad`: Where Memory Lives

The `agent_scratchpad` is not a database or a vector store. It is **a string that gets appended to the prompt on every iteration**.

### How It Works

1. **Iteration 0:** The prompt is sent with an empty scratchpad. The LLM generates:
   ```
   Thought: I need to find the current weather in Tokyo.
   Action: weather_search
   Action Input: Tokyo
   ```

2. **LangChain parses** the Action and Action Input, executes the tool, and gets an Observation.

3. **Iteration 1:** The scratchpad now contains:
   ```
   Thought: I need to find the current weather in Tokyo.
   Action: weather_search
   Action Input: Tokyo
   Observation: Current weather in Tokyo is 22°C and cloudy.
   ```
   This entire string is substituted into `{agent_scratchpad}`, and the LLM is called again.

4. **Iteration 2:** The LLM sees the history and generates:
   ```
   Thought: I now know the final answer.
   Final Answer: The current weather in Tokyo is 22°C and cloudy.
   ```

### Visualizing the Scratchpad

```
Prompt at Iteration 2:
─────────────────────────────────────────
[System instructions + tool list]
Question: What's the weather in Tokyo?
Thought: I need to find the current weather in Tokyo.
Action: weather_search
Action Input: Tokyo
Observation: Current weather in Tokyo is 22°C and cloudy.
Thought: I now know the final answer.
Final Answer: The current weather in Tokyo is 22°C and cloudy.
─────────────────────────────────────────
                                          ↑
                                    agent_scratchpad
```

**Important:** The scratchpad is ephemeral. It lives only for the duration of a single agent run. If you need memory across separate conversations, you must add a separate memory component (see Section 5).

---

## 3.4 `create_react_agent` vs. `initialize_agent`

LangChain has two ways to build ReAct agents. You should prefer `create_react_agent` for new projects.

### `create_react_agent` (Recommended, LangChain v0.1+)

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.tools import tool

# 1. Define tools
@tool
def search(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression))

tools = [search, calculator]

# 2. Define the prompt template
prompt = PromptTemplate.from_template("""Answer the following questions as best you can.

You have access to these tools:
{tools}

Use this format:
Question: {input}
Thought:{agent_scratchpad}

Begin!

Question: {input}
Thought:{agent_scratchpad}""")

# 3. Create the agent
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
agent = create_react_agent(llm, tools, prompt)

# 4. Run with an executor
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
result = agent_executor.invoke({"input": "What is 25 * 17?"})
print(result["output"])
```

**Why `create_react_agent` is better:**
- Uses the modern LangChain Expression Language (LCEL) under the hood.
- Prompt is fully customizable — you pass your own `PromptTemplate`.
- Compatible with streaming, async, and tracing.
- No hidden prompt magic; what you see is what the LLM gets.

### `initialize_agent` (Legacy, pre-v0.1)

```python
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain.tools import tool

@tool
def search(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
tools = [search]

# The prompt is baked into the AgentType
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

result = agent.run("What is the capital of France?")
print(result)
```

**Why `initialize_agent` is discouraged:**
- Prompt is hidden inside the `AgentType` enum.
- Harder to customize — you must override internal prompt templates.
- Not built on LCEL; less composable.
- May be deprecated in future LangChain versions.

### Migration Cheat Sheet

| Feature | `initialize_agent` | `create_react_agent` |
|---------|-------------------|----------------------|
| Prompt control | Hidden / hard to override | Fully explicit |
| Underlying runtime | Custom | LCEL-based |
| Streaming | Limited | Native support |
| Async | Limited | Native support |
| Debuggability | Low | High (you see the full prompt) |

---

## 3.5 Customizing the ReAct Prompt Template

The real power of `create_react_agent` is that **you own the prompt**. Here are the most common customization patterns.

### Pattern 1: Injecting a System Persona

```python
from langchain_core.prompts import PromptTemplate

persona_prompt = PromptTemplate.from_template("""You are a meticulous research assistant. You never guess. You always verify facts with tools before answering.

Available tools:
{tools}

Use this exact format:
Thought: your reasoning
Action: one of [{tool_names}]
Action Input: the input
Observation: the tool result
...repeat until you are certain.
Thought: I now know the final answer
Final Answer: your verified answer

Question: {input}
Thought:{agent_scratchpad}""")

agent = create_react_agent(llm, tools, persona_prompt)
```

**Effect:** The agent becomes more conservative, preferring to make extra tool calls rather than hallucinate.

### Pattern 2: Adding Custom Instructions / Constraints

```python
constraint_prompt = PromptTemplate.from_template("""Answer questions using tools. Follow these rules:
1. Always cite your sources in the Final Answer.
2. If a tool returns an error, try a different approach — do not give up.
3. Never reveal internal tool names to the user.

Tools:
{tools}

Format:
Thought: consider what to do
Action: [{tool_names}]
Action Input: input
Observation: result
Thought: I now know the final answer
Final Answer: the answer with citations

Question: {input}
Thought:{agent_scratchpad}""")

agent = create_react_agent(llm, tools, constraint_prompt)
```

**Effect:** The agent's output format and behavior are constrained by your rules.

### Pattern 3: Customizing the Scratchpad Format

By default, the scratchpad uses a plain-text format. You can change this if your LLM responds better to a different structure (e.g., JSON, XML, or markdown).

```python
xml_prompt = PromptTemplate.from_template("""You are an agent with tools. Respond in XML-like tags.

Tools:
{tools}

Format:
<thought>your reasoning</thought>
<action>tool name</action>
<action_input>input</action_input>
<observation>tool result</observation>
...
<final_answer>your answer</final_answer>

Question: {input}
{agent_scratchpad}""")

# Note: You must also provide a custom output parser to handle XML tags.
```

> **Warning:** Changing the scratchpad format requires a matching `AgentOutputParser`. The default parser expects the exact `Thought/Action/Action Input/Observation` format. If you deviate, you must build or import a compatible parser.

### Pattern 4: Using `ChatPromptTemplate` for Message-Based Models

For chat models (GPT-4, Claude, etc.), a message-based prompt often performs better than a raw string.

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage

chat_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="""You are a ReAct agent. You have access to tools.
Follow the ReAct loop: Thought -> Action -> Observation -> ... -> Final Answer.

Available tools:
{tools}"""),
    HumanMessage(content="""Question: {input}

Begin!
Thought:{agent_scratchpad}"""),
])

agent = create_react_agent(llm, tools, chat_prompt)
```

**Advantage:** Chat models are fine-tuned to respect system vs. user message boundaries. Putting instructions in a `SystemMessage` often improves adherence.

---

## 3.6 Controlling Behavior Through Prompt Engineering

The prompt is your primary lever for shaping agent behavior. Here are proven techniques:

### Technique 1: Few-Shot Examples in the Prompt

Including examples of correct reasoning chains helps the model, especially for smaller LLMs.

```python
few_shot_prompt = PromptTemplate.from_template("""Answer questions using tools.

Tools:
{tools}

Example:
Question: What is 12 + 8?
Thought: The user wants me to calculate 12 + 8. I should use the calculator.
Action: calculator
Action Input: 12 + 8
Observation: 20
Thought: I now know the final answer.
Final Answer: 20

Now your turn:
Question: {input}
Thought:{agent_scratchpad}""")
```

### Technique 2: Explicit "Stop" Instructions

Tell the agent exactly when to stop looping.

```python
stop_prompt = PromptTemplate.from_template("""Use tools to answer the question.

Rules:
- Only use a tool if you lack the information.
- If you already know the answer from previous observations, output Final Answer immediately.
- Do NOT make unnecessary tool calls.

Tools:
{tools}

Question: {input}
Thought:{agent_scratchpad}""")
```

**Effect:** Reduces redundant tool calls and saves tokens / latency.

### Technique 3: Negative Prompting ("Do Not...")

Explicitly forbidding bad behavior can be surprisingly effective.

```python
negative_prompt = PromptTemplate.from_template("""You are a helpful agent.

CRITICAL RULES:
- Do NOT make up facts. Use tools to verify.
- Do NOT ask the user for clarification. Use tools to resolve ambiguity.
- Do NOT reveal that you are an AI. Just answer the question.

Tools:
{tools}

Question: {input}
Thought:{agent_scratchpad}""")
```

### Technique 4: Output Format Enforcement

Forcing a structured output format reduces parsing errors.

```python
format_prompt = PromptTemplate.from_template("""Answer using tools.

Your response must follow this EXACT pattern (including newlines):

Thought: <reasoning>
Action: <tool_name>
Action Input: <input>

OR, if you are done:

Thought: I now know the final answer
Final Answer: <answer>

Tools:
{tools}

Question: {input}
Thought:{agent_scratchpad}""")
```

---

## 3.7 Common Prompt Customization Patterns

### Pattern A: Dynamic Tool Descriptions

The `{tools}` variable is rendered from the tool's `description` field. Make your descriptions count.

```python
from langchain.tools import tool

@tool
def stock_price(ticker: str) -> str:
    """Get the current stock price for a given ticker symbol.
    Use this when the user asks about stock prices, market value, or share price.
    Input should be a valid ticker symbol like 'AAPL' or 'TSLA'.
    """
    return f"${150.00} (mock)"
```

**Tip:** The description is part of the prompt. Treat it as prompt engineering.

### Pattern B: Conditional Prompts Based on Input

You can use a function to dynamically generate prompts.

```python
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda

def build_prompt(inputs):
    base = """Answer questions using tools.\n\nTools:\n{tools}\n\n"""
    if "urgent" in inputs["input"].lower():
        base += "This is URGENT. Prioritize speed over thoroughness.\n\n"
    else:
        base += "Take your time and be thorough.\n\n"
    base += "Question: {input}\nThought:{agent_scratchpad}"
    return PromptTemplate.from_template(base).format(**inputs)

dynamic_prompt = RunnableLambda(build_prompt)
# Pass dynamic_prompt to create_react_agent
```

### Pattern C: Multi-Language Prompts

If your agent must handle multiple languages, embed the instruction in the prompt.

```python
multilingual_prompt = PromptTemplate.from_template("""You are a multilingual agent. Detect the language of the question and respond in that language.

Tools:
{tools}

Question: {input}
Thought:{agent_scratchpad}""")
```

---

## 3.8 Putting It All Together: A Complete Custom ReAct Agent

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.tools import tool

# ─── Step 1: Define Tools ───
@tool
def search(query: str) -> str:
    """Search for factual information on the internet.
    Use this for questions about current events, people, places, or general knowledge.
    """
    # In production, replace with real search API (SerpAPI, Tavily, etc.)
    return f"[Mock search results for: {query}]"

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression.
    Use this for any calculation, arithmetic, or numeric reasoning.
    Input must be a valid Python expression like '25 * 17' or 'sqrt(144)'.
    """
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

tools = [search, calculator]

# ─── Step 2: Build a Custom Prompt ───
custom_prompt = PromptTemplate.from_template("""You are a precise research assistant. Your job is to answer user questions accurately by using available tools.

## Rules
1. Always verify facts with tools. Never guess.
2. Show your reasoning in the Thought section.
3. If a tool fails, try a different approach.
4. Cite which tools you used in your Final Answer.

## Available Tools
{tools}

## Output Format
You MUST follow this exact format:

Thought: your step-by-step reasoning
Action: the tool to use (one of [{tool_names}])
Action Input: the input to the tool
Observation: the result from the tool
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now know the final answer
Final Answer: your complete answer to the user

## Example
Question: What is 15 squared?
Thought: The user wants to know 15 squared. I should calculate this.
Action: calculator
Action Input: 15 ** 2
Observation: 225
Thought: I now know the final answer.
Final Answer: 15 squared is 225.

## Your Turn
Question: {input}
Thought:{agent_scratchpad}""")

# ─── Step 3: Create the Agent ───
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
agent = create_react_agent(llm, tools, custom_prompt)

# ─── Step 4: Execute ───
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,          # Print the ReAct loop steps
    max_iterations=10,      # Safety cap to prevent infinite loops
    handle_parsing_errors=True  # Gracefully recover from format mistakes
)

# ─── Step 5: Run ───
response = agent_executor.invoke({
    "input": "What is the population of Tokyo, and what is 2.5% of that number?"
})

print("\n=== FINAL OUTPUT ===")
print(response["output"])
```

### Expected Output

```
> Entering new AgentExecutor chain...
Thought: The user is asking two things: the population of Tokyo, and 2.5% of that number. I should first find the population, then calculate the percentage.
Action: search
Action Input: population of Tokyo 2024
Observation: [Mock search results for: population of Tokyo 2024]
Thought: The search returned information. Let me assume the population is approximately 14 million. Now I need to calculate 2.5% of 14,000,000.
Action: calculator
Action Input: 0.025 * 14000000
Observation: 350000.0
Thought: I now know the final answer.
Final Answer: The population of Tokyo is approximately 14 million, and 2.5% of that is 350,000.

> Finished chain.

=== FINAL OUTPUT ===
The population of Tokyo is approximately 14 million, and 2.5% of that is 350,000.
```

---

## 3.9 Key Takeaways

| Concept | Summary |
|---------|---------|
| **ReAct Loop** | Thought → Action → Observation → repeat → Final Answer |
| **Prompt Role** | The prompt *teaches* the LLM the ReAct format. Without it, the model won't use tools correctly. |
| **`agent_scratchpad`** | A running string appended to the prompt on every iteration. It is the agent's short-term memory. |
| **`create_react_agent`** | The modern, explicit way to build ReAct agents. You supply the full prompt. |
| **`initialize_agent`** | Legacy approach with hidden prompts. Avoid for new projects. |
| **Customization** | You control behavior via system instructions, few-shot examples, constraints, and output formatting in the prompt. |
| **Tool Descriptions** | These are injected into the prompt via `{tools}`. Good descriptions are prompt engineering. |

---

## 3.10 Further Reading

- [LangChain Agents Documentation](https://python.langchain.com/docs/modules/agents/)
- [ReAct Paper: Yao et al., 2022](https://arxiv.org/abs/2210.03629)
- [LangChain Hub — ReAct Prompts](https://smith.langchain.com/hub)
- [LCEL (LangChain Expression Language) Primer](https://python.langchain.com/docs/expression_language/)

---

*Next: Section 4 — Adding Memory to Agents (Conversation History Across Runs)*
