"""Tests for _build_agent_variables / _build_router_variables safety limits.

Covers:
  - C-1: diff truncation at config.max_diff_size characters
  - H-6: pr_title capped at 500 chars, pr_body (router only) capped at 2000 chars
"""

from __future__ import annotations

from ai_council_review.config import CouncilConfig
from ai_council_review.llm.agents.generalist import _build_agent_variables as generalist_vars
from ai_council_review.llm.agents.router import _build_router_variables
from ai_council_review.llm.agents.specialist import _build_agent_variables as specialist_vars
from ai_council_review.models import FileInfo, PRMetadata, ReviewState

# All three specialist shims delegate to the same implementation.
security_vars = specialist_vars
quality_vars = specialist_vars
arch_vars = specialist_vars


def _make_state(
    title: str = "Normal title",
    body: str = "Normal body",
    patch: str = "small patch",
) -> ReviewState:
    """Build a ReviewState with configurable title, body, and patch content."""
    pr = PRMetadata(
        number=1,
        title=title,
        body=body,
        state="open",
        author="alice",
        author_association="CONTRIBUTOR",
        base_ref="main",
        base_sha="abc",
        head_ref="feat",
        head_sha="def",
        html_url="https://github.com/owner/repo/pull/1",
    )
    files = [FileInfo(filename="src/app.py", status="modified", patch=patch)]
    return ReviewState(pr_metadata=pr, changed_files=files)


class TestDiffTruncation:
    """C-1: diff is truncated to config.max_diff_size characters."""

    def _config(self, max_chars: int = 100) -> CouncilConfig:
        return CouncilConfig(max_diff_size=max_chars)

    def test_diff_not_truncated_when_within_limit(self) -> None:
        """Short diffs pass through unchanged."""
        patch = "x" * 50
        state = _make_state(patch=patch)
        result = security_vars(state, self._config(max_chars=100))
        assert result["diff"] == f"=== src/app.py ===\n{patch}"

    def test_diff_truncated_at_max_diff_size(self) -> None:
        """Diff longer than max_diff_size is cut and a marker is appended."""
        patch = "x" * 200
        state = _make_state(patch=patch)
        config = self._config(max_chars=50)
        result = security_vars(state, config)

        assert len(result["diff"]) > 50  # marker adds chars
        assert result["diff"].startswith("=== src/app.py ===\n")
        assert "[... diff truncated at 50 chars ...]" in result["diff"]
        # The diff body itself is cut at 50 chars before the marker
        truncated_body = result["diff"][: result["diff"].index("\n\n[... diff")]
        assert len(truncated_body) == 50

    def test_diff_truncation_consistent_across_specialist_agents(self) -> None:
        """All four specialist agents apply the same truncation logic."""
        patch = "y" * 300
        state = _make_state(patch=patch)
        config = self._config(max_chars=100)

        sec = security_vars(state, config)
        qual = quality_vars(state, config)
        arch = arch_vars(state, config)
        gen = generalist_vars(state, config)

        for result in (sec, qual, arch, gen):
            assert "[... diff truncated at 100 chars ...]" in result["diff"]

    def test_diff_truncation_in_router(self) -> None:
        """Router's _build_router_variables also truncates the diff."""
        patch = "z" * 300
        state = _make_state(patch=patch)
        config = self._config(max_chars=80)
        result = _build_router_variables(state, config)

        assert "[... diff truncated at 80 chars ...]" in result["diff"]

    def test_diff_not_truncated_at_exact_limit(self) -> None:
        """A diff exactly at the limit is not truncated."""
        prefix = "=== src/app.py ===\n"
        available = 100 - len(prefix)
        patch = "a" * available
        state = _make_state(patch=patch)
        result = security_vars(state, self._config(max_chars=100))

        assert "[... diff truncated" not in result["diff"]
        assert len(result["diff"]) == 100


class TestPrTitleTruncation:
    """H-6: pr_title is capped at 500 characters."""

    def test_short_title_passes_through(self) -> None:
        """Titles under 500 chars are unchanged."""
        state = _make_state(title="Short title")
        result = security_vars(state, CouncilConfig())
        assert result["pr_title"] == "Short title"

    def test_title_truncated_at_500_chars(self) -> None:
        """Titles over 500 chars are cut to exactly 500 chars."""
        long_title = "T" * 600
        state = _make_state(title=long_title)
        result = security_vars(state, CouncilConfig())
        assert len(result["pr_title"]) == 500
        assert result["pr_title"] == "T" * 500

    def test_title_truncation_in_router(self) -> None:
        """Router also caps pr_title at 500 chars."""
        long_title = "R" * 700
        state = _make_state(title=long_title)
        result = _build_router_variables(state, CouncilConfig())
        assert len(result["pr_title"]) == 500


class TestPrBodyTruncation:
    """H-6: pr_body (router only) is capped at 2000 characters."""

    def test_short_body_passes_through(self) -> None:
        """Bodies under 2000 chars are unchanged."""
        state = _make_state(body="Short body")
        result = _build_router_variables(state, CouncilConfig())
        assert result["pr_body"] == "Short body"

    def test_body_truncated_at_2000_chars(self) -> None:
        """Bodies over 2000 chars are cut to exactly 2000 chars."""
        long_body = "B" * 3000
        state = _make_state(body=long_body)
        result = _build_router_variables(state, CouncilConfig())
        assert len(result["pr_body"]) == 2000
        assert result["pr_body"] == "B" * 2000
