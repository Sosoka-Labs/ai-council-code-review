"""Tests for agent output parsing utilities."""

from __future__ import annotations

from ai_council_review.llm.agents.parsing import _extract_first_json_array, parse_findings


class TestExtractFirstJsonArray:
    """Tests for the brace-counting JSON array extractor."""

    def test_returns_plain_array(self) -> None:
        text = '[{"a": 1}, {"b": 2}]'
        assert _extract_first_json_array(text) == text

    def test_extracts_array_with_surrounding_prose(self) -> None:
        text = 'Here are the findings:\n[{"path": "foo.py", "line": 1}]\nDone.'
        result = _extract_first_json_array(text)
        assert result == '[{"path": "foo.py", "line": 1}]'

    def test_extracts_only_first_array_when_multiple_present(self) -> None:
        text = '[1, 2, 3] and then [4, 5, 6]'
        result = _extract_first_json_array(text)
        assert result == "[1, 2, 3]"

    def test_returns_none_when_no_opening_bracket(self) -> None:
        assert _extract_first_json_array("no array here") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert _extract_first_json_array("") is None

    def test_handles_nested_arrays(self) -> None:
        text = '[[1, 2], [3, 4]]'
        assert _extract_first_json_array(text) == "[[1, 2], [3, 4]]"

    def test_bracket_inside_string_not_counted_as_depth(self) -> None:
        # The "]" inside the string value must not close the outer array.
        text = '[{"key": "value with ] bracket"}]'
        result = _extract_first_json_array(text)
        assert result == '[{"key": "value with ] bracket"}]'

    def test_handles_escaped_quote_inside_string(self) -> None:
        text = r'[{"key": "say \"hello\" to [me]"}]'
        result = _extract_first_json_array(text)
        assert result == r'[{"key": "say \"hello\" to [me]"}]'


class TestParseFindings:
    """Integration tests for parse_findings end-to-end."""

    def test_parses_bare_json_array(self) -> None:
        text = (
            '[{"path": "src/foo.py", "line": 10, "severity": "high",'
            ' "category": "security", "body": "Use parameterized queries.",'
            ' "confidence": 0.9}]'
        )
        findings = parse_findings(text)
        assert len(findings) == 1
        assert findings[0].path == "src/foo.py"
        assert findings[0].severity.value == "high"

    def test_parses_array_wrapped_in_prose(self) -> None:
        text = (
            "Here are my findings:\n"
            '[{"path": "app.py", "line": 5, "severity": "medium",'
            ' "category": "quality", "body": "Missing type hint.", "confidence": 0.8}]'
            "\nEnd of review."
        )
        findings = parse_findings(text)
        assert len(findings) == 1
        assert findings[0].path == "app.py"

    def test_tags_findings_with_agent_name(self) -> None:
        text = '[{"path": "x.py", "severity": "low", "category": "quality", "body": "ok"}]'
        findings = parse_findings(text, agent_name="security")
        assert findings[0].agent == "security"

    def test_returns_empty_list_for_empty_input(self) -> None:
        assert parse_findings("") == []
        assert parse_findings("   ") == []

    def test_returns_empty_list_for_non_json(self) -> None:
        assert parse_findings("no JSON here at all") == []

    def test_strips_markdown_code_block(self) -> None:
        text = (
            "```json\n"
            '[{"path": "b.py", "severity": "info", "category": "quality",'
            ' "body": "ok"}]\n'
            "```"
        )
        findings = parse_findings(text)
        assert len(findings) == 1
