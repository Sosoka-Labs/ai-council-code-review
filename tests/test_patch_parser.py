"""Tests for ai_council_review.patch_parser."""

from __future__ import annotations

from ai_council_review.patch_parser import (
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
        """Test finding positions of added lines."""
        positions = get_added_line_positions(SAMPLE_PATCH)
        # Hunk 1: line 2 is added at position 3
        # Hunk 2: line 12 is added at position 12, line 13 at position 13
        assert len(positions) == 3

        # First hunk: @@=1, context=2, removed=3, added=4
        # new_line starts at 1, context increments to 2, removed stays 2, added at 2
        assert positions[0] == (4, 2, '    print("new")')

        # Second hunk: @@=6, context=7, context=8, removed=9, added=10, added=11
        # new_line starts at 10, context increments to 11, context increments to 12,
        # removed stays 12, added at 12, added at 13
        assert positions[1] == (10, 12, "    y = 3")
        assert positions[2] == (11, 13, "    z = 4")

    def test_empty_patch(self) -> None:
        """Test with empty patch."""
        positions = get_added_line_positions("")
        assert positions == []


class TestGetPositionForLine:
    """Tests for get_position_for_line."""

    def test_find_position(self) -> None:
        """Test getting position for a specific line."""
        pos = get_position_for_line(SAMPLE_PATCH, 2)
        assert pos == 4

        pos = get_position_for_line(SAMPLE_PATCH, 12)
        assert pos == 10

    def test_missing_line(self) -> None:
        """Test line not in patch."""
        pos = get_position_for_line(SAMPLE_PATCH, 999)
        assert pos is None


class TestGetLineForPosition:
    """Tests for get_line_for_position."""

    def test_find_line(self) -> None:
        """Test getting line number for a position."""
        line = get_line_for_position(SAMPLE_PATCH, 4)
        assert line == 2

        line = get_line_for_position(SAMPLE_PATCH, 10)
        assert line == 12

    def test_missing_position(self) -> None:
        """Test position not in patch."""
        line = get_line_for_position(SAMPLE_PATCH, 999)
        assert line is None
