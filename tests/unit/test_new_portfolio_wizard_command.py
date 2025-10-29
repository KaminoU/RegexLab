"""
Unit tests for New Portfolio Wizard Command.

Tests cover:
- Wizard initialization
- Step navigation (name → description → author → tags → confirmation)
- Input validation (name validation, reserved names, invalid characters)
- Portfolio existence check
- Portfolio creation and auto-loading
- Cancellation handling
"""

import unittest
from unittest.mock import Mock, patch

from src.commands.new_portfolio_wizard_command import NewPortfolioWizardCommand
from src.core.models import Portfolio


class MockWindow:
    """Mock Sublime Text window for testing."""

    def __init__(self):
        self.input_panels = []  # Track show_input_panel calls
        self.quick_panels = []  # Track show_quick_panel calls
        self.status_messages = []  # Track status messages
        self.extract_vars = {"packages": "/path/to/Packages"}

    def show_input_panel(self, caption, initial_text, on_done, on_change, on_cancel):
        """Mock show_input_panel."""
        self.input_panels.append(
            {
                "caption": caption,
                "initial_text": initial_text,
                "on_done": on_done,
                "on_change": on_change,
                "on_cancel": on_cancel,
            }
        )

    def show_quick_panel(self, items, on_select, flags=0):
        """Mock show_quick_panel."""
        self.quick_panels.append({"items": items, "on_select": on_select, "flags": flags})

    def status_message(self, message):
        """Mock status_message."""
        self.status_messages.append(message)

    def extract_variables(self):
        """Mock extract_variables."""
        return self.extract_vars


class TestNewPortfolioWizardCommandInit(unittest.TestCase):
    """Test wizard initialization."""

    def test_init_default_services(self):
        """Test initialization with default services."""
        wizard = NewPortfolioWizardCommand()
        self.assertIsNotNone(wizard.portfolio_service)
        self.assertIsNotNone(wizard.settings_manager)
        self.assertIsNotNone(wizard.logger)
        self.assertEqual(wizard.wizard_data, {})

    def test_init_custom_services(self):
        """Test initialization with custom services."""
        mock_service = Mock()
        mock_settings = Mock()
        wizard = NewPortfolioWizardCommand(portfolio_service=mock_service, settings_manager=mock_settings)
        self.assertEqual(wizard.portfolio_service, mock_service)
        self.assertEqual(wizard.settings_manager, mock_settings)


class TestNewPortfolioWizardCommandRun(unittest.TestCase):
    """Test wizard run (entry point)."""

    def test_run_shows_name_input(self):
        """Test that run() shows the name input panel."""
        wizard = NewPortfolioWizardCommand()
        window = MockWindow()

        wizard.run(window)

        self.assertEqual(len(window.input_panels), 1)
        self.assertEqual(window.input_panels[0]["caption"], "📦 Portfolio Name:")
        self.assertEqual(window.input_panels[0]["initial_text"], "")

    def test_run_resets_wizard_data(self):
        """Test that run() resets wizard data."""
        wizard = NewPortfolioWizardCommand()
        wizard.wizard_data = {"old": "data"}
        window = MockWindow()

        wizard.run(window)

        self.assertEqual(wizard.wizard_data, {})


class TestNewPortfolioWizardCommandNameValidation(unittest.TestCase):
    """Test portfolio name validation."""

    def setUp(self):
        self.wizard = NewPortfolioWizardCommand()

    def test_validate_empty_name(self):
        """Test validation rejects empty name."""
        error = self.wizard._validate_portfolio_name("")
        self.assertEqual(error, "Name cannot be empty")

    def test_validate_whitespace_only_name(self):
        """Test validation rejects whitespace-only name."""
        error = self.wizard._validate_portfolio_name("   ")
        self.assertEqual(error, "Name cannot be empty")

    def test_validate_too_long_name(self):
        """Test validation rejects names > 50 characters."""
        long_name = "a" * 51
        error = self.wizard._validate_portfolio_name(long_name)
        self.assertEqual(error, "Name too long (max 50 characters)")

    def test_validate_invalid_characters(self):
        """Test validation rejects invalid filesystem characters."""
        invalid_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]
        for char in invalid_chars:
            name = f"test{char}portfolio"
            error = self.wizard._validate_portfolio_name(name)
            self.assertIsNotNone(error)
            assert error is not None  # Type narrowing for mypy
            self.assertIn("invalid characters", error)

    def test_validate_reserved_names_windows(self):
        """Test validation rejects Windows reserved names."""
        reserved = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
        for name in reserved:
            error = self.wizard._validate_portfolio_name(name)
            self.assertIsNotNone(error)
            assert error is not None  # Type narrowing for mypy
            self.assertIn("reserved", error.lower())

            # Test case-insensitive
            error = self.wizard._validate_portfolio_name(name.lower())
            self.assertIsNotNone(error)

    def test_validate_valid_name(self):
        """Test validation accepts valid names."""
        valid_names = ["MyPortfolio", "test-portfolio", "portfolio_123", "simple"]
        for name in valid_names:
            error = self.wizard._validate_portfolio_name(name)
            self.assertIsNone(error)


class TestNewPortfolioWizardCommandNameInput(unittest.TestCase):
    """Test Step 1: Name input."""

    def setUp(self):
        self.wizard = NewPortfolioWizardCommand()
        self.window = MockWindow()

    def test_name_input_valid_proceeds_to_description(self):
        """Test valid name proceeds to description step."""
        with patch.object(self.wizard.portfolio_service, "portfolio_exists", return_value=False):
            self.wizard._on_name_done(self.window, "ValidName")

        # Check wizard data
        self.assertEqual(self.wizard.wizard_data["name"], "ValidName")

        # Check proceeded to Step 2
        self.assertEqual(len(self.window.input_panels), 1)
        self.assertEqual(self.window.input_panels[0]["caption"], "📝 Description (optional):")

    def test_name_input_empty_reprompts(self):
        """Test empty name shows error and re-prompts."""
        self.wizard._on_name_done(self.window, "")

        # Check error message
        self.assertEqual(len(self.window.status_messages), 1)
        self.assertIn("Invalid name", self.window.status_messages[0])

        # Check re-prompted
        self.assertEqual(len(self.window.input_panels), 1)
        self.assertEqual(self.window.input_panels[0]["caption"], "📦 Portfolio Name:")

    def test_name_input_existing_portfolio_reprompts(self):
        """Test existing portfolio name shows error and re-prompts."""
        with patch.object(self.wizard.portfolio_service, "portfolio_exists", return_value=True):
            self.wizard._on_name_done(self.window, "ExistingPortfolio")

        # Check error message
        self.assertEqual(len(self.window.status_messages), 1)
        self.assertIn("already exists", self.window.status_messages[0])

        # Check re-prompted
        self.assertEqual(len(self.window.input_panels), 1)

    def test_name_input_invalid_characters_reprompts(self):
        """Test name with invalid characters shows error and re-prompts."""
        self.wizard._on_name_done(self.window, "Invalid<Name>")

        # Check error message
        self.assertEqual(len(self.window.status_messages), 1)
        self.assertIn("invalid characters", self.window.status_messages[0])

        # Check re-prompted
        self.assertEqual(len(self.window.input_panels), 1)


class TestNewPortfolioWizardCommandDescriptionInput(unittest.TestCase):
    """Test Step 2: Description input."""

    def setUp(self):
        self.wizard = NewPortfolioWizardCommand()
        self.window = MockWindow()
        self.wizard.wizard_data = {"name": "TestPortfolio"}

    def test_description_input_proceeds_to_author(self):
        """Test description input proceeds to author step."""
        self.wizard._on_description_done(self.window, "Test description")

        # Check wizard data
        self.assertEqual(self.wizard.wizard_data["description"], "Test description")

        # Check proceeded to Step 3
        self.assertEqual(len(self.window.input_panels), 1)
        self.assertEqual(self.window.input_panels[0]["caption"], "👤 Author (optional):")

    def test_description_input_empty_proceeds(self):
        """Test empty description is allowed and proceeds."""
        self.wizard._on_description_done(self.window, "")

        # Check wizard data
        self.assertEqual(self.wizard.wizard_data["description"], "")

        # Check proceeded to Step 3
        self.assertEqual(len(self.window.input_panels), 1)


class TestNewPortfolioWizardCommandAuthorInput(unittest.TestCase):
    """Test Step 3: Author input."""

    def setUp(self):
        self.wizard = NewPortfolioWizardCommand()
        self.window = MockWindow()
        self.wizard.wizard_data = {"name": "TestPortfolio", "description": "Test"}

    def test_author_input_proceeds_to_tags(self):
        """Test author input proceeds to tags step."""
        self.wizard._on_author_done(self.window, "John Doe")

        # Check wizard data
        self.assertEqual(self.wizard.wizard_data["author"], "John Doe")

        # Check proceeded to Step 4
        self.assertEqual(len(self.window.input_panels), 1)
        self.assertEqual(self.window.input_panels[0]["caption"], "🏷️  Tags (optional, comma-separated):")

    def test_author_input_uses_default(self):
        """Test author input panel shows default author from variables.username."""
        with patch.object(self.wizard.settings_manager, "get_nested", return_value="DefaultAuthor"):
            self.wizard._show_author_input(self.window)

        # Check default author shown
        self.assertEqual(self.window.input_panels[0]["initial_text"], "DefaultAuthor")

    def test_author_input_fallback_to_system_user(self):
        """Test author defaults to system username if no setting."""
        with patch.object(self.wizard.settings_manager, "get_nested", return_value=""), patch(
            "getpass.getuser", return_value="system_user"
        ):
            default = self.wizard._get_default_author()

        self.assertEqual(default, "system_user")


class TestNewPortfolioWizardCommandTagsInput(unittest.TestCase):
    """Test Step 4: Tags input."""

    def setUp(self):
        self.wizard = NewPortfolioWizardCommand()
        self.window = MockWindow()
        self.wizard.wizard_data = {"name": "TestPortfolio", "description": "Test", "author": "John"}

    def test_tags_input_parses_comma_separated(self):
        """Test tags are parsed from comma-separated string."""
        self.wizard._on_tags_done(self.window, "tag1, tag2, tag3")

        # Check wizard data
        self.assertEqual(self.wizard.wizard_data["tags"], ["tag1", "tag2", "tag3"])

    def test_tags_input_strips_whitespace(self):
        """Test whitespace is stripped from tags."""
        self.wizard._on_tags_done(self.window, "  tag1  ,  tag2  ,  tag3  ")

        # Check wizard data (no extra whitespace)
        self.assertEqual(self.wizard.wizard_data["tags"], ["tag1", "tag2", "tag3"])

    def test_tags_input_empty_creates_empty_list(self):
        """Test empty tags input creates empty list."""
        self.wizard._on_tags_done(self.window, "")

        # Check wizard data
        self.assertEqual(self.wizard.wizard_data["tags"], [])

    @patch.dict("sys.modules", {"sublime": Mock(MONOSPACE_FONT=1)})
    def test_tags_input_proceeds_to_confirmation(self):
        """Test tags input proceeds to confirmation."""
        self.wizard._on_tags_done(self.window, "tag1")

        # Check proceeded to Step 5 (quick panel shown)
        self.assertEqual(len(self.window.quick_panels), 1)


class TestNewPortfolioWizardCommandConfirmation(unittest.TestCase):
    """Test Step 5: Confirmation."""

    def setUp(self):
        self.wizard = NewPortfolioWizardCommand()
        self.window = MockWindow()
        self.wizard.wizard_data = {
            "name": "TestPortfolio",
            "description": "Test description",
            "author": "John Doe",
            "tags": ["tag1", "tag2"],
        }

    def test_confirmation_builds_summary(self):
        """Test confirmation panel builds summary correctly."""
        summary = self.wizard._build_summary()

        # Check summary contains all data
        summary_text = "\n".join(summary)
        self.assertIn("TestPortfolio", summary_text)
        self.assertIn("Test description", summary_text)
        self.assertIn("John Doe", summary_text)
        self.assertIn("tag1, tag2", summary_text)

    @patch.dict("sys.modules", {"sublime": Mock(MONOSPACE_FONT=1)})
    def test_confirmation_shows_quick_panel(self):
        """Test confirmation shows quick panel with actions."""
        self.wizard._show_confirmation(self.window)

        # Check quick panel shown
        self.assertEqual(len(self.window.quick_panels), 1)

        # Check items include summary and actions
        items = self.window.quick_panels[0]["items"]
        items_text = "\n".join(items)
        self.assertIn("TestPortfolio", items_text)
        self.assertIn("\u2705 Create Portfolio", items_text)  # ✅
        self.assertIn("\u274c Cancel", items_text)  # ❌

    def test_confirmation_user_cancels(self):
        """Test user canceling confirmation (index=-1)."""
        self.wizard._on_confirmation_done(self.window, -1, 5)

        # Check cancelled
        self.assertEqual(len(self.window.status_messages), 1)
        self.assertIn("cancelled", self.window.status_messages[0])

    def test_confirmation_user_clicks_summary(self):
        """Test clicking summary line re-shows confirmation."""
        self.wizard._on_confirmation_done(self.window, 0, 5)

        # Check confirmation re-shown (quick panel count should increase if tracked)
        # For now, just ensure no crash
        pass


class TestNewPortfolioWizardCommandCreation(unittest.TestCase):
    """Test portfolio creation."""

    def setUp(self):
        self.wizard = NewPortfolioWizardCommand()
        self.window = MockWindow()
        self.wizard.wizard_data = {
            "name": "TestPortfolio",
            "description": "Test description",
            "author": "John Doe",
            "tags": ["tag1", "tag2"],
        }

    @patch("pathlib.Path.mkdir")
    @patch.object(NewPortfolioWizardCommand, "_create_portfolio")
    def test_create_portfolio_called_on_confirm(self, mock_create, mock_mkdir):
        """Test _create_portfolio is called when user confirms."""
        summary_line_count = 5
        create_index = summary_line_count + 2  # summary + blank + separator + create

        self.wizard._on_confirmation_done(self.window, create_index, summary_line_count)

        # Check _create_portfolio called
        mock_create.assert_called_once_with(self.window)

    @patch("pathlib.Path.mkdir")
    def test_create_portfolio_saves_file(self, mock_mkdir):
        """Test portfolio creation saves file."""
        mock_service = Mock()
        self.wizard.portfolio_service = mock_service

        self.wizard._create_portfolio(self.window)

        # Check save_portfolio called
        self.assertEqual(mock_service.save_portfolio.call_count, 1)

        # Check Portfolio object passed
        portfolio_arg = mock_service.save_portfolio.call_args[0][0]
        self.assertIsInstance(portfolio_arg, Portfolio)
        self.assertEqual(portfolio_arg.name, "TestPortfolio")
        self.assertEqual(portfolio_arg.description, "Test description")

    @patch("pathlib.Path.mkdir")
    def test_create_portfolio_adds_to_settings(self, mock_mkdir):
        """Test portfolio file is created in portfolios/ (V2.2.1+ auto-discovery)."""
        mock_service = Mock()
        mock_settings = Mock()

        self.wizard.portfolio_service = mock_service
        self.wizard.settings_manager = mock_settings

        self.wizard._create_portfolio(self.window)

        # V2.2.1+: No longer updates settings, file creation in portfolios/ is sufficient
        # Check settings.set was NOT called
        mock_settings.set.assert_not_called()

        # Check file saved to portfolios/ directory
        mock_service.save_portfolio.assert_called_once()
        save_args = mock_service.save_portfolio.call_args
        filepath = save_args[0][1]  # Second argument is filepath
        self.assertIn("User", filepath)
        self.assertIn("RegexLab", filepath)
        self.assertIn("portfolios", filepath)

    @patch("pathlib.Path.mkdir")
    def test_create_portfolio_loads_into_session(self, mock_mkdir):
        """Test portfolio is loaded into session after creation."""
        mock_service = Mock()
        self.wizard.portfolio_service = mock_service

        self.wizard._create_portfolio(self.window)

        # Check load_portfolio called
        mock_service.portfolio_manager.load_portfolio.assert_called_once()

    @patch("pathlib.Path.mkdir")
    def test_create_portfolio_shows_success_message(self, mock_mkdir):
        """Test success message shown after creation."""
        mock_service = Mock()
        self.wizard.portfolio_service = mock_service

        self.wizard._create_portfolio(self.window)

        # Check success message
        self.assertEqual(len(self.window.status_messages), 1)
        self.assertIn("created and loaded successfully", self.window.status_messages[0])


class TestNewPortfolioWizardCommandCancellation(unittest.TestCase):
    """Test wizard cancellation."""

    def test_cancel_clears_wizard_data(self):
        """Test cancellation clears wizard data."""
        wizard = NewPortfolioWizardCommand()
        wizard.wizard_data = {"name": "Test", "description": "Test"}
        window = MockWindow()

        wizard._on_cancel(window)

        # Check data cleared
        self.assertEqual(wizard.wizard_data, {})

    def test_cancel_shows_message(self):
        """Test cancellation shows status message."""
        wizard = NewPortfolioWizardCommand()
        window = MockWindow()

        wizard._on_cancel(window)

        # Check message shown
        self.assertEqual(len(window.status_messages), 1)
        self.assertIn("cancelled", window.status_messages[0])


if __name__ == "__main__":
    unittest.main()
