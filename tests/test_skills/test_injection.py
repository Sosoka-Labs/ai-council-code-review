"""Tests for ai_council_review.skills.injection."""

from __future__ import annotations

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.chat import SystemMessagePromptTemplate

from ai_council_review.skills.injection import apply_skill_catalog, apply_skills
from ai_council_review.skills.models import Skill

_SYSTEM = "You are a helpful reviewer."
_HUMAN = "Review this: {{ code }}"

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "skills"


def _make_prompt(system: str = _SYSTEM, human: str = _HUMAN) -> ChatPromptTemplate:
    """Return a minimal Jinja2 ChatPromptTemplate."""
    return ChatPromptTemplate.from_messages(
        [("system", system), ("human", human)],
        template_format="jinja2",
    )


def _make_skill(
    name: str = "test-skill",
    description: str = "A test skill.",
    body: str = "## Test skill body\n",
) -> Skill:
    """Return a Skill for testing without touching the filesystem."""
    return Skill(
        name=name,
        description=description,
        body=body,
        path=Path(f"/fake/{name}/SKILL.md"),
        raw_frontmatter={"name": name, "description": description},
    )


def _get_system_text(prompt: ChatPromptTemplate) -> str:
    """Extract the system message template text from a ChatPromptTemplate."""
    for msg in prompt.messages:
        if isinstance(msg, SystemMessagePromptTemplate):
            return msg.prompt.template
    raise AssertionError("No system message found in prompt")


class TestApplySkills:
    """apply_skills() appends skill bodies to the system message."""

    def test_empty_skills_returns_same_prompt(self) -> None:
        """apply_skills with an empty list returns the prompt object unchanged."""
        prompt = _make_prompt()
        result = apply_skills(prompt, [])

        assert result is prompt

    def test_single_skill_appended_to_system_message(self) -> None:
        """A skill body appears in the system message after injection."""
        prompt = _make_prompt()
        skill = _make_skill(body="## My Guidance\n\nDo the thing.\n")

        result = apply_skills(prompt, [skill])

        system_text = _get_system_text(result)
        assert "## My Guidance" in system_text
        assert "Do the thing." in system_text

    def test_skills_block_wrapped_in_markers(self) -> None:
        """The injected block is wrapped in the stable HTML comment markers."""
        prompt = _make_prompt()
        skill = _make_skill()

        result = apply_skills(prompt, [skill])
        system_text = _get_system_text(result)

        assert "<!-- ai-council:skills:start -->" in system_text
        assert "<!-- ai-council:skills:end -->" in system_text

    def test_both_skills_present_for_two_skills(self) -> None:
        """Both skill bodies appear in the system message when two skills are injected."""
        prompt = _make_prompt()
        s1 = _make_skill("alpha-skill", body="Alpha body.\n")
        s2 = _make_skill("beta-skill", body="Beta body.\n")

        result = apply_skills(prompt, [s1, s2])
        system_text = _get_system_text(result)

        assert "Alpha body." in system_text
        assert "Beta body." in system_text

    def test_skill_order_matches_input_order(self) -> None:
        """Skills appear in the output in the same order they were passed."""
        prompt = _make_prompt()
        s1 = _make_skill("first-skill", body="First.\n")
        s2 = _make_skill("second-skill", body="Second.\n")

        result = apply_skills(prompt, [s1, s2])
        system_text = _get_system_text(result)

        assert system_text.index("First.") < system_text.index("Second.")

    def test_original_system_message_is_preserved(self) -> None:
        """The original system message content remains intact after injection."""
        prompt = _make_prompt(system="You are a senior reviewer.")
        skill = _make_skill()

        result = apply_skills(prompt, [skill])
        system_text = _get_system_text(result)

        assert "You are a senior reviewer." in system_text

    def test_returns_new_prompt_object(self) -> None:
        """apply_skills returns a new ChatPromptTemplate, not the same object."""
        prompt = _make_prompt()
        skill = _make_skill()

        result = apply_skills(prompt, [skill])

        assert result is not prompt

    def test_jinja2_tokens_in_skill_body_do_not_cause_render_error(self) -> None:
        """Skill bodies containing {{ }} or {%  %} do not break template rendering."""
        prompt = _make_prompt()
        skill = _make_skill(body="Use {{ some_var }} for config values.\n")

        result = apply_skills(prompt, [skill])

        # This must not raise a Jinja2 error when formatted with normal vars
        rendered = result.format_messages(code="def foo(): pass")
        assert rendered  # At least one message came back

    def test_endraw_in_skill_body_does_not_leak_template_variables(self) -> None:
        """A malicious skill body containing {%- endraw -%} cannot bypass escaping.

        Regression: the previous raw-block strategy was bypassable because Jinja2
        terminates raw at the first endraw token. A body containing endraw could
        re-enable template evaluation of subsequent text. With token-substitution
        escaping the bypass is impossible.
        """
        prompt = _make_prompt()
        # Body tries to break out of raw and reference a template variable.
        body = "before {%- endraw -%} {{ code }} after"
        skill = _make_skill(body=body)

        result = apply_skills(prompt, [skill])
        rendered = result.format_messages(code="SHOULD_NOT_LEAK")
        system_text = rendered[0].content
        assert isinstance(system_text, str)
        # The injected {{ code }} must NOT have been evaluated as a template var.
        assert "SHOULD_NOT_LEAK" not in system_text

    def test_skill_heading_includes_name_and_description(self) -> None:
        """Each skill section heading contains the skill name and description."""
        prompt = _make_prompt()
        skill = _make_skill(name="my-skill", description="Does something useful.")

        result = apply_skills(prompt, [skill])
        system_text = _get_system_text(result)

        assert "my-skill" in system_text
        assert "Does something useful." in system_text


class TestApplySkillCatalog:
    """apply_skill_catalog() appends name+description catalog to the system message."""

    def test_empty_skills_returns_same_prompt(self) -> None:
        """apply_skill_catalog with an empty list returns the prompt object unchanged."""
        prompt = _make_prompt()
        result = apply_skill_catalog(prompt, [])

        assert result is prompt

    def test_catalog_contains_name_and_description(self) -> None:
        """The catalog block contains the skill name and description."""
        prompt = _make_prompt()
        skill = _make_skill(name="oauth-flows", description="OAuth review guidance.")

        result = apply_skill_catalog(prompt, [skill])
        system_text = _get_system_text(result)

        assert "oauth-flows" in system_text
        assert "OAuth review guidance." in system_text

    def test_catalog_does_not_contain_body(self) -> None:
        """The catalog block must not include the full skill body."""
        prompt = _make_prompt()
        skill = _make_skill(body="This is the body content that should not appear.\n")

        result = apply_skill_catalog(prompt, [skill])
        system_text = _get_system_text(result)

        assert "This is the body content that should not appear." not in system_text

    def test_catalog_wrapped_in_markers(self) -> None:
        """The catalog block is wrapped in its own stable HTML comment markers."""
        prompt = _make_prompt()
        skill = _make_skill()

        result = apply_skill_catalog(prompt, [skill])
        system_text = _get_system_text(result)

        assert "<!-- ai-council:skill-catalog:start -->" in system_text
        assert "<!-- ai-council:skill-catalog:end -->" in system_text

    def test_catalog_order_matches_input_order(self) -> None:
        """Skills appear in catalog order matching the input list order."""
        prompt = _make_prompt()
        s1 = _make_skill("aaa-skill", description="First skill.")
        s2 = _make_skill("zzz-skill", description="Second skill.")

        result = apply_skill_catalog(prompt, [s1, s2])
        system_text = _get_system_text(result)

        assert system_text.index("First skill.") < system_text.index("Second skill.")
