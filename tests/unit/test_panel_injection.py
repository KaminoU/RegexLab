"""
Unit tests for Panel Injection utilities.

Tests the core pattern injection logic for Find, Replace, and Find in Files panels.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.utils.panel_injection import (
    inject_into_find_in_files_panel,
    inject_into_find_panel,
    inject_into_replace_panel,
)


class TestInjectIntoFindPanel:
    """Tests for inject_into_find_panel function."""

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_into_find_panel_success(self, mock_get_logger: MagicMock) -> None:
        """Test successful injection into Find panel."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        window = MagicMock()
        view = MagicMock()
        window.active_view.return_value = view
        view.is_read_only.return_value = False
        view.sel.return_value = MagicMock()

        inject_into_find_panel(window, r"\d{3}-\d{4}", "Test Pattern")

        # Verify panel opened with regex OFF
        window.run_command.assert_any_call("show_panel", {"panel": "find", "regex": False})

        # Verify pattern inserted
        view.run_command.assert_any_call("insert", {"characters": r"\d{3}-\d{4}"})

        # Verify slurp_find_string called
        window.run_command.assert_any_call("slurp_find_string")

        # Verify undo called
        view.run_command.assert_any_call("undo")

        # Verify regex toggled ON
        window.run_command.assert_any_call("toggle_regex")

        # Verify success message
        window.status_message.assert_called_once_with("Regex Lab: Loaded pattern 'Test Pattern'")

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_into_find_panel_no_active_view(self, mock_get_logger: MagicMock) -> None:
        """Test injection when no active view is available."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        window = MagicMock()
        window.active_view.return_value = None

        inject_into_find_panel(window, r"\d+", "Pattern")

        # Should show error message
        window.status_message.assert_called_once_with("Regex Lab: Pattern copied to clipboard (no active view)")

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_into_find_panel_no_view_sets_clipboard(self, mock_get_logger: MagicMock) -> None:
        """When sublime is available, clipboard should receive the pattern on error."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        clipboard_calls: list[str] = []

        fake_sublime = SimpleNamespace()

        def set_clipboard(value: str) -> None:
            clipboard_calls.append(value)

        class FakeRegion:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

        fake_sublime.set_clipboard = set_clipboard
        fake_sublime.Region = FakeRegion

        window = MagicMock()
        window.active_view.return_value = None

        with patch.dict("sys.modules", {"sublime": fake_sublime}):
            inject_into_find_panel(window, "clipboard_pattern", "Pattern")

        assert clipboard_calls == ["clipboard_pattern"]

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_into_find_panel_readonly_view(self, mock_get_logger: MagicMock) -> None:
        """Test injection with read-only view."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        window = MagicMock()
        view = MagicMock()
        window.active_view.return_value = view
        view.is_read_only.return_value = True
        view.sel.return_value = MagicMock()

        inject_into_find_panel(window, r"[a-z]+", "Pattern")

        # Should disable read-only before injection
        view.set_read_only.assert_any_call(False)

        # Should restore read-only after injection
        view.set_read_only.assert_any_call(True)

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_into_find_panel_uses_sublime_region(self, mock_get_logger: MagicMock) -> None:
        """Should create Regions via sublime module when available."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        region_calls: list[tuple[int, int]] = []

        class FakeRegion:
            def __init__(self, a: int, b: int) -> None:
                region_calls.append((a, b))

        fake_sublime = SimpleNamespace(set_clipboard=lambda _value: None, Region=FakeRegion)

        window = MagicMock()
        view = MagicMock()
        window.active_view.return_value = view
        view.is_read_only.return_value = False
        view.sel.return_value = MagicMock()

        with patch.dict("sys.modules", {"sublime": fake_sublime}):
            inject_into_find_panel(window, "abc", "Pattern")

        assert (0, 0) in region_calls
        assert (0, 3) in region_calls


class TestInjectIntoReplacePanel:
    """Tests for inject_into_replace_panel function."""

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_into_replace_panel_success(self, mock_get_logger: MagicMock) -> None:
        """Test successful injection into Replace panel."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        window = MagicMock()
        view = MagicMock()
        window.active_view.return_value = view
        view.is_read_only.return_value = False
        view.sel.return_value = MagicMock()

        inject_into_replace_panel(window, r"(\w+)", "Capture Pattern")

        # Verify panel opened with regex OFF (Replace panel)
        window.run_command.assert_any_call("show_panel", {"panel": "replace", "regex": False})

        # Verify success message (Replace-specific)
        window.status_message.assert_called_once_with("Regex Lab: Loaded pattern 'Capture Pattern' into Replace panel")


class TestInjectIntoFindInFilesPanel:
    """Tests for inject_into_find_in_files_panel function."""

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_into_find_in_files_panel_success(self, mock_get_logger: MagicMock) -> None:
        """Test successful injection into Find in Files panel."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        window = MagicMock()
        view = MagicMock()
        window.active_view.return_value = view
        view.is_read_only.return_value = False
        view.sel.return_value = MagicMock()

        inject_into_find_in_files_panel(window, r"TODO:", "Todo Pattern")

        # Verify panel opened with regex OFF (Find in Files panel)
        window.run_command.assert_any_call("show_panel", {"panel": "find_in_files", "regex": False})

        # Verify success message (Find in Files-specific)
        window.status_message.assert_called_once_with("Regex Lab: Loaded pattern 'Todo Pattern' into Find in Files")


class TestPanelInjectionSelectionRestore:
    """Tests for selection restoration after injection."""

    @patch("src.utils.panel_injection.get_logger")
    def test_selection_restored_after_injection(self, mock_get_logger: MagicMock) -> None:
        """Test that original selection is restored after injection."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        window = MagicMock()
        view = MagicMock()
        window.active_view.return_value = view
        view.is_read_only.return_value = False

        # Mock selection with regions
        mock_sel = MagicMock()
        mock_region1 = MagicMock()
        mock_region2 = MagicMock()
        mock_sel.__iter__.return_value = iter([mock_region1, mock_region2])
        view.sel.return_value = mock_sel

        inject_into_find_panel(window, r"test", "Pattern")

        # Verify selection cleared
        assert mock_sel.clear.call_count >= 2

        # Verify original regions added back
        mock_sel.add.assert_any_call(mock_region1)
        mock_sel.add.assert_any_call(mock_region2)


class TestPanelInjectionEdgeCases:
    """Tests for edge cases in panel injection."""

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_empty_pattern(self, mock_get_logger: MagicMock) -> None:
        """Test injection with empty pattern."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        window = MagicMock()
        view = MagicMock()
        window.active_view.return_value = view
        view.is_read_only.return_value = False
        view.sel.return_value = MagicMock()

        inject_into_find_panel(window, "", "Empty Pattern")

        # Should still call insert (even with empty string)
        view.run_command.assert_any_call("insert", {"characters": ""})

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_complex_regex_pattern(self, mock_get_logger: MagicMock) -> None:
        """Test injection with complex regex pattern."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        window = MagicMock()
        view = MagicMock()
        window.active_view.return_value = view
        view.is_read_only.return_value = False
        view.sel.return_value = MagicMock()

        complex_pattern = r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})"
        inject_into_find_panel(window, complex_pattern, "Date Pattern")

        # Verify complex pattern inserted correctly
        view.run_command.assert_any_call("insert", {"characters": complex_pattern})

    @patch("src.utils.panel_injection.get_logger")
    def test_inject_pattern_with_special_characters(self, mock_get_logger: MagicMock) -> None:
        """Test injection with special characters."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        window = MagicMock()
        view = MagicMock()
        window.active_view.return_value = view
        view.is_read_only.return_value = False
        view.sel.return_value = MagicMock()

        special_pattern = r"[\[\]{}().*+?^$|\\]"
        inject_into_find_panel(window, special_pattern, "Special Chars")

        # Verify special characters handled correctly
        view.run_command.assert_any_call("insert", {"characters": special_pattern})
