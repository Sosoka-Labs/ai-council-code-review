"""Parameterized specialist agent — single implementation for all specialist roles.

All specialist agents (security, quality, architecture, performance, documentation,
devops, …) share identical logic; only their ``AgentSpec`` and prompt differ.
This module exposes ``build_specialist_chain`` and ``run_specialist_agent`` as the
single implementation that ``graph.py`` calls for every registry entry.

The old per-agent modules (``security.py``, ``quality.py``, ``architecture.py``)
are kept as thin shims that delegate here so that any downstream code importing
them directly continues to work without modification.

Cross-file browsing (tool loop):
    When a ``RepositoryBrowser`` is available the agent enters a bounded multi-turn
    loop.  The LLM is given the ``read_file / list_files / find_files`` tools and
    may call them to inspect unchanged repository files.  The loop terminates when:

    * The model emits a message with no tool calls (it has finished reasoning).
    * ``_MAX_TOOL_ROUNDS`` (5) loop iterations are reached.
    * The cumulative tool-call count across all rounds reaches ``_MAX_TOOL_CALLS``
      (12).

    On loop exit the last model response is handed to the existing ``parse_findings``
    parsing layer, which already handles malformed / loose JSON and falls back to a
    generalist re-parse pass.  When no browser is available the agent falls back to
    a single-turn ``prompt | llm.with_structured_output(FindingList)`` chain,
    identical to the pre-refactor behaviour.

Security note:
    Diffs are attacker-controllable.  The hard bounds above prevent a crafted diff
    from driving the agent into an unbounded tool-reading loop that exhausts the LLM
    budget or hits rate limits.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from ai_council_review.config import AgentConfig, CouncilConfig
from ai_council_review.exceptions import BudgetExceededError
from ai_council_review.github.browser import RepositoryBrowser
from ai_council_review.llm.agents.output_models import FindingList
from ai_council_review.llm.agents.parsing import parse_findings
from ai_council_review.llm.agents.registry import AgentSpec
from ai_council_review.llm.prompts.loader import load_prompt
from ai_council_review.llm.providers.factory import LLMProviderFactory
from ai_council_review.llm.tools.repository import make_repository_tools
from ai_council_review.models import Finding, ReviewState
from ai_council_review.skills import Skill, apply_skills
from ai_council_review.skills.registry import SkillRegistry
from ai_council_review.skills.resolution import (
    SkillMode,
    bind_chain_metadata,
    resolve_skills_for_agent,
)

logger = structlog.get_logger()

_PR_TITLE_MAX_CHARS = 500

# Security bounds for the agentic tool loop.  Keep these conservative —
# diffs are attacker-controllable and an adversarial prompt could attempt to
# drive the agent into an unbounded reading loop.
_MAX_TOOL_ROUNDS: int = 5  # max LLM ↔ tool back-and-forth iterations
_MAX_TOOL_CALLS: int = 12  # max cumulative tool calls across all rounds


def _build_agent_variables(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Build prompt variables from review state.

    Applies safety limits on untrusted PR content (title, body, diff) before
    injecting into LLM prompts.

    Args:
        state: Current review state.
        config: Council configuration (used for max_diff_size).

    Returns:
        Dict of prompt template variables.
    """
    changed_files = state.changed_files
    file_list = "\n".join(
        f"- {f.filename} ({f.status}, +{f.additions}/-{f.deletions})" for f in changed_files
    )

    diff_parts: list[str] = []
    for f in changed_files:
        if f.patch:
            diff_parts.append(f"=== {f.filename} ===\n{f.patch}")
    diff_text = "\n\n".join(diff_parts)

    max_chars = config.max_diff_size
    if len(diff_text) > max_chars:
        diff_text = diff_text[:max_chars] + f"\n\n[... diff truncated at {max_chars} chars ...]"

    pr = state.pr_metadata
    pr_title = (pr.title or "")[:_PR_TITLE_MAX_CHARS] if pr else ""
    pr_number = pr.number if pr else 0
    repo = pr.html_url if pr else ""

    return {
        "repo": repo,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "changed_files": file_list,
        "diff": diff_text,
    }


def _find_git_root(cwd: Path) -> Path | None:
    """Return the git work-tree root at or above *cwd*, or None.

    Walks upward looking for a ``.git`` entry rather than spawning a subprocess,
    keeping this check fast and side-effect free.  Returning the root (not just a
    bool) lets callers anchor the browser at the repo root even when invoked from
    a nested subdirectory, so diff-relative paths resolve correctly.

    Args:
        cwd: Directory to inspect.

    Returns:
        The directory containing ``.git``, or None when *cwd* is not inside a
        git checkout.
    """
    # Walk upwards — stop at the filesystem root.
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _make_browser_from_env() -> RepositoryBrowser | None:
    """Construct a RepositoryBrowser appropriate for the current environment.

    Resolution order:
    1. If the process is running inside a local git checkout (the common CI
       case where the target repo is already checked out on disk), return a
       browser with **no** GitHub client attached.  This makes browsing zero
       API calls — all file reads go directly to the filesystem.
    2. If we are NOT inside a checkout but a ``GITHUB_TOKEN`` and
       ``GITHUB_REPOSITORY`` are set, attach a ``GitHubClient`` so the browser
       can fall back to the Contents API.
    3. Return ``None`` when neither a checkout nor API credentials are
       available — callers degrade gracefully to diff-only mode.

    The local-checkout check deliberately avoids spawning a subprocess (uses
    ``.git`` detection) to keep the hot path fast.
    """
    git_root = _find_git_root(Path.cwd())
    if git_root is not None:
        # INFO, not DEBUG: which browser mode we pick is the exact decision that
        # separates a fast filesystem review from the GitHub-API rate-limit hang
        # that stalled the pilot. Keep it visible at the default log level.
        logger.info(
            "Local git checkout detected; building filesystem-only browser",
            repo_path=str(git_root),
        )
        return RepositoryBrowser(repo_path=git_root, github_client=None)

    # No local checkout — fall back to API-backed browser if credentials exist.
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        return None

    from ai_council_review.github.client import GitHubClient

    logger.info(
        "No local checkout; building API-backed browser",
        repo=repo,
    )
    client = GitHubClient(token, repo)
    return RepositoryBrowser(github_client=client)


def _execute_tool_calls(
    message: AIMessage, tools_by_name: dict[str, BaseTool]
) -> list[ToolMessage]:
    """Execute all tool calls in a model message and return the results.

    Args:
        message: AI message that may contain ``tool_calls``.
        tools_by_name: Mapping of tool name → BaseTool instance.

    Returns:
        List of ToolMessage results, one per tool call.
    """
    results: list[ToolMessage] = []
    for call in message.tool_calls:
        tool_name = call["name"]
        tool_args = call["args"]
        tool_id = call["id"]

        tool = tools_by_name.get(tool_name)
        if tool is None:
            content = f"Unknown tool: {tool_name}"
        else:
            try:
                content = tool.invoke(tool_args)
                if not isinstance(content, str):
                    content = str(content)
            except Exception as exc:
                content = f"Tool error ({tool_name}): {exc}"

        results.append(ToolMessage(content=content, tool_call_id=tool_id))
    return results


def _run_tool_loop(
    llm: Any,
    messages: list[BaseMessage],
    tools: list[BaseTool],
    agent_name: str,
) -> str:
    """Drive a bounded multi-turn tool-use loop and return the final text output.

    The model is called in a loop.  If it emits tool calls they are executed and
    their results are appended to the message history before the next iteration.
    The loop terminates (and the last model response is returned) when:

    * The model produces a message with no tool calls (natural stopping point).
    * ``_MAX_TOOL_ROUNDS`` iterations are reached.
    * The cumulative tool-call count reaches ``_MAX_TOOL_CALLS``.

    Args:
        llm: A LangChain ``BaseChatModel`` with tools bound via ``bind_tools``.
        messages: Initial prompt messages.
        tools: Tool list — used to build the name→tool lookup.
        agent_name: Agent identifier for logging.

    Returns:
        The ``content`` string of the final AIMessage (may be empty string if the
        model only emitted tool calls on the last round).
    """
    tools_by_name: dict[str, BaseTool] = {t.name: t for t in tools}
    history: list[BaseMessage] = list(messages)
    total_calls = 0

    for round_idx in range(_MAX_TOOL_ROUNDS):
        response: AIMessage = llm.invoke(history)
        history.append(response)

        tool_calls = getattr(response, "tool_calls", []) or []
        if not tool_calls:
            # Model is done — no pending tool calls.
            logger.debug(
                "Tool loop finished naturally",
                agent=agent_name,
                rounds=round_idx + 1,
                total_tool_calls=total_calls,
            )
            break

        # Enforce the cumulative tool-call ceiling before executing.
        remaining_budget = _MAX_TOOL_CALLS - total_calls
        calls_to_run = tool_calls[:remaining_budget]
        total_calls += len(calls_to_run)

        # Execute only the allowed calls; pretend we executed the rest with an
        # informational message so the model context stays consistent.
        tool_results = _execute_tool_calls(
            AIMessage(content="", tool_calls=calls_to_run), tools_by_name
        )
        history.extend(tool_results)

        if total_calls >= _MAX_TOOL_CALLS:
            logger.warning(
                "Tool loop hit call ceiling; stopping early",
                agent=agent_name,
                max_tool_calls=_MAX_TOOL_CALLS,
                rounds_completed=round_idx + 1,
            )
            # Run one final unconstrained LLM pass so the model can summarise.
            final_response: AIMessage = llm.invoke(history)
            return str(final_response.content) if final_response.content else ""
    else:
        logger.warning(
            "Tool loop hit round ceiling; parsing last response",
            agent=agent_name,
            max_rounds=_MAX_TOOL_ROUNDS,
        )

    # Return the content of the last response in history.
    last_msg = history[-1]
    return str(last_msg.content) if last_msg.content else ""


def build_specialist_chain(
    spec: AgentSpec,
    config: CouncilConfig,
    registry: SkillRegistry | None = None,
    browser: RepositoryBrowser | None = None,
) -> Runnable[dict[str, Any], Any]:
    """Build an LCEL chain for the given specialist agent spec.

    When *no* browser is available (dry-run, fork, or missing token) the chain
    is a single-turn ``prompt | llm.with_structured_output(FindingList)`` —
    identical to pre-refactor behaviour.

    When a ``browser`` is provided, the LLM has access to ``read_file``,
    ``list_files``, and ``find_files`` tools.  The chain is still returned as a
    ``Runnable`` but ``run_specialist_agent`` switches to the agentic tool loop
    (``_run_tool_loop``) instead of ``chain.invoke``.  The tool loop terminates
    deterministically via ``_MAX_TOOL_ROUNDS`` / ``_MAX_TOOL_CALLS`` ceilings.

    Args:
        spec: Agent specification from the registry.
        config: Global council configuration.
        registry: Optional skill registry.  When provided, resolved skill bodies
            are appended to the system prompt.
        browser: Optional repository browser.  When provided, repository-browsing
            tools are bound to the chain for cross-file analysis.

    Returns:
        Configured Runnable chain (diff-only) or ``prompt | llm_with_tools``
        (tool-enabled — the caller is responsible for driving the tool loop).
    """
    agent_name = spec.name
    agent_config = config.agents.get(agent_name, AgentConfig())
    llm = LLMProviderFactory.from_config(agent_config, config.providers)
    prompt = load_prompt(spec.prompt_key)

    skills: list[Skill] = []
    skill_mode: SkillMode = "none"
    if registry is not None:
        skills = resolve_skills_for_agent(agent_name, config, registry)
        if skills:
            prompt = apply_skills(prompt, skills)
            skill_mode = "bodies"

    tools = make_repository_tools(browser)
    chain: Any
    if tools:
        try:
            # Bind tool schemas to the LLM so it can emit tool calls.
            # We do NOT chain .with_structured_output() here — that would
            # overwrite the tool binding on the underlying model (the bug
            # described in C-1).  Instead, run_specialist_agent drives the
            # multi-turn loop and then hands the final text to parse_findings().
            llm_with_tools = llm.bind_tools(tools)
            chain = prompt | llm_with_tools
        except (AttributeError, NotImplementedError):
            # Provider does not support tool-calling — fall back to diff-only.
            logger.debug(
                "Provider does not support tool-calling; using diff-only chain",
                agent=agent_name,
                provider=agent_config.model,
            )
            chain = prompt | llm.with_structured_output(FindingList)
    else:
        chain = prompt | llm.with_structured_output(FindingList)

    return bind_chain_metadata(chain, agent_name, skills, skill_mode)


def run_specialist_agent(
    spec: AgentSpec,
    state: ReviewState,
    config: CouncilConfig,
    callbacks: list[Any] | None = None,
    registry: SkillRegistry | None = None,
    browser: RepositoryBrowser | None = None,
) -> list[Finding]:
    """Run a specialist agent and return findings.

    Execution has two modes depending on whether repository-browsing tools are
    available:

    **Diff-only mode** (no browser):
        A single-turn ``chain.invoke`` with ``with_structured_output(FindingList)``
        produces a ``FindingList`` directly.

    **Tool-enabled mode** (browser available):
        The LLM is invoked in a bounded multi-turn loop (``_run_tool_loop``).
        Tool calls emitted by the model are executed against the browser (each
        tool call is subject to the size cap in ``make_repository_tools``).  The
        loop terminates when the model stops calling tools, or when the hard
        ceilings ``_MAX_TOOL_ROUNDS`` / ``_MAX_TOOL_CALLS`` are hit.  The final
        model response is parsed with the existing ``parse_findings`` layer, which
        handles loose / malformed JSON.

    Args:
        spec: Agent specification from the registry.
        state: Current review state.
        config: Council configuration.
        callbacks: Optional LangChain callbacks (e.g., CostCallbackHandler).
        registry: Optional skill registry for skill injection.
        browser: Optional repository browser.  When provided, the agent may call
            repository-browsing tools for cross-file analysis.  When ``None``,
            the chain uses diff-only mode.

    Returns:
        List of findings tagged with ``agent=spec.name``.
    """
    agent_name = spec.name
    logger.info("Specialist agent starting", agent=agent_name)

    # Resolve browser from environment if caller did not supply one.
    effective_browser = browser if browser is not None else _make_browser_from_env()

    tools = make_repository_tools(effective_browser)
    chain = build_specialist_chain(spec, config, registry=registry, browser=effective_browser)

    try:
        variables = _build_agent_variables(state, config)
        run_config = {"callbacks": callbacks} if callbacks else None

        if tools and effective_browser is not None:
            # Tool-enabled mode: drive the multi-turn loop, then parse text output.
            logger.info("Specialist agent using tool-enabled mode", agent=agent_name)
            prompt_obj = load_prompt(spec.prompt_key)
            # Render the prompt into concrete messages using the variables.
            messages = prompt_obj.format_messages(**variables)
            # Extract the tool-bound LLM from the chain (prompt | llm_with_tools).
            llm_with_tools = chain.last  # type: ignore[attr-defined]
            raw_text = _run_tool_loop(llm_with_tools, messages, tools, agent_name)
            findings = parse_findings(raw_text, agent_name=agent_name, logger=logger)
        else:
            # Diff-only mode: single-turn structured output.
            result = chain.invoke(variables, config=run_config)  # type: ignore[arg-type]
            findings = result.findings if isinstance(result, FindingList) else []

        for f in findings:
            f.agent = agent_name
        logger.info("Specialist agent finished", agent=agent_name, findings=len(findings))
        return findings
    except BudgetExceededError:
        raise
    except Exception as e:
        logger.error("Specialist agent failed", agent=agent_name, error=str(e))
        return []
