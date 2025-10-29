"""
New Portfolio Wizard Command

This module provides a multi-step wizard interface for creating new portfolios.
The wizard guides users through 5 steps:
    1. Portfolio Name (required, validated)
    2. Description (optional)
    3. Author (optional, defaults to username)
    4. Tags (optional, comma-separated)
    5. Confirmation (displays summary, creates portfolio)

After creation, the portfolio is automatically saved to User/RegexLab/portfolios/
and loaded into the active session.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from ..core.helpers import format_aligned_summary
from ..core.logger import get_logger
from ..core.models import Portfolio
from ..core.settings_manager import SettingsManager
from ..services.portfolio_service import PortfolioService

# Type alias for the on_done callback
OnDoneCallback = Callable[[str], None]


class NewPortfolioWizardCommand:
    """
    Multi-step wizard for creating new portfolios.

    Provides an interactive input panel chain that collects portfolio metadata,
    validates input, and creates/loads the new portfolio.
    """

    def __init__(
        self,
        portfolio_service: PortfolioService | None = None,
        settings_manager: SettingsManager | None = None,
    ) -> None:
        """
        Initialize the New Portfolio Wizard.

        Args:
            portfolio_service: Optional PortfolioService instance (uses singleton if None)
            settings_manager: Optional SettingsManager instance (uses singleton if None)
        """
        self.portfolio_service = portfolio_service or PortfolioService()
        self.settings_manager = settings_manager or SettingsManager.get_instance()
        self.logger = get_logger()

        # Wizard state (stores collected data across steps)
        self.wizard_data: dict[str, Any] = {}

        self.logger.debug("New Portfolio Wizard: Initialized")

    def run(self, window: Any) -> None:
        """
        Start the New Portfolio Wizard.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("New Portfolio Wizard: Starting wizard")

        # Reset wizard state
        self.wizard_data = {}

        # Start with Step 1: Portfolio Name
        self._show_name_input(window)

    # =========================================================================
    # STEP 1: Portfolio Name
    # =========================================================================

    def _show_name_input(self, window: Any) -> None:
        """
        Show input panel for portfolio name (Step 1).

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("New Portfolio Wizard: Step 1 - Portfolio Name")

        window.show_input_panel(
            "📦 Portfolio Name:",
            "",
            lambda name: self._on_name_done(window, name),
            None,  # on_change
            lambda: self._on_cancel(window),
        )

    def _on_name_done(self, window: Any, name: str) -> None:
        """
        Handle portfolio name input completion.

        Args:
            window: Sublime Text window instance
            name: User-provided portfolio name
        """
        name = name.strip()
        self.logger.debug("New Portfolio Wizard: Step 1 - Name entered: '%s'", name)

        # Validate name
        validation_error = self._validate_portfolio_name(name)
        if validation_error:
            self.logger.debug("New Portfolio Wizard: Step 1 - Validation failed: %s", validation_error)
            window.status_message(f"Invalid name: {validation_error}")
            # Re-prompt with error message
            self._show_name_input(window)
            return

        # Check if portfolio already exists
        try:
            packages_path = Path(window.extract_variables()["packages"])
            if self.portfolio_service.portfolio_exists(name, str(packages_path)):
                self.logger.debug("New Portfolio Wizard: Step 1 - Portfolio '%s' already exists", name)
                window.status_message(f"Portfolio '{name}' already exists. Choose a different name.")
                self._show_name_input(window)
                return
        except (KeyError, ValueError, AttributeError) as e:
            # KeyError: Missing 'packages' variable from Sublime Text
            # ValueError: Invalid path format
            # AttributeError: window.extract_variables() unavailable
            self.logger.warning(
                "New Portfolio Wizard: Failed to check portfolio existence - %s: %s", type(e).__name__, e
            )
            # Continue anyway (non-fatal error)

        # Store name and proceed to Step 2
        self.wizard_data["name"] = name
        self.logger.debug("New Portfolio Wizard: Step 1 - Name validated, proceeding to Step 2")
        self._show_description_input(window)

    def _validate_portfolio_name(self, name: str) -> str | None:
        """
        Validate portfolio name.

        Args:
            name: Portfolio name to validate

        Returns:
            Error message if invalid, None if valid
        """
        # Strip whitespace first
        name = name.strip()

        if not name:
            return "Name cannot be empty"

        # Check length
        if len(name) > 50:
            return "Name too long (max 50 characters)"

        # Check for invalid characters (Windows/Unix filesystem restrictions)
        invalid_chars = r'[<>:"/\\|?*]'
        if re.search(invalid_chars, name):
            return 'Name contains invalid characters (< > : " / \\ | ? *)'

        # Check for reserved names (Windows)
        reserved_names = [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        ]
        if name.upper() in reserved_names:
            return f"Name '{name}' is reserved by the system"

        return None

    # =========================================================================
    # STEP 2: Description
    # =========================================================================

    def _show_description_input(self, window: Any) -> None:
        """
        Show input panel for portfolio description (Step 2).

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("New Portfolio Wizard: Step 2 - Description")

        window.show_input_panel(
            "📝 Description (optional):",
            "",
            lambda desc: self._on_description_done(window, desc),
            None,  # on_change
            lambda: self._on_cancel(window),
        )

    def _on_description_done(self, window: Any, description: str) -> None:
        """
        Handle description input completion.

        Args:
            window: Sublime Text window instance
            description: User-provided description
        """
        description = description.strip()
        self.logger.debug("New Portfolio Wizard: Step 2 - Description entered: '%s'", description)

        # Store description (can be empty) and proceed to Step 3
        self.wizard_data["description"] = description
        self.logger.debug("New Portfolio Wizard: Step 2 - Proceeding to Step 3")
        self._show_author_input(window)

    # =========================================================================
    # STEP 3: Author
    # =========================================================================

    def _show_author_input(self, window: Any) -> None:
        """
        Show input panel for portfolio author (Step 3).

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("New Portfolio Wizard: Step 3 - Author")

        # Get default author from settings or system username
        default_author = self._get_default_author()
        self.logger.debug("New Portfolio Wizard: Step 3 - Default author: '%s'", default_author)

        window.show_input_panel(
            "👤 Author (optional):",
            default_author,
            lambda author: self._on_author_done(window, author),
            None,  # on_change
            lambda: self._on_cancel(window),
        )

    def _get_default_author(self) -> str:
        """
        Get default author name from settings or system username.

        Returns:
            Default author name
        """
        # Try variables.username first (same as pattern_engine)
        username: str = self.settings_manager.get_nested("variables.username", "")
        if username:
            return username

        # Fallback to system username
        try:
            import getpass

            return getpass.getuser()
        except (KeyError, OSError, ImportError):
            # KeyError: user not found in pwd database (Unix)
            # OSError: system errors accessing user info
            # ImportError: pwd module not available (Windows)
            return ""

    def _on_author_done(self, window: Any, author: str) -> None:
        """
        Handle author input completion.

        Args:
            window: Sublime Text window instance
            author: User-provided author
        """
        author = author.strip()
        self.logger.debug("New Portfolio Wizard: Step 3 - Author entered: '%s'", author)

        # Store author (can be empty) and proceed to Step 4
        self.wizard_data["author"] = author
        self.logger.debug("New Portfolio Wizard: Step 3 - Proceeding to Step 4")
        self._show_tags_input(window)

    # =========================================================================
    # STEP 4: Tags
    # =========================================================================

    def _show_tags_input(self, window: Any) -> None:
        """
        Show input panel for portfolio tags (Step 4).

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("New Portfolio Wizard: Step 4 - Tags")

        window.show_input_panel(
            "🏷️  Tags (optional, comma-separated):",
            "",
            lambda tags: self._on_tags_done(window, tags),
            None,  # on_change
            lambda: self._on_cancel(window),
        )

    def _on_tags_done(self, window: Any, tags: str) -> None:
        """
        Handle tags input completion.

        Args:
            window: Sublime Text window instance
            tags: User-provided tags (comma-separated)
        """
        self.logger.debug("New Portfolio Wizard: Step 4 - Tags entered: '%s'", tags)

        # Parse tags (split by comma, strip whitespace, filter empty)
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        self.logger.debug("New Portfolio Wizard: Step 4 - Parsed tags: %s", tag_list)

        # Store tags and proceed to Step 5
        self.wizard_data["tags"] = tag_list
        self.logger.debug("New Portfolio Wizard: Step 4 - Proceeding to Step 5")
        self._show_confirmation(window)

    # =========================================================================
    # STEP 5: Confirmation
    # =========================================================================

    def _show_confirmation(self, window: Any) -> None:
        """
        Show confirmation quick panel with summary (Step 5).

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("New Portfolio Wizard: Step 5 - Confirmation")

        try:
            import sublime  # pyright: ignore[reportMissingImports]

            # Build summary lines
            summary_lines = self._build_summary()
            self.logger.debug("New Portfolio Wizard: Step 5 - Summary built (%s lines)", len(summary_lines))

            # Show quick panel with summary + action choices
            items = [*summary_lines, "", "─" * 60, "✅ Create Portfolio", "❌ Cancel"]

            window.show_quick_panel(
                items,
                lambda index: self._on_confirmation_done(window, index, len(summary_lines)),
                sublime.MONOSPACE_FONT,
            )
        except ImportError:
            self.logger.error("New Portfolio Wizard: sublime module not available")
            return

    def _build_summary(self) -> list[str]:
        """
        Build summary lines for confirmation panel.

        Returns:
            List of formatted summary lines
        """
        # Collect all labels and values
        summary_items = []

        # Name (required)
        summary_items.append(("Name", self.wizard_data["name"]))

        # Description (optional)
        desc = self.wizard_data.get("description", "")
        if desc:
            summary_items.append(("Description", desc))

        # Author (optional)
        author = self.wizard_data.get("author", "")
        if author:
            summary_items.append(("Author", author))

        # Tags (optional)
        tags = self.wizard_data.get("tags", [])
        if tags:
            summary_items.append(("Tags", ", ".join(tags)))

        return format_aligned_summary("Portfolio Summary", summary_items)

    def _on_confirmation_done(self, window: Any, index: int, summary_line_count: int) -> None:
        """
        Handle confirmation selection.

        Args:
            window: Sublime Text window instance
            index: Selected index in quick panel
            summary_line_count: Number of summary lines (to identify action buttons)
        """
        self.logger.debug("New Portfolio Wizard: Step 5 - Selection: index=%s", index)

        # User cancelled
        if index == -1:
            self._on_cancel(window)
            return

        # Calculate action index (summary + blank + separator + 2 actions)
        create_index = summary_line_count + 2  # "✅ Create Portfolio"
        cancel_index = summary_line_count + 3  # "❌ Cancel"

        if index == create_index:
            self.logger.debug("New Portfolio Wizard: Step 5 - User confirmed creation")
            self._create_portfolio(window)
        elif index == cancel_index:
            self.logger.debug("New Portfolio Wizard: Step 5 - User cancelled")
            self._on_cancel(window)
        else:
            # User clicked on summary line (ignore)
            self.logger.debug("New Portfolio Wizard: Step 5 - Summary line clicked, ignoring")
            self._show_confirmation(window)

    # =========================================================================
    # Portfolio Creation
    # =========================================================================

    def _create_portfolio(self, window: Any) -> None:
        """
        Create the portfolio with collected data.

        Args:
            window: Sublime Text window instance
        """
        name = self.wizard_data["name"]
        self.logger.debug("New Portfolio Wizard: Creating portfolio '%s'", name)

        try:
            # Create Portfolio object
            portfolio = Portfolio(
                name=name,
                description=self.wizard_data.get("description", ""),
                author=self.wizard_data.get("author", ""),
                tags=self.wizard_data.get("tags", []),
                patterns=[],  # Empty portfolio
            )

            # Save to User/RegexLab/portfolios/
            packages_path = Path(window.extract_variables()["packages"])
            portfolios_dir = packages_path / "User" / "RegexLab" / "portfolios"
            portfolios_dir.mkdir(parents=True, exist_ok=True)

            portfolio_path = portfolios_dir / f"{name}.json"
            self.logger.debug("New Portfolio Wizard: Saving to: %s", portfolio_path)

            self.portfolio_service.save_portfolio(portfolio, str(portfolio_path))

            # V2.2.1+ Auto-Discovery: File saved to portfolios/ is automatically loaded
            # No need to update loaded_portfolios setting anymore
            self.logger.debug("New Portfolio Wizard: Portfolio saved to portfolios/ (auto-discovery enabled)")

            # Load into active session immediately
            self.portfolio_service.portfolio_manager.load_portfolio(portfolio_path, set_as_builtin=False, reload=False)
            self.logger.debug("New Portfolio Wizard: Portfolio loaded into session")

            # Success message
            window.status_message(f"Portfolio '{name}' created and loaded successfully!")
            self.logger.debug("New Portfolio Wizard: Creation complete")

        except (OSError, ValueError) as e:
            # OSError: File I/O errors (disk full, permissions, directory creation)
            # ValueError: Invalid portfolio data or configuration
            error_msg = f"Failed to create portfolio: {e}"
            self.logger.error("New Portfolio Wizard: %s - %s: %s", error_msg, type(e).__name__, e)
            window.status_message(error_msg)

    # =========================================================================
    # Cancellation
    # =========================================================================

    def _on_cancel(self, window: Any) -> None:
        """
        Handle wizard cancellation.

        Args:
            window: Sublime Text window instance
        """
        self.logger.debug("New Portfolio Wizard: Cancelled")
        window.status_message("Portfolio creation cancelled")
        self.wizard_data = {}  # Clear state
