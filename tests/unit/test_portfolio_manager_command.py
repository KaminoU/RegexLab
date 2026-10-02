"""
Tests for Portfolio Manager Command.

Tests for the central portfolio management hub.
"""

import builtins
import contextlib
import errno
import io
import json
import os
import shutil
import tempfile
import traceback
import unicodedata
import unittest
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Optional, Tuple
from unittest.mock import patch

from src.commands.edit_pattern_command import EditPatternCommand
from src.commands.portfolio_manager_command import PortfolioManagerCommand
from src.core.models import Pattern, PatternType, Portfolio
from src.core.portfolio_manager import PortfolioManager
from src.core.settings_manager import SettingsManager
from src.services.portfolio_service import PortfolioService


class MockWindow:
    """Mock Sublime Text window for testing."""

    def __init__(self) -> None:
        """Initialize mock window."""
        self.status_messages: List[str] = []
        self.quick_panels: List[tuple] = []
        self.commands_run: List[tuple] = []
        self.extract_vars: Dict[str, str] = {"packages": str(Path.home() / ".config" / "sublime-text" / "Packages")}
        self.file_dialog_callback: Optional[Callable[[str], None]] = None

    def status_message(self, message: str) -> None:
        """Mock status_message."""
        self.status_messages.append(message)

    def show_quick_panel(
        self,
        items: List[List[str]],
        on_done: Callable[[int], None],
        flags: Optional[int] = None,
    ) -> None:
        """Mock show_quick_panel."""
        self.quick_panels.append((items, on_done, flags))

    def run_command(self, command: str, args: Optional[Dict[str, Any]] = None) -> None:
        """Mock run_command."""
        self.commands_run.append((command, args))

    def extract_variables(self) -> Dict[str, str]:
        """Mock extract_variables."""
        return self.extract_vars

    def show_open_file_dialog(
        self,
        on_done: Callable[[str], None],
        file_types: Optional[List[tuple]] = None,
        directory: Optional[str] = None,
    ) -> None:
        """Mock show_open_file_dialog."""
        self.file_dialog_callback = on_done

    def show_input_panel(
        self,
        caption: str,
        initial_text: str,
        on_done: Callable[[str], None],
        on_change: Optional[Callable[[str], None]],
        on_cancel: Optional[Callable[[], None]],
    ) -> None:
        """Mock show_input_panel."""
        self.file_dialog_callback = on_done


class TestPortfolioManagerCommand(unittest.TestCase):
    """Test suite for Portfolio Manager Command."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Reset singletons
        SettingsManager._instance = None
        PortfolioManager._instance = None

        # Create mock services
        self.settings_manager = SettingsManager()
        self.portfolio_manager = PortfolioManager.get_instance()
        self.portfolio_service = PortfolioService(portfolio_manager=self.portfolio_manager)

        # Create command instance
        self.command = PortfolioManagerCommand(
            portfolio_service=self.portfolio_service,
            settings_manager=self.settings_manager,
        )

        # Create mock window
        self.window = MockWindow()

    def tearDown(self) -> None:
        """Clean up after tests."""
        SettingsManager._instance = None
        PortfolioManager._instance = None

    def test_run_with_no_portfolios(self) -> None:
        """Test run() with no portfolios loaded."""
        # Act
        self.command.run(self.window)

        # Assert
        self.assertEqual(len(self.window.quick_panels), 1)
        items, _on_done, _flags = self.window.quick_panels[0]

        # Should have separator + actions section only
        # No loaded portfolios, no available portfolios
        separator_count = sum(1 for item in items if "─" in item[0])
        self.assertGreaterEqual(separator_count, 1)  # At least "Actions" separator

    def test_run_with_loaded_portfolios(self) -> None:
        """Test run() with loaded portfolios."""
        # Arrange
        portfolio = Portfolio(
            name="Test Portfolio",
            patterns=[
                Pattern(
                    name="Test Pattern",
                    regex=r"\d+",
                    description="Test",
                    type=PatternType.STATIC,
                )
            ],
            readonly=False,
        )
        # Use PortfolioManager's internal dict (name -> portfolio)
        self.portfolio_manager._loaded_portfolios = {"Test Portfolio": portfolio}

        # Act
        self.command.run(self.window)

        # Assert
        self.assertEqual(len(self.window.quick_panels), 1)
        items, _on_done, _flags = self.window.quick_panels[0]

        # Should have "Loaded Portfolios" section
        loaded_section = any("📁 Loaded Portfolios" in item[0] for item in items)
        self.assertTrue(loaded_section)

        # Should have the portfolio listed
        portfolio_item = any("Test Portfolio" in item[0] for item in items)
        self.assertTrue(portfolio_item)

    def test_format_separator(self) -> None:
        """Test _format_separator() formats correctly."""
        # Act
        separator = self.command._format_separator("Test Label", 100)

        # Assert
        self.assertEqual(len(separator), 100)
        self.assertIn("Test Label", separator)
        self.assertIn("─", separator)

    def test_format_portfolio_line_loaded_readonly(self) -> None:
        """Test _format_portfolio_line() for readonly portfolio."""
        # Arrange
        portfolio = Portfolio(
            name="Builtin Portfolio",
            patterns=[],
            readonly=True,
        )

        # Act
        line = self.command._format_portfolio_line(portfolio, 100, is_loaded=True, is_builtin=True)

        # Assert
        self.assertIn("Builtin Portfolio", line)
        self.assertIn("🔒", line)
        self.assertIn("Built-in", line)
        self.assertEqual(len(line), 100)

    def test_format_portfolio_line_loaded_custom(self) -> None:
        """Test _format_portfolio_line() for custom portfolio."""
        # Arrange
        portfolio = Portfolio(
            name="Custom Portfolio",
            patterns=[],
            readonly=False,
        )

        # Act
        line = self.command._format_portfolio_line(portfolio, 100, is_loaded=True)

        # Assert
        self.assertIn("Custom Portfolio", line)
        self.assertIn("📝", line)
        self.assertIn("Custom", line)

    def test_format_available_portfolio_line(self) -> None:
        """Test _format_disabled_portfolio_line()."""
        # Act
        line = self.command._format_disabled_portfolio_line("Disabled Portfolio", 100)

        # Assert
        self.assertIn("Disabled Portfolio", line)
        self.assertTrue("Disabled" in line)  # Check for text instead of emoji
        self.assertEqual(len(line), 100)

    def test_format_action_line(self) -> None:
        """Test _format_action_line() with dynamic padding."""
        # Test New Portfolio action
        line = self.command._format_action_line("New Portfolio", "Create New", 100)
        self.assertIn("New Portfolio", line)
        self.assertIn("\u2795", line)  # U+2795 HEAVY PLUS SIGN
        self.assertIn("Create New", line)
        self.assertEqual(len(line), 100)

        # Test Reload Portfolios action
        line = self.command._format_action_line("Reload Portfolios", "Refresh All", 100)
        self.assertIn("Reload Portfolios", line)
        self.assertIn("🔄", line)
        self.assertIn("Refresh All", line)
        self.assertEqual(len(line), 100)

        # Test Settings action
        line = self.command._format_action_line("Settings", "Configure", 100)
        self.assertIn("Settings", line)
        self.assertIn("⚙️", line)
        self.assertIn("Configure", line)
        self.assertEqual(len(line), 100)

        # Test with different panel width (68 like in settings)
        line = self.command._format_action_line("New Portfolio", "Create New", 68)
        self.assertEqual(len(line), 68)

        # Test unknown action (default icon)
        line = self.command._format_action_line("Unknown Action", "Do Something", 100)
        self.assertIn("🔧", line)  # Default icon
        self.assertEqual(len(line), 100)

    def test_handle_separator_selection(self) -> None:
        """Test _handle_selection() with separator - should do nothing."""
        # Arrange
        action = {"type": "separator"}

        # Act
        self.command._handle_selection(self.window, action)

        # Assert - no actions should be taken
        self.assertEqual(len(self.window.status_messages), 0)
        self.assertEqual(len(self.window.commands_run), 0)

    def test_handle_loaded_portfolio_selection(self) -> None:
        """Test _handle_selection() with loaded portfolio - should show context menu."""
        # Arrange
        portfolio = Portfolio(
            name="Test Portfolio",
            patterns=[
                Pattern(
                    name="Pattern1",
                    regex=r"\d+",
                    description="Test",
                    type=PatternType.STATIC,
                )
            ],
            readonly=False,
        )
        action = {
            "type": "loaded_portfolio",
            "portfolio": portfolio,
            "name": "Test Portfolio",
        }

        # Act
        self.command._handle_selection(self.window, action)

        # Assert - Should show Quick Panel with context menu
        self.assertEqual(len(self.window.quick_panels), 1)
        items, _on_done, _flags = self.window.quick_panels[0]

        # Verify context menu items are present
        item_labels = [item[0] for item in items]
        self.assertTrue(any("Browse Patterns" in label for label in item_labels))
        self.assertTrue(any("Back" in label for label in item_labels))

        # Non-readonly portfolio should have Add Pattern and Delete options
        self.assertTrue(any("Add Pattern" in label for label in item_labels))
        self.assertTrue(any("Delete Portfolio" in label for label in item_labels))

        # Edit Portfolio should NOT be present (removed from context menu)
        self.assertFalse(any("Edit Portfolio" in label for label in item_labels))

    def test_handle_available_portfolio_selection(self) -> None:
        """Test _handle_selection() with available portfolio."""
        # Arrange
        test_portfolio_path = Path(__file__).parent.parent / "data" / "portfolios" / "test.json"
        action = {
            "type": "available_portfolio",
            "filepath": str(test_portfolio_path),
            "name": "Test Portfolio",
            "metadata": {"name": "Test Portfolio", "patterns": []},
        }

        # Mock extract_variables to return predictable path
        packages_path = str(test_portfolio_path.parent.parent.parent)
        with patch.object(self.window, "extract_variables", return_value={"packages": packages_path}):
            # Act
            self.command._handle_selection(self.window, action)

        # Assert - should attempt to load
        # Note: Will fail if file doesn't exist, but that's expected in test
        self.assertGreaterEqual(len(self.window.status_messages), 1)

    def test_action_new_portfolio(self) -> None:
        """Test _action_new_portfolio()."""
        # Act
        self.command._action_new_portfolio(self.window)

        # Assert - should run the wizard command, not show a status message
        self.assertEqual(len(self.window.commands_run), 1)
        command, _args = self.window.commands_run[0]
        self.assertEqual(command, "regex_lab_new_portfolio_wizard")

    def test_action_reload_portfolios(self) -> None:
        """Test _action_reload_portfolios() delegates to reload command."""
        # Arrange - load a portfolio first
        portfolio = Portfolio(name="Test", patterns=[], readonly=False)
        self.portfolio_manager._loaded_portfolios = {"Test": portfolio}

        # Act
        self.command._action_reload_portfolios(self.window)

        # Assert - should call the reload command
        self.assertEqual(len(self.window.commands_run), 1)
        command, _args = self.window.commands_run[0]
        self.assertEqual(command, "regex_lab_reload_portfolios")

    def test_action_open_settings(self) -> None:
        """Test _action_open_settings()."""
        # Act
        self.command._action_open_settings(self.window)

        # Assert
        self.assertEqual(len(self.window.commands_run), 1)
        command, args = self.window.commands_run[0]
        self.assertEqual(command, "edit_settings")
        self.assertIn("base_file", args)
        self.assertIn("RegexLab.sublime-settings", args["base_file"])

    def test_handle_unknown_action_type(self) -> None:
        """Test _handle_selection() with unknown action type."""
        # Arrange
        action = {"type": "unknown_type"}

        # Act
        self.command._handle_selection(self.window, action)

        # Assert
        self.assertEqual(len(self.window.status_messages), 1)
        self.assertIn("Unknown action type", self.window.status_messages[0])

    def test_handle_unknown_action_name(self) -> None:
        """Test _handle_action() with unknown action name."""
        # Arrange
        action = {"type": "action", "action": "unknown_action"}

        # Act
        self.command._handle_selection(self.window, action)

        # Assert
        self.assertEqual(len(self.window.status_messages), 1)
        self.assertIn("Unknown action", self.window.status_messages[0])

    def test_quick_panel_uses_monospace_font(self) -> None:
        """Test that Quick Panel uses MONOSPACE_FONT flag."""
        # Arrange - create a mock sublime module with MONOSPACE_FONT constant
        import sys
        from unittest.mock import MagicMock

        mock_sublime = MagicMock()
        mock_sublime.MONOSPACE_FONT = 1
        mock_sublime.packages_path.return_value = str(Path.home() / ".config" / "sublime-text" / "Packages")

        # Inject mock into sys.modules before command execution
        sys.modules["sublime"] = mock_sublime

        try:
            # Act
            self.command.run(self.window)

            # Assert
            self.assertEqual(len(self.window.quick_panels), 1)
            _items, _on_done, flags = self.window.quick_panels[0]
            self.assertEqual(flags, 1)  # MONOSPACE_FONT

        finally:
            # Cleanup - remove mock from sys.modules
            if "sublime" in sys.modules:
                del sys.modules["sublime"]

    def test_available_portfolios_section(self) -> None:
        """Test that disabled portfolios section appears when portfolios found."""
        # Arrange
        with patch.object(
            self.portfolio_service,
            "get_disabled_portfolios",
            return_value=[
                (
                    "/path/to/portfolio.json",
                    {"name": "Disabled Portfolio", "patterns": []},
                )
            ],
        ):
            # Act
            self.command.run(self.window)

            # Assert
            items, _on_done, _flags = self.window.quick_panels[0]
            disabled_section = any("Disabled Portfolios" in item[0] for item in items)
            self.assertTrue(disabled_section)

    def test_actions_section_always_present(self) -> None:
        """Test that Actions section is always present."""
        # Act
        self.command.run(self.window)

        # Assert
        items, _on_done, _flags = self.window.quick_panels[0]
        actions_section = any("⚙️ Actions" in item[0] for item in items)
        self.assertTrue(actions_section)

        # Should have New Portfolio action
        new_portfolio = any("New Portfolio" in item[0] for item in items)
        self.assertTrue(new_portfolio)

        # Should have Reload action
        reload_action = any("Reload Portfolios" in item[0] for item in items)
        self.assertTrue(reload_action)

        # Should have Settings action
        settings_action = any("Settings" in item[0] for item in items)
        self.assertTrue(settings_action)

    def test_user_cancels_quick_panel(self) -> None:
        """Test that cancelling Quick Panel (index=-1) does nothing."""
        # Arrange
        self.command.run(self.window)
        _items, on_done, _flags = self.window.quick_panels[0]

        # Act
        on_done(-1)

        # Assert - no additional status messages or commands
        self.assertEqual(len(self.window.status_messages), 0)
        self.assertEqual(len(self.window.commands_run), 0)


class TestPortfolioManagerImportAction(unittest.TestCase):
    """Test Import Portfolio action (Phase 2.2.2)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        import tempfile

        # Reset singletons
        SettingsManager._instance = None
        PortfolioManager._instance = None

        # Create services
        self.settings_manager = SettingsManager()
        self.portfolio_manager = PortfolioManager.get_instance()
        self.portfolio_service = PortfolioService(portfolio_manager=self.portfolio_manager)
        self.command = PortfolioManagerCommand(
            portfolio_service=self.portfolio_service,
            settings_manager=self.settings_manager,
        )

        # Create temp directory for test files
        self.temp_dir = tempfile.mkdtemp()

        # Create mock window (has show_open_file_dialog by default now)
        self.window = MockWindow()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        SettingsManager._instance = None
        PortfolioManager._instance = None

    def test_import_action_shows_file_dialog(self) -> None:
        """Test that import action shows file picker dialog."""
        # Act
        self.command._action_import_portfolio(self.window)

        # Assert - file dialog callback should be set
        self.assertIsNotNone(self.window.file_dialog_callback)

    def test_import_valid_portfolio_success(self) -> None:
        """Test importing a valid portfolio file."""
        import json
        import os

        # Create valid portfolio file
        portfolio_data = {
            "name": "Imported Portfolio",
            "description": "Test import",
            "version": "1.0.0",
            "patterns": [{"name": "Pattern1", "regex": r"\d+", "description": "Test", "type": "static"}],
            "readonly": False,
            "author": "Test",
            "tags": [],
        }

        test_file = os.path.join(self.temp_dir, "import_test.json")
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f)

        # Mock packages path
        self.window.extract_vars = {"packages": self.temp_dir}

        # Trigger import
        self.command._action_import_portfolio(self.window)
        callback = self.window.file_dialog_callback

        # Verify callback was set
        self.assertIsNotNone(callback)
        assert callback is not None  # Type narrowing for mypy

        # Simulate user selecting file
        with patch.object(self.portfolio_service, "portfolio_exists", return_value=False):
            callback(test_file)

        # Assert success message
        self.assertTrue(any("imported" in msg for msg in self.window.status_messages))

    def test_import_invalid_portfolio_fails(self) -> None:
        """Test importing invalid portfolio shows error."""
        import os

        # Create invalid portfolio (missing required fields)
        test_file = os.path.join(self.temp_dir, "invalid.json")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('{"name": "Invalid"}')  # Missing required fields

        # Mock packages path
        self.window.extract_vars = {"packages": self.temp_dir}

        # Trigger import
        self.command._action_import_portfolio(self.window)
        callback = self.window.file_dialog_callback

        # Verify callback was set
        self.assertIsNotNone(callback)
        assert callback is not None  # Type narrowing for mypy

        # Simulate user selecting file
        callback(test_file)

        # Assert error message
        self.assertTrue(any("Invalid portfolio" in msg for msg in self.window.status_messages))

    def test_import_duplicate_portfolio_fails(self) -> None:
        """Test importing duplicate portfolio name shows error."""
        import json
        import os

        # Create valid portfolio file
        portfolio_data = {
            "name": "Duplicate Portfolio",
            "description": "Test",
            "version": "1.0.0",
            "patterns": [],
            "readonly": False,
            "author": "Test",
            "tags": [],
        }

        test_file = os.path.join(self.temp_dir, "duplicate.json")
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f)

        # Mock packages path
        self.window.extract_vars = {"packages": self.temp_dir}

        # Trigger import
        self.command._action_import_portfolio(self.window)
        callback = self.window.file_dialog_callback

        # Verify callback was set
        self.assertIsNotNone(callback)
        assert callback is not None  # Type narrowing for mypy

        # Simulate portfolio already exists
        with patch.object(self.portfolio_service, "portfolio_exists", return_value=True):
            callback(test_file)

        # Assert error message
        self.assertTrue(any("already exists" in msg for msg in self.window.status_messages))

    def test_import_non_json_file_fails(self) -> None:
        """Test importing non-.json file shows error."""
        import os

        # Create non-JSON file
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Not a JSON file")

        # Mock packages path
        self.window.extract_vars = {"packages": self.temp_dir}

        # Trigger import
        self.command._action_import_portfolio(self.window)
        callback = self.window.file_dialog_callback

        # Verify callback was set
        self.assertIsNotNone(callback)
        assert callback is not None  # Type narrowing for mypy

        # Simulate user selecting file
        callback(test_file)

        # Assert error message
        self.assertTrue(any("Invalid file type" in msg for msg in self.window.status_messages))

    def test_import_cancelled_by_user(self) -> None:
        """Test user cancelling import shows cancelled message."""
        # Trigger import
        self.command._action_import_portfolio(self.window)
        callback = self.window.file_dialog_callback

        # Verify callback was set
        self.assertIsNotNone(callback)
        assert callback is not None  # Type narrowing for mypy

        # Simulate user cancelling (None or empty string)
        callback("")

        # Assert cancelled message
        self.assertTrue(any("cancelled" in msg for msg in self.window.status_messages))


def _symlinks_refused(error: BaseException) -> bool:
    """Tell whether an error raised by os.symlink means the system refuses symlinks, not a faulty test setup."""
    if isinstance(error, NotImplementedError):
        return True
    # 1314 is ERROR_PRIVILEGE_NOT_HELD: Windows without the symlink privilege or Developer Mode
    refusals = (errno.EPERM, errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP)
    return isinstance(error, OSError) and (getattr(error, "winerror", None) == 1314 or error.errno in refusals)


class _RecordingLogger:
    """Logger double that records every call as (level, message) in a shared timeline."""

    def __init__(self, events: List[Tuple[str, str]]) -> None:
        """Keep a reference to the shared timeline."""
        self.events = events

    def _record(self, level: str, message: str, *args: Any) -> None:
        self.events.append((level, message % args if args else message))

    def debug(self, message: str, *args: Any) -> None:
        """Record a debug call."""
        self._record("debug", message, *args)

    def info(self, message: str, *args: Any) -> None:
        """Record an info call."""
        self._record("info", message, *args)

    def warning(self, message: str, *args: Any) -> None:
        """Record a warning call."""
        self._record("warning", message, *args)

    def error(self, message: str, *args: Any) -> None:
        """Record an error call."""
        self._record("error", message, *args)


class _TooLargeToRead(io.StringIO):
    """Text stream whose read() raises MemoryError, as reading a file too large for memory does."""

    def read(self, size: Optional[int] = -1) -> str:
        """Raise MemoryError instead of reading."""
        raise MemoryError


class _TimelineWindow(MockWindow):
    """MockWindow that also records its status messages in the shared timeline, as ("status", message)."""

    def __init__(self, events: List[Tuple[str, str]]) -> None:
        """Keep a reference to the shared timeline."""
        super().__init__()
        self.events = events

    def status_message(self, message: str) -> None:
        """Record the status message in the timeline, then as MockWindow does."""
        self.events.append(("status", message))
        super().status_message(message)


class _EditPatternWindow(MockWindow):
    """
    MockWindow that a test drives like a user through the panels of EditPatternCommand.

    It keeps the callbacks of the last quick panel and of the last input panel shown: pick() selects an item of
    the quick panel, enter() submits a text to the input panel.
    """

    def __init__(self) -> None:
        """Start with no panel shown."""
        super().__init__()
        self.on_pick: Optional[Callable[[int], None]] = None
        self.on_enter: Optional[Callable[[str], None]] = None

    def show_quick_panel(
        self,
        items: List[List[str]],
        on_done: Callable[[int], None],
        flags: Optional[int] = None,
        placeholder: Optional[str] = None,
    ) -> None:
        """Keep the callback of the quick panel."""
        self.on_pick = on_done

    def show_input_panel(
        self,
        caption: str,
        initial_text: str,
        on_done: Callable[[str], None],
        on_change: Optional[Callable[[str], None]],
        on_cancel: Optional[Callable[[], None]],
    ) -> None:
        """Keep the callback of the input panel."""
        self.on_enter = on_done

    def pick(self, index: int) -> None:
        """Select an item of the last quick panel shown."""
        assert self.on_pick is not None, "no quick panel was shown"
        self.on_pick(index)

    def enter(self, text: str) -> None:
        """Submit a text to the last input panel shown."""
        assert self.on_enter is not None, "no input panel was shown"
        self.on_enter(text)


class TestPortfolioManagerPathSafety(unittest.TestCase):
    """
    Issue #16: a portfolio JSON is shared data, so none of its fields may choose the file to delete or move.

    A loaded portfolio is deleted or disabled through the path recorded when it was loaded, and only if that
    file sits directly in portfolios/; a disabled portfolio is deleted only if its file sits directly in
    disabled_portfolios/. Either way, the file must still hold the portfolio: it is read again, and must carry
    exactly its name. A symlink placed in the folder stays a symlink: if the action goes on, it deletes or moves
    the link, never its target, and the disable never writes through a link at its destination.
    """

    MOTIVE_NOT_RECORDED = "No file recorded for portfolio"
    MOTIVE_OUTSIDE_PORTFOLIOS = "is outside portfolios/"
    MOTIVE_OUTSIDE_DISABLED = "is outside disabled_portfolios/"
    MOTIVE_MISSING = "Portfolio file does not exist"
    MOTIVE_NO_LONGER_HOLDS = "no longer holds portfolio"
    MOTIVE_UNREADABLE = "is unreadable"
    MOTIVE_NOT_REGULAR = "(not a regular file)"
    MOTIVE_NOT_OBJECT = "(not a JSON object)"
    MOTIVE_DESTINATION_TAKEN = "already exists in disabled_portfolios/"
    MOTIVE_NAME_NOT_JSON = 'must have a name that ends with ".json" in lowercase (rename it, then reload portfolios)'

    # Items of the Edit Pattern submenu
    EDIT_ITEMS: ClassVar[Dict[str, int]] = {"name": 0, "regex": 2}
    EDIT_DONE = 4

    LONG_NAME = "x" * 300

    # A JSON root that is a string, not an object: it holds no portfolio, though it contains every field name
    UNREADABLE_STRING_ROOT = json.dumps("name description version patterns")
    # Arrays nested so deep that decoding them raises RecursionError
    UNREADABLE_DEEP_NESTING = "[" * 100000 + "]" * 100000

    def setUp(self) -> None:
        """Build a throwaway folder that plays Sublime Text's Packages, with fresh singletons."""
        self.sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.sandbox), ignore_errors=True)
        self.addCleanup(self._reset_singletons)
        self._reset_singletons()

        self.settings_manager = SettingsManager()
        self.portfolio_manager = PortfolioManager.get_instance()
        self.portfolio_service = PortfolioService(portfolio_manager=self.portfolio_manager)
        self.command = PortfolioManagerCommand(
            portfolio_service=self.portfolio_service,
            settings_manager=self.settings_manager,
        )

        self.portfolios_dir = self.sandbox / "User" / "RegexLab" / "portfolios"
        self.disabled_dir = self.sandbox / "User" / "RegexLab" / "disabled_portfolios"
        self.portfolios_dir.mkdir(parents=True)
        self.disabled_dir.mkdir(parents=True)

        self.events: List[Tuple[str, str]] = []
        self.command.logger = _RecordingLogger(self.events)
        self.window = _TimelineWindow(self.events)
        self.window.extract_vars = {"packages": str(self.sandbox)}

        # The command reopens the Portfolio Manager after an action: keep it closed
        run_patcher = patch.object(self.command, "run")
        run_patcher.start()
        self.addCleanup(run_patcher.stop)

    @staticmethod
    def _reset_singletons() -> None:
        """Forget the settings and portfolio managers, so that their state does not cross tests."""
        SettingsManager._instance = None
        PortfolioManager._instance = None

    def _write_portfolio(self, path: Path, name: str) -> Path:
        """Write a minimal valid portfolio file that carries the given name."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"name": name, "description": "", "version": "1.0.0", "patterns": []}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _write_victim(self, path: Path) -> Path:
        """Write a JSON file that is not a portfolio (a project or tool configuration, say)."""
        path.write_text('{"important": true}', encoding="utf-8")
        return path

    def _load(self, path: Path) -> Portfolio:
        """Load a portfolio file as the plugin does, which records the path it was loaded from."""
        return self.portfolio_manager.load_portfolio(path, set_as_builtin=False, reload=False)

    def _load_like_startup(self) -> None:
        """Load portfolios/ as plugin_loaded does: sorted file names, and a name already loaded is skipped."""
        for path in sorted(self.portfolios_dir.glob("*.json")):
            try:
                self._load(path)
            except ValueError:
                pass

    def _reload_like_command(self, builtin_dir: Path) -> None:
        """
        Load portfolios as the Reload Portfolios command of RegexLab.py does.

        It forgets every portfolio, then loads builtin_dir (its first file becomes the principal built-in) and
        portfolios/, all with reload=True: a file loaded later takes over a name already loaded.
        """
        self.portfolio_manager._loaded_portfolios.clear()
        self.portfolio_manager._builtin_portfolio = None
        self.portfolio_manager._portfolio_paths.clear()
        files = [(path, True) for path in sorted(builtin_dir.glob("*.json"))]
        files += [(path, False) for path in sorted(self.portfolios_dir.glob("*.json"))]
        first_builtin = True
        for path, is_builtin in files:
            self.portfolio_manager.load_portfolio(path, set_as_builtin=is_builtin and first_builtin, reload=True)
            if is_builtin:
                first_builtin = False

    def _recorded_path(self, name: str) -> Optional[Path]:
        """Return the path recorded when the portfolio of this name was loaded, if any."""
        return self.portfolio_manager._portfolio_paths.get(name)

    def _load_mine_edited(self, pattern_field: str, text: str) -> Tuple[Portfolio, Path]:
        """
        Save and load 'Mine' (patterns P1 and P2), then set a field of P1 through Edit Pattern, as a user does.

        Edit Pattern saves the portfolio to the file it was loaded from, and saves what it is given: it neither
        compiles a regex nor checks that a pattern name is unique.
        """
        own_file = self.portfolios_dir / "mine.json"
        mine = Portfolio(
            name="Mine",
            patterns=[
                Pattern(name="P1", regex="foo", type=PatternType.STATIC),
                Pattern(name="P2", regex="bar", type=PatternType.STATIC),
            ],
        )
        self.portfolio_service.save_portfolio(mine, str(own_file))
        portfolio = self._load(own_file)
        pattern = portfolio.get_pattern("P1")
        assert pattern is not None  # Type narrowing for mypy

        window = _EditPatternWindow()
        EditPatternCommand(portfolio_service=self.portfolio_service).run(window, pattern, portfolio)
        window.pick(self.EDIT_ITEMS[pattern_field])
        window.enter(text)
        window.pick(self.EDIT_DONE)

        saved = json.loads(own_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["patterns"][0][pattern_field], text, "Edit Pattern did not save the change")
        return portfolio, own_file

    def _save_as_disabled(self, portfolio: Portfolio) -> Path:
        """Save a portfolio to disabled_portfolios/ with save_portfolio; the Portfolio Manager must list it."""
        path = self.disabled_dir / "mine.json"
        self.portfolio_service.save_portfolio(portfolio, str(path))
        listed = [metadata["name"] for _, metadata in self.portfolio_service.get_disabled_portfolios(str(self.sandbox))]
        self.assertEqual(listed, [portfolio.name], "the disabled portfolio is not listed")
        return path

    def _listed_disabled_files(self, packages: Path) -> List[str]:
        """Return the names of the files that the list of disabled portfolios shows for this Packages folder."""
        return [os.path.basename(path) for path, _ in self.portfolio_service.get_disabled_portfolios(str(packages))]

    def _import_then_disable(self, file_name: str, name: str) -> bytes:
        """
        Import a file that carries name, as a user does, then disable the portfolio; return the imported file's content.

        Import admits a file whose name ends with ".json" in any case (it compares the lowercase name), and copies it
        to the portfolios/ folder of the window's Packages under its own name. The caller checks what the disable did.
        """
        source = self._write_portfolio(Path(self.window.extract_vars["packages"]) / "shared" / file_name, name)
        self.command._action_import_portfolio(self.window)
        on_done = self.window.file_dialog_callback
        assert on_done is not None  # Type narrowing for mypy
        on_done(str(source))
        own_file = self._recorded_path(name)
        self.assertIsNotNone(own_file, "Import did not load the portfolio")
        assert own_file is not None  # Type narrowing for mypy
        self.assertEqual(own_file.name, file_name, "Import did not keep the file's name")
        portfolio = self.portfolio_manager.get_portfolio(name)
        assert portfolio is not None  # Type narrowing for mypy

        self.command._disable_portfolio(self.window, portfolio)

        return source.read_bytes()

    def _run_without_escape(self, action: Callable[[], None]) -> None:
        """Run action: an exception that escapes it fails the test."""
        try:
            action()
        except Exception as e:
            self.fail(f"an exception escaped the action: {e!r}\n{traceback.format_exc()}")

    def _symlink_or_skip(self, link: Path, target: Path) -> None:
        """Create a symlink, or skip the test where the system refuses symlinks; any other error fails it."""
        try:
            os.symlink(str(target), str(link), target_is_directory=target.is_dir())
        except (OSError, NotImplementedError) as e:
            if not _symlinks_refused(e):
                raise
            self.skipTest(f"symlinks not available here: {e}")

    def _run_recording_file_operations(self, action: Callable[[], None]) -> List[str]:
        """
        Run action with os.remove and shutil.move replaced by recorders; return what they were asked.

        The action must answer, never let an exception out: one that escapes fails the test.
        """
        operations: List[str] = []
        with patch("os.remove", side_effect=lambda path: operations.append(f"remove {path}")), patch(
            "shutil.move", side_effect=lambda source, dest: operations.append(f"move {source} -> {dest}")
        ):
            self._run_without_escape(action)
        return operations

    @staticmethod
    def _raising_permission_error(method: Callable[..., Any], target: Path) -> Callable[..., Any]:
        """Wrap a Path method so that it raises PermissionError on target, as a system that denies access does."""

        def guarded(path: Path, *args: Any, **kwargs: Any) -> Any:
            if path == target:
                raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), str(path))
            return method(path, *args, **kwargs)

        return guarded

    @staticmethod
    def _opening_too_large_to_read(method: Callable[..., Any], target: Path) -> Callable[..., Any]:
        """Wrap Path.open so that target opens as a stream whose read raises MemoryError; other paths open as usual."""

        def guarded(path: Path, *args: Any, **kwargs: Any) -> Any:
            if path == target:
                return _TooLargeToRead()
            return method(path, *args, **kwargs)

        return guarded

    @contextlib.contextmanager
    def _name_too_long(self, marker: str) -> Iterator[List[str]]:
        """
        Make the calls listed in targets fail with ENAMETOOLONG on a path that holds marker; yield those calls.

        A real system refuses such a path as well, with an error and an errno that vary by system and Python
        version: for the calls it lists, the simulation answers the same everywhere. They look up, open,
        delete, move or copy a file through os, os.path, shutil, pathlib and open(). Each layer is patched on
        its own: pathlib in Python 3.8 keeps its own references to the os functions, and on Windows with
        Python 3.13, os.path.exists, lexists, isfile, isdir and islink are built-in functions that do not call
        os.stat. A call left out of targets is not seen.
        """
        calls: List[str] = []

        def guard(function: Callable[..., Any]) -> Callable[..., Any]:
            def guarded(*args: Any, **kwargs: Any) -> Any:
                if any(marker in str(arg) for arg in args):
                    calls.append(f"{function.__name__} {args[0]}")
                    raise OSError(errno.ENAMETOOLONG, os.strerror(errno.ENAMETOOLONG), str(args[0]))
                return function(*args, **kwargs)

            return guarded

        targets = [
            (os, "stat"),
            (os, "lstat"),
            (os, "open"),
            (os, "remove"),
            (os, "unlink"),
            (os, "rename"),
            (os, "replace"),
            (os.path, "exists"),
            (os.path, "lexists"),
            (os.path, "isfile"),
            (os.path, "isdir"),
            (os.path, "islink"),
            (shutil, "move"),
            (shutil, "copy2"),
            (shutil, "copyfile"),
            (Path, "exists"),
            (Path, "is_file"),
            (Path, "is_dir"),
            (Path, "is_symlink"),
            (Path, "stat"),
            (Path, "lstat"),
            (Path, "open"),
            (Path, "read_text"),
            (Path, "read_bytes"),
            (Path, "unlink"),
            (Path, "rename"),
            (Path, "replace"),
            (builtins, "open"),
            (io, "open"),
        ]
        with contextlib.ExitStack() as stack:
            for owner, attribute in targets:
                stack.enter_context(patch.object(owner, attribute, guard(getattr(owner, attribute))))
            yield calls

    def _assert_refused(self, operations: List[str], motive: str) -> None:
        """A refusal: no file operation, then a warning and a status message that give the motive, in that order."""
        self.assertEqual(operations, [], "a file operation ran")
        self._assert_motive(motive)

    def _assert_motive(self, motive: str) -> None:
        """A warning, then a status message, both giving the motive."""
        warnings = [i for i, (level, message) in enumerate(self.events) if level == "warning" and motive in message]
        statuses = [i for i, (level, message) in enumerate(self.events) if level == "status" and motive in message]
        self.assertTrue(warnings, f"no warning gives the motive {motive!r}: {self.events}")
        self.assertTrue(statuses, f"no status message gives the motive {motive!r}: {self.events}")
        self.assertLess(warnings[0], statuses[0], "the status message came before the warning")

    def _assert_no_warning(self) -> None:
        """A legitimate action: nothing was logged at warning level or above."""
        problems = [(level, message) for level, message in self.events if level in ("warning", "error")]
        self.assertEqual(problems, [], "a legitimate action was refused or failed")

    def _assert_disable_refused_for_name(self, file_name: str, name: str, content: bytes) -> None:
        """
        The disable of a portfolio loaded from portfolios/file_name was refused for the file's name: nothing moved,
        the portfolio is still loaded from that file, and a warning, then a status message, give the motive, which
        names the portfolio and ends with the file's path.
        """
        own_file = self.portfolios_dir / file_name
        self.assertEqual(os.listdir(str(self.portfolios_dir)), [file_name], "the portfolio's file left portfolios/")
        self.assertEqual(own_file.read_bytes(), content, "the portfolio's file was changed")
        self.assertEqual(os.listdir(str(self.disabled_dir)), [], "disabled_portfolios/ was changed")
        self.assertTrue(self.portfolio_manager.is_loaded(name), "a refused disable unloaded the portfolio")
        self.assertEqual(self._recorded_path(name), own_file, "the recorded file changed")
        self._assert_motive(self.MOTIVE_NAME_NOT_JSON)
        warning = next(m for level, m in self.events if level == "warning" and self.MOTIVE_NAME_NOT_JSON in m)
        self.assertIn(f"File of portfolio '{name}' ", warning, "the refusal does not name the portfolio")
        self.assertTrue(warning.endswith(str(own_file)), f"the refusal does not end with the file's path: {warning}")

    # Traversal through the name of a loaded portfolio

    def test_delete_loaded_name_with_dot_dot_spares_outside_file(self) -> None:
        """'../../../victim' deletes the file the portfolio was loaded from, never Packages/victim.json."""
        victim = self._write_victim(self.sandbox / "victim.json")
        own_file = self._write_portfolio(self.portfolios_dir / "shared_from_a_friend.json", "../../../victim")
        self._load(own_file)
        self.assertEqual(self._recorded_path("../../../victim"), own_file)

        self.command._execute_delete(self.window, "../../../victim", None)

        self.assertTrue(victim.exists(), "a file outside portfolios/ was deleted")
        self.assertFalse(own_file.exists(), "the portfolio's file is still there")
        self.assertFalse(self.portfolio_manager.is_loaded("../../../victim"), "the portfolio is still loaded")

    def test_delete_loaded_name_with_backslashes_spares_outside_file(self) -> None:
        """
        '..\\..\\..\\victim' deletes the file the portfolio was loaded from, never Packages/victim.json.

        Platform: the name climbs out of portfolios/ only where backslash separates paths (Windows); elsewhere
        this test already passes on the code before the fix.
        """
        victim = self._write_victim(self.sandbox / "victim.json")
        own_file = self._write_portfolio(self.portfolios_dir / "shared_from_a_friend.json", "..\\..\\..\\victim")
        self._load(own_file)
        self.assertEqual(self._recorded_path("..\\..\\..\\victim"), own_file)

        self.command._execute_delete(self.window, "..\\..\\..\\victim", None)

        self.assertTrue(victim.exists(), "a file outside portfolios/ was deleted")
        self.assertFalse(own_file.exists(), "the portfolio's file is still there")

    def test_delete_loaded_absolute_path_name_spares_outside_file(self) -> None:
        """
        A name that holds an absolute path spares the file it points to.

        Platform: before the fix, the path built from the name is lowercased and its spaces become
        underscores, so it reaches the file only where the temporary folder's path has no space, and on a
        case-insensitive file system or where that path has no capital letter.
        """
        victim = self._write_victim(self.sandbox / "abs_victim.json")
        name = str(self.sandbox / "abs_victim")
        own_file = self._write_portfolio(self.portfolios_dir / "shared_from_a_friend.json", name)
        self._load(own_file)
        self.assertEqual(self._recorded_path(name), own_file)

        self.command._execute_delete(self.window, name, None)

        self.assertTrue(victim.exists(), "a file outside portfolios/ was deleted")
        self.assertFalse(own_file.exists(), "the portfolio's file is still there")

    # Collision: the file named after the portfolio holds another portfolio

    def test_delete_loaded_spares_file_named_after_it(self) -> None:
        """'Foo Bar' was loaded from b.json: foo_bar.json, which holds another portfolio, survives."""
        other = self._write_portfolio(self.portfolios_dir / "foo_bar.json", "Other Portfolio")
        own_file = self._write_portfolio(self.portfolios_dir / "b.json", "Foo Bar")
        self._load_like_startup()
        self.assertEqual(self._recorded_path("Foo Bar"), own_file)

        self.command._execute_delete(self.window, "Foo Bar", None)

        self.assertTrue(other.exists(), "another portfolio's file was deleted")
        self.assertFalse(own_file.exists(), "the portfolio's file is still there")

    def test_disable_spares_file_named_after_it(self) -> None:
        """Disabling 'Foo Bar', loaded from b.json, moves b.json and leaves foo_bar.json in place."""
        other = self._write_portfolio(self.portfolios_dir / "foo_bar.json", "Other Portfolio")
        own_file = self._write_portfolio(self.portfolios_dir / "b.json", "Foo Bar")
        self._load_like_startup()
        self.assertEqual(self._recorded_path("Foo Bar"), own_file)
        portfolio = self.portfolio_manager.get_portfolio("Foo Bar")
        assert portfolio is not None  # Type narrowing for mypy

        self.command._disable_portfolio(self.window, portfolio)

        self.assertTrue(other.exists(), "another portfolio's file was moved")
        self.assertFalse((self.disabled_dir / "foo_bar.json").exists(), "another portfolio was disabled")
        self.assertTrue((self.disabled_dir / "b.json").exists(), "the portfolio's file was not moved")
        self.assertFalse(own_file.exists(), "the portfolio's file is still in portfolios/")

    # Two files carry the same name: only the one loaded is acted on

    def test_delete_duplicate_name_acts_on_loaded_file_only(self) -> None:
        """a.json and foo_bar.json both carry 'Foo Bar'; startup loads a.json and skips foo_bar.json."""
        loaded_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo Bar")
        duplicate = self._write_portfolio(self.portfolios_dir / "foo_bar.json", "Foo Bar")
        content = duplicate.read_bytes()
        self._load_like_startup()
        self.assertEqual(self._recorded_path("Foo Bar"), loaded_file)

        self.command._execute_delete(self.window, "Foo Bar", None)

        self.assertTrue(duplicate.exists(), "the file that was not loaded was deleted")
        self.assertEqual(duplicate.read_bytes(), content, "the file that was not loaded was changed")
        self.assertFalse(loaded_file.exists(), "the loaded file is still there")

    def test_disable_duplicate_name_acts_on_loaded_file_only(self) -> None:
        """Disabling 'Foo Bar' moves a.json, which startup loaded, and leaves foo_bar.json in place."""
        loaded_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo Bar")
        duplicate = self._write_portfolio(self.portfolios_dir / "foo_bar.json", "Foo Bar")
        content = duplicate.read_bytes()
        self._load_like_startup()
        self.assertEqual(self._recorded_path("Foo Bar"), loaded_file)
        portfolio = self.portfolio_manager.get_portfolio("Foo Bar")
        assert portfolio is not None  # Type narrowing for mypy

        self.command._disable_portfolio(self.window, portfolio)

        self.assertTrue(duplicate.exists(), "the file that was not loaded was moved")
        self.assertEqual(duplicate.read_bytes(), content, "the file that was not loaded was changed")
        self.assertFalse((self.disabled_dir / "foo_bar.json").exists(), "the file that was not loaded was disabled")
        self.assertTrue((self.disabled_dir / "a.json").exists(), "the loaded file was not moved")
        self.assertFalse(loaded_file.exists(), "the loaded file is still in portfolios/")

    # A name too long for a file name: no path built from it is used

    def test_delete_long_name_uses_recorded_file(self) -> None:
        """A 300-character name: its recorded file is deleted, and no watched call gets a path built from the name."""
        own_file = self._write_portfolio(self.portfolios_dir / "long_name.json", self.LONG_NAME)
        self._load(own_file)
        self.assertEqual(self._recorded_path(self.LONG_NAME), own_file)

        with self._name_too_long(self.LONG_NAME) as calls:
            self.command._execute_delete(self.window, self.LONG_NAME, None)

        self.assertEqual(calls, [], "a path built from the name was used")
        self.assertFalse(own_file.exists(), "the portfolio's file is still there")
        self.assertFalse(self.portfolio_manager.is_loaded(self.LONG_NAME), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_disable_long_name_uses_recorded_file(self) -> None:
        """A 300-character name: its recorded file is moved, and no watched call gets a path built from the name."""
        own_file = self._write_portfolio(self.portfolios_dir / "long_name.json", self.LONG_NAME)
        portfolio = self._load(own_file)
        self.assertEqual(self._recorded_path(self.LONG_NAME), own_file)

        with self._name_too_long(self.LONG_NAME) as calls:
            self.command._disable_portfolio(self.window, portfolio)

        self.assertEqual(calls, [], "a path built from the name was used")
        self.assertTrue((self.disabled_dir / "long_name.json").exists(), "the portfolio's file was not moved")
        self.assertFalse(own_file.exists(), "the portfolio's file is still in portfolios/")
        self._assert_no_warning()

    # Every refusal: no file operation, then a warning and a status message that give its motive

    def test_delete_without_recorded_file_is_refused(self) -> None:
        """No file is recorded for '../../../victim', which is not loaded: refused, and Packages/victim.json stays."""
        victim = self._write_victim(self.sandbox / "victim.json")
        self.assertIsNone(self._recorded_path("../../../victim"))

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "../../../victim", None)
        )

        self._assert_refused(operations, self.MOTIVE_NOT_RECORDED)
        self.assertTrue(victim.exists())

    def test_disable_without_recorded_file_is_refused(self) -> None:
        """No file is recorded for 'Ghost Town'; ghost_town.json holds another portfolio: refused, nothing moved."""
        other = self._write_portfolio(self.portfolios_dir / "ghost_town.json", "Other Portfolio")
        self._load_like_startup()
        self.assertIsNone(self._recorded_path("Ghost Town"))

        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, Portfolio(name="Ghost Town"))
        )

        self._assert_refused(operations, self.MOTIVE_NOT_RECORDED)
        self.assertTrue(other.exists())

    def test_disable_refusal_is_logged_under_its_action(self) -> None:
        """A refused disable is logged under its own action, as 'Disable portfolio refused: ...'."""
        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, Portfolio(name="Ghost Town"))
        )

        self._assert_refused(operations, self.MOTIVE_NOT_RECORDED)
        prefixed = [m for level, m in self.events if level == "warning" and m.startswith("Disable portfolio refused: ")]
        self.assertTrue(prefixed, f"no warning names the action: {self.events}")

    def test_delete_recorded_file_outside_folder_is_refused(self) -> None:
        """A portfolio loaded from builtin_portfolios/ is not deleted: its file is outside portfolios/."""
        builtin_file = self._write_portfolio(
            self.sandbox / "User" / "RegexLab" / "builtin_portfolios" / "regexlab.json", "RegexLab"
        )
        self._load(builtin_file)
        self.assertEqual(self._recorded_path("RegexLab"), builtin_file)

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "RegexLab", None)
        )

        self._assert_refused(operations, self.MOTIVE_OUTSIDE_PORTFOLIOS)
        self.assertTrue(builtin_file.exists())
        self.assertTrue(self.portfolio_manager.is_loaded("RegexLab"), "a refused delete unloaded the portfolio")

    def test_disable_recorded_file_outside_folder_is_refused(self) -> None:
        """A portfolio loaded from builtin_portfolios/ is not disabled: its file is outside portfolios/."""
        builtin_file = self._write_portfolio(
            self.sandbox / "User" / "RegexLab" / "builtin_portfolios" / "regexlab.json", "RegexLab"
        )
        portfolio = self._load(builtin_file)
        self.assertEqual(self._recorded_path("RegexLab"), builtin_file)

        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, portfolio)
        )

        self._assert_refused(operations, self.MOTIVE_OUTSIDE_PORTFOLIOS)
        self.assertTrue(builtin_file.exists())
        self.assertTrue(self.portfolio_manager.is_loaded("RegexLab"), "a refused disable unloaded the portfolio")

    def test_delete_recorded_file_missing_is_refused(self) -> None:
        """The file 'Gone' was loaded from has been removed: refused, and other.json, which also carries it, stays."""
        own_file = self._write_portfolio(self.portfolios_dir / "gone.json", "Gone")
        self._load(own_file)
        other = self._write_portfolio(self.portfolios_dir / "other.json", "Gone")
        own_file.unlink()
        self.assertEqual(self._recorded_path("Gone"), own_file)
        self.assertFalse(os.path.lexists(str(own_file)))

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "Gone", None)
        )

        self._assert_refused(operations, self.MOTIVE_MISSING)
        self.assertTrue(other.exists())

    def test_disable_recorded_file_missing_is_refused(self) -> None:
        """The file 'Gone' was loaded from has been removed: refused, and other.json, which also carries it, stays."""
        own_file = self._write_portfolio(self.portfolios_dir / "gone.json", "Gone")
        portfolio = self._load(own_file)
        other = self._write_portfolio(self.portfolios_dir / "other.json", "Gone")
        own_file.unlink()
        self.assertEqual(self._recorded_path("Gone"), own_file)
        self.assertFalse(os.path.lexists(str(own_file)))

        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, portfolio)
        )

        self._assert_refused(operations, self.MOTIVE_MISSING)
        self.assertTrue(other.exists())

    # The file is read again for its name, not its validity: a file that still carries the portfolio's name is
    # acted on, be it reduced to that name, holding patterns that loading rejects, or a listed disabled portfolio

    def test_delete_name_only_portfolio_is_deleted(self) -> None:
        """A portfolio loaded from a file that holds only its name is deleted: no false refusal."""
        own_file = self.portfolios_dir / "minimal.json"
        own_file.write_text(json.dumps({"name": "Minimal"}), encoding="utf-8")
        self._load(own_file)
        self.assertEqual(self._recorded_path("Minimal"), own_file)

        self.command._execute_delete(self.window, "Minimal", None)

        self.assertFalse(own_file.exists(), "the portfolio's file is still there")
        self.assertFalse(self.portfolio_manager.is_loaded("Minimal"), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_disable_name_only_portfolio_is_moved(self) -> None:
        """A portfolio loaded from a file that holds only its name is disabled: no false refusal."""
        own_file = self.portfolios_dir / "minimal.json"
        own_file.write_text(json.dumps({"name": "Minimal"}), encoding="utf-8")
        content = own_file.read_bytes()
        portfolio = self._load(own_file)
        self.assertEqual(self._recorded_path("Minimal"), own_file)

        self.command._disable_portfolio(self.window, portfolio)

        disabled_file = self.disabled_dir / "minimal.json"
        self.assertTrue(disabled_file.exists(), "the portfolio's file was not moved")
        self.assertEqual(disabled_file.read_bytes(), content, "the portfolio's file was changed")
        self.assertFalse(own_file.exists(), "the portfolio's file is still in portfolios/")
        self.assertFalse(self.portfolio_manager.is_loaded("Minimal"), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_delete_non_ascii_name_saved_by_plugin_is_deleted(self) -> None:
        """
        save_portfolio writes a name that is not ASCII as it is, in UTF-8: the re-read decodes it as UTF-8, whatever
        the system's encoding, and the delete goes on.
        """
        name = "Caf\N{LATIN SMALL LETTER E WITH ACUTE} \N{HOT BEVERAGE}"
        own_file = self.portfolios_dir / "cafe.json"
        self.portfolio_service.save_portfolio(Portfolio(name=name), str(own_file))
        self.assertIn(name.encode("utf-8"), own_file.read_bytes(), "the name was not written unescaped in UTF-8")
        self._load(own_file)

        self.command._execute_delete(self.window, name, None)

        self.assertFalse(own_file.exists(), "the portfolio's file is still there")
        self.assertFalse(self.portfolio_manager.is_loaded(name), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_delete_after_edit_pattern_saved_invalid_regex(self) -> None:
        """Edit Pattern saved P1 as '(foo', which loading rejects: deleting 'Mine' still deletes its file."""
        _, own_file = self._load_mine_edited("regex", "(foo")
        with self.assertRaises(ValueError):
            self.portfolio_manager.load_portfolio_from_file(own_file)

        self.command._execute_delete(self.window, "Mine", None)

        self.assertFalse(own_file.exists(), "the portfolio's file is still there")
        self.assertFalse(self.portfolio_manager.is_loaded("Mine"), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_disable_after_edit_pattern_saved_invalid_regex(self) -> None:
        """Edit Pattern saved P1 as '(foo', which loading rejects: disabling 'Mine' still moves its file."""
        portfolio, own_file = self._load_mine_edited("regex", "(foo")
        content = own_file.read_bytes()
        with self.assertRaises(ValueError):
            self.portfolio_manager.load_portfolio_from_file(own_file)

        self.command._disable_portfolio(self.window, portfolio)

        disabled_file = self.disabled_dir / "mine.json"
        self.assertTrue(disabled_file.exists(), "the portfolio's file was not moved")
        self.assertEqual(disabled_file.read_bytes(), content, "the portfolio's file was changed")
        self.assertFalse(own_file.exists(), "the portfolio's file is still in portfolios/")
        self.assertFalse(self.portfolio_manager.is_loaded("Mine"), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_delete_after_edit_pattern_saved_duplicate_name(self) -> None:
        """
        Edit Pattern renamed P1 to P2, so two patterns share a name, which loading rejects: deleting 'Mine' still
        deletes its file.
        """
        _, own_file = self._load_mine_edited("name", "P2")
        with self.assertRaises(ValueError):
            self.portfolio_manager.load_portfolio_from_file(own_file)

        self.command._execute_delete(self.window, "Mine", None)

        self.assertFalse(own_file.exists(), "the portfolio's file is still there")
        self.assertFalse(self.portfolio_manager.is_loaded("Mine"), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_disable_after_edit_pattern_saved_duplicate_name(self) -> None:
        """
        Edit Pattern renamed P1 to P2, so two patterns share a name, which loading rejects: disabling 'Mine' still
        moves its file.
        """
        portfolio, own_file = self._load_mine_edited("name", "P2")
        content = own_file.read_bytes()
        with self.assertRaises(ValueError):
            self.portfolio_manager.load_portfolio_from_file(own_file)

        self.command._disable_portfolio(self.window, portfolio)

        disabled_file = self.disabled_dir / "mine.json"
        self.assertTrue(disabled_file.exists(), "the portfolio's file was not moved")
        self.assertEqual(disabled_file.read_bytes(), content, "the portfolio's file was changed")
        self.assertFalse(own_file.exists(), "the portfolio's file is still in portfolios/")
        self.assertFalse(self.portfolio_manager.is_loaded("Mine"), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_delete_with_repeat_count_too_large(self) -> None:
        """
        Edit Pattern saved P1 as 'a{4294967296}', on which compiling raises OverflowError: deleting 'Mine' deletes
        its file, and no exception escapes.
        """
        _, own_file = self._load_mine_edited("regex", "a{4294967296}")
        with self.assertRaises(OverflowError):
            self.portfolio_manager.load_portfolio_from_file(own_file)

        self._run_without_escape(lambda: self.command._execute_delete(self.window, "Mine", None))

        self.assertFalse(own_file.exists(), "the portfolio's file is still there")
        self.assertFalse(self.portfolio_manager.is_loaded("Mine"), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_disable_with_repeat_count_too_large(self) -> None:
        """
        Edit Pattern saved P1 as 'a{4294967296}', on which compiling raises OverflowError: disabling 'Mine' moves
        its file, and no exception escapes.
        """
        portfolio, own_file = self._load_mine_edited("regex", "a{4294967296}")
        content = own_file.read_bytes()
        with self.assertRaises(OverflowError):
            self.portfolio_manager.load_portfolio_from_file(own_file)

        self._run_without_escape(lambda: self.command._disable_portfolio(self.window, portfolio))

        disabled_file = self.disabled_dir / "mine.json"
        self.assertTrue(disabled_file.exists(), "the portfolio's file was not moved")
        self.assertEqual(disabled_file.read_bytes(), content, "the portfolio's file was changed")
        self.assertFalse(own_file.exists(), "the portfolio's file is still in portfolios/")
        self.assertFalse(self.portfolio_manager.is_loaded("Mine"), "the portfolio is still loaded")
        self._assert_no_warning()

    def test_delete_disabled_with_repeat_count_too_large(self) -> None:
        """
        A listed disabled portfolio whose P1 is 'a{4294967296}', on which compiling raises OverflowError: deleting
        it deletes its file, and no exception escapes.
        """
        portfolio, _ = self._load_mine_edited("regex", "a{4294967296}")
        disabled_file = self._save_as_disabled(portfolio)
        with self.assertRaises(OverflowError):
            self.portfolio_manager.load_portfolio_from_file(disabled_file)

        self._run_without_escape(lambda: self.command._execute_delete(self.window, "Mine", str(disabled_file)))

        self.assertFalse(disabled_file.exists(), "the disabled portfolio's file is still there")
        self._assert_no_warning()

    def test_delete_disabled_that_loading_rejects(self) -> None:
        """
        The Portfolio Manager lists a disabled portfolio whose P1 is '(foo', which loading rejects: deleting it
        deletes its file.
        """
        portfolio, _ = self._load_mine_edited("regex", "(foo")
        disabled_file = self._save_as_disabled(portfolio)
        with self.assertRaises(ValueError):
            self.portfolio_manager.load_portfolio_from_file(disabled_file)

        self.command._execute_delete(self.window, "Mine", str(disabled_file))

        self.assertFalse(disabled_file.exists(), "the disabled portfolio's file is still there")
        self._assert_no_warning()

    def test_delete_disabled_spares_loaded_homonym(self) -> None:
        """
        Deleting the disabled 'Mine' leaves the loaded 'Mine' alone: it stays loaded, and its file in portfolios/
        is unchanged.
        """
        portfolio, own_file = self._load_mine_edited("regex", "(foo")
        disabled_file = self._save_as_disabled(portfolio)
        own_content = own_file.read_bytes()

        self.command._execute_delete(self.window, "Mine", str(disabled_file))

        self.assertFalse(disabled_file.exists(), "the disabled portfolio's file is still there")
        self.assertEqual(own_file.read_bytes(), own_content, "the loaded portfolio's file was changed")
        self.assertTrue(self.portfolio_manager.is_loaded("Mine"), "the loaded homonym was unloaded")
        self._assert_no_warning()

    # The file must still hold the portfolio: a stale entry, a replaced file or an unreadable one is refused

    def test_delete_stale_entry_spares_file_saved_later_under_its_name(self) -> None:
        """
        A shared file named like the first built-in takes its entry on Reload, and deleting it cannot unload that
        name: the entry outlives the file. Deleting the stale entry again spares the portfolio saved since under
        the same file name.
        """
        builtin_dir = self.sandbox / "User" / "RegexLab" / "builtin_portfolios"
        self._write_portfolio(builtin_dir / "rxl_data.json", "RXL - Data")
        shared = self._write_portfolio(self.portfolios_dir / "evil.json", "RXL - Data")
        self._reload_like_command(builtin_dir)
        self.assertEqual(self._recorded_path("RXL - Data"), shared)
        self.command._execute_delete(self.window, "RXL - Data", None)
        self.assertFalse(os.path.lexists(str(shared)), "the first delete kept the shared file")
        self.assertEqual(self._recorded_path("RXL - Data"), shared, "the entry did not outlive its file")
        newcomer = self._write_portfolio(self.portfolios_dir / "evil.json", "Friend v2")
        self._load(newcomer)
        content = newcomer.read_bytes()
        self.events.clear()

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "RXL - Data", None)
        )

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self.assertEqual(newcomer.read_bytes(), content, "the new portfolio's file was changed")
        self.assertTrue(self.portfolio_manager.is_loaded("Friend v2"))

    def test_delete_replaced_file_is_refused(self) -> None:
        """a.json was loaded as 'Foo', then replaced by a file that holds 'Bar': deleting 'Foo' is refused."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        self._write_portfolio(own_file, "Bar")
        content = own_file.read_bytes()
        self.assertEqual(self._recorded_path("Foo"), own_file)

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self._assert_motive("reload portfolios")
        self.assertEqual(own_file.read_bytes(), content, "the replacing file was changed")
        self.assertTrue(self.portfolio_manager.is_loaded("Foo"), "a refused delete unloaded the portfolio")

    def test_delete_file_renamed_by_case_is_refused(self) -> None:
        """Names are compared exactly: a.json loaded as 'Foo' and now holding 'foo' no longer holds 'Foo'."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        self._write_portfolio(own_file, "foo")
        content = own_file.read_bytes()

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self.assertEqual(own_file.read_bytes(), content, "the replacing file was changed")

    def test_delete_file_renamed_with_trailing_blank_is_refused(self) -> None:
        """Names are compared exactly: a.json loaded as 'Foo' and now holding 'Foo ' no longer holds 'Foo'."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        self._write_portfolio(own_file, "Foo ")
        content = own_file.read_bytes()

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self.assertEqual(own_file.read_bytes(), content, "the replacing file was changed")

    def test_delete_file_renamed_in_other_unicode_form_is_refused(self) -> None:
        """
        Names are compared without Unicode normalization: a.json loaded as 'Café' with a precomposed 'é', and now
        holding 'Café' with a combining accent, no longer holds it, though both forms normalize to the same name.
        """
        precomposed = "Caf\N{LATIN SMALL LETTER E WITH ACUTE}"
        decomposed = "Cafe\N{COMBINING ACUTE ACCENT}"
        self.assertNotEqual(decomposed, precomposed)
        self.assertEqual(unicodedata.normalize("NFC", decomposed), precomposed)
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", precomposed)
        self._load(own_file)
        self._write_portfolio(own_file, decomposed)
        content = own_file.read_bytes()

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, precomposed, None)
        )

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self.assertEqual(own_file.read_bytes(), content, "the replacing file was changed")

    def test_delete_file_whose_name_became_a_number_is_refused(self) -> None:
        """Names are not converted: a.json loaded as '1', now named by the number 1, no longer holds it."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "1")
        self._load(own_file)
        data = {"name": 1, "description": "", "version": "1.0.0", "patterns": []}
        own_file.write_text(json.dumps(data), encoding="utf-8")
        content = own_file.read_bytes()

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "1", None))

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self.assertEqual(own_file.read_bytes(), content, "the replacing file was changed")

    def test_refused_delete_loads_nothing(self) -> None:
        """
        The re-read has no side effect: refusing to delete 'Foo', whose file now holds 'Bar', neither loads 'Bar'
        nor changes the paths recorded at loading.
        """
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        self._write_portfolio(own_file, "Bar")
        loaded = list(self.portfolio_manager._loaded_portfolios)
        recorded = dict(self.portfolio_manager._portfolio_paths)

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self.assertEqual(list(self.portfolio_manager._loaded_portfolios), loaded, "the re-read loaded a portfolio")
        self.assertEqual(self.portfolio_manager._portfolio_paths, recorded, "the re-read changed the recorded paths")

    def test_disable_replaced_file_is_refused(self) -> None:
        """a.json was loaded as 'Foo', then replaced by a file that holds 'Bar': disabling 'Foo' is refused."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        portfolio = self._load(own_file)
        self._write_portfolio(own_file, "Bar")
        content = own_file.read_bytes()
        self.assertEqual(self._recorded_path("Foo"), own_file)

        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, portfolio)
        )

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self.assertEqual(own_file.read_bytes(), content, "the replacing file was changed")
        self.assertTrue(self.portfolio_manager.is_loaded("Foo"), "a refused disable unloaded the portfolio")

    def test_delete_unreadable_string_root_is_refused(self) -> None:
        """a.json now holds a JSON string, not an object: the delete is refused as unreadable."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        own_file.write_text(self.UNREADABLE_STRING_ROOT, encoding="utf-8")

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self.assertTrue(own_file.exists())

    def test_delete_unreadable_deep_nesting_is_refused(self) -> None:
        """a.json now nests arrays so deep that decoding it raises RecursionError: refused as unreadable."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        own_file.write_text(self.UNREADABLE_DEEP_NESTING, encoding="utf-8")
        with self.assertRaises(RecursionError):
            self.portfolio_service.validate_portfolio_file(str(own_file))

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self.assertTrue(
            any(level == "warning" and "RecursionError" in message for level, message in self.events),
            f"no warning names the RecursionError: {self.events}",
        )
        self.assertTrue(own_file.exists())

    def test_delete_invalid_json_is_refused(self) -> None:
        """a.json is no longer valid JSON: the validator rejects it, and the delete is refused as unreadable."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        own_file.write_text("{ not json", encoding="utf-8")
        valid, _ = self.portfolio_service.validate_portfolio_file(str(own_file))
        self.assertFalse(valid)

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self.assertTrue(own_file.exists())

    def test_delete_file_not_in_utf8_is_refused(self) -> None:
        """
        a.json now holds a byte that is not UTF-8, which loading rejects too: the delete is refused as unreadable,
        with the error's class, and nothing escapes.
        """
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        own_file.write_bytes(b'{"name": "Foo", "description": "\xff", "version": "1.0.0", "patterns": []}')
        with self.assertRaises(ValueError):
            self.portfolio_manager.load_portfolio_from_file(own_file)

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self._assert_motive("(UnicodeDecodeError)")
        self.assertTrue(own_file.exists())

    def test_delete_file_with_utf8_bom_is_refused(self) -> None:
        """
        a.json now starts with a UTF-8 byte order mark, which loading rejects too: the delete is refused as
        unreadable.
        """
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        own_file.write_bytes(b"\xef\xbb\xbf" + own_file.read_bytes())
        with self.assertRaises(ValueError):
            self.portfolio_manager.load_portfolio_from_file(own_file)

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self.assertTrue(own_file.exists())

    def test_delete_json_array_root_is_refused(self) -> None:
        """a.json now holds a JSON array: the delete is refused as unreadable, the file holding no JSON object."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        own_file.write_text(json.dumps(["name", "Foo"]), encoding="utf-8")

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self._assert_motive(self.MOTIVE_NOT_OBJECT)
        self.assertTrue(own_file.exists())

    def test_delete_file_that_cannot_be_opened_is_refused(self) -> None:
        """Opening a.json fails with PermissionError: the delete is refused as unreadable, with the error's class."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)

        with patch.object(Path, "open", self._raising_permission_error(Path.open, own_file)):
            operations = self._run_recording_file_operations(
                lambda: self.command._execute_delete(self.window, "Foo", None)
            )

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self._assert_motive("(PermissionError)")
        self.assertTrue(own_file.exists())

    def test_delete_file_whose_status_cannot_be_read_is_refused(self) -> None:
        """
        Reading the status of a.json fails with PermissionError: the delete is refused as unreadable, with the
        error's class, rather than failing as an error of the action.
        """
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)

        with patch.object(Path, "is_file", self._raising_permission_error(Path.is_file, own_file)):
            operations = self._run_recording_file_operations(
                lambda: self.command._execute_delete(self.window, "Foo", None)
            )

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self._assert_motive("(PermissionError)")
        self.assertTrue(own_file.exists())

    def test_delete_memory_error_while_decoding_propagates(self) -> None:
        """
        MemoryError while decoding the JSON of a.json (raised by json.loads) makes no refusal: it propagates, as
        _checked_portfolio_file says, and a.json stays.
        """
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)

        with patch("json.loads", side_effect=MemoryError), self.assertRaises(MemoryError):
            self.command._execute_delete(self.window, "Foo", None)

        self.assertTrue(own_file.exists())
        self._assert_no_warning()
        self.assertEqual([m for level, m in self.events if level == "status"], [], "a status message was shown")

    def test_delete_memory_error_while_reading_propagates(self) -> None:
        """
        MemoryError while reading a.json (raised by the read of the opened file, before any decoding) makes no
        refusal either: it propagates, and a.json stays.
        """
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)

        too_large = self._opening_too_large_to_read(Path.open, own_file)
        with patch.object(Path, "open", too_large), self.assertRaises(MemoryError):
            self.command._execute_delete(self.window, "Foo", None)

        self.assertTrue(own_file.exists())
        self._assert_no_warning()
        self.assertEqual([m for level, m in self.events if level == "status"], [], "a status message was shown")

    def test_disable_unreadable_file_is_refused(self) -> None:
        """Disabling 'Foo', whose file now holds a JSON string, not an object: refused as unreadable, nothing moves."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        portfolio = self._load(own_file)
        own_file.write_text(self.UNREADABLE_STRING_ROOT, encoding="utf-8")

        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, portfolio)
        )

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self.assertTrue(own_file.exists())
        self.assertFalse((self.disabled_dir / "a.json").exists())

    def test_delete_recorded_path_now_a_directory_is_refused(self) -> None:
        """a.json, loaded as 'Foo', is now a directory: refused as not a regular file, and nothing is deleted."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        own_file.unlink()
        own_file.mkdir()

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_NOT_REGULAR)
        self._assert_motive(self.MOTIVE_UNREADABLE)
        self.assertTrue(own_file.is_dir())
        self.assertTrue(self.portfolio_manager.is_loaded("Foo"), "a refused delete unloaded the portfolio")

    def test_disable_recorded_path_now_a_directory_is_refused(self) -> None:
        """a.json, loaded as 'Foo', is now a directory: refused as not a regular file, and nothing is moved."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        portfolio = self._load(own_file)
        own_file.unlink()
        own_file.mkdir()

        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, portfolio)
        )

        self._assert_refused(operations, self.MOTIVE_NOT_REGULAR)
        self._assert_motive(self.MOTIVE_UNREADABLE)
        self.assertTrue(own_file.is_dir())
        self.assertFalse(os.path.lexists(str(self.disabled_dir / "a.json")))
        self.assertTrue(self.portfolio_manager.is_loaded("Foo"), "a refused disable unloaded the portfolio")

    def test_delete_object_without_name_is_refused(self) -> None:
        """a.json, loaded as 'Foo', now holds a JSON object without "name": it no longer holds 'Foo'."""
        own_file = self._write_portfolio(self.portfolios_dir / "a.json", "Foo")
        self._load(own_file)
        own_file.write_text(json.dumps({"description": "", "version": "1.0.0", "patterns": []}), encoding="utf-8")
        content = own_file.read_bytes()

        operations = self._run_recording_file_operations(lambda: self.command._execute_delete(self.window, "Foo", None))

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self.assertEqual(own_file.read_bytes(), content, "the replacing file was changed")

    # A disabled portfolio's file must sit directly in disabled_portfolios/

    def test_delete_disabled_outside_folder_is_refused(self) -> None:
        """A filepath outside disabled_portfolios/ is refused; nothing is deleted."""
        outside = self._write_portfolio(self.sandbox / "outside.json", "Outside")
        self.assertTrue(outside.exists())

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "Outside", str(outside))
        )

        self._assert_refused(operations, self.MOTIVE_OUTSIDE_DISABLED)
        self.assertTrue(outside.exists())

    def test_delete_disabled_dot_dot_filepath_is_refused(self) -> None:
        """A filepath that climbs out of disabled_portfolios/ with '..' is refused."""
        outside = self._write_portfolio(self.sandbox / "User" / "outside.json", "Outside")
        filepath = str(self.disabled_dir / ".." / ".." / "outside.json")
        self.assertTrue(os.path.exists(filepath))

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "Outside", filepath)
        )

        self._assert_refused(operations, self.MOTIVE_OUTSIDE_DISABLED)
        self.assertTrue(outside.exists())

    def test_delete_disabled_outside_file_holding_no_portfolio_is_refused_as_outside(self) -> None:
        """
        A filepath outside disabled_portfolios/ whose file holds no portfolio: the motive of the refusal is the
        folder, not the file's content.
        """
        outside = self._write_victim(self.sandbox / "outside.json")
        content = outside.read_bytes()

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "Outside", str(outside))
        )

        self._assert_refused(operations, self.MOTIVE_OUTSIDE_DISABLED)
        self.assertEqual(outside.read_bytes(), content)

    def test_delete_disabled_missing_outside_folder_is_refused_as_outside(self) -> None:
        """
        A filepath outside disabled_portfolios/ whose file does not exist: the folder is checked before the
        file's existence, so the motive is the folder.
        """
        filepath = str(self.sandbox / "nowhere.json")
        self.assertFalse(os.path.lexists(filepath))

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "Nowhere", filepath)
        )

        self._assert_refused(operations, self.MOTIVE_OUTSIDE_DISABLED)

    def test_delete_disabled_missing_file_is_refused(self) -> None:
        """A filepath of disabled_portfolios/ whose file has gone is refused."""
        filepath = str(self.disabled_dir / "gone.json")
        self.assertFalse(os.path.lexists(filepath))

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "Gone", filepath)
        )

        self._assert_refused(operations, self.MOTIVE_MISSING)

    def test_delete_disabled_inside_folder_is_deleted(self) -> None:
        """A disabled portfolio whose file sits directly in disabled_portfolios/ is deleted: no false refusal."""
        own_file = self._write_portfolio(self.disabled_dir / "old.json", "Old Portfolio")

        self.command._execute_delete(self.window, "Old Portfolio", str(own_file))

        self.assertFalse(own_file.exists(), "the disabled portfolio's file is still there")
        self.assertTrue(any("deleted" in message for message in self.window.status_messages))
        self._assert_no_warning()

    def test_delete_disabled_replaced_file_is_refused(self) -> None:
        """disabled_portfolios/old.json was listed as 'Old Portfolio' but now holds 'Other': the delete is refused."""
        own_file = self._write_portfolio(self.disabled_dir / "old.json", "Other")
        content = own_file.read_bytes()

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "Old Portfolio", str(own_file))
        )

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        self._assert_motive("reopen the Portfolio Manager")
        self.assertEqual(own_file.read_bytes(), content)

    # A symlink placed in the folder stays a symlink: an action on it never reaches its target

    def test_delete_loaded_symlink_removes_link_not_target(self) -> None:
        """
        portfolios/linked.json links to a file outside: deleting the portfolio removes the link only.

        Platform: skipped where the system refuses to create symlinks.
        """
        target = self._write_portfolio(self.sandbox / "outside_target.json", "Linked")
        content = target.read_bytes()
        link = self.portfolios_dir / "linked.json"
        self._symlink_or_skip(link, target)
        self._load(link)
        self.assertEqual(self._recorded_path("Linked"), link)

        self.command._execute_delete(self.window, "Linked", None)

        self.assertFalse(os.path.lexists(str(link)), "the link is still there")
        self.assertFalse(os.path.lexists(str(self.disabled_dir / "linked.json")), "the link was moved, not deleted")
        self.assertTrue(target.exists(), "the link's target was deleted")
        self.assertEqual(target.read_bytes(), content, "the link's target was changed")
        self._assert_no_warning()

    def test_disable_symlink_moves_link_not_target(self) -> None:
        """
        portfolios/linked.json links to a file outside: disabling the portfolio moves the link only.

        Platform: skipped where the system refuses to create symlinks.
        """
        target = self._write_portfolio(self.sandbox / "outside_target.json", "Linked")
        content = target.read_bytes()
        link = self.portfolios_dir / "linked.json"
        self._symlink_or_skip(link, target)
        portfolio = self._load(link)
        self.assertEqual(self._recorded_path("Linked"), link)
        self.assertTrue(os.path.islink(str(link)))

        self.command._disable_portfolio(self.window, portfolio)

        self.assertFalse(os.path.lexists(str(link)), "the link is still in portfolios/")
        self.assertTrue(os.path.islink(str(self.disabled_dir / "linked.json")), "the link was not moved")
        self.assertTrue(target.exists(), "the link's target was moved or deleted")
        self.assertEqual(target.read_bytes(), content, "the link's target was changed")
        self._assert_no_warning()

    def test_delete_disabled_symlink_removes_link_not_target(self) -> None:
        """
        disabled_portfolios/linked.json links to a file outside: deleting it removes the link only.

        Platform: skipped where the system refuses to create symlinks.
        """
        target = self._write_portfolio(self.sandbox / "outside_target.json", "Linked")
        content = target.read_bytes()
        link = self.disabled_dir / "linked.json"
        self._symlink_or_skip(link, target)
        self.assertTrue(os.path.islink(str(link)))

        self.command._execute_delete(self.window, "Linked", str(link))

        self.assertFalse(os.path.lexists(str(link)), "the link is still there")
        self.assertTrue(target.exists(), "the link's target was deleted")
        self.assertEqual(target.read_bytes(), content, "the link's target was changed")
        self._assert_no_warning()

    def test_delete_loaded_dangling_symlink_is_refused(self) -> None:
        """
        The target of portfolios/linked.json has gone: the link leads to no regular file, so the delete is refused
        as unreadable, and the link stays.

        Platform: skipped where the system refuses to create symlinks.
        """
        target = self._write_portfolio(self.sandbox / "outside_target.json", "Linked")
        link = self.portfolios_dir / "linked.json"
        self._symlink_or_skip(link, target)
        self._load(link)
        target.unlink()
        self.assertTrue(os.path.lexists(str(link)))
        self.assertFalse(os.path.exists(str(link)))

        operations = self._run_recording_file_operations(
            lambda: self.command._execute_delete(self.window, "Linked", None)
        )

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self._assert_motive(self.MOTIVE_NOT_REGULAR)
        self.assertTrue(os.path.islink(str(link)), "the dangling link is gone")

    def test_disable_dangling_symlink_is_refused(self) -> None:
        """
        The target of portfolios/linked.json has gone: the link leads to no regular file, so the disable is
        refused as unreadable, and the link stays in portfolios/.

        Platform: skipped where the system refuses to create symlinks.
        """
        target = self._write_portfolio(self.sandbox / "outside_target.json", "Linked")
        link = self.portfolios_dir / "linked.json"
        self._symlink_or_skip(link, target)
        portfolio = self._load(link)
        target.unlink()
        self.assertTrue(os.path.lexists(str(link)))
        self.assertFalse(os.path.exists(str(link)))

        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, portfolio)
        )

        self._assert_refused(operations, self.MOTIVE_UNREADABLE)
        self._assert_motive(self.MOTIVE_NOT_REGULAR)
        self.assertTrue(os.path.islink(str(link)), "the dangling link left portfolios/")
        self.assertFalse(os.path.lexists(str(self.disabled_dir / "linked.json")))

    # The disable never moves onto an entry of disabled_portfolios/, a dangling link included

    def test_disable_refuses_file_at_destination(self) -> None:
        """disabled_portfolios/mine.json already holds a portfolio: disabling 'Mine' is refused, both files intact."""
        own_file = self._write_portfolio(self.portfolios_dir / "mine.json", "Mine")
        own_content = own_file.read_bytes()
        portfolio = self._load(own_file)
        taken = self._write_portfolio(self.disabled_dir / "mine.json", "Old Mine")
        taken_content = taken.read_bytes()

        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, portfolio)
        )

        self._assert_refused(operations, self.MOTIVE_DESTINATION_TAKEN)
        self.assertEqual(own_file.read_bytes(), own_content, "the portfolio's file was changed")
        self.assertEqual(taken.read_bytes(), taken_content, "the file already disabled was changed")
        self.assertTrue(self.portfolio_manager.is_loaded("Mine"), "a refused disable unloaded the portfolio")

    def test_disable_refuses_dangling_link_at_destination(self) -> None:
        """
        disabled_portfolios/mine.json is a dangling link: disabling 'Mine' is refused, nothing is written to the
        link's target, and portfolios/mine.json stays.

        Platform: skipped where the system refuses to create symlinks. Before the fix, Windows wrote the portfolio
        through the link (the rename fails, then shutil.move copies the file) and POSIX replaced the link.
        """
        own_file = self._write_portfolio(self.portfolios_dir / "mine.json", "Mine")
        content = own_file.read_bytes()
        portfolio = self._load(own_file)
        outside = self.sandbox / "outside"
        outside.mkdir()
        target = outside / "linked.json"
        link = self.disabled_dir / "mine.json"
        self._symlink_or_skip(link, target)
        self.assertTrue(os.path.lexists(str(link)))
        self.assertFalse(os.path.lexists(str(target)))

        self.command._disable_portfolio(self.window, portfolio)

        self.assertFalse(os.path.lexists(str(target)), "the disable wrote through the dangling link")
        self.assertTrue(own_file.exists(), "the portfolio's file left portfolios/")
        self.assertEqual(own_file.read_bytes(), content, "the portfolio's file was changed")
        self.assertTrue(os.path.islink(str(link)), "the dangling link was replaced")
        self._assert_motive(self.MOTIVE_DESTINATION_TAKEN)
        self.assertTrue(self.portfolio_manager.is_loaded("Mine"), "a refused disable unloaded the portfolio")

    # The disable keeps the file's name, and refuses a file whose name does not end with ".json", which the list of
    # disabled portfolios would not show: a file that Import admitted with ".json" in capitals stays in portfolios/,
    # still loaded, and nothing appears in disabled_portfolios/

    def test_disable_after_import_of_upper_case_json_name_is_refused(self) -> None:
        """
        'Up', imported from UP.JSON, is not disabled, since the list of disabled portfolios would not show UP.JSON:
        the refusal gives its motive, and UP.JSON stays in portfolios/, unchanged, with 'Up' still loaded from it.
        """
        content = self._import_then_disable("UP.JSON", "Up")

        self._assert_disable_refused_for_name("UP.JSON", "Up", content)

    def test_disable_after_import_of_upper_case_json_name_and_other_portfolio_name_is_refused(self) -> None:
        """
        'Other', imported from UP.JSON, is not disabled either: the refusal depends on the file's name, not on the
        portfolio's name.
        """
        content = self._import_then_disable("UP.JSON", "Other")

        self._assert_disable_refused_for_name("UP.JSON", "Other", content)

    def test_refused_disable_of_upper_case_json_name_leaves_nothing_to_enable(self) -> None:
        """
        After the refused disable of 'Up', imported from UP.JSON, the list of disabled portfolios is empty: there is
        nothing to enable, and 'Up' stays loaded from portfolios/UP.JSON.
        """
        content = self._import_then_disable("UP.JSON", "Up")

        self._assert_disable_refused_for_name("UP.JSON", "Up", content)
        self.assertEqual(self._listed_disabled_files(self.sandbox), [], "a disabled portfolio is listed")

    def test_disable_after_import_of_mixed_case_json_name_is_refused(self) -> None:
        """'Mixed', imported from Up.Json, is not disabled: Up.Json stays in portfolios/, under that exact name."""
        content = self._import_then_disable("Up.Json", "Mixed")

        self._assert_disable_refused_for_name("Up.Json", "Mixed", content)

    def test_disable_then_enable_keeps_a_name_that_ends_with_json(self) -> None:
        """
        'Mixed', imported from Mixed.json, is disabled to disabled_portfolios/Mixed.json, listed, then enabled from the
        list back to portfolios/Mixed.json: neither action changes the case of a letter of the file's name.
        """
        content = self._import_then_disable("Mixed.json", "Mixed")
        self.assertEqual(os.listdir(str(self.disabled_dir)), ["Mixed.json"], "the disabled file has another name")
        self.assertEqual(os.listdir(str(self.portfolios_dir)), [], "the portfolio's file is still in portfolios/")
        listed = [path for path, _ in self.portfolio_service.get_disabled_portfolios(str(self.sandbox))]
        self.assertEqual([os.path.basename(path) for path in listed], ["Mixed.json"], "the disabled file is not listed")

        self.command._enable_portfolio(self.window, listed[0], "Mixed")

        self.assertEqual(os.listdir(str(self.portfolios_dir)), ["Mixed.json"], "the enabled file has another name")
        self.assertEqual((self.portfolios_dir / "Mixed.json").read_bytes(), content, "the portfolio's file was changed")
        self.assertEqual(os.listdir(str(self.disabled_dir)), [], "a file is left in disabled_portfolios/")
        recorded = self._recorded_path("Mixed")
        assert recorded is not None  # Type narrowing for mypy
        self.assertEqual(recorded.name, "Mixed.json", "the portfolio is not loaded from its file")
        self._assert_no_warning()

    def test_disable_refuses_name_ending_with_json_without_the_dot(self) -> None:
        """
        'Nodot', loaded from portfolios/wjson, is not disabled: the disable asks for ".json", dot included, as the
        list of disabled portfolios does. No action of the plugin loads such a file; the test loads it directly.
        """
        own_file = self._write_portfolio(self.portfolios_dir / "wjson", "Nodot")
        content = own_file.read_bytes()
        portfolio = self._load(own_file)

        self.command._disable_portfolio(self.window, portfolio)

        self._assert_disable_refused_for_name("wjson", "Nodot", content)

    def test_disable_refusal_for_a_replaced_file_gives_that_motive_before_its_name(self) -> None:
        """
        'Up' was loaded from UP.JSON, which now holds 'Other': the disable is refused because the file no longer
        holds 'Up', and the name of the file is not given as the motive, since renaming the file would not help.
        """
        own_file = self._write_portfolio(self.portfolios_dir / "UP.JSON", "Up")
        portfolio = self._load(own_file)
        self._write_portfolio(own_file, "Other")

        operations = self._run_recording_file_operations(
            lambda: self.command._disable_portfolio(self.window, portfolio)
        )

        self._assert_refused(operations, self.MOTIVE_NO_LONGER_HOLDS)
        named = [message for _, message in self.events if self.MOTIVE_NAME_NOT_JSON in message]
        self.assertEqual(named, [], "the refusal gave the name of the file as its motive")

    # Contract between the disable and the list of disabled portfolios: the disable moves a file to
    # disabled_portfolios/ if and only if the list would show a file so named there

    def test_disable_moves_a_file_if_and_only_if_the_list_of_disabled_portfolios_would_show_it(self) -> None:
        """
        For each file name below, which Import admits, with a portfolio valid for the validator in the file: the
        disable moves the file if and only if get_disabled_portfolios lists a file so named. A refused disable leaves
        disabled_portfolios/ as it was: absent here, since Import creates only portfolios/.

        Each name gets its own Packages folder. The list is first asked about a copy placed by hand in the
        disabled_portfolios/ folder of a probe Packages; then the file is imported and disabled. The names cover
        both outcomes.
        """
        shown: Dict[str, bool] = {}
        moved: Dict[str, bool] = {}
        listed: Dict[str, bool] = {}
        still_loaded: Dict[str, bool] = {}
        created: Dict[str, bool] = {}
        for index, file_name in enumerate(("UP.JSON", "x.Json", ".JSON", "a.json.JSON", "b.json", ".json")):
            name = f"Contract {index}"
            probe = self.sandbox / f"probe{index}"
            self._write_portfolio(probe / "User" / "RegexLab" / "disabled_portfolios" / file_name, name)
            shown[file_name] = file_name in self._listed_disabled_files(probe)

            packages = self.sandbox / f"packages{index}"
            self.window.extract_vars = {"packages": str(packages)}
            self._import_then_disable(file_name, name)

            disabled_dir = packages / "User" / "RegexLab" / "disabled_portfolios"
            created[file_name] = disabled_dir.is_dir()
            on_disk = os.listdir(str(disabled_dir)) if created[file_name] else []
            moved[file_name] = on_disk == [file_name]
            listed[file_name] = file_name in self._listed_disabled_files(packages)
            still_loaded[file_name] = self.portfolio_manager.is_loaded(name)

        self.assertEqual(moved, shown, "the disable moved a file that the list would not show, or kept one it would")
        self.assertEqual(listed, moved, "the list does not show exactly what the disable moved")
        self.assertEqual(still_loaded, {n: not m for n, m in moved.items()}, "a portfolio's state does not match")
        self.assertEqual(created, moved, "a refused disable created disabled_portfolios/")
        self.assertEqual(sorted(set(moved.values())), [False, True], "the names do not cover both outcomes")


if __name__ == "__main__":
    unittest.main()
