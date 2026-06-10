"""Integration-style tests for ai_council_review.__main__."""

from __future__ import annotations

import sys
import threading
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from ai_council_review.models.state import ReviewState


def _ensure_main_importable() -> None:
    """Inject stub modules for heavy transitive imports so __main__ can load.

    ``ai_council_review.__main__`` imports ``build_graph`` from
    ``ai_council_review.llm.graph``, which pulls in langchain agents that have
    a broken ``ToolCallTransformer`` import in the installed version.  We stub
    the whole ``llm`` sub-package at the sys.modules level so the import
    succeeds without hitting real LLM code.
    """
    stubs = [
        "ai_council_review.llm",
        "ai_council_review.llm.graph",
    ]
    for name in stubs:
        if name not in sys.modules:
            mod = ModuleType(name)
            sys.modules[name] = mod

    # Ensure build_graph is resolvable from the graph stub
    sys.modules["ai_council_review.llm.graph"].build_graph = MagicMock()  # type: ignore[attr-defined]


_ensure_main_importable()

# Now the import is safe.
import ai_council_review.__main__ as _main_module  # noqa: E402

# Minimal sys.argv that satisfies parse_args() required arguments (no --dry-run
# so the real graph execution path is exercised).
_GRAPH_ARGV = [
    "ai_council_review",
    "--pr-number",
    "1",
    "--repo",
    "owner/repo",
]


def _make_valid_result() -> dict:
    """Return a minimal dict that ReviewState(**result) will accept."""
    return ReviewState().model_dump()


class TestMainSuccess:
    """main() returns 0 when the graph completes successfully."""

    def test_main_returns_zero_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return 0 when graph.invoke succeeds and returns a valid state."""
        valid_result = _make_valid_result()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = valid_result

        monkeypatch.setattr(sys, "argv", _GRAPH_ARGV)
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-key")
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

        with (
            patch("ai_council_review.__main__.build_graph", return_value=mock_graph),
            patch("ai_council_review.__main__.load_config") as mock_load,
            patch("ai_council_review.__main__.validate_config"),
            patch("ai_council_review.__main__.PRIngestor") as mock_ingestor_cls,
        ):
            mock_load.return_value = MagicMock(
                total_timeout_seconds=30,
                debug=False,
                agents={},
                providers={},
            )
            mock_ingestor = MagicMock()
            mock_ingestor.parse_pr_metadata.return_value = MagicMock(head_sha="abc", base_sha="def")
            mock_ingestor.should_skip.return_value = (False, None)
            mock_ingestor_cls.return_value = mock_ingestor

            exit_code = _main_module.main()

        assert exit_code == 0


class TestMainGraphException:
    """main() returns non-zero when the graph raises an exception."""

    def test_main_returns_nonzero_on_graph_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return non-zero exit code when graph.invoke raises an Exception."""
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = RuntimeError("graph exploded")

        monkeypatch.setattr(sys, "argv", _GRAPH_ARGV)
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-key")
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

        with (
            patch("ai_council_review.__main__.build_graph", return_value=mock_graph),
            patch("ai_council_review.__main__.load_config") as mock_load,
            patch("ai_council_review.__main__.validate_config"),
            patch("ai_council_review.__main__.PRIngestor") as mock_ingestor_cls,
        ):
            mock_load.return_value = MagicMock(
                total_timeout_seconds=30,
                debug=False,
                agents={},
                providers={},
            )
            mock_ingestor = MagicMock()
            mock_ingestor.parse_pr_metadata.return_value = MagicMock(head_sha="abc", base_sha="def")
            mock_ingestor.should_skip.return_value = (False, None)
            mock_ingestor_cls.return_value = mock_ingestor

            exit_code = _main_module.main()

        assert exit_code != 0


class TestMainTimeout:
    """main() returns non-zero when the graph thread times out."""

    def test_main_returns_nonzero_on_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return 1 when the graph thread is still alive after the timeout."""
        monkeypatch.setattr(sys, "argv", _GRAPH_ARGV)
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-key")
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

        # Simulate a thread that never finishes: is_alive() always returns True
        never_finishing_thread = MagicMock(spec=threading.Thread)
        never_finishing_thread.is_alive.return_value = True

        mock_graph = MagicMock()

        with (
            patch("ai_council_review.__main__.build_graph", return_value=mock_graph),
            patch("ai_council_review.__main__.load_config") as mock_load,
            patch("ai_council_review.__main__.validate_config"),
            patch("ai_council_review.__main__.PRIngestor") as mock_ingestor_cls,
            patch(
                "ai_council_review.__main__.threading.Thread",
                return_value=never_finishing_thread,
            ),
        ):
            mock_load.return_value = MagicMock(
                total_timeout_seconds=1,
                debug=False,
                agents={},
                providers={},
            )
            mock_ingestor = MagicMock()
            mock_ingestor.parse_pr_metadata.return_value = MagicMock(head_sha="abc", base_sha="def")
            mock_ingestor.should_skip.return_value = (False, None)
            mock_ingestor_cls.return_value = mock_ingestor

            exit_code = _main_module.main()

        assert exit_code == 1
