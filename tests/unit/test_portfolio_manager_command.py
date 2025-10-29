"""
Tests for Portfolio Manager Command.

Tests for the central portfolio management hub.
"""

import unittest
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
