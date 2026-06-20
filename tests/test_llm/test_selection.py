"""Tests for ai_council_review.llm.selection — pure ranking and capping logic."""

from __future__ import annotations

from ai_council_review.llm.selection import (
    SelectionResult,
    dedupe_findings,
    select_inline_findings,
)
from ai_council_review.models import Finding, Severity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    *,
    path: str = "src/main.py",
    line: int | None = 10,
    severity: Severity = Severity.MEDIUM,
    confidence: float = 0.8,
    body: str = "A finding.",
    agent: str | None = "quality",
) -> Finding:
    """Build a minimal Finding for test use."""
    return Finding(
        path=path,
        severity=severity,
        category="test",
        body=body,
        confidence=confidence,
        line=line,
        agent=agent,
    )


# ---------------------------------------------------------------------------
# dedupe_findings
# ---------------------------------------------------------------------------


class TestDedupeFindings:
    """Unit tests for dedupe_findings."""

    def test_empty_input_returns_empty(self) -> None:
        """Empty input list returns an empty list."""
        assert dedupe_findings([]) == []

    def test_single_finding_unchanged(self) -> None:
        """A single finding is returned as-is."""
        f = _finding()
        result = dedupe_findings([f])
        assert result == [f]

    def test_identical_findings_deduped(self) -> None:
        """Two findings with the same key produce one result."""
        f1 = _finding(path="a.py", line=5, body="SQL injection")
        f2 = _finding(path="a.py", line=5, body="SQL injection")
        result = dedupe_findings([f1, f2])
        assert len(result) == 1
        assert result[0] is f1  # first wins

    def test_different_line_not_deduped(self) -> None:
        """Same body but different lines are distinct findings."""
        f1 = _finding(line=1, body="Same body")
        f2 = _finding(line=2, body="Same body")
        result = dedupe_findings([f1, f2])
        assert len(result) == 2

    def test_different_path_not_deduped(self) -> None:
        """Same body and line but different paths are distinct."""
        f1 = _finding(path="a.py", body="Same body", line=1)
        f2 = _finding(path="b.py", body="Same body", line=1)
        result = dedupe_findings([f1, f2])
        assert len(result) == 2

    def test_case_insensitive_body_deduplication(self) -> None:
        """Body comparison is case-insensitive and strips whitespace."""
        f1 = _finding(body="  SQL Injection  ")
        f2 = _finding(body="sql injection")
        result = dedupe_findings([f1, f2])
        assert len(result) == 1
        assert result[0] is f1

    def test_body_prefix_used_for_key(self) -> None:
        """Only the first 200 chars of the body are compared for dedup."""
        long_common = "x" * 200
        f1 = _finding(body=long_common + " extra in f1")
        f2 = _finding(body=long_common + " different suffix")
        # First 200 chars are identical → treated as duplicate
        result = dedupe_findings([f1, f2])
        assert len(result) == 1

    def test_original_order_preserved(self) -> None:
        """Non-duplicate findings retain their original relative order."""
        findings = [_finding(line=i, body=f"Finding {i}") for i in range(5)]
        result = dedupe_findings(findings)
        assert result == findings

    def test_none_line_findings_deduped_correctly(self) -> None:
        """Findings with line=None are keyed on (path, None, body_prefix)."""
        f1 = _finding(line=None, body="no line")
        f2 = _finding(line=None, body="no line")
        result = dedupe_findings([f1, f2])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# select_inline_findings — threshold partitioning
# ---------------------------------------------------------------------------


class TestSelectInlineFindingsThreshold:
    """Tests for confidence-threshold partitioning."""

    def test_empty_input(self) -> None:
        """Empty input produces an empty SelectionResult."""
        result = select_inline_findings([], max_comments=10, min_confidence=0.5)
        assert isinstance(result, SelectionResult)
        assert result.selected == []
        assert result.omitted_low_confidence == []
        assert result.omitted_over_cap == []

    def test_all_below_threshold_produces_no_selected(self) -> None:
        """When all findings are below the threshold, selected is empty."""
        findings = [_finding(confidence=0.4), _finding(confidence=0.3, line=2)]
        result = select_inline_findings(findings, max_comments=10, min_confidence=0.5)
        assert result.selected == []
        assert len(result.omitted_low_confidence) == 2
        assert result.omitted_over_cap == []

    def test_above_threshold_included(self) -> None:
        """Findings at or above the threshold are included."""
        f_high = _finding(confidence=0.9, line=1)
        f_exact = _finding(confidence=0.5, line=2)
        f_low = _finding(confidence=0.4, line=3)
        result = select_inline_findings(
            [f_high, f_exact, f_low], max_comments=10, min_confidence=0.5
        )
        assert len(result.selected) == 2
        assert len(result.omitted_low_confidence) == 1
        assert result.omitted_low_confidence[0] is f_low

    def test_zero_threshold_passes_all(self) -> None:
        """A min_confidence of 0.0 passes every finding."""
        findings = [_finding(confidence=c, line=i) for i, c in enumerate([0.0, 0.1, 0.99])]
        result = select_inline_findings(findings, max_comments=10, min_confidence=0.0)
        assert len(result.selected) == 3
        assert result.omitted_low_confidence == []

    def test_threshold_of_one_only_keeps_perfect_confidence(self) -> None:
        """A min_confidence of 1.0 keeps only findings with confidence == 1.0."""
        findings = [
            _finding(confidence=1.0, line=1),
            _finding(confidence=0.99, line=2),
        ]
        result = select_inline_findings(findings, max_comments=10, min_confidence=1.0)
        assert len(result.selected) == 1
        assert result.selected[0].line == 1


# ---------------------------------------------------------------------------
# select_inline_findings — ranking
# ---------------------------------------------------------------------------


class TestSelectInlineFindingsRanking:
    """Tests for severity-first, confidence-tiebreaker ordering."""

    def test_severity_is_primary_sort_key(self) -> None:
        """Critical beats high beats medium regardless of confidence."""
        f_medium_high_conf = _finding(
            severity=Severity.MEDIUM, confidence=1.0, line=1, body="medium 1.0"
        )
        f_high_low_conf = _finding(severity=Severity.HIGH, confidence=0.1, line=2, body="high 0.1")
        f_critical_low_conf = _finding(
            severity=Severity.CRITICAL, confidence=0.1, line=3, body="critical 0.1"
        )
        result = select_inline_findings(
            [f_medium_high_conf, f_high_low_conf, f_critical_low_conf],
            max_comments=3,
            min_confidence=0.0,
        )
        lines = [f.line for f in result.selected]
        assert lines == [3, 2, 1], "Expected critical → high → medium, got lines: " + str(lines)

    def test_confidence_breaks_severity_ties(self) -> None:
        """Among same-severity findings, higher confidence ranks first."""
        f_low_conf = _finding(severity=Severity.HIGH, confidence=0.5, line=1, body="low c")
        f_high_conf = _finding(severity=Severity.HIGH, confidence=0.9, line=2, body="high c")
        result = select_inline_findings(
            [f_low_conf, f_high_conf], max_comments=2, min_confidence=0.0
        )
        assert result.selected[0].line == 2  # high confidence first
        assert result.selected[1].line == 1

    def test_all_severity_levels_ordered(self) -> None:
        """The full severity ladder — critical, high, medium, low, info."""
        severities = [
            Severity.INFO,
            Severity.LOW,
            Severity.MEDIUM,
            Severity.HIGH,
            Severity.CRITICAL,
        ]
        findings = [
            _finding(severity=s, line=i, body=f"body {i}") for i, s in enumerate(severities)
        ]

        result = select_inline_findings(findings, max_comments=10, min_confidence=0.0)
        result_severities = [f.severity for f in result.selected]
        expected = [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
            Severity.INFO,
        ]
        assert result_severities == expected

    def test_stable_order_for_equal_severity_and_confidence(self) -> None:
        """When severity and confidence are equal, sort by path then line."""
        findings = [
            _finding(path="z.py", line=1, severity=Severity.LOW, confidence=0.8, body="z1"),
            _finding(path="a.py", line=2, severity=Severity.LOW, confidence=0.8, body="a2"),
            _finding(path="a.py", line=1, severity=Severity.LOW, confidence=0.8, body="a1"),
        ]
        result = select_inline_findings(findings, max_comments=10, min_confidence=0.0)
        keys = [(f.path, f.line) for f in result.selected]
        assert keys == [("a.py", 1), ("a.py", 2), ("z.py", 1)]


# ---------------------------------------------------------------------------
# select_inline_findings — cap boundaries
# ---------------------------------------------------------------------------


class TestSelectInlineFindingsCapBoundary:
    """Tests for exact-N and N+1 cap behavior."""

    def test_exactly_n_findings_all_selected(self) -> None:
        """When count equals max_comments, all findings are selected."""
        findings = [_finding(line=i, body=f"body {i}") for i in range(5)]
        result = select_inline_findings(findings, max_comments=5, min_confidence=0.0)
        assert len(result.selected) == 5
        assert result.omitted_over_cap == []

    def test_n_plus_one_finding_one_goes_to_cap(self) -> None:
        """When count is max_comments + 1, exactly one is in omitted_over_cap."""
        findings = [_finding(line=i, body=f"body {i}") for i in range(6)]
        result = select_inline_findings(findings, max_comments=5, min_confidence=0.0)
        assert len(result.selected) == 5
        assert len(result.omitted_over_cap) == 1

    def test_zero_cap_all_over_cap(self) -> None:
        """A max_comments of 0 puts everything in omitted_over_cap."""
        findings = [_finding(line=i, body=f"body {i}") for i in range(3)]
        result = select_inline_findings(findings, max_comments=0, min_confidence=0.0)
        assert result.selected == []
        assert len(result.omitted_over_cap) == 3

    def test_large_cap_no_overflow(self) -> None:
        """A cap larger than the finding count produces no overflow."""
        findings = [_finding(line=i, body=f"body {i}") for i in range(3)]
        result = select_inline_findings(findings, max_comments=100, min_confidence=0.0)
        assert len(result.selected) == 3
        assert result.omitted_over_cap == []

    def test_cap_applied_after_threshold(self) -> None:
        """The cap counts findings that PASSED the threshold, not all findings."""
        # 5 findings; 2 below threshold, 3 above. Cap = 2 → 2 selected, 1 over cap.
        findings = [
            _finding(confidence=0.2, line=1, body="below 1"),
            _finding(confidence=0.2, line=2, body="below 2"),
            _finding(confidence=0.9, line=3, body="above 1"),
            _finding(confidence=0.9, line=4, body="above 2"),
            _finding(confidence=0.9, line=5, body="above 3"),
        ]
        result = select_inline_findings(findings, max_comments=2, min_confidence=0.5)
        assert len(result.omitted_low_confidence) == 2
        assert len(result.selected) == 2
        assert len(result.omitted_over_cap) == 1

    def test_dedup_happens_before_cap(self) -> None:
        """Duplicate removal occurs before the cap is applied."""
        # 3 unique findings, 2 duplicates. After dedup: 3. Cap = 2.
        base = _finding(body="same body", line=1)
        dup1 = _finding(body="same body", line=1)
        dup2 = _finding(body="same body", line=1)
        unique1 = _finding(body="unique1", line=2)
        unique2 = _finding(body="unique2", line=3)

        result = select_inline_findings(
            [base, dup1, dup2, unique1, unique2],
            max_comments=2,
            min_confidence=0.0,
        )
        assert len(result.selected) == 2
        assert len(result.omitted_over_cap) == 1
