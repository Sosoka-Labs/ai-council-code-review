"""Tests for ai_council_review.utils.patch_parser."""

from __future__ import annotations

from ai_council_review.utils.patch_parser import (
    get_added_line_positions,
    get_line_for_position,
    get_position_for_line,
    parse_patch,
)

SAMPLE_PATCH = """\
@@ -1,5 +1,5 @@
 def hello():
-    print("old")
+    print("new")
     return 42

@@ -10,7 +10,8 @@
 def world():
     x = 1
-    y = 2
+    y = 3
+    z = 4
     return x + y
"""


class TestParsePatch:
    """Tests for parse_patch."""

    def test_parse_hunks(self) -> None:
        """Test parsing a patch into hunks."""
        hunks = parse_patch(SAMPLE_PATCH)
        assert len(hunks) == 2

        hunk1 = hunks[0]
        assert hunk1.old_start == 1
        assert hunk1.new_start == 1
        assert hunk1.lines == [
            (" ", "def hello():"),
            ("-", '    print("old")'),
            ("+", '    print("new")'),
            (" ", "    return 42"),
        ]

        hunk2 = hunks[1]
        assert hunk2.old_start == 10
        assert hunk2.new_start == 10

    def test_empty_patch(self) -> None:
        """Test parsing an empty patch."""
        hunks = parse_patch("")
        assert hunks == []

    def test_no_newline_marker(self) -> None:
        """Test that \\ No newline marker is ignored."""
        patch = "@@ -1,1 +1,1 @@\n-old\n+new\n\\ No newline at end of file"
        hunks = parse_patch(patch)
        assert len(hunks) == 1
        assert len(hunks[0].lines) == 2


class TestGetAddedLinePositions:
    """Tests for get_added_line_positions."""

    def test_added_positions(self) -> None:
        """Test finding positions of added lines.

        GitHub positions are 1-based from the first line after the first @@.
        @@ lines themselves are not counted. Positions continue across hunks.
        """
        positions = get_added_line_positions(SAMPLE_PATCH)
        assert len(positions) == 3

        # First hunk: context=1, removed=2, added=3
        # new_line starts at 1, context increments to 2, removed stays 2, added at 2
        assert positions[0] == (3, 2, '    print("new")')

        # Second hunk: context=5, context=6, removed=7, added=8, added=9
        # new_line starts at 10, context increments to 11, context increments to 12,
        # removed stays 12, added at 12, added at 13
        assert positions[1] == (8, 12, "    y = 3")
        assert positions[2] == (9, 13, "    z = 4")

    def test_empty_patch(self) -> None:
        """Test with empty patch."""
        positions = get_added_line_positions("")
        assert positions == []


class TestGetPositionForLine:
    """Tests for get_position_for_line."""

    def test_find_position(self) -> None:
        """Test getting position for a specific line."""
        pos = get_position_for_line(SAMPLE_PATCH, 2)
        assert pos == 3

        pos = get_position_for_line(SAMPLE_PATCH, 12)
        assert pos == 8

    def test_missing_line(self) -> None:
        """Test line not in patch."""
        pos = get_position_for_line(SAMPLE_PATCH, 999)
        assert pos is None


class TestGetLineForPosition:
    """Tests for get_line_for_position."""

    def test_find_line(self) -> None:
        """Test getting line number for a position."""
        line = get_line_for_position(SAMPLE_PATCH, 3)
        assert line == 2

        line = get_line_for_position(SAMPLE_PATCH, 8)
        assert line == 12

    def test_missing_position(self) -> None:
        """Test position not in patch."""
        line = get_line_for_position(SAMPLE_PATCH, 999)
        assert line is None
