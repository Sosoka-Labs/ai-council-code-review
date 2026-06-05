"""Prompt loading utilities."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from ai_council_review.llm.prompts import templates

_REGISTRY: dict[str, ChatPromptTemplate] = {
    "router": templates.ROUTER,
    "quality": templates.QUALITY,
    "security": templates.SECURITY,
    "generalist": templates.GENERALIST,
    "synthesis": templates.SYNTHESIS,
    "architecture": templates.ARCHITECTURE,
}


def load_prompt(name: str) -> ChatPromptTemplate:
    """Load a chat prompt template by name.

    Args:
        name: Prompt name (e.g., ``"generalist"``).

    Returns:
        A :class:`~langchain_core.prompts.ChatPromptTemplate` configured
        with Jinja2 formatting.

    Raises:
        KeyError: If the prompt name is not registered.
    """
    if name not in _REGISTRY:
        raise KeyError(f"Prompt not found: {name}")
    return _REGISTRY[name]
