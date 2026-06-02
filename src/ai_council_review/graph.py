"""LangGraph state machine for AI Council Code Review."""

from __future__ import annotations

import os
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from ai_council_review.agents.architecture import ArchitectureAgent
from ai_council_review.agents.quality import QualityAgent
from ai_council_review.agents.router import RouterAgent
from ai_council_review.agents.security import SecurityAgent
from ai_council_review.agents.synthesis import SynthesisAgent
from ai_council_review.config import CouncilConfig
from ai_council_review.github_client import GitHubClient
from ai_council_review.models import FileInfo, Finding, ReviewComment, ReviewState
from ai_council_review.pr_ingestor import PRIngestor
from ai_council_review.publisher import Publisher
from ai_council_review.repository_browser import RepositoryBrowser

logger = structlog.get_logger()


def ingest_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Ingest PR metadata and changed files.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state.
    """
    logger.info("Ingest node starting")
    ingestor = PRIngestor(config)

    # Load from environment if available
    payload = None
    if os.environ.get("GITHUB_EVENT_PATH"):
        payload = ingestor.load_event_payload()

    pr, files, skipped, skip_reason = ingestor.ingest(payload)

    if skipped:
        return {
            "pr_metadata": pr,
            "skipped": True,
            "skip_reason": skip_reason,
        }

    # Fetch files from GitHub if we have a token
    token = os.environ.get("GITHUB_TOKEN")
    if token and pr:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if repo:
            client = GitHubClient(token, repo)
            raw_files = client.get_pr_files(pr.number)
            files = [
                FileInfo(
                    filename=f["filename"],
                    status=f["status"],
                    additions=f.get("additions", 0),
                    deletions=f.get("deletions", 0),
                    changes=f.get("changes", 0),
                    patch=f.get("patch"),
                    previous_filename=f.get("previous_filename"),
                    sha=f.get("sha"),
                    raw_url=f.get("raw_url"),
                )
                for f in raw_files
            ]
            files = ingestor.filter_files(files)

    return {
        "pr_metadata": pr,
        "changed_files": files,
        "skipped": skipped,
        "skip_reason": skip_reason,
    }


def router_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Run the router agent to decide which agents are needed.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state with routing decision.
    """
    logger.info("Router node starting")

    if state.skipped:
        return {}

    if not state.changed_files:
        logger.info("No files to review")
        return {}

    router = RouterAgent(config)
    result = router.run(state)

    logger.info(
        "Router complete",
        agents=result.agents_needed,
        depth=result.review_depth,
    )

    return {
        "agents_needed": result.agents_needed,
        "review_depth": result.review_depth,
    }


def security_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Run the security agent.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state.
    """
    if state.skipped:
        return {}

    browser = _get_browser()
    agent = SecurityAgent(config, browser=browser)
    findings = agent.run(state)

    return {
        "agent_outputs": {agent.name: findings},
    }


def quality_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Run the quality agent.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state.
    """
    if state.skipped:
        return {}

    browser = _get_browser()
    agent = QualityAgent(config, browser=browser)
    findings = agent.run(state)

    return {
        "agent_outputs": {agent.name: findings},
    }


def architecture_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Run the architecture agent.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state.
    """
    if state.skipped:
        return {}

    browser = _get_browser()
    agent = ArchitectureAgent(config, browser=browser)
    findings = agent.run(state)

    return {
        "agent_outputs": {agent.name: findings},
    }


def synthesis_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Run the synthesis agent to merge findings.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state.
    """
    logger.info("Synthesis node starting")

    if state.skipped:
        return {}

    if not state.agent_outputs:
        logger.info("No agent outputs to synthesize")
        return {}

    agent = SynthesisAgent(config)
    result = agent.run(state)

    return {
        "summary": result.summary,
        "verdict": result.verdict,
        "agent_outputs": {"synthesis": result.findings},
    }


def post_node(state: ReviewState, config: CouncilConfig) -> dict[str, Any]:
    """Post the review to GitHub.

    Args:
        state: Current review state.
        config: Council configuration.

    Returns:
        Updates to the state.
    """
    logger.info("Post node starting")

    if state.skipped:
        logger.info("PR skipped, nothing to post", reason=state.skip_reason)
        return {}

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo or not state.pr_metadata:
        logger.warning("Missing token, repo, or PR metadata — skipping post")
        return {}

    client = GitHubClient(token, repo)
    publisher = Publisher(client)

    # Build findings from all agents (excluding synthesis)
    all_findings: list[Finding] = []
    for agent_name, agent_findings in state.agent_outputs.items():
        if agent_name != "synthesis":
            all_findings.extend(agent_findings)

    if not all_findings:
        logger.info("No findings to post")
        summary = "## AI Code Review\n\nNo issues found in this PR. ✅"
        publisher.post_review(
            pr_number=state.pr_metadata.number,
            summary=summary,
            comments=[],
            commit_id=state.pr_metadata.head_sha,
        )
        return {
            "summary": summary,
            "verdict": "approve",
        }

    # Convert findings to ReviewComments
    comments: list[ReviewComment] = []
    for finding in all_findings:
        if finding.position is not None:
            comments.append(
                ReviewComment(
                    path=finding.path,
                    position=finding.position,
                    body=finding.body,
                )
            )

    # Validate comments against changed files
    comments = publisher.validate_comments(comments, state.changed_files)

    # Build summary from synthesis if available
    summary_text: str = state.summary or ""
    if not summary_text:
        summary_parts = ["## AI Code Review\n"]
        severity_counts: dict[str, int] = {}
        for finding in all_findings:
            severity_counts[finding.severity.value] = (
                severity_counts.get(finding.severity.value, 0) + 1
            )

        summary_parts.append("\n**Findings by severity:**\n")
        for severity, count in sorted(
            severity_counts.items(),
            key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(x[0], 5),
        ):
            summary_parts.append(f"- {severity.capitalize()}: {count}")

        summary_parts.append(f"\n**Total findings:** {len(all_findings)}")
        summary_parts.append(
            "\n---\n\n*This review was generated automatically. Please verify all suggestions before applying.*"
        )
        summary_text = "\n".join(summary_parts)

    verdict = state.verdict or "comment"

    publisher.post_review(
        pr_number=state.pr_metadata.number,
        summary=summary_text,
        comments=comments,
        commit_id=state.pr_metadata.head_sha,
    )

    return {
        "summary": summary_text,
        "github_comments": comments,
        "verdict": verdict,
    }


def _get_browser() -> RepositoryBrowser | None:
    """Create a RepositoryBrowser if GitHub token is available.

    Returns:
        RepositoryBrowser or None.
    """
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if token and repo:
        client = GitHubClient(token, repo)
        return RepositoryBrowser(github_client=client)
    return None


def _route_from_router(state: ReviewState) -> list[str]:
    """Determine which agents to run based on router output.

    Args:
        state: Current review state.

    Returns:
        List of agent node names to execute.
    """
    agents = getattr(state, "agents_needed", ["security", "quality", "architecture"])
    valid_agents = {"security", "quality", "architecture"}
    return [a for a in agents if a in valid_agents]


def build_graph(config: CouncilConfig) -> Any:
    """Build the LangGraph state machine with multi-agent routing.

    Args:
        config: Council configuration.

    Returns:
        Compiled StateGraph.
    """
    workflow = StateGraph(ReviewState)

    # Nodes
    workflow.add_node("ingest", lambda state: ingest_node(state, config))
    workflow.add_node("router", lambda state: router_node(state, config))
    workflow.add_node("security", lambda state: security_node(state, config))
    workflow.add_node("quality", lambda state: quality_node(state, config))
    workflow.add_node("architecture", lambda state: architecture_node(state, config))
    workflow.add_node("synthesis", lambda state: synthesis_node(state, config))
    workflow.add_node("post", lambda state: post_node(state, config))

    # Edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "router")

    # Conditional routing from router
    # LangGraph doesn't support dynamic conditional edges easily in v0.0.x,
    # so we'll run all agents in parallel and let them skip if not needed.
    # In v0.1.x, we could use Send() for conditional routing.
    # For now: router -> all agents in parallel
    workflow.add_edge("router", "security")
    workflow.add_edge("router", "quality")
    workflow.add_edge("router", "architecture")

    # Parallel agents converge to synthesis
    workflow.add_edge("security", "synthesis")
    workflow.add_edge("quality", "synthesis")
    workflow.add_edge("architecture", "synthesis")

    # Synthesis -> post
    workflow.add_edge("synthesis", "post")
    workflow.add_edge("post", END)

    return workflow.compile()
