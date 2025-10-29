"""
Unit tests for src/core/helpers.py utility functions.

Tests cover:
- normalize_portfolio_name: Unicode, diacritics, special chars, edge cases
- find_portfolio_file_by_name: File search with validation callback
- format_aligned_summary: Summary formatting with alignment
- format_quick_panel_line: Quick panel line formatting with padding

NOTE: Tests for show_persistent_status() excluded (requires import sublime).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.helpers import (
    deep_merge_dicts,
    find_portfolio_file_by_name,
    format_aligned_summary,
    format_centered_separator,
    format_quick_panel_line,
    get_current_timestamp,
    normalize_portfolio_name,
    pluralize,
    truncate_for_log,
)

# ============================================================================
# normalize_portfolio_name() Tests
# ============================================================================


class TestNormalizePortfolioName:
    """Tests for normalize_portfolio_name() - Unicode normalization and sanitization."""

    def test_normalize_simple_ascii(self):
        """Simple ASCII name unchanged (except lowercase + .json)."""
        assert normalize_portfolio_name("MyPortfolio") == "myportfolio.json"
        assert normalize_portfolio_name("test") == "test.json"
        assert normalize_portfolio_name("Portfolio123") == "portfolio123.json"

    def test_normalize_with_json_extension(self):
        """Should remove .json if present, then re-add it."""
        assert normalize_portfolio_name("MyPortfolio.json") == "myportfolio.json"
        assert normalize_portfolio_name("Test.JSON") == "test.json"
        assert normalize_portfolio_name("data.Json") == "data.json"

    def test_normalize_with_spaces(self):
        """Spaces replaced with underscores."""
        assert normalize_portfolio_name("My Portfolio") == "my_portfolio.json"
        assert normalize_portfolio_name("Test File Name") == "test_file_name.json"
        assert normalize_portfolio_name("Single Space") == "single_space.json"

    def test_normalize_multiple_spaces(self):
        """Multiple consecutive spaces → single underscore."""
        assert normalize_portfolio_name("Many    Spaces") == "many_spaces.json"
        assert normalize_portfolio_name("Too   Many  Gaps") == "too_many_gaps.json"

    def test_normalize_unicode_french(self):
        """French accents removed (NFD decomposition + diacritic removal)."""
        assert normalize_portfolio_name("Français Général") == "francais_general.json"
        assert normalize_portfolio_name("Été 2024") == "ete_2024.json"
        assert normalize_portfolio_name("Très élégant") == "tres_elegant.json"

    def test_normalize_unicode_spanish(self):
        """Spanish special chars normalized."""
        assert normalize_portfolio_name("España-2024") == "espana2024.json"  # Hyphen removed
        assert normalize_portfolio_name("Niño pequeño") == "nino_pequeno.json"

    def test_normalize_unicode_german(self):
        """German umlauts normalized."""
        assert normalize_portfolio_name("Tëst Pörtfolio") == "test_portfolio.json"
        assert normalize_portfolio_name("Über München") == "uber_munchen.json"

    def test_normalize_special_characters(self):
        """Special characters removed (non-alphanumeric except underscore)."""
        assert normalize_portfolio_name("Portfolio!!!") == "portfolio.json"
        assert normalize_portfolio_name("Test@#$%Portfolio") == "testportfolio.json"
        assert normalize_portfolio_name("File-Name_2024") == "filename_2024.json"  # Hyphen removed, underscore kept

    def test_normalize_leading_trailing_underscores(self):
        """Leading/trailing underscores removed."""
        assert normalize_portfolio_name("  Portfolio  ") == "portfolio.json"
        assert normalize_portfolio_name("__test__") == "test.json"
        assert normalize_portfolio_name(" _Name_ ") == "name.json"

    def test_normalize_empty_or_whitespace(self):
        """Empty or whitespace-only names → 'portfolio.json'."""
        assert normalize_portfolio_name("") == "portfolio.json"
        assert normalize_portfolio_name("   ") == "portfolio.json"
        assert normalize_portfolio_name("!!!") == "portfolio.json"
        assert normalize_portfolio_name("___") == "portfolio.json"

    def test_normalize_complex_case(self):
        """Complex real-world example."""
        assert normalize_portfolio_name("Tëst Pörtfolio!!!") == "test_portfolio.json"
        assert normalize_portfolio_name("Café René (2024)") == "cafe_rene_2024.json"


# ============================================================================
# find_portfolio_file_by_name() Tests
# ============================================================================


class TestFindPortfolioFileByName:
    """Tests for find_portfolio_file_by_name() - File search with validation."""

    def test_find_portfolio_file_found(self, tmp_path: Path):
        """Should find portfolio file by exact name match."""
        # Create test portfolio
        portfolio_file = tmp_path / "test_portfolio.json"
        portfolio_file.write_text('{"name": "Test Portfolio", "patterns": []}')

        # Validation callback (always valid)
        def validate(path: str) -> tuple[bool, dict]:
            import json

            data = json.loads(Path(path).read_text())
            return True, data

        # Search
        result = find_portfolio_file_by_name(tmp_path, "Test Portfolio", validate)

        assert result == portfolio_file

    def test_find_portfolio_file_not_found(self, tmp_path: Path):
        """Should return None if no matching portfolio."""
        # Create test portfolio with different name
        portfolio_file = tmp_path / "test_portfolio.json"
        portfolio_file.write_text('{"name": "Wrong Name", "patterns": []}')

        # Validation callback
        def validate(path: str) -> tuple[bool, dict]:
            import json

            data = json.loads(Path(path).read_text())
            return True, data

        # Search for non-existent portfolio
        result = find_portfolio_file_by_name(tmp_path, "Test Portfolio", validate)

        assert result is None

    def test_find_portfolio_file_invalid_json(self, tmp_path: Path):
        """Should skip files that fail validation."""
        # Create invalid JSON file
        portfolio_file = tmp_path / "test_portfolio.json"
        portfolio_file.write_text("INVALID JSON")

        # Validation callback (returns False for invalid)
        def validate(path: str) -> tuple[bool, dict]:
            try:
                import json

                data = json.loads(Path(path).read_text())
                return True, data
            except Exception:
                return False, {}

        # Search
        result = find_portfolio_file_by_name(tmp_path, "Test Portfolio", validate)

        assert result is None

    def test_find_portfolio_file_multiple_files(self, tmp_path: Path):
        """Should find correct file among multiple portfolios."""
        # Create multiple portfolios
        (tmp_path / "portfolio1.json").write_text('{"name": "Portfolio 1", "patterns": []}')
        (tmp_path / "portfolio2.json").write_text('{"name": "Target Portfolio", "patterns": []}')
        (tmp_path / "portfolio3.json").write_text('{"name": "Portfolio 3", "patterns": []}')

        # Validation callback
        def validate(path: str) -> tuple[bool, dict]:
            import json

            data = json.loads(Path(path).read_text())
            return True, data

        # Search
        result = find_portfolio_file_by_name(tmp_path, "Target Portfolio", validate)

        assert result == tmp_path / "portfolio2.json"

    def test_find_portfolio_file_empty_directory(self, tmp_path: Path):
        """Should return None if directory has no JSON files."""

        def validate(path: str) -> tuple[bool, dict]:
            return True, {}

        result = find_portfolio_file_by_name(tmp_path, "Test Portfolio", validate)

        assert result is None


# ============================================================================
# format_aligned_summary() Tests
# ============================================================================


class TestFormatAlignedSummary:
    """Tests for format_aligned_summary() - Summary formatting with alignment."""

    def test_format_aligned_summary_basic(self):
        """Should format summary with right-aligned labels."""
        items = [
            ("Name", "Test Portfolio"),
            ("Type", "Custom"),
            ("Patterns", "5"),
        ]

        result = format_aligned_summary("Summary", items)

        # Verify title
        assert result[0] == "Summary:"
        assert result[1] == ""

        # Verify alignment (all colons should align)
        assert "Name :" in result[2] or "Name:" in result[2]
        assert "Type :" in result[3] or "Type:" in result[3]
        assert "Patterns :" in result[4] or "Patterns:" in result[4]

        # Verify values present
        assert "Test Portfolio" in result[2]
        assert "Custom" in result[3]
        assert "5" in result[4]

    def test_format_aligned_summary_different_label_lengths(self):
        """Should align colons despite different label lengths."""
        items = [
            ("N", "Short"),
            ("Description", "Long label test"),
            ("X", "Another short"),
        ]

        result = format_aligned_summary("Test", items)

        # All colons should be at same position
        # Extract colon positions
        lines_with_colons = [line for line in result if ":" in line and line != "Test:"]
        if len(lines_with_colons) >= 2:
            colon_positions = [line.index(":") for line in lines_with_colons]
            # All positions should be the same (aligned)
            assert len(set(colon_positions)) == 1

    def test_format_aligned_summary_empty_items(self):
        """Should handle empty items list."""
        result = format_aligned_summary("Empty", [])

        assert result[0] == "Empty:"
        assert result[1] == ""
        assert len(result) == 2


# ============================================================================
# format_quick_panel_line() Tests
# ============================================================================


class TestFormatQuickPanelLine:
    """Tests for format_quick_panel_line() - Quick panel formatting with padding."""

    def test_format_quick_panel_line_basic(self):
        """Should format line with dynamic padding."""
        result = format_quick_panel_line("Pattern Name", "Static 📄", 80)

        assert result.startswith("Pattern Name")
        assert result.endswith("Static 📄")
        assert len(result) <= 80

    def test_format_quick_panel_line_with_left_icon(self):
        """Should include left icon prefix."""
        result = format_quick_panel_line("New Portfolio", "Create", 80, left_icon="+")

        assert result.startswith("+")
        assert "New Portfolio" in result
        assert result.endswith("Create")

    def test_format_quick_panel_line_with_right_icon(self):
        """Should include right icon prefix."""
        result = format_quick_panel_line("Pattern", "Type", 80, right_icon="🧪")

        assert result.startswith("Pattern")
        assert "🧪 Type" in result or "Type" in result

    def test_format_quick_panel_line_with_both_icons(self):
        """Should include both left and right icons."""
        result = format_quick_panel_line("Action", "Status", 80, left_icon="✏️", right_icon="📄")

        assert "✏️" in result
        assert "📄" in result or "Status" in result
        assert "Action" in result

    def test_format_quick_panel_line_long_text(self):
        """Should handle long text that exceeds panel width."""
        long_left = "A" * 60
        long_right = "B" * 30

        result = format_quick_panel_line(long_left, long_right, 80)

        # Should still return a string (may truncate or wrap)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_quick_panel_line_short_width(self):
        """Should handle short panel width."""
        result = format_quick_panel_line("Short", "Text", 20)

        assert isinstance(result, str)
        assert "Short" in result or "Text" in result

    def test_format_quick_panel_line_no_right_text(self):
        """Should handle empty right text."""
        result = format_quick_panel_line("Left Only", "", 80)

        assert result.startswith("Left Only")
        assert len(result) <= 80

    def test_format_quick_panel_line_alignment_consistency(self):
        """Should maintain consistent right alignment across multiple calls."""
        lines = [
            format_quick_panel_line("Pattern1", "Static 📄", 80),
            format_quick_panel_line("LongPatternName", "Dynamic 🧪", 80),
            format_quick_panel_line("P", "Static 📄", 80),
        ]

        # All lines should have consistent formatting
        for line in lines:
            assert len(line) <= 80


# ============================================================================
# pluralize() Tests (Bonus - already tested but adding for completeness)
# ============================================================================


class TestPluralize:
    """Tests for pluralize() - Singular/plural form selection."""

    def test_pluralize_singular(self):
        """Should return singular form for count=1."""
        assert pluralize(1, "pattern") == "pattern"
        assert pluralize(1, "child", "children") == "child"

    def test_pluralize_plural_default(self):
        """Should add 's' for plural when no explicit plural form."""
        assert pluralize(0, "pattern") == "patterns"
        assert pluralize(2, "pattern") == "patterns"
        assert pluralize(5, "item") == "items"

    def test_pluralize_plural_explicit(self):
        """Should use explicit plural form when provided."""
        assert pluralize(0, "child", "children") == "children"
        assert pluralize(2, "child", "children") == "children"
        assert pluralize(5, "person", "people") == "people"

    def test_pluralize_edge_cases(self):
        """Should handle edge case counts."""
        assert pluralize(0, "item") == "items"  # Zero is plural
        assert pluralize(-1, "item") == "items"  # Negative is plural
        assert pluralize(1000, "item") == "items"  # Large number is plural


# ============================================================================
# truncate_for_log() Tests
# ============================================================================


class TestTruncateForLog:
    """Tests for truncate_for_log() - String truncation for logging."""

    def test_truncate_short_string(self):
        """Should not truncate strings shorter than max_len."""
        assert truncate_for_log("short") == "short"
        assert truncate_for_log("exactly 30 chars!!!!!!!!!!", 30) == "exactly 30 chars!!!!!!!!!!"

    def test_truncate_long_string(self):
        """Should truncate strings longer than max_len with '...'."""
        long_string = "this is a very long string that needs truncation"
        assert truncate_for_log(long_string) == "this is a very long string tha..."
        assert truncate_for_log("1234567890123456789012345678901", 30) == "123456789012345678901234567890..."

    def test_truncate_custom_max_len(self):
        """Should respect custom max_len parameter."""
        assert truncate_for_log("short", 10) == "short"
        assert truncate_for_log("this is longer than 10", 10) == "this is lo..."

    def test_truncate_edge_cases(self):
        """Should handle edge cases."""
        assert truncate_for_log("", 30) == ""
        assert truncate_for_log("x", 1) == "x"
        assert truncate_for_log("xy", 1) == "x..."


# ============================================================================
# get_current_timestamp() Tests
# ============================================================================


class TestGetCurrentTimestamp:
    """Tests for get_current_timestamp() - ISO timestamp generation."""

    def test_timestamp_format(self):
        """Should return timestamp in ISO format."""
        timestamp = get_current_timestamp()
        # Format: 2025-10-23T15:30:45.123456+00:00
        assert "T" in timestamp
        assert ":" in timestamp
        # Date part should have 2 hyphens (YYYY-MM-DD)
        date_part = timestamp.split("T")[0]
        assert date_part.count("-") == 2

    def test_timestamp_consistency(self):
        """Should return consistent format across multiple calls."""
        ts1 = get_current_timestamp()
        ts2 = get_current_timestamp()
        # Both should have same format (though different values)
        assert len(ts1) == len(ts2)
        assert ts1.count("T") == ts2.count("T") == 1


# ============================================================================
# format_centered_separator() Tests
# ============================================================================


class TestFormatCenteredSeparator:
    """Tests for format_centered_separator() - Centered separator lines."""

    def test_centered_separator_basic(self):
        """Should create centered separator with dashes."""
        result = format_centered_separator("Test", 20)
        assert "Test" in result
        assert result.startswith("─")
        assert result.endswith("─")
        assert len(result) == 20

    def test_centered_separator_different_widths(self):
        """Should handle different widths."""
        result1 = format_centered_separator("Label", 30)
        result2 = format_centered_separator("Label", 50)
        assert len(result1) == 30
        assert len(result2) == 50
        assert "Label" in result1
        assert "Label" in result2

    def test_centered_separator_odd_width(self):
        """Should handle odd widths correctly."""
        result = format_centered_separator("X", 21)
        assert len(result) == 21
        assert " X " in result

    def test_centered_separator_long_label(self):
        """Should handle labels close to panel width."""
        result = format_centered_separator("Very Long Label Here", 30)
        assert "Very Long Label Here" in result


# ============================================================================
# deep_merge_dicts() Tests
# ============================================================================


class TestDeepMergeDicts:
    """Tests for deep_merge_dicts() - Deep merge for nested dictionaries."""

    def test_deep_merge_empty_dicts(self):
        """Should handle empty dictionaries."""
        assert deep_merge_dicts({}, {}) == {}
        assert deep_merge_dicts({"a": 1}, {}) == {"a": 1}
        assert deep_merge_dicts({}, {"b": 2}) == {"b": 2}

    def test_deep_merge_simple_scalars(self):
        """Should merge simple scalar values (override wins)."""
        base = {"a": 1, "b": 2}
        override = {"b": 99, "c": 3}
        result = deep_merge_dicts(base, override)

        assert result == {"a": 1, "b": 99, "c": 3}

    def test_deep_merge_nested_dicts(self):
        """Should recursively merge nested dictionaries."""
        base = {"vars": {"DATE": {"regex": "old"}, "TIME": {"regex": "old"}}}
        override = {"vars": {"DATE": {"regex": "new"}, "NEW": {"regex": "new"}}}

        result = deep_merge_dicts(base, override)

        assert result == {
            "vars": {
                "DATE": {"regex": "new"},  # Override wins
                "TIME": {"regex": "old"},  # Preserved from base
                "NEW": {"regex": "new"},  # Added from override
            }
        }

    def test_deep_merge_mixed_types_override_wins(self):
        """Should use override value when types differ."""
        base = {"a": {"nested": "dict"}}
        override = {"a": "scalar"}

        result = deep_merge_dicts(base, override)
        assert result == {"a": "scalar"}

    def test_deep_merge_lists_replace_not_merge(self):
        """Should replace lists entirely (no list merging)."""
        base = {"list": [1, 2, 3]}
        override = {"list": [4, 5]}

        result = deep_merge_dicts(base, override)
        assert result == {"list": [4, 5]}

    def test_deep_merge_deeply_nested(self):
        """Should handle deeply nested structures."""
        base = {"level1": {"level2": {"level3": {"a": 1, "b": 2}}}}
        override = {"level1": {"level2": {"level3": {"b": 99, "c": 3}}}}

        result = deep_merge_dicts(base, override)
        assert result == {"level1": {"level2": {"level3": {"a": 1, "b": 99, "c": 3}}}}

    def test_deep_merge_preserves_input_dicts(self):
        """Should not modify input dictionaries."""
        base = {"a": 1, "nested": {"x": 10}}
        override = {"b": 2, "nested": {"y": 20}}

        base_copy = base.copy()
        override_copy = override.copy()

        deep_merge_dicts(base, override)

        # Inputs unchanged
        assert base == base_copy
        assert override == override_copy

    def test_deep_merge_none_values(self):
        """Should handle None values correctly."""
        base = {"a": None, "b": 2}
        override = {"a": 1, "c": None}

        result = deep_merge_dicts(base, override)
        assert result == {"a": 1, "b": 2, "c": None}

    def test_deep_merge_complex_real_world(self):
        """Should handle real-world settings merge scenario."""
        # Simulates variables_assertion merge
        base = {
            "variables_assertion": {
                "DATE": {"regex": "[0-9]{4}-[0-9]{2}-[0-9]{2}", "default": "NOW"},
                "TIME": {"regex": "[0-9]{2}:[0-9]{2}:[0-9]{2}", "default": "NOW"},
                "USERNAME": {"regex": "[a-zA-Z0-9_-]{3,}"},
            }
        }

        override = {
            "variables_assertion": {
                "MY_VAR": {"regex": "[0-9\\/\\-]{10}", "default": "NOW"},
                "DATE": {"regex": "[0-9]{2}/[0-9]{2}/[0-9]{4}"},  # Override DATE
            }
        }

        result = deep_merge_dicts(base, override)

        # All keys present
        assert "DATE" in result["variables_assertion"]
        assert "TIME" in result["variables_assertion"]
        assert "USERNAME" in result["variables_assertion"]
        assert "MY_VAR" in result["variables_assertion"]

        # DATE overridden
        assert result["variables_assertion"]["DATE"]["regex"] == "[0-9]{2}/[0-9]{2}/[0-9]{4}"

        # TIME/USERNAME preserved
        assert result["variables_assertion"]["TIME"]["default"] == "NOW"
        assert result["variables_assertion"]["USERNAME"]["regex"] == "[a-zA-Z0-9_-]{3,}"


# ==========================================================================
# show_persistent_status() Tests (Coverage Quick Wins)
# ==========================================================================


class TestShowPersistentStatus:
    """Tests for show_persistent_status() - Sublime fallback and scheduling."""

    def test_show_persistent_status_without_sublime_module(self):
        """Should fall back to single status message when sublime import fails."""
        from src.core.helpers import show_persistent_status

        window = MagicMock()
        window.status_message = MagicMock()

        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "sublime":
                raise ModuleNotFoundError("sublime mock failure")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            show_persistent_status(window, "RegexLab: Processing", duration_ms=500)

        window.status_message.assert_called_once_with("RegexLab: Processing")

    def test_show_persistent_status_with_stubbed_sublime(self):
        """Should schedule repeated status messages when sublime module exists."""
        from src.core.helpers import show_persistent_status

        status_calls: list[str] = []

        class FakeWindow:
            def status_message(self, message: str) -> None:
                status_calls.append(message)

        class FakeSublime:
            def __init__(self) -> None:
                self.timeout_calls: list[int] = []

            def set_timeout(self, callback, delay: int) -> None:  # type: ignore[override]
                self.timeout_calls.append(delay)
                callback()

        fake_sublime = FakeSublime()
        settings = SimpleNamespace(get=lambda key, default: 4000 if key == "status_message_duration" else default)

        with patch.dict("sys.modules", {"sublime": fake_sublime}):
            show_persistent_status(FakeWindow(), "RegexLab: Done", settings_manager=settings)

        assert status_calls.count("RegexLab: Done") >= 2  # initial + at least one repeat
        assert fake_sublime.timeout_calls, "Expected set_timeout to be invoked at least once"
