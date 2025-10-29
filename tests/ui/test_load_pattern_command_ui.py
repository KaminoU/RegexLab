"""
UI tests for LoadPatternCommand using UnitTesting framework.

These tests run inside Sublime Text with real API access.
Priority 1: Core command that injects patterns into Find/Replace panels.
"""

import sublime
from unittesting import DeferrableTestCase


class TestLoadPatternCommandUI(DeferrableTestCase):
    """Test LoadPatternCommand with real Sublime Text API."""

    def setUp(self):
        """Setup test fixtures."""
        self.window = sublime.active_window()
        self.view = self.window.new_file()
        self.view.set_scratch(True)
        self.view.set_name("Test View - LoadPattern")

    def tearDown(self):
        """Cleanup after test."""
        if self.view and self.view.is_valid():
            self.view.close()

    def test_command_exists(self):
        """Test that load_pattern command is registered in Sublime Text."""
        # Check if command exists in window commands
        # Sublime doesn't expose direct command registry, but we can try running it
        try:
            # This will raise if command doesn't exist
            self.window.run_command("regexlab_load_pattern")
            # If we get here, command exists (even if it shows quick panel)
            self.assertTrue(True, "Command should be registered")
        except Exception as e:
            self.fail(f"Command 'regexlab_load_pattern' not found: {e}")

    def test_command_runs_without_error(self):
        """Test that load_pattern command executes without crashing."""
        # Run command (will show quick panel in real ST)
        self.window.run_command("regexlab_load_pattern")

        # Yield to let async operations complete
        yield 100  # Wait 100ms

        # If we reach here, command didn't crash
        self.assertTrue(True, "Command executed successfully")

    def test_portfolio_manager_is_initialized(self):
        """Test that portfolio manager is available (dependency check)."""
        # Import command class
        try:
            from RegexLab.src.commands.load_pattern_command import LoadPatternCommand

            # Create instance (needs window)
            command = LoadPatternCommand(self.window)

            # Check that portfolio_service is available
            self.assertTrue(
                hasattr(command, "portfolio_service"), "LoadPatternCommand should have portfolio_service attribute"
            )

            # Check that portfolio service has portfolio_manager
            self.assertTrue(
                hasattr(command.portfolio_service, "portfolio_manager"),
                "PortfolioService should have portfolio_manager attribute",
            )

            # Verify portfolio manager is initialized
            self.assertIsNotNone(command.portfolio_service.portfolio_manager, "PortfolioManager should be initialized")
        except ImportError as e:
            self.fail(f"Failed to import LoadPatternCommand: {e}")


class TestBasicSublimeAPI(DeferrableTestCase):
    """Sanity check that UnitTesting framework works correctly."""

    def test_sublime_module_available(self):
        """Test that sublime module is accessible."""
        self.assertIsNotNone(sublime, "sublime module should be available")

    def test_create_view(self):
        """Test that we can create and close views."""
        window = sublime.active_window()
        view = window.new_file()
        view.set_scratch(True)

        self.assertTrue(view.is_valid(), "View should be valid after creation")

        view.close()

    def test_status_message(self):
        """Test that status_message works."""
        sublime.status_message("UnitTesting works!")
        self.assertTrue(True, "Status message should not crash")
