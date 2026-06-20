"""Deterministic ranking and capping of inline review findings.

This module is purely functional — no I/O, no LLM calls.  It is responsible for:

1. Deduplicating findings that point at the same location with equivalent text.
2. Partitioning by confidence threshold.
3. Ranking the survivors by severity (primary) then confidence (tiebreaker).
4. Hard-capping the inline comment count.

Usage::

    from ai_council_review.llm.selection import select_inline_findings

    result = select_inline_findings(
        postable_findings,
        max_comments=config.max_inline_comments,
        min_confidence=config.min_confidence,
    )
    # result.selected        → post as inline comments
    # result.omitted_low_confidence → below threshold
    # result.omitted_over_cap       → ranked out (still surfaced in body)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_council_review.models.review import Finding

# Numeric rank per severity string (lower = higher priority).
_SEVERITY_RANK: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def _severity_rank(finding: Finding) -> int:
    """Return the numeric priority rank for a finding's severity.

    Args:
        finding: The finding to rank.

    Returns:
        Integer rank; lower values are higher priority.  Unknown severity
        strings are placed after ``info``.
    """
    return _SEVERITY_RANK.get(finding.severity.value, 5)


def _dedup_key(finding: Finding) -> tuple[str, int | None, str]:
    """Build a deduplication key for a finding.

    Two findings are considered duplicates when they share the same file path,
    line number, and the first 200 characters of their body (case-folded and
    stripped).

    Args:
        finding: Finding to compute the key for.

    Returns:
        A hashable tuple ``(path, line, body_prefix)``.
    """
    body_prefix = finding.body[:200].lower().strip()
    return (finding.path, finding.line, body_prefix)


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """Remove duplicate findings, keeping the first occurrence of each key.

    Deduplication key: ``(path, line, body[:200].lower().strip())``.
    Input order is preserved for non-duplicate entries.

    Args:
        findings: Raw list of findings, possibly containing duplicates.

    Returns:
        Deduplicated list in the same relative order as the input.
    """
    seen: set[tuple[str, int | None, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = _dedup_key(finding)
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return unique


@dataclass
class SelectionResult:
    """The output of :func:`select_inline_findings`.

    Attributes:
        selected: Findings chosen for inline posting, ranked by priority.
        omitted_low_confidence: Findings excluded because their confidence
            score is below ``min_confidence``.
        omitted_over_cap: Findings that passed the confidence threshold but
            were cut off by ``max_comments``.
    """

    selected: list[Finding] = field(default_factory=list)
    omitted_low_confidence: list[Finding] = field(default_factory=list)
    omitted_over_cap: list[Finding] = field(default_factory=list)


def select_inline_findings(
    findings: list[Finding],
    *,
    max_comments: int,
    min_confidence: float,
) -> SelectionResult:
    """Rank and cap findings for inline posting.

    Processing pipeline:

    1. Deduplicate by ``(path, line, body[:200])``.
    2. Partition into ``kept`` (confidence >= ``min_confidence``) and
       ``omitted_low_confidence``.
    3. Sort ``kept`` by ``(severity_rank asc, confidence desc, path asc,
       line asc)`` so higher-priority findings sort first and the order is
       stable for equal keys.
    4. Slice: ``selected = kept[:max_comments]``; the remainder becomes
       ``omitted_over_cap``.

    Args:
        findings: Candidate findings (typically those whose line resolves to
            an added line in the patch — i.e. *postable* findings).
        max_comments: Hard cap on the number of inline comments returned in
            ``selected``.  Must be >= 0.
        min_confidence: Minimum confidence score required for a finding to be
            eligible for inline posting.  Must be in ``[0.0, 1.0]``.

    Returns:
        A :class:`SelectionResult` with ``selected``, ``omitted_low_confidence``,
        and ``omitted_over_cap`` lists.
    """
    deduped = dedupe_findings(findings)

    kept: list[Finding] = []
    omitted_low_confidence: list[Finding] = []
    for finding in deduped:
        if finding.confidence >= min_confidence:
            kept.append(finding)
        else:
            omitted_low_confidence.append(finding)

    # Sort: severity ascending (0 = critical), confidence descending (higher first),
    # then path and line ascending for a fully stable, deterministic order.
    kept.sort(
        key=lambda f: (
            _severity_rank(f),
            -f.confidence,  # negate so higher confidence sorts first
            f.path,
            f.line if f.line is not None else 0,
        )
    )

    selected = kept[:max_comments]
    omitted_over_cap = kept[max_comments:]

    return SelectionResult(
        selected=selected,
        omitted_low_confidence=omitted_low_confidence,
        omitted_over_cap=omitted_over_cap,
    )
