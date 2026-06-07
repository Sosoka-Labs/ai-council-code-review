"""Patch parser — parse unified diff and map line numbers to positions."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Hunk:
    """A single hunk from a unified diff patch."""

    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    lines: list[tuple[str, str]]
    """List of (type, text) tuples where type is ' ' (context), '+' (added), '-' (removed)."""


HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_patch(patch: str) -> list[Hunk]:
    """Parse a unified diff patch into hunks.

    Args:
        patch: The unified diff patch text.

    Returns:
        List of Hunk objects.
    """
    hunks: list[Hunk] = []
    current_hunk: Hunk | None = None

    for line in patch.split("\n"):
        match = HUNK_HEADER_RE.match(line)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            old_start = int(match.group(1))
            old_lines = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_lines = int(match.group(4)) if match.group(4) else 1
            current_hunk = Hunk(
                old_start=old_start,
                old_lines=old_lines,
                new_start=new_start,
                new_lines=new_lines,
                lines=[],
            )
        elif current_hunk is not None:
            if line.startswith("+"):
                current_hunk.lines.append(("+", line[1:]))
            elif line.startswith("-"):
                current_hunk.lines.append(("-", line[1:]))
            elif line.startswith(" "):
                current_hunk.lines.append((" ", line[1:]))
            elif line.startswith("\\"):
                # "\ No newline at end of file" — skip
                pass

    if current_hunk:
        hunks.append(current_hunk)

    return hunks


def get_added_line_positions(patch: str) -> list[tuple[int, int, str]]:
    """Find positions of all added lines in a patch.

    The `position` is the 1-based index within the file's patch, counting
    from the first line after the first @@ hunk header. This is the value
    GitHub expects for review comment `position`.

    Args:
        patch: The unified diff patch text.

    Returns:
        List of (position, new_line_number, text) tuples.
    """
    positions: list[tuple[int, int, str]] = []
    position = 0
    new_line = 0
    in_hunk = False

    for line in patch.split("\n"):
        if line.startswith("@@"):
            match = HUNK_HEADER_RE.match(line)
            if match:
                new_line = int(match.group(3))
            in_hunk = True
            # Do not increment position for @@ lines
        elif in_hunk:
            if line.startswith("+"):
                position += 1
                positions.append((position, new_line, line[1:]))
                new_line += 1
            elif line.startswith("-"):
                position += 1
                # Removed lines don't increment new_line
            elif line.startswith(" "):
                position += 1
                new_line += 1
            elif line.startswith("\\"):
                # "No newline at end of file" marker
                pass

    return positions


def get_position_for_line(patch: str, target_line: int) -> int | None:
    """Get the diff position for a specific new file line number.

    Args:
        patch: The unified diff patch text.
        target_line: The line number in the new file.

    Returns:
        The diff position, or None if the line is not in the patch.
    """
    for position, new_line, _ in get_added_line_positions(patch):
        if new_line == target_line:
            return position
    return None


def get_line_for_position(patch: str, target_position: int) -> int | None:
    """Get the new file line number for a specific diff position.

    Args:
        patch: The unified diff patch text.
        target_position: The diff position (1-based from first @@).

    Returns:
        The new file line number, or None if not found.
    """
    for position, new_line, _ in get_added_line_positions(patch):
        if position == target_position:
            return new_line
    return None
