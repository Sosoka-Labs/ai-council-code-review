"""Custom exceptions for AI Council Code Review."""

from __future__ import annotations


class AICouncilError(Exception):
    """Base exception for all AI Council errors."""

    pass


class GitHubAPIError(AICouncilError):
    """Error interacting with the GitHub API."""

    pass


class RateLimitError(GitHubAPIError):
    """GitHub API rate limit exceeded."""

    pass


class ConfigError(AICouncilError):
    """Invalid configuration."""

    pass


class IngestorError(AICouncilError):
    """Error ingesting PR data."""

    pass


class AgentError(AICouncilError):
    """Error running an agent."""

    pass


class LLMProviderError(AICouncilError):
    """Error with an LLM provider."""

    pass


class BudgetExceededError(AICouncilError):
    """Review budget exceeded."""

    pass


class SkillError(AICouncilError):
    """Base for all skill-related errors."""

    pass


class SkillLoadError(SkillError):
    """Raised when a SKILL.md cannot be parsed or fails validation."""

    pass


class SkillNotFoundError(SkillError):
    """Raised when a requested skill name is not in the registry."""

    pass
