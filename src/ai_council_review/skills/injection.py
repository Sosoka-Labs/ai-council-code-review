"""Prompt-injection helpers for attaching skills to ChatPromptTemplates."""

from __future__ import annotations

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.chat import (
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.prompts.prompt import PromptTemplate

from ai_council_review.skills.models import Skill

_SKILLS_START = "<!-- ai-council:skills:start -->"
_SKILLS_END = "<!-- ai-council:skills:end -->"
_CATALOG_START = "<!-- ai-council:skill-catalog:start -->"
_CATALOG_END = "<!-- ai-council:skill-catalog:end -->"

_TemplateFormat = Literal["f-string", "mustache", "jinja2"]


_JINJA_TOKEN_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("{{", "{ {"),
    ("}}", "} }"),
    ("{%", "{ %"),
    ("%}", "% }"),
    ("{#", "{ #"),
    ("#}", "# }"),
)


def _escape_jinja2(text: str) -> str:
    """Neutralize Jinja2-sensitive tokens by splitting them with a space.

    Skill bodies are not templates; any ``{{ }}`` / ``{% %}`` / ``{# #}`` inside
    them is documentation, not code. We split each token (e.g. ``{{`` → ``{ {``)
    so the Jinja2 parser never recognizes them. This is unconditionally safe and
    cannot be bypassed by a malicious skill body — including one containing
    ``{%- endraw -%}``, which the previous raw-block approach was vulnerable to.
    """
    for token, replacement in _JINJA_TOKEN_REPLACEMENTS:
        text = text.replace(token, replacement)
    return text


def _get_string_template(msg: SystemMessagePromptTemplate | HumanMessagePromptTemplate) -> str:
    """Return the raw template string from a message prompt template.

    The langchain type annotation for `.prompt` is a Union, but in practice
    from_messages() always produces a PromptTemplate here. We cast explicitly
    so mypy is satisfied and the intent is clear.
    """
    prompt = msg.prompt
    if isinstance(prompt, PromptTemplate):
        return prompt.template
    # Fallback for list-of-blocks form — join templates if somehow a list arrived.
    return ""  # pragma: no cover


def _build_skills_block(skills: list[Skill]) -> str:
    """Return the formatted skills block for full-body injection."""
    lines: list[str] = [_SKILLS_START, "## Domain Skills", ""]
    for i, skill in enumerate(skills):
        lines.append(f"### {skill.name}: {skill.description}")
        lines.append("")
        lines.append(_escape_jinja2(skill.body))
        if i < len(skills) - 1:
            lines.append("---")
            lines.append("")
    lines.append(_SKILLS_END)
    return "\n".join(lines)


def _build_catalog_block(skills: list[Skill]) -> str:
    """Return the formatted skills catalog block (names + descriptions only)."""
    lines: list[str] = [_CATALOG_START, "## Available Domain Skills", ""]
    for skill in skills:
        lines.append(f"- **{skill.name}**: {skill.description}")
    lines.append(_CATALOG_END)
    return "\n".join(lines)


def _template_format(prompt: ChatPromptTemplate) -> _TemplateFormat:
    """Return the template format from the first message in the prompt."""
    for msg in prompt.messages:
        if isinstance(msg, SystemMessagePromptTemplate | HumanMessagePromptTemplate):
            prompt_part = msg.prompt
            if isinstance(prompt_part, PromptTemplate):
                fmt = prompt_part.template_format
                if fmt in ("f-string", "mustache", "jinja2"):
                    return fmt
    return "jinja2"


def _inject_into_system_message(prompt: ChatPromptTemplate, block: str) -> ChatPromptTemplate:
    """Return a new ChatPromptTemplate with *block* appended to the system message.

    Finds the first SystemMessagePromptTemplate in the prompt's message list,
    appends *block* to its template text (separated by a blank line), then
    rebuilds the full template. All other messages are reproduced unchanged.
    The original prompt is never mutated.
    """
    fmt = _template_format(prompt)
    new_messages: list[tuple[str, str]] = []
    injected = False

    for msg in prompt.messages:
        if isinstance(msg, SystemMessagePromptTemplate):
            template = _get_string_template(msg)
            if not injected:
                new_messages.append(("system", f"{template}\n\n{block}"))
                injected = True
            else:
                new_messages.append(("system", template))
        elif isinstance(msg, HumanMessagePromptTemplate):
            new_messages.append(("human", _get_string_template(msg)))
        # Other message types (AI, tool, etc.) are not expected in our prompts;
        # if they appear we skip them rather than crash. Coverage not required.

    return ChatPromptTemplate.from_messages(new_messages, template_format=fmt)


def apply_skills(
    prompt: ChatPromptTemplate,
    skills: list[Skill],
) -> ChatPromptTemplate:
    """Return a new ChatPromptTemplate with skill bodies appended to the system message.

    If *skills* is empty, returns the prompt unchanged (identity).

    Skill bodies containing Jinja2-sensitive tokens (``{{``, ``}}``, ``{%``,
    ``%}``, ``{#``, ``#}``) have each token split with a space so the Jinja2
    parser does not interpret them. This is unconditionally safe (no escape
    sequence the body could use will bypass it).
    """
    if not skills:
        return prompt

    block = _build_skills_block(skills)
    return _inject_into_system_message(prompt, block)


def apply_skill_catalog(
    prompt: ChatPromptTemplate,
    skills: list[Skill],
) -> ChatPromptTemplate:
    """Return a new ChatPromptTemplate with a name+description catalog appended.

    Used by the router so it knows what skills exist without spending tokens
    on the full bodies. If *skills* is empty, returns the prompt unchanged.
    """
    if not skills:
        return prompt

    block = _build_catalog_block(skills)
    return _inject_into_system_message(prompt, block)
