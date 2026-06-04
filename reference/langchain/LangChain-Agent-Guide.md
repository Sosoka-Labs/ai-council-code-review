# The LangChain Agent Team Guide

> **A comprehensive reference for building agents with LangChain**  
> **Topics:** ChatPromptTemplates · Cost Tracking · ReAct Agent Prompts · Tool Creation & Binding · DeepAgents SDK · LangSmith Tracing  
> **Version:** June 2026 | LangChain v0.2.x+

---

## Table of Contents

| Section | Topic | Page |
|---------|-------|------|
| **1** | ChatPromptTemplates — Structured Prompts for Conversational LLMs | 3 |
| **2** | Cost Tracking — Token Usage, Budgets, and Multi-Provider Monitoring | 15 |
| **3** | Binding Prompts to ReAct Agents — The Thought-Action-Observation Loop | 28 |
| **4** | Tool Creation & Binding — From `@tool` to Production-Grade Agents | 40 |
| **5** | DeepAgents SDK — Batteries-Included Agent Harness | 55 |
| **6** | LangSmith Tracing — Observability for LLM Applications | 70 |

---

## How to Use This Guide

This document is designed as a **progressive reference** — each section builds on concepts from the previous ones, but can also be read independently.

- **New to LangChain?** Start with Section 1 (ChatPromptTemplates) and work forward.
- **Building your first agent?** Jump to Section 3 (ReAct Agents) and Section 4 (Tools).
- **Going to production?** Section 2 (Cost Tracking) and Section 6 (LangSmith) are essential.
- **Need advanced orchestration?** Section 5 (DeepAgents) covers multi-agent patterns.

Every section includes working Python code examples. Copy, paste, and experiment.

---

# Section 1: ChatPromptTemplates — Structured Prompts for Conversational LLMs

> **Prerequisites:** Basic Python. No prior LangChain experience required.
> **LangChain Version:** This guide covers the modern LangChain API (v0.1.x+). Legacy `PromptTemplate` patterns are noted where relevant.

---

## 1.1 What Is ChatPromptTemplate and Why It Exists

### The Problem: Chat Models Speak in Messages

Modern LLMs like GPT-4, Claude, and Gemini are **chat models**. They don't just take a raw string—they expect a **list of messages**, each with a **role** (`system`, `user`, `assistant`) and **content**. If you feed them a single flat string, you lose the structural signals that make conversations work.

LangChain's `ChatPromptTemplate` is the abstraction that lets you build these structured message lists programmatically, with variable substitution, composition, and type safety.

### ChatPromptTemplate vs String Prompt Templates

| Aspect | `PromptTemplate` (Legacy) | `ChatPromptTemplate` (Modern) |
|--------|---------------------------|-------------------------------|
| **Output** | Single string | List of `BaseMessage` objects |
| **Target models** | Text completion models (e.g., `text-davinci-003`) | Chat models (e.g., GPT-4, Claude, Llama) |
| **Structure** | Flat—one template string | Structured—multiple message templates |
| **Role separation** | Manual (e.g., `System: ...\nUser: ...`) | Native (`SystemMessage`, `HumanMessage`, `AIMessage`) |
| **Composability** | Limited | Rich—messages can be appended, prepended, merged |
| **LCEL support** | Basic | First-class `.pipe()` and `RunnableSequence` |

> **Rule of thumb:** If you're using a chat model (and you almost certainly are), use `ChatPromptTemplate`. The old `PromptTemplate` is for legacy text-completion endpoints.

### A Minimal Example

```python
from langchain_core.prompts import ChatPromptTemplate

# Define a chat prompt with two messages
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant named {name}."),
    ("human", "What is the capital of {country}?"),
])

# Format it into a list of message objects
messages = prompt.invoke({"name": "Atlas", "country": "France"})
print(messages.to_messages())
# → [
#     SystemMessage(content='You are a helpful assistant named Atlas.'),
#     HumanMessage(content='What is the capital of France?')
# ]
```

Notice that `prompt.invoke()` returns a `ChatPromptValue`—a container of messages—not a raw string. This is the modern LangChain pattern. You pass the whole object to a chat model, which knows how to render it into the API-specific format.

---

## 1.2 Message Role Templates

`ChatPromptTemplate.from_messages()` accepts a list of tuples: `(role, template_string)`. LangChain maps these roles to specific message classes internally.

### The Three Core Roles

| Role String | Class | Purpose |
|-------------|-------|---------|
| `"system"` | `SystemMessagePromptTemplate` | Sets behavior, persona, constraints |
| `"human"` | `HumanMessagePromptTemplate` | Represents the user's input |
| `"ai"` | `AIMessagePromptTemplate` | Represents assistant responses (useful for few-shot examples) |

### SystemMessagePromptTemplate — The Persona Layer

The system message is the "stage directions" for the model. It typically defines:
- The assistant's persona or expertise
- Output format constraints (JSON, Markdown, bullet points)
- Guardrails (what NOT to do)
- Context that applies to the entire conversation

```python
from langchain_core.prompts import ChatPromptTemplate

system_template = """You are {role}. Your expertise is {domain}.

Rules:
- Always answer in {language}
- Keep responses under {max_words} words
- If you don't know, say "I don't know" rather than guessing
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    ("human", "{question}"),
])

messages = prompt.invoke({
    "role": "a senior DevOps engineer",
    "domain": "Kubernetes and container orchestration",
    "language": "English",
    "max_words": "100",
    "question": "How do I debug a CrashLoopBackOff?"
})
```

> **Best practice:** Keep system prompts stable across invocations. They're ideal for `.partial()` (see Section 1.4).

### HumanMessagePromptTemplate — The User Input

This is the dynamic part that changes every turn. It captures the user's actual question, query, or task.

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a code reviewer."),
    ("human", "Review this {language} code for {concern}:\n\n```{language}\n{code}\n```"),
])

messages = prompt.invoke({
    "language": "python",
    "concern": "security vulnerabilities",
    "code": "import os\npassword = os.getenv('DB_PASSWORD')"
})
```

Notice the `{language}` variable is used **twice** in the same template—LangChain handles this correctly.

### AIMessagePromptTemplate — Simulating Assistant Responses

The AI message template is most commonly used for **few-shot prompting** (Section 1.6). It lets you inject example assistant responses into the prompt structure.

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a sentiment classifier. Respond with ONLY 'positive' or 'negative'."),
    ("human", "The movie was absolutely fantastic!"),
    ("ai", "positive"),
    ("human", "I wasted two hours of my life."),
    ("ai", "negative"),
    ("human", "{review}"),
])

messages = prompt.invoke({"review": "The cinematography was stunning but the plot made no sense."})
```

This creates a structured few-shot prompt where the examples are properly typed as `HumanMessage` / `AIMessage` pairs.

### Explicit Class Constructors (Alternative Syntax)

Instead of the tuple shorthand, you can construct message templates explicitly. This is useful when you need more control:

```python
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
    ChatPromptTemplate,
)

system_msg = SystemMessagePromptTemplate.from_template("You are {role}")
human_msg = HumanMessagePromptTemplate.from_template("{question}")
ai_msg = AIMessagePromptTemplate.from_template("{response}")

prompt = ChatPromptTemplate.from_messages([system_msg, human_msg, ai_msg])
```

The tuple syntax `("system", "...")` is just sugar for the above. Use whichever style your team prefers—consistency matters more than the choice.

---

## 1.3 MessagesPlaceholder — Dynamic Message Lists

### The Problem: Variable-Length Conversations

What if you don't know how many messages you'll have at prompt construction time? A chat history could be 2 messages or 200. You can't define 200 `("human", ...)` tuples upfront.

`MessagesPlaceholder` solves this by creating a **slot** that gets filled with a list of messages at runtime.

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{question}"),
])

# Provide a list of messages for the placeholder
from langchain_core.messages import HumanMessage, AIMessage

messages = prompt.invoke({
    "chat_history": [
        HumanMessage(content="Hi, what's your name?"),
        AIMessage(content="I'm Claude, an AI assistant."),
        HumanMessage(content="Nice to meet you."),
    ],
    "question": "Can you help me with Python?"
})

print(messages.to_messages())
# → [
#     SystemMessage(content='You are a helpful assistant.'),
#     HumanMessage(content='Hi, what's your name?'),
#     AIMessage(content="I'm Claude, an AI assistant."),
#     HumanMessage(content='Nice to meet you.'),
#     HumanMessage(content='Can you help me with Python?')
# ]
```

### Optional Placeholders

By default, if `MessagesPlaceholder` receives an empty list, it inserts nothing. You can make it optional with `optional=True`:

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{question}"),
])

# Works even with no chat_history provided
messages = prompt.invoke({"question": "Hello!"})
# → [SystemMessage(...), HumanMessage(content='Hello!')]
```

### Common Use Case: Conversation Memory

`MessagesPlaceholder` is the standard pattern for adding conversation history to a prompt:

```python
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

memory = ConversationBufferMemory(return_messages=True)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

# In a real app, you'd load history from memory
history = memory.load_memory_variables({})["history"]
messages = prompt.invoke({"history": history, "input": "What did we discuss earlier?"})
```

> **Note:** LangChain's built-in memory classes (like `ConversationBufferMemory`) are being phased out in favor of simpler patterns. In modern LCEL chains, you typically manage history as a list variable and pass it directly to `MessagesPlaceholder`.

---

## 1.4 Partial Variables and Prompt Composition

### Partial Variables: Freezing Some Inputs

Often you want to build a prompt template where some variables are fixed early (e.g., the system persona) and others are filled later (e.g., the user's question). `.partial()` creates a new prompt template with some variables already bound.

```python
from langchain_core.prompts import ChatPromptTemplate

# Base template with multiple variables
base_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are {role}. You speak in {tone}."),
    ("human", "{question}"),
])

# Freeze the role and tone
sarcastic_dev_prompt = base_prompt.partial(
    role="a sarcastic senior developer",
    tone="dry, sarcastic English"
)

# Now only 'question' is required
messages = sarcastic_dev_prompt.invoke({"question": "Why is my code slow?"})
# → SystemMessage: 'You are a sarcastic senior developer. You speak in dry, sarcastic English.'
# → HumanMessage: 'Why is my code slow?'
```

### Partial with Functions (Lazy Evaluation)

You can also bind variables to **functions** that are evaluated at `invoke()` time. This is useful for dynamic values like timestamps:

```python
from datetime import datetime

prompt = ChatPromptTemplate.from_messages([
    ("system", "Current date: {date}. You are a helpful assistant."),
    ("human", "{question}"),
])

# Bind 'date' to a function that returns the current date
prompt_with_date = prompt.partial(date=lambda: datetime.now().strftime("%Y-%m-%d"))

messages = prompt_with_date.invoke({"question": "What day is it?"})
# → SystemMessage: 'Current date: 2026-06-04. You are a helpful assistant.'
```

### Prompt Composition: Adding Messages

`ChatPromptTemplate` supports `+` for concatenation, letting you build prompts from reusable pieces:

```python
from langchain_core.prompts import ChatPromptTemplate

# Reusable system persona
persona = ChatPromptTemplate.from_messages([
    ("system", "You are {role}. Be concise."),
])

# Reusable task instruction
task = ChatPromptTemplate.from_messages([
    ("human", "Summarize this text in {style}:\n\n{text}"),
])

# Compose them
full_prompt = persona + task

messages = full_prompt.invoke({
    "role": "a professional editor",
    "style": "bullet points",
    "text": "LangChain is a framework for building applications with LLMs..."
})
```

### Prepending vs Appending

```python
# Add a safety instruction to the BEGINNING of any prompt
safety_prefix = ChatPromptTemplate.from_messages([
    ("system", "Never provide instructions for illegal activities."),
])

any_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful coding assistant."),
    ("human", "{question}"),
])

safe_prompt = safety_prefix + any_prompt
# → Messages: [Safety system, Persona system, Human question]
```

> **Composition rule:** When you `+` two `ChatPromptTemplate`s, their message lists are concatenated in order. This is a shallow merge—no deduplication happens.

---

## 1.5 The LCEL Approach: `.pipe()` and RunnableSequence

### What Is LCEL?

**LangChain Expression Language (LCEL)** is a declarative way to compose LangChain components using the `|` operator (or `.pipe()`). It treats prompts, models, and output parsers as **runnables** that can be chained together.

### Chaining Prompt → Model → Parser

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

# 1. Define the prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a concise technical writer."),
    ("human", "Explain {topic} in one sentence."),
])

# 2. Define the model
model = ChatOpenAI(model="gpt-4", temperature=0)

# 3. Define the output parser
parser = StrOutputParser()

# 4. Compose with LCEL using the pipe operator
chain = prompt | model | parser

# 5. Invoke the entire chain
result = chain.invoke({"topic": "vector databases"})
print(result)
# → "Vector databases are specialized data stores designed to efficiently index and query high-dimensional vector embeddings for similarity search."
```

### What's Happening Under the Hood

When you write `prompt | model | parser`, LangChain creates a `RunnableSequence`. Each component's output becomes the next component's input:

```
{"topic": "vector databases"}
    ↓
[ChatPromptTemplate] → ChatPromptValue (messages)
    ↓
[ChatOpenAI] → AIMessage (raw model output)
    ↓
[StrOutputParser] → str (clean text)
    ↓
"Vector databases are..."
```

### The `.pipe()` Method

The `|` operator is syntactic sugar for `.pipe()`:

```python
# These are equivalent:
chain = prompt | model | parser
chain = prompt.pipe(model).pipe(parser)
```

Use `.pipe()` when you need to pass configuration:

```python
chain = prompt.pipe(model, config={"run_name": "topic-explainer"}).pipe(parser)
```

### Passing Prompt Output Directly to Model

A key insight: `ChatPromptTemplate.invoke()` returns a `ChatPromptValue`, and `ChatOpenAI` (and other chat models) accept `ChatPromptValue` directly. The type system handles the conversion:

```python
# This works because ChatPromptValue is a valid input for ChatOpenAI
prompt_value = prompt.invoke({"topic": "RAG"})
response = model.invoke(prompt_value)
```

This is why LCEL chains work seamlessly—each runnable's output type matches the next runnable's input type.

### Streaming with LCEL

LCEL chains support streaming out of the box:

```python
# Stream tokens as they arrive from the model
for token in chain.stream({"topic": "LangChain"}):
    print(token, end="", flush=True)
```

Because `StrOutputParser` is a simple text transformer, it passes tokens through with minimal overhead. The stream flows from model → parser → your code.

### Batch Processing

```python
# Process multiple inputs in parallel
topics = [
    {"topic": "RAG"},
    {"topic": "fine-tuning"},
    {"topic": "prompt engineering"},
]
results = chain.batch(topics)
# → ["RAG is...", "Fine-tuning is...", "Prompt engineering is..."]
```

### Async Support

```python
result = await chain.ainvoke({"topic": "async programming"})
```

> **LCEL Best Practice:** Prefer `|` composition over imperative `chain = LLMChain(...)` patterns. LCEL is more transparent, debuggable, and supports streaming/batching natively.

---

## 1.6 Few-Shot Prompting with ChatPromptTemplate

### Static Few-Shot Examples

The simplest approach is hardcoding examples directly into the message list:

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a classifier. Respond with ONLY the category name."),
    ("human", "Email: 'Your invoice is ready.'"),
    ("ai", "billing"),
    ("human", "Email: 'The server is down again.'"),
    ("ai", "incident"),
    ("human", "Email: 'Can we schedule a meeting?'"),
    ("ai", "scheduling"),
    ("human", "Email: '{email}'"),
])

messages = prompt.invoke({"email": "Your password reset was successful."})
```

### Dynamic Few-Shot with Example Selectors

For large example sets, LangChain provides **example selectors** that pick the most relevant examples based on similarity:

```python
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.example_selectors import SemanticSimilarityExampleSelector

# Define your example set
examples = [
    {"input": "What is 2+2?", "output": "4"},
    {"input": "What is 10*5?", "output": "50"},
    {"input": "What is the capital of France?", "output": "Paris"},
    {"input": "Solve for x: 2x + 4 = 10", "output": "x = 3"},
]

# Create a few-shot prompt template
example_prompt = ChatPromptTemplate.from_messages([
    ("human", "{input}"),
    ("ai", "{output}"),
])

# Use semantic similarity to pick the best examples
example_selector = SemanticSimilarityExampleSelector.from_examples(
    examples,
    OpenAIEmbeddings(),
    Chroma,
    k=2,  # Pick top 2 most similar examples
)

few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_selector=example_selector,
    example_prompt=example_prompt,
)

# Compose into full prompt
final_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful math and trivia assistant."),
    few_shot_prompt,
    ("human", "{input}"),
])

messages = final_prompt.invoke({"input": "What is 3*7?"})
# → Will include the 2 most similar examples (likely the math ones)
```

### Formatting Examples Manually (Without Selectors)

If you don't need semantic selection, use `FewShotChatMessagePromptTemplate` with a fixed example list:

```python
from langchain_core.prompts import FewShotChatMessagePromptTemplate

examples = [
    {"input": "happy", "output": "😊"},
    {"input": "sad", "output": "😢"},
    {"input": "angry", "output": "😠"},
]

example_prompt = ChatPromptTemplate.from_messages([
    ("human", "{input}"),
    ("ai", "{output}"),
])

few_shot_prompt = FewShotChatMessagePromptTemplate(
    examples=examples,
    example_prompt=example_prompt,
)

final_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an emoji translator."),
    few_shot_prompt,
    ("human", "{input}"),
])

messages = final_prompt.invoke({"input": "excited"})
```

### Converting Few-Shot to Messages

`FewShotChatMessagePromptTemplate` is itself a template. When you call `.invoke()` on the parent `ChatPromptTemplate`, it:

1. Selects examples (via selector or fixed list)
2. Formats each example through `example_prompt`
3. Inserts the resulting `HumanMessage`/`AIMessage` pairs into the message list
4. Appends the final user query

---

## 1.7 Best Practices and Common Pitfalls

### ✅ Best Practices

**1. Always use ChatPromptTemplate with chat models**

```python
# ❌ Wrong: Using PromptTemplate with a chat model
from langchain_core.prompts import PromptTemplate  # Legacy
prompt = PromptTemplate.from_template("System: You are helpful.\nHuman: {question}")

# ✅ Correct: Using ChatPromptTemplate
from langchain_core.prompts import ChatPromptTemplate
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are helpful."),
    ("human", "{question}"),
])
```

**2. Use `.partial()` for stable configuration**

```python
# Good: Freeze the system persona once
base_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are {role}."),
    ("human", "{question}"),
])

coder_prompt = base_prompt.partial(role="a senior Python developer")
writer_prompt = base_prompt.partial(role="a technical writer")
# Both share the same structure, different personas
```

**3. Prefer tuple syntax for readability**

```python
# Clean and readable
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are {role}."),
    ("human", "{question}"),
])

# Only use explicit classes when you need the extra control
```

**4. Use MessagesPlaceholder for history, not hardcoded turns**

```python
# ❌ Brittle: Hardcoded history slots
prompt = ChatPromptTemplate.from_messages([
    ("system", "..."),
    ("human", "{q1}"), ("ai", "{a1}"),
    ("human", "{q2}"), ("ai", "{a2}"),
    ("human", "{current_question}"),
])

# ✅ Flexible: MessagesPlaceholder
prompt = ChatPromptTemplate.from_messages([
    ("system", "..."),
    MessagesPlaceholder("history"),
    ("human", "{current_question}"),
])
```

**5. Validate your prompt with `.invoke()` before chaining**

```python
# Always test that your variables resolve correctly
test_messages = prompt.invoke({"role": "test", "question": "test"})
print(test_messages.to_messages())  # Verify structure
```

### ⚠️ Common Pitfalls

**Pitfall 1: Variable name collisions in composed prompts**

```python
prompt_a = ChatPromptTemplate.from_messages([
    ("system", "You are {role}."),
])
prompt_b = ChatPromptTemplate.from_messages([
    ("human", "Act as {role} and answer: {question}"),
])

# ❌ Problem: Both templates use {role}
combined = prompt_a + prompt_b
# When invoked, both {role} slots get the same value
# If you wanted different roles, you're stuck

# ✅ Fix: Use distinct variable names
prompt_a = ChatPromptTemplate.from_messages([
    ("system", "You are {system_role}."),
])
prompt_b = ChatPromptTemplate.from_messages([
    ("human", "Pretend to be {character_role} and answer: {question}"),
])
```

**Pitfall 2: Forgetting that `invoke()` returns a prompt value, not a string**

```python
messages = prompt.invoke({"question": "Hello"})

# ❌ Wrong: Trying to use as string
model.invoke(str(messages))  # Passes garbage

# ✅ Correct: Pass the ChatPromptValue directly
model.invoke(messages)  # Model knows how to handle it

# ✅ Or in LCEL: the types flow automatically
chain = prompt | model
```

**Pitfall 3: MessagesPlaceholder without `optional=True` when history might be empty**

```python
# ❌ Will raise KeyError if 'history' is missing
MessagesPlaceholder("history")

# ✅ Safe for stateless invocations
MessagesPlaceholder("history", optional=True)
```

**Pitfall 4: Using f-strings instead of template variables**

```python
# ❌ Bad: f-string prevents reuse and composition
name = "Atlas"
prompt = ChatPromptTemplate.from_messages([
    ("system", f"You are {name}."),  # Hardcoded at definition time!
])

# ✅ Good: Template variable enables late binding
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are {name}."),
])
```

**Pitfall 5: Not handling Jinja2 vs f-string syntax correctly**

LangChain supports both `{var}` (default, f-string style) and `{{var}}` (Jinja2 style). Don't mix them unintentionally:

```python
# Default: f-string style (single braces)
prompt = ChatPromptTemplate.from_messages([
    ("human", "Hello, my name is {name}."),
])

# Jinja2 style (double braces) — must opt in
from langchain_core.prompts import PromptTemplate
prompt = PromptTemplate.from_template(
    "Hello, my name is {{name}}.",
    template_format="jinja2"
)
```

**Pitfall 6: Overloading the system message**

```python
# ❌ Too long — models may ignore or truncate
system_msg = """You are a helpful assistant. Here are 5000 words of context...
[5000 words later]
...and that's your entire knowledge base."""

# ✅ Better: Put long context in a separate message
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "Here is the reference material:\n\n{context}"),
    ("ai", "Got it. I'll use this material to answer your questions."),
    ("human", "{question}"),
])
```

**Pitfall 7: Forgetting that `+` concatenation is shallow**

```python
prompt_a = ChatPromptTemplate.from_messages([
    ("system", "You are {role}."),
])
prompt_b = ChatPromptTemplate.from_messages([
    ("system", "You are {role}."),  # Same variable
])

combined = prompt_a + prompt_b
# Result: TWO system messages with {role}
# If you invoke with {"role": "assistant"}, both become "assistant"
# No deduplication happens — be intentional about composition
```

---

## 1.8 Quick Reference

### Import Cheat Sheet

```python
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
    MessagesPlaceholder,
    FewShotChatMessagePromptTemplate,
)
```

### Common Patterns

```python
# Basic chat prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are {role}."),
    ("human", "{question}"),
])

# With conversation history
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are {role}."),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])

# With few-shot examples
few_shot = FewShotChatMessagePromptTemplate(
    examples=examples,
    example_prompt=ChatPromptTemplate.from_messages([
        ("human", "{input}"),
        ("ai", "{output}"),
    ]),
)
prompt = ChatPromptTemplate.from_messages([
    ("system", "..."),
    few_shot,
    ("human", "{input}"),
])

# Partial application
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are {role}."),
    ("human", "{question}"),
]).partial(role="a helpful assistant")

# LCEL chain
chain = prompt | ChatOpenAI() | StrOutputParser()
```

---

## 1.9 Summary

| Concept | Key Takeaway |
|---------|-------------|
| **ChatPromptTemplate** | Use it for all chat models. Outputs a list of messages, not a string. |
| **Message roles** | `system` = persona, `human` = user input, `ai` = assistant responses (for few-shot). |
| **MessagesPlaceholder** | The escape hatch for variable-length message lists (e.g., chat history). |
| **Partial variables** | Freeze early, bind late. Use `.partial()` for reusable prompt components. |
| **Composition** | `+` concatenates prompt templates. Watch for variable name collisions. |
| **LCEL** | `prompt \| model \| parser` is the modern, composable, streamable pattern. |
| **Few-shot** | Use `FewShotChatMessagePromptTemplate` with example selectors for dynamic examples. |

> **Next Section:** Section 2 covers Output Parsers — how to turn unstructured LLM text into structured Python objects.
-e 
---

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
-e 
---

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
-e 
---

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
-e 
---

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
-e 
---

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