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
